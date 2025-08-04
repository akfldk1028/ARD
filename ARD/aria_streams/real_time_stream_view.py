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
            self.kafka_producer = AriaKafkaProducer('localhost:9092')
            logger.info("✅ Kafka Producer 초기화 성공 (메타데이터 전송용)")
        except Exception as e:
            self.kafka_producer = None
            logger.warning(f"❌ Kafka Producer 초기화 실패: {e}")
        
    def on_image_received(self, image: np.array, timestamp_ns: int):
        """공식 API 콜백 - 새로운 이미지 수신 시 호출"""
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
                        'stream_type': 'rgb',
                        'data_type': 'frame_metadata'
                    }
                    
                    # 메타데이터만 Kafka로 전송 (이미지는 공식 API 사용)
                    success = self.kafka_producer.send_real_time_frame(
                        stream_type='rgb',
                        compressed_data=b'',  # 이미지 데이터는 비워둠 (공식 API로 별도 전송)
                        metadata=metadata
                    )
                    
                    if success:
                        kafka_sent = True
                        kafka_topic = 'aria-rgb-real-time'
                        logger.debug(f"📡 Kafka 메타데이터 전송 성공: Frame {self.frame_count}")
                    else:
                        logger.warning(f"❌ Kafka 메타데이터 전송 실패: Frame {self.frame_count}")
                    
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
                'kafka_topic': kafka_topic
            })
            
            logger.debug(f"새 이미지 수신: Frame {self.frame_count}, 크기: {len(image_bytes)} bytes")
            
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
    공식 API 패턴을 따라서 구현
    """
    def __init__(self, vrs_file_path='ARD/data/mps_samples/sample.vrs'):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        self.observer = None
        self.vrs_provider = None
        self.streaming_thread = None
        
        # VRS 데이터 소스 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            self.rgb_stream_id = StreamId("214-1")  # RGB 카메라 스트림
            self.total_frames = self.vrs_provider.get_num_data(self.rgb_stream_id)
            logger.info(f"VRS 시뮬레이터 초기화: {self.total_frames} 프레임")
        except Exception as e:
            logger.error(f"VRS 파일 로드 실패: {e}")
            
    def set_streaming_client_observer(self, observer):
        """공식 API 패턴: Observer 등록"""
        self.observer = observer
        
    def start_streaming(self):
        """공식 API 패턴: 스트리밍 시작"""
        if self.is_streaming:
            return
            
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop)
        self.streaming_thread.start()
        logger.info("Aria 실시간 스트리밍 시작")
        
    def stop_streaming(self):
        """공식 API 패턴: 스트리밍 중지"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join()
        logger.info("Aria 실시간 스트리밍 중지")
        
    def _streaming_loop(self):
        """실시간 스트리밍 루프 (30 FPS)"""
        if not self.vrs_provider or not self.observer:
            return
            
        frame_interval = 1.0 / 30.0  # 30 FPS
        frame_idx = 0
        
        while self.is_streaming:
            try:
                # VRS에서 이미지 데이터 가져오기
                image_data = self.vrs_provider.get_image_data_by_index(self.rgb_stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    timestamp_ns = image_data[1].capture_timestamp_ns
                    
                    # Observer 콜백 호출 (공식 API 패턴)
                    self.observer.on_image_received(numpy_image, timestamp_ns)
                
                frame_idx = (frame_idx + 1) % self.total_frames  # 순환 재생
                time.sleep(frame_interval)
                
            except Exception as e:
                logger.error(f"스트리밍 루프 오류: {e}")
                time.sleep(0.1)

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
            display: flex;
            justify-content: center;
            gap: 15px;
            margin: 20px 0;
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
                <button class="btn" onclick="startStreaming()">🚀 스트리밍 시작</button>
                <button class="btn" onclick="stopStreaming()">🛑 스트리밍 중지</button>
                <button class="btn" onclick="captureFrame()">📸 프레임 캡처</button>
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
                    <div class="stat-value" id="kafkaStatus">대기</div>
                    <div class="stat-label">Kafka 상태</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="kafkaTopic">-</div>
                    <div class="stat-label">Kafka 토픽</div>
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
        
        const statusEl = document.getElementById('status');
        const imageEl = document.getElementById('streamImage');
        const loadingEl = document.getElementById('loadingText');
        
        function startStreaming() {
            if (streamingActive) return;
            
            streamingActive = true;
            statusEl.textContent = '🚀 Device Stream 시작 중...';
            statusEl.style.color = '#ffff00';
            
            // 백엔드에 스트리밍 시작 요청
            fetch('/api/v1/aria/device-stream/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Device Stream 시작:', data);
                statusEl.textContent = '📡 실시간 스트리밍 활성화';
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
            })
            .catch(error => {
                console.error('스트리밍 중지 실패:', error);
            });
        }
        
        function loadLatestFrame() {
            if (!streamingActive) return;
            
            const startTime = Date.now();
            
            fetch('/api/v1/aria/device-stream/latest-frame/')
            .then(response => {
                if (response.ok) {
                    // Kafka 메타데이터 헤더 추출
                    const kafkaSent = response.headers.get('X-Kafka-Sent');
                    const kafkaTopic = response.headers.get('X-Kafka-Topic');
                    const frameNumber = response.headers.get('X-Frame-Number');
                    
                    // Kafka 상태 업데이트
                    document.getElementById('kafkaStatus').textContent = 
                        kafkaSent === 'true' ? '✅ 전송됨' : '❌ 실패';
                    document.getElementById('kafkaTopic').textContent = 
                        kafkaTopic || '-';
                    
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
            if action == 'start':
                device_simulator.start_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Device Stream 시작됨',
                    'streaming': True
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
            latest_image = streaming_observer.get_latest_image()
            
            if latest_image is None:
                return HttpResponse(
                    status=204,  # No Content
                    headers={'Cache-Control': 'no-cache'}
                )
            
            response = HttpResponse(
                latest_image['image_data'],
                content_type=latest_image['content_type']
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Frame-Number'] = str(latest_image['frame_number'])
            response['X-Timestamp-NS'] = str(latest_image['timestamp_ns'])
            
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