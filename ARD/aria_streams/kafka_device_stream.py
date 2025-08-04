"""
Project Aria 공식 Device Stream API + Kafka 통합
Facebook Research 공식 Observer 패턴을 Kafka Producer와 연결
"""

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import time
import logging
import numpy as np
from typing import Optional
import asyncio
import threading
from queue import Queue, Empty

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from .producers import AriaKafkaProducer
# BinaryKafkaProducer 불필요 - JSON 메타데이터만 사용

logger = logging.getLogger(__name__)

class AriaKafkaStreamingObserver:
    """
    Project Aria 공식 Observer 패턴 + Kafka Producer 통합 (간단 버전)
    """
    def __init__(self, kafka_servers='ARD_KAFKA:9092'):
        # 작동하는 일반 Observer와 동일한 구조
        self.latest_image_queue = Queue(maxsize=1)
        self.frame_count = 0
        self.last_timestamp = None
        
        # Kafka Producer 추가
        try:
            self.kafka_producer = AriaKafkaProducer(kafka_servers)
            logger.info("✅ Kafka Producer 초기화 성공")
        except:
            self.kafka_producer = None
            logger.warning("❌ Kafka Producer 초기화 실패")
        
        logger.info("✅ AriaKafkaStreamingObserver 초기화 완료")
        
    def on_image_received(self, image: np.array, timestamp_ns: int):
        """Observer 콜백 - 작동하는 패턴과 완전히 동일"""
        print(f"🔥 Kafka Observer 콜백 호출! image_shape={image.shape}")
        
        try:
            self.frame_count += 1
            self.last_timestamp = timestamp_ns
            
            # JPEG로 압축 (작동하는 패턴과 동일)
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            
            # Kafka로 전송 (추가 기능)
            kafka_sent = False
            if self.kafka_producer:
                try:
                    kafka_sent = self.kafka_producer.send_real_time_frame(
                        stream_type='rgb',
                        compressed_data=image_bytes,
                        metadata={'frame_number': self.frame_count, 'timestamp_ns': timestamp_ns}
                    )
                    print(f"🚀 Kafka 전송: {kafka_sent}")
                except Exception as e:
                    print(f"❌ Kafka 전송 실패: {e}")
            
            # 캐시 업데이트 (작동하는 패턴과 완전히 동일)
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
                'kafka_sent': kafka_sent
            })
            
            print(f"✅ 캐시 업데이트 완료: Frame {self.frame_count}, 크기: {len(image_bytes)} bytes")
            
        except Exception as e:
            print(f"❌ Observer 오류: {e}")
            logger.error(f"Observer 콜백 오류: {e}")
    
    def get_latest_image(self):
        """최신 이미지 가져오기 (작동하는 패턴과 동일)"""
        try:
            result = self.latest_image_queue.get_nowait()
            print(f"✅ 캐시에서 이미지 반환: Frame {result.get('frame_number', 'Unknown')}")
            return result
        except Empty:
            print("⚠️ 캐시가 비어있음")
            return None
    
    def close(self):
        """리소스 정리"""
        if self.metadata_producer:
            self.metadata_producer.close()

