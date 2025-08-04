"""
Project Aria 공식 Device Stream API를 사용한 실시간 스트리밍 뷰어
Facebook Research 공식 문서 기반: https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/device_stream
"""

from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.template import Template, Context
import json
import base64
import time
import logging
import numpy as np
from typing import Optional
import asyncio
import threading
from queue import Queue, Empty

# Project Aria 공식 SDK 임포트
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    # 실제 Device Stream API는 실제 Aria 기기가 필요하므로 시뮬레이션으로 구현
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

# Kafka Producer 추가 (메타데이터 전송용)
from .producers import AriaKafkaProducer

logger = logging.getLogger(__name__)

class AriaStreamingClientObserver:
    """
    Project Aria 공식 StreamingClientObserver 패턴
    실시간으로 받은 이미지를 큐에 저장
    """
    def __init__(self):
        self.rgb_image = None
        self.latest_image_queue = Queue(maxsize=10)  # 최대 10개 이미지 버퍼
        self.frame_count = 0
        self.last_timestamp = None
        
        # Kafka Producer 추가 (메타데이터 전송용)
        try:
            # Docker 환경에서는 ARD_KAFKA, 로컬에서는 localhost 사용
            import os
            kafka_host = 'ARD_KAFKA:9092' if os.getenv('DOCKER_ENV') else 'localhost:9092'
            self.kafka_producer = AriaKafkaProducer(kafka_host)
            logger.info(f"✅ Kafka Producer 초기화 성공 ({kafka_host})")
        except Exception as e:
            self.kafka_producer = None
            logger.warning(f"❌ Kafka Producer 초기화 실패: {e}")
        
    def on_image_received(self, image: np.array, timestamp_ns: int, stream_type: str = 'rgb'):
        """공식 API 콜백 - 새로운 이미지 수신 시 호출 (다중 스트림 지원)"""
        try:
            self.rgb_image = image
            self.frame_count += 1
            self.last_timestamp = timestamp_ns
            
            # JPEG로 압축해서 큐에 추가
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            
            # 큐가 가득 찬 경우 가장 오래된 이미지 제거
            if self.latest_image_queue.full():
                try:
                    self.latest_image_queue.get_nowait()
                except Empty:
                    pass
            
            # 새 이미지 추가
            # Kafka 전송 성공 여부 추적
            kafka_sent = False
            kafka_topic = None
            
            # 🚀 Kafka 메타데이터 전송 (이미지는 별도 API로, 메타데이터만 동기화)
            if self.kafka_producer:
                try:
                    metadata = {
                        'frame_number': self.frame_count,
                        'timestamp_ns': timestamp_ns,
                        'image_width': image.shape[1],
                        'image_height': image.shape[0],
                        'image_size': len(image_bytes),
                        'stream_type': stream_type,
                        'data_type': 'frame_metadata'
                    }
                    
                    # 메타데이터만 Kafka로 전송 (이미지는 공식 API 사용)
                    success = self.kafka_producer.send_real_time_frame(
                        stream_type=stream_type,
                        compressed_data=b'',  # 이미지 데이터는 비워둠 (공식 API로 별도 전송)
                        metadata=metadata
                    )
                    
                    if success:
                        kafka_sent = True
                        # 스트림 타입별 토픽 설정
                        topic_map = {
                            'rgb': 'aria-rgb-real-time',
                            'slam-left': 'aria-slam-real-time',
                            'slam-right': 'aria-slam-real-time', 
                            'eye-tracking': 'aria-et-real-time'
                        }
                        kafka_topic = topic_map.get(stream_type, 'aria-general-real-time')
                        logger.debug(f"📡 Kafka 메타데이터 전송 성공: {stream_type} Frame {self.frame_count}")
                    else:
                        logger.warning(f"❌ Kafka 메타데이터 전송 실패: {stream_type} Frame {self.frame_count}")
                    
                except Exception as e:
                    logger.warning(f"❌ Kafka 메타데이터 전송 오류: {e}")
            
            # 캐시 업데이트 (Kafka 정보 포함)
            if self.latest_image_queue.full():
                try:
                    self.latest_image_queue.get_nowait()
                except Empty:
                    pass
            
            self.latest_image_queue.put({
                'image_data': image_bytes,
                'timestamp_ns': timestamp_ns,
                'frame_number': self.frame_count,
                'content_type': 'image/jpeg',
                'kafka_sent': kafka_sent,
                'kafka_topic': kafka_topic,
                'stream_type': stream_type
            })
            
            logger.debug(f"새 이미지 수신: {stream_type} Frame {self.frame_count}, 크기: {len(image_bytes)} bytes")
            
        except Exception as e:
            logger.error(f"이미지 처리 오류: {e}")
    
    def get_latest_image(self):
        """가장 최신 이미지 가져오기"""
        try:
            return self.latest_image_queue.get_nowait()
        except Empty:
            return None

# 글로벌 Observer 인스턴스 (실제 구현에서는 세션별로 관리)
streaming_observer = AriaStreamingClientObserver()

class AriaDeviceStreamSimulator:
    """
    실제 Aria 기기가 없을 때 VRS 파일을 이용한 시뮬레이션
    공식 API 패턴을 따라서 구현 - 다중 스트림 지원
    """
    def __init__(self, vrs_file_path='ARD/data/mps_samples/sample.vrs'):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        self.observer = None
        self.vrs_provider = None
        self.streaming_thread = None
        self.current_stream_type = 'rgb'
        
        # 다양한 VRS 스트림 ID 정의
        self.stream_ids = {
            'rgb': StreamId("214-1"),           # RGB 카메라
            'slam-left': StreamId("1201-1"),    # SLAM 왼쪽 카메라
            'slam-right': StreamId("1201-2"),   # SLAM 오른쪽 카메라
            'eye-tracking': StreamId("211-1")   # Eye Tracking 카메라
        }
        
        self.stream_info = {}
        
        # VRS 데이터 소스 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            
            # 각 스트림의 프레임 수 확인
            for stream_name, stream_id in self.stream_ids.items():
                try:
                    frame_count = self.vrs_provider.get_num_data(stream_id)
                    self.stream_info[stream_name] = {
                        'stream_id': stream_id,
                        'frame_count': frame_count,
                        'available': frame_count > 0
                    }
                    logger.info(f"스트림 {stream_name}: {frame_count} 프레임")
                except:
                    self.stream_info[stream_name] = {
                        'stream_id': stream_id,
                        'frame_count': 0,
                        'available': False
                    }
                    logger.warning(f"스트림 {stream_name}: 사용 불가")
            
        except Exception as e:
            logger.error(f"VRS 파일 로드 실패: {e}")
            
    def set_streaming_client_observer(self, observer):
        """공식 API 패턴: Observer 등록"""
        self.observer = observer
        
    def start_streaming(self, stream_type='rgb'):
        """공식 API 패턴: 스트리밍 시작"""
        if self.is_streaming:
            return
        
        # 스트림 타입 설정
        self.current_stream_type = stream_type
        
        # 스트림 사용 가능 여부 확인
        if stream_type not in self.stream_info or not self.stream_info[stream_type]['available']:
            logger.warning(f"스트림 {stream_type} 사용 불가")
            return
            
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop)
        self.streaming_thread.start()
        logger.info(f"Aria {stream_type} 스트리밍 시작")
        
    def stop_streaming(self):
        """공식 API 패턴: 스트리밍 중지"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join()
        logger.info(f"Aria {self.current_stream_type} 스트리밍 중지")
        
    def _streaming_loop(self):
        """실시간 스트리밍 루프 (30 FPS) - 다중 스트림 지원"""
        if not self.vrs_provider or not self.observer:
            return
        
        # 현재 스트림 정보 가져오기
        current_stream = self.stream_info.get(self.current_stream_type)
        if not current_stream or not current_stream['available']:
            logger.error(f"스트림 {self.current_stream_type} 사용 불가")
            return
            
        stream_id = current_stream['stream_id']
        total_frames = current_stream['frame_count']
        
        frame_interval = 1.0 / 30.0  # 30 FPS
        frame_idx = 0
        
        logger.info(f"{self.current_stream_type} 스트리밍 루프 시작: {total_frames} 프레임")
        
        while self.is_streaming:
            try:
                # 현재 스트림에서 이미지 데이터 가져오기
                image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    timestamp_ns = image_data[1].capture_timestamp_ns
                    
                    # Observer 콜백 호출 (스트림 타입 포함)
                    self.observer.on_image_received(numpy_image, timestamp_ns, self.current_stream_type)
                
                frame_idx = (frame_idx + 1) % total_frames  # 순환 재생
                time.sleep(frame_interval)
                
            except Exception as e:
                logger.error(f"{self.current_stream_type} 스트리밍 루프 오류: {e}")
                time.sleep(0.1)
        
        logger.info(f"{self.current_stream_type} 스트리밍 루프 종료")

# 글로벌 디바이스 시뮬레이터
device_simulator = AriaDeviceStreamSimulator()
device_simulator.set_streaming_client_observer(streaming_observer)

class RealTimeStreamView(View):
    """Project Aria 공식 Device Stream API 기반 실시간 스트리밍 뷰어"""
    
    def get(self, request):
        """실시간 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Project Aria 실시간 Device Stream</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .title {
            font-size: 2.5rem;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            margin: 10px 0;
        }
        
        .stream-container {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        
        .image-container {
            width: 100%;
            height: 600px;
            background: #000;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        #streamImage {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.2rem;
            color: #00ff00;
        }
        
        .controls {
            margin: 20px 0;
        }
        
        .stream-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .control-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            background: linear-gradient(45deg, #00ff00, #00cc00);
            color: #000;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,255,0,0.3);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .stream-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            min-width: 140px;
        }
        
        .stream-btn:hover {
            box-shadow: 0 5px 15px rgba(76,175,80,0.3);
        }
        
        .stream-btn.active {
            background: linear-gradient(45deg, #ff9800, #f57c00);
            box-shadow: 0 0 15px rgba(255,152,0,0.5);
        }
        
        .status {
            text-align: center;
            font-size: 1.1rem;
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-box {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00ff00;
        }
        
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.8;
        }
        
        .kafka-details {
            margin-top: 30px;
            background: rgba(0,0,0,0.4);
            border-radius: 15px;
            padding: 20px;
        }
        
        .kafka-details h3 {
            margin: 0 0 20px 0;
            color: #00ff00;
            text-align: center;
        }
        
        .kafka-status-box {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .kafka-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .kafka-row:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        
        .kafka-label {
            font-weight: bold;
            color: #ffffff;
            min-width: 120px;
        }
        
        .kafka-value {
            color: #00ff00;
            font-family: 'Courier New', monospace;
            word-break: break-all;
        }
        
        .json-metadata {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 15px;
        }
        
        .json-metadata h4 {
            margin: 0 0 15px 0;
            color: #ffffff;
        }
        
        .json-metadata pre {
            background: #000;
            color: #00ff00;
            padding: 15px;
            border-radius: 8px;
            font-size: 0.9rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🚀 Project Aria Device Stream</h1>
            <p class="subtitle">Facebook Research 공식 SDK 기반 실시간 스트리밍</p>
        </div>
        
        <div class="stream-container">
            <div class="image-container">
                <img id="streamImage" style="display: none;">
                <div id="loadingText" class="loading">📡 스트리밍 준비 중...</div>
            </div>
            
            <div class="controls">
                <div class="stream-buttons">
                    <button class="btn stream-btn" onclick="startStreaming('rgb')">📷 RGB Camera</button>
                    <button class="btn stream-btn" onclick="startStreaming('slam-left')">👁️ SLAM Left</button>
                    <button class="btn stream-btn" onclick="startStreaming('slam-right')">👁️ SLAM Right</button>
                    <button class="btn stream-btn" onclick="startStreaming('eye-tracking')">👀 Eye Tracking</button>
                </div>
                <div class="control-buttons">
                    <button class="btn" onclick="stopStreaming()">🛑 스트리밍 중지</button>
                    <button class="btn" onclick="captureFrame()">📸 프레임 캡처</button>
                </div>
            </div>
            
            <div class="status" id="status">준비됨 - Project Aria Device Stream API</div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value" id="fpsValue">0</div>
                    <div class="stat-label">FPS (실시간)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="frameCount">0</div>
                    <div class="stat-label">총 프레임 수</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="latency">0ms</div>
                    <div class="stat-label">지연시간</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="quality">실시간</div>
                    <div class="stat-label">스트림 품질</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="streamType">RGB</div>
                    <div class="stat-label">스트림 타입</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="imageSize">0KB</div>
                    <div class="stat-label">이미지 크기</div>
                </div>
            </div>
            
            <!-- Kafka 메타데이터 상세 표시 -->
            <div class="kafka-details">
                <h3>📡 Kafka 메타데이터 실시간</h3>
                <div class="kafka-status-box">
                    <div class="kafka-row">
                        <span class="kafka-label">연결 상태:</span>
                        <span class="kafka-value" id="kafkaStatus">대기 중</span>
                    </div>
                    <div class="kafka-row">
                        <span class="kafka-label">토픽:</span>
                        <span class="kafka-value" id="kafkaTopic">-</span>
                    </div>
                    <div class="kafka-row">
                        <span class="kafka-label">프레임 번호:</span>
                        <span class="kafka-value" id="kafkaFrameNum">-</span>
                    </div>
                    <div class="kafka-row">
                        <span class="kafka-label">타임스탬프:</span>
                        <span class="kafka-value" id="kafkaTimestamp">-</span>
                    </div>
                    <div class="kafka-row">
                        <span class="kafka-label">전송 시간:</span>
                        <span class="kafka-value" id="kafkaSentTime">-</span>
                    </div>
                </div>
                
                <!-- JSON 메타데이터 표시 -->
                <div class="json-metadata">
                    <h4>🔍 전체 메타데이터 (JSON)</h4>
                    <pre id="kafkaJson">{
  "status": "대기 중",
  "message": "스트리밍을 시작하세요"
}</pre>
                </div>
            </div>
        </div>
    </div>

    <script>
        let streamingActive = false;
        let streamingInterval = null;
        let frameCount = 0;
        let lastFrameTime = Date.now();
        let fps = 0;
        let currentStreamType = 'rgb';
        
        const statusEl = document.getElementById('status');
        const imageEl = document.getElementById('streamImage');
        const loadingEl = document.getElementById('loadingText');
        
        function startStreaming(streamType) {
            if (streamingActive) return;
            
            currentStreamType = streamType;
            streamingActive = true;
            
            // 모든 버튼 비활성화
            document.querySelectorAll('.stream-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            statusEl.textContent = `🚀 ${streamType.toUpperCase()} Stream 시작 중...`;
            statusEl.style.color = '#ffff00';
            
            // 스트림 타입 업데이트
            document.getElementById('streamType').textContent = streamType.toUpperCase();
            
            // 백엔드에 스트리밍 시작 요청
            fetch('/api/v1/aria/device-stream/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({stream_type: streamType})
            })
            .then(response => response.json())
            .then(data => {
                console.log('Device Stream 시작:', data);
                statusEl.textContent = `📡 ${streamType.toUpperCase()} 실시간 스트리밍 활성화`;
                statusEl.style.color = '#00ff00';
                
                // 실시간 이미지 로딩 시작 (60 FPS)
                streamingInterval = setInterval(loadLatestFrame, 16); // ~60 FPS
                loadLatestFrame(); // 즉시 첫 프레임 로드
            })
            .catch(error => {
                console.error('스트리밍 시작 실패:', error);
                statusEl.textContent = '❌ Device Stream 시작 실패';
                statusEl.style.color = '#ff0000';
                streamingActive = false;
                event.target.classList.remove('active');
            });
        }
        
        function stopStreaming() {
            streamingActive = false;
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
            
            statusEl.textContent = '🛑 스트리밍 중지 중...';
            statusEl.style.color = '#ffff00';
            
            fetch('/api/v1/aria/device-stream/stop/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Device Stream 중지:', data);
                statusEl.textContent = '⏹️ 스트리밍 중지됨';
                statusEl.style.color = '#666666';
                imageEl.style.display = 'none';
                loadingEl.style.display = 'block';
                loadingEl.textContent = '📡 스트리밍 준비 중...';
                
                // 모든 버튼 비활성화
                document.querySelectorAll('.stream-btn').forEach(btn => btn.classList.remove('active'));
                
                // Kafka 상태 초기화
                resetKafkaStatus();
            })
            .catch(error => {
                console.error('스트리밍 중지 실패:', error);
            });
        }
        
        function loadLatestFrame() {
            if (!streamingActive) return;
            
            const startTime = Date.now();
            
            fetch(`/api/v1/aria/device-stream/latest-frame/?stream_type=${currentStreamType}`)
            .then(response => {
                if (response.ok) {
                    // Kafka 메타데이터 헤더 추출
                    const kafkaSent = response.headers.get('X-Kafka-Sent');
                    const kafkaTopic = response.headers.get('X-Kafka-Topic');
                    const frameNumber = response.headers.get('X-Frame-Number');
                    const timestamp = response.headers.get('X-Timestamp-NS');
                    const contentLength = response.headers.get('Content-Length');
                    
                    // Kafka 상세 메타데이터 업데이트
                    updateKafkaMetadata({
                        kafkaSent: kafkaSent === 'true',
                        kafkaTopic: kafkaTopic || '-',
                        frameNumber: frameNumber || '-',
                        timestamp: timestamp || '-',
                        contentLength: contentLength || '0',
                        streamType: currentStreamType
                    });
                    
                    return response.blob();
                }
                throw new Error('No frame available');
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                imageEl.src = url;
                imageEl.style.display = 'block';
                loadingEl.style.display = 'none';
                
                // 이전 URL 해제 (메모리 누수 방지)
                if (imageEl.dataset.oldUrl) {
                    URL.revokeObjectURL(imageEl.dataset.oldUrl);
                }
                imageEl.dataset.oldUrl = url;
                
                // 통계 업데이트
                frameCount++;
                const now = Date.now();
                const timeDiff = now - lastFrameTime;
                if (timeDiff > 1000) { // 1초마다 FPS 계산
                    fps = Math.round(frameCount * 1000 / timeDiff);
                    lastFrameTime = now;
                    frameCount = 0;
                }
                
                const latency = now - startTime;
                updateStats(fps, frameCount, latency);
            })
            .catch(error => {
                console.log('프레임 로드 실패:', error.message);
                // 실시간 스트리밍에서는 프레임 없음이 정상적일 수 있음
            });
        }
        
        function updateStats(currentFps, totalFrames, latency) {
            document.getElementById('fpsValue').textContent = currentFps;
            document.getElementById('frameCount').textContent = totalFrames;
            document.getElementById('latency').textContent = latency + 'ms';
            
            // 품질 표시
            let quality = '실시간';
            if (currentFps >= 25) quality = '최고';
            else if (currentFps >= 15) quality = '좋음';
            else if (currentFps >= 5) quality = '보통';
            else if (currentFps > 0) quality = '느림';
            
            document.getElementById('quality').textContent = quality;
        }
        
        function updateKafkaMetadata(data) {
            // Kafka 상태 표시
            document.getElementById('kafkaStatus').textContent = 
                data.kafkaSent ? '✅ 전송 성공' : '❌ 전송 실패';
            document.getElementById('kafkaTopic').textContent = data.kafkaTopic;
            document.getElementById('kafkaFrameNum').textContent = data.frameNumber;
            
            // 타임스탬프 포맷팅
            let timestampFormatted = '-';
            if (data.timestamp !== '-') {
                const date = new Date(parseInt(data.timestamp) / 1000000);
                timestampFormatted = date.toLocaleTimeString('ko-KR');
            }
            document.getElementById('kafkaTimestamp').textContent = timestampFormatted;
            document.getElementById('kafkaSentTime').textContent = new Date().toLocaleTimeString('ko-KR');
            
            // 이미지 크기 업데이트
            const sizeKB = Math.round(parseInt(data.contentLength) / 1024);
            document.getElementById('imageSize').textContent = sizeKB + 'KB';
            
            // JSON 메타데이터 표시
            const jsonData = {
                "stream_type": data.streamType,
                "kafka_sent": data.kafkaSent,
                "kafka_topic": data.kafkaTopic,
                "frame_number": data.frameNumber,
                "timestamp_ns": data.timestamp,
                "image_size_bytes": data.contentLength,
                "image_size_kb": sizeKB,
                "local_time": new Date().toISOString(),
                "status": data.kafkaSent ? "SUCCESS" : "FAILED"
            };
            
            document.getElementById('kafkaJson').textContent = JSON.stringify(jsonData, null, 2);
        }
        
        function resetKafkaStatus() {
            document.getElementById('kafkaStatus').textContent = '대기 중';
            document.getElementById('kafkaTopic').textContent = '-';
            document.getElementById('kafkaFrameNum').textContent = '-';
            document.getElementById('kafkaTimestamp').textContent = '-';
            document.getElementById('kafkaSentTime').textContent = '-';
            document.getElementById('imageSize').textContent = '0KB';
            document.getElementById('streamType').textContent = 'NONE';
            
            document.getElementById('kafkaJson').textContent = JSON.stringify({
                "status": "대기 중",
                "message": "스트리밍을 시작하세요"
            }, null, 2);
        }
        
        function captureFrame() {
            if (!imageEl.src) {
                alert('캡처할 프레임이 없습니다.');
                return;
            }
            
            const link = document.createElement('a');
            link.download = `aria_device_stream_${Date.now()}.jpg`;
            link.href = imageEl.src;
            link.click();
        }
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)

@method_decorator(csrf_exempt, name='dispatch')
class DeviceStreamControlView(View):
    """Device Stream 제어 API"""
    
    def post(self, request, action):
        """스트리밍 시작/중지"""
        try:
            # JSON 데이터 파싱
            data = {}
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body)
                except:
                    pass
            
            stream_type = data.get('stream_type', 'rgb')
            
            if action == 'start':
                device_simulator.start_streaming(stream_type)
                return JsonResponse({
                    'status': 'success',
                    'message': f'{stream_type.upper()} Device Stream 시작됨',
                    'streaming': True,
                    'stream_type': stream_type
                })
            elif action == 'stop':
                device_simulator.stop_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Device Stream 중지됨',
                    'streaming': False
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid action'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