class AriaKafkaDeviceSimulator:
    """
    Kafka 통합 시뮬레이터 (작동하는 패턴 사용)
    """
    def __init__(self, vrs_file_path='data/mps_samples/sample.vrs'):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False  # 작동하는 패턴과 동일
        self.observer = None
        self.vrs_provider = None
        self.streaming_thread = None
        
        # VRS 데이터 소스 초기화 (작동하는 패턴과 완전히 동일)
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            self.rgb_stream_id = StreamId("214-1")  # RGB 카메라 스트림
            self.total_frames = self.vrs_provider.get_num_data(self.rgb_stream_id)
            print(f"✅ Kafka VRS 시뮬레이터 초기화: {self.total_frames} 프레임")
            logger.info(f"✅ Kafka VRS 시뮬레이터 초기화: {self.total_frames} 프레임")
        except Exception as e:
            print(f"❌ VRS 파일 로드 실패: {e}")
            logger.error(f"VRS 파일 로드 실패: {e}")
            self.total_frames = 0
            
    def set_streaming_client_observer(self, observer):
        """Observer 등록 (작동하는 패턴과 동일)"""
        self.observer = observer
        
    def start_streaming(self):
        """스트리밍 시작 (작동하는 패턴과 동일)"""
        if self.is_streaming:
            return "이미 스트리밍 중"
            
        if self.total_frames == 0:
            print(f"❌ VRS 데이터 없음: {self.total_frames} 프레임")
            return "VRS 데이터 없음"
            
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop)
        self.streaming_thread.start()
        print("✅ Kafka 스트리밍 시작")
        logger.info("✅ Kafka 스트리밍 시작")
        return "Kafka 스트리밍 시작됨"
        
    def stop_streaming(self):
        """스트리밍 중지 (작동하는 패턴과 동일)"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join()
        print("✅ Kafka 스트리밍 중지")
        logger.info("✅ Kafka 스트리밍 중지")
        return "Kafka 스트리밍 중지됨"
        
    def _streaming_loop(self):
        """스트리밍 루프 (작동하는 패턴과 완전히 동일)"""
        if not self.vrs_provider or not self.observer:
            print("❌ VRS Provider 또는 Observer 없음")
            return
            
        frame_interval = 1.0 / 30.0  # 30 FPS
        frame_idx = 0
        
        print(f"🚀 Kafka 스트리밍 루프 시작 ({self.total_frames} 프레임)")
        
        while self.is_streaming:  # 작동하는 패턴과 동일
            try:
                # VRS에서 이미지 데이터 가져오기
                image_data = self.vrs_provider.get_image_data_by_index(self.rgb_stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    timestamp_ns = image_data[1].capture_timestamp_ns
                    
                    # Observer 콜백 호출 (작동하는 패턴과 동일)
                    self.observer.on_image_received(numpy_image, timestamp_ns)
                
                frame_idx = (frame_idx + 1) % self.total_frames  # 순환 재생
                time.sleep(frame_interval)
                
            except Exception as e:
                print(f"❌ 스트리밍 루프 오류: {e}")
                logger.error(f"스트리밍 루프 오류: {e}")
                time.sleep(0.1)
        
        print("✅ Kafka 스트리밍 루프 종료")

# 글로벌 Kafka 인스턴스 (강제 재생성)
import os

# Django 프로젝트 루트에서 VRS 파일 경로 찾기
vrs_path = None
for possible_path in ['data/mps_samples/sample.vrs', '../data/mps_samples/sample.vrs', 'ARD/data/mps_samples/sample.vrs']:
    if os.path.exists(possible_path):
        vrs_path = possible_path
        break

if not vrs_path:
    # 절대 경로 사용
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

print(f"🔥 Kafka 인스턴스 생성 중... VRS 경로: {vrs_path}")
kafka_observer = AriaKafkaStreamingObserver()
kafka_device_simulator = AriaKafkaDeviceSimulator(vrs_path)
kafka_device_simulator.set_streaming_client_observer(kafka_observer)
print("✅ Kafka 인스턴스 생성 완료")

@method_decorator(csrf_exempt, name='dispatch')
class KafkaDeviceStreamControlView(View):
    """Kafka Device Stream 제어 API (다중 스트림 지원)"""
    
    def post(self, request, action):
        """Kafka 스트리밍 시작/중지 (단순화)"""
        try:
            if action == 'start':
                result = kafka_device_simulator.start_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': kafka_device_simulator.is_streaming,
                    'method': 'VRS → Observer → Kafka → API'
                })
            elif action == 'stop' or action == 'stop-all':
                result = kafka_device_simulator.stop_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': kafka_device_simulator.is_streaming
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

class KafkaLatestFrameView(View):
    """Kafka 기반 최신 프레임 API (다중 스트림 지원)"""
    
    def get(self, request):
        """Kafka Observer에서 가장 최신 프레임 가져오기 (단순화)"""
        try:
            latest_image = kafka_observer.get_latest_image()
            
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
            response['X-Kafka-Sent'] = 'true' if latest_image.get('kafka_sent') else 'false'
            response['X-Source'] = 'kafka-observer'
            
            return response
            
        except Exception as e:
            logger.error(f"Kafka 최신 프레임 가져오기 실패: {e}")
            return HttpResponse(
                status=500,
                content=f"Kafka frame error: {str(e)}"
            )

class KafkaDeviceStreamView(View):
    """Kafka Device Stream 뷰어 페이지"""
    
    def get(self, request):
        """Kafka 기반 실시간 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Project Aria → Kafka 실시간 스트리밍</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            background: linear-gradient(45deg, #ff6b6b, #ee5a52);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255,107,107,0.3);
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
        
        .stop-btn {
            background: linear-gradient(45deg, #f44336, #d32f2f);
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
            color: #ff6b6b;
        }
        
        .kafka-badge {
            background: #ff6b6b;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 Project Aria → Kafka Stream</h1>
            <p class="subtitle">공식 Observer 패턴 + Kafka Producer 통합 <span class="kafka-badge">KAFKA</span></p>
        </div>
        
        <div class="stream-container">
            <div class="image-container">
                <img id="streamImage" style="display: none;">
                <div id="loadingText" class="loading">🔥 Kafka 스트리밍 준비 중...</div>
            </div>
            
            <div class="controls">
                <div class="stream-buttons">
                    <button class="btn stream-btn" onclick="startStream('rgb')">📷 RGB Camera</button>
                    <button class="btn stream-btn" onclick="startStream('slam-left')">👁️ SLAM Left</button>
                    <button class="btn stream-btn" onclick="startStream('slam-right')">👁️ SLAM Right</button>
                    <button class="btn stream-btn" onclick="startStream('eye-tracking')">👀 Eye Tracking</button>
                </div>
                <div class="control-buttons">
                    <button class="btn stop-btn" onclick="stopAllStreams()">🛑 모든 스트리밍 중지</button>
                    <button class="btn" onclick="captureFrame()">📸 프레임 캡처</button>
                </div>
            </div>
            
            <div class="status" id="status">준비됨 - VRS → Observer → Kafka → API</div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value" id="fpsValue">0</div>
                    <div class="stat-label">FPS (Kafka 기반)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="frameCount">0</div>
                    <div class="stat-label">Kafka 전송 프레임</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="kafkaStatus">대기</div>
                    <div class="stat-label">Kafka 상태</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="source">Observer</div>
                    <div class="stat-label">데이터 소스</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let activeStreams = new Set();
        let currentStreamType = 'rgb';
        let streamingInterval = null;
        let frameCount = 0;
        let lastFrameTime = Date.now();
        let fps = 0;
        
        const statusEl = document.getElementById('status');
        const imageEl = document.getElementById('streamImage');
        const loadingEl = document.getElementById('loadingText');
        
        function startStream(streamType) {
            if (activeStreams.has(streamType)) return;
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = '시작 중...';
            
            fetch('/api/v1/aria/kafka-device-stream/start/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stream_type: streamType })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Kafka Stream 시작:', data);
                
                if (data.status === 'success') {
                    activeStreams.add(streamType);
                    btn.classList.add('active');
                    btn.textContent = btn.textContent.replace('시작 중...', '') + ' (활성화)';
                    
                    // 첫 번째 스트림인 경우 뷰어 시작
                    if (activeStreams.size === 1) {
                        currentStreamType = streamType;
                        statusEl.textContent = `🔥 ${streamType.toUpperCase()} → Kafka → API 활성화`;
                        statusEl.style.color = '#ff6b6b';
                        document.getElementById('kafkaStatus').textContent = '활성화';
                        
                        // 실시간 이미지 로딩 시작
                        streamingInterval = setInterval(loadLatestKafkaFrame, 16);
                        loadLatestKafkaFrame();
                    }
                } else {
                    btn.textContent = btn.textContent.replace('시작 중...', '');
                }
                
                btn.disabled = false;
            })
            .catch(error => {
                console.error('Kafka 스트리밍 시작 실패:', error);
                btn.textContent = btn.textContent.replace('시작 중...', '');
                btn.disabled = false;
            });
        }
        
        function stopAllStreams() {
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
            
            fetch('/api/v1/aria/kafka-device-stream/stop-all/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('모든 Kafka Stream 중지:', data);
                
                // 모든 버튼 상태 초기화
                document.querySelectorAll('.stream-btn').forEach(btn => {
                    btn.classList.remove('active');
                    btn.textContent = btn.textContent.replace(' (활성화)', '');
                });
                
                activeStreams.clear();
                statusEl.textContent = '⏹️ 모든 Kafka 스트리밍 중지됨';
                statusEl.style.color = '#666666';
                document.getElementById('kafkaStatus').textContent = '대기';
                imageEl.style.display = 'none';
                loadingEl.style.display = 'block';
                loadingEl.textContent = '🔥 Kafka 스트리밍 준비 중...';
            });
        }
        
        function loadLatestKafkaFrame() {
            if (activeStreams.size === 0) return;
            
            const startTime = Date.now();
            
            fetch(`/api/v1/aria/kafka-device-stream/latest-frame/?stream_type=${currentStreamType}`)
            .then(response => {
                if (response.ok) {
                    const kafkaSent = response.headers.get('X-Kafka-Sent');
                    const streamType = response.headers.get('X-Stream-Type');
                    const streamName = response.headers.get('X-Stream-Name');
                    
                    document.getElementById('source').textContent = kafkaSent === 'true' ? `${streamName} ✓` : 'Cache';
                    
                    return response.blob();
                }
                throw new Error('No frame available');
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                imageEl.src = url;
                imageEl.style.display = 'block';
                loadingEl.style.display = 'none';
                
                if (imageEl.dataset.oldUrl) {
                    URL.revokeObjectURL(imageEl.dataset.oldUrl);
                }
                imageEl.dataset.oldUrl = url;
                
                // 통계 업데이트
                frameCount++;
                const now = Date.now();
                const timeDiff = now - lastFrameTime;
                if (timeDiff > 1000) {
                    fps = Math.round(frameCount * 1000 / timeDiff);
                    lastFrameTime = now;
                    frameCount = 0;
                }
                
                document.getElementById('fpsValue').textContent = fps;
                document.getElementById('frameCount').textContent = frameCount;
            })
            .catch(error => {
                console.log('Kafka 프레임 로드:', error.message);
            });
        }
        
        function captureFrame() {
            if (!imageEl.src) {
                alert('캡처할 프레임이 없습니다.');
                return;
            }
            
            const link = document.createElement('a');
            link.download = `kafka_stream_${Date.now()}.jpg`;
            link.href = imageEl.src;
            link.click();
        }
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)# reload