class LatestFrameView(View):
    """최신 프레임 API - 공식 Device Stream 패턴"""
    
    def get(self, request):
        """Observer에서 가장 최신 프레임 가져오기"""
        try:
            # stream_type 파라미터 확인 (현재는 RGB만 지원하지만 확장 가능)
            stream_type = request.GET.get('stream_type', 'rgb')
            
            latest_image = streaming_observer.get_latest_image()
            
            if latest_image is None:
                return HttpResponse(
                    status=204,  # No Content
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Stream-Type': stream_type
                    }
                )
            
            response = HttpResponse(
                latest_image['image_data'],
                content_type=latest_image['content_type']
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Frame-Number'] = str(latest_image['frame_number'])
            response['X-Timestamp-NS'] = str(latest_image['timestamp_ns'])
            response['X-Stream-Type'] = stream_type
            response['X-Stream-Name'] = f"camera-{stream_type}"
            
            # Kafka 메타데이터 정보를 헤더에 추가
            response['X-Kafka-Sent'] = 'true' if latest_image.get('kafka_sent', False) else 'false'
            if latest_image.get('kafka_topic'):
                response['X-Kafka-Topic'] = latest_image['kafka_topic']
            
            return response
            
        except Exception as e:
            logger.error(f"최신 프레임 가져오기 실패: {e}")
            return HttpResponse(
                status=500,
                content=f"Frame error: {str(e)}"
            )