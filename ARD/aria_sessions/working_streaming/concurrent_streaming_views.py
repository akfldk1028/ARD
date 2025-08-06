"""
동시 4카메라 스트리밍 - Project Aria 공식 Observer 패턴 구현
Facebook Research 공식 문서 기반: deliver_queued_sensor_data + Kafka
"""

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import time
import logging
import threading
import asyncio
from queue import Queue, Empty
from typing import Dict, Optional
import numpy as np

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions
    from projectaria_tools.core.stream_id import RecordableTypeId, StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from aria_sessions.models import AriaStreamingSession

logger = logging.getLogger(__name__)

class ConcurrentAriaObserver:
    """
    Project Aria 공식 Observer 패턴 구현 - 4카메라 동시 지원
    """
    def __init__(self):
        # 4개 카메라별 이미지 저장 (공식 패턴)
        self.images = {}  # camera_id -> latest_image
        self.frame_counts = {}  # camera_id -> count
        self.image_queues = {}  # camera_id -> Queue
        
        # 카메라 ID 매핑 (공식 스트림 ID)
        self.camera_mappings = {
            'rgb': {'stream_id': StreamId("214-1"), 'name': 'camera-rgb'},
            'slam-left': {'stream_id': StreamId("1201-1"), 'name': 'camera-slam-left'}, 
            'slam-right': {'stream_id': StreamId("1201-2"), 'name': 'camera-slam-right'},
            'eye-tracking': {'stream_id': StreamId("211-1"), 'name': 'camera-et'}
        }
        
        # 각 카메라별 Queue 초기화
        for camera_type in self.camera_mappings.keys():
            self.image_queues[camera_type] = Queue(maxsize=2)
            self.frame_counts[camera_type] = 0
        
        print("✅ ConcurrentAriaObserver 초기화 - 4카메라 동시 지원")
    
    def on_image_received(self, image: np.array, record, camera_type: str):
        """
        공식 Observer 패턴 콜백 - on_image_received(image, record)
        """
        try:
            # 타임스탬프 추출
            timestamp_ns = record.capture_timestamp_ns if hasattr(record, 'capture_timestamp_ns') else int(time.time() * 1e9)
            
            # 프레임 카운트 증가
            self.frame_counts[camera_type] = self.frame_counts[camera_type] + 1
            
            # JPEG 압축
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])  # 성능 향상을 위해 품질 75로 설정
            image_bytes = buffer.tobytes()
            
            # Queue에 최신 이미지 저장
            if self.image_queues[camera_type].full():
                try:
                    self.image_queues[camera_type].get_nowait()
                except Empty:
                    pass
            
            image_data = {
                'image_data': image_bytes,
                'timestamp_ns': timestamp_ns,
                'frame_number': self.frame_counts[camera_type],
                'camera_type': camera_type,
                'content_type': 'image/jpeg'
            }
            
            self.image_queues[camera_type].put(image_data)
            self.images[camera_type] = image_data
            
            print(f"🔥 [{camera_type}] Frame {self.frame_counts[camera_type]}, {len(image_bytes)} bytes")
            
        except Exception as e:
            logger.error(f"Observer 콜백 오류 [{camera_type}]: {e}")
    
    def get_latest_image(self, camera_type: str) -> Optional[dict]:
        """특정 카메라의 최신 이미지 반환"""
        try:
            return self.image_queues[camera_type].get_nowait()
        except Empty:
            return None
    
    def get_all_latest_images(self) -> Dict[str, dict]:
        """모든 카메라의 최신 이미지 반환"""
        result = {}
        for camera_type in self.camera_mappings.keys():
            latest = self.get_latest_image(camera_type)
            if latest:
                result[camera_type] = latest
        return result


class ConcurrentAriaStreaming:
    """
    Project Aria 공식 deliver_queued_sensor_data 기반 동시 스트리밍
    """
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.provider = None
        self.observer = ConcurrentAriaObserver()
        self.is_streaming = False
        self.streaming_thread = None
        
        # VRS 프로바이더 초기화
        try:
            self.provider = data_provider.create_vrs_data_provider(vrs_file_path)
            if not self.provider:
                raise Exception("Invalid VRS data provider")
            print(f"✅ VRS 프로바이더 생성: {vrs_file_path}")
        except Exception as e:
            logger.error(f"VRS 초기화 실패: {e}")
            raise
    
    def setup_concurrent_streaming_options(self):
        """
        공식 deliver_queued_sensor_data 옵션 설정 - 4카메라 동시
        """
        # Step 1: 공식 패턴 - 기본 옵션 획득
        options = self.provider.get_default_deliver_queued_options()
        
        # Step 2: 시간 범위 설정 (성능을 위해 짧게)
        options.set_truncate_first_device_time_ns(int(1e8))  # 0.1초 후
        options.set_truncate_last_device_time_ns(int(2e9))   # 2초 전 (더 짧게)
        
        # Step 3: 모든 센서 비활성화 후 카메라만 활성화
        options.deactivate_stream_all()
        
        # Step 4: 4개 카메라 스트림 활성화
        for camera_type, config in self.observer.camera_mappings.items():
            try:
                stream_id = config['stream_id']
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 3)  # 성능 향상: 3프레임마다 1개씩
                print(f"✅ {camera_type} ({stream_id}) 활성화")
            except Exception as e:
                print(f"❌ {camera_type} 활성화 실패: {e}")
        
        return options
    
    def start_concurrent_streaming(self):
        """동시 4카메라 스트리밍 시작"""
        if self.is_streaming:
            return "이미 스트리밍 중"
        
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._concurrent_streaming_loop)
        self.streaming_thread.daemon = True
        self.streaming_thread.start()
        
        print("🚀 동시 4카메라 스트리밍 시작")
        return "동시 4카메라 스트리밍 시작됨"
    
    def stop_streaming(self):
        """스트리밍 중지"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join(timeout=5.0)
        print("⏹️ 동시 4카메라 스트리밍 중지")
        return "스트리밍 중지됨"
    
    def _concurrent_streaming_loop(self):
        """
        공식 deliver_queued_sensor_data 이터레이터 기반 동시 스트리밍 루프 + 순환 재생
        """
        replay_count = 0
        
        while self.is_streaming:
            try:
                replay_count += 1
                print(f"🔄 스트리밍 순환 재생 시작 - {replay_count}회차")
                
                # 공식 옵션 설정
                options = self.setup_concurrent_streaming_options()
                
                # 공식 이터레이터 생성
                iterator = self.provider.deliver_queued_sensor_data(options)
                
                print(f"🔥 공식 deliver_queued_sensor_data 이터레이터 시작 ({replay_count}회차)")
                
                # 스트림 ID -> camera_type 매핑 생성
                stream_to_camera = {}
                for camera_type, config in self.observer.camera_mappings.items():
                    stream_to_camera[str(config['stream_id'])] = camera_type
                
                frame_count_in_cycle = 0
                
                for sensor_data in iterator:
                    if not self.is_streaming:
                        break
                    
                    # 센서 데이터 정보 추출
                    stream_id = str(sensor_data.stream_id())
                    sensor_type = sensor_data.sensor_data_type()
                    
                    # 이미지 데이터만 처리
                    if str(sensor_type) == 'SensorDataType.IMAGE':
                        camera_type = stream_to_camera.get(stream_id)
                        if camera_type:
                            try:
                                # 이미지 데이터 추출
                                image_data, record = sensor_data.image_data_and_record()
                                image_array = image_data.to_numpy_array()
                                
                                # Observer 콜백 호출 (공식 패턴)
                                self.observer.on_image_received(image_array, record, camera_type)
                                frame_count_in_cycle += 1
                                
                            except Exception as e:
                                logger.error(f"이미지 처리 오류 [{camera_type}]: {e}")
                
                print(f"✅ {replay_count}회차 순환 완료 (총 {frame_count_in_cycle} 프레임)")
                
                # 스트리밍이 계속 활성화되어 있으면 자동으로 다시 시작
                if self.is_streaming:
                    print("🔄 VRS 데이터 끝 - 처음부터 다시 재생")
                    time.sleep(0.1)  # 짧은 대기 후 재시작
                    
            except Exception as e:
                logger.error(f"동시 스트리밍 루프 오류 ({replay_count}회차): {e}")
                print(f"❌ 스트리밍 오류 ({replay_count}회차): {e}")
                
                # 오류 발생시 잠시 대기 후 재시도
                if self.is_streaming:
                    print("⏳ 3초 후 재시도...")
                    time.sleep(3)
        
        print(f"⏹️ 동시 스트리밍 루프 종료 (총 {replay_count}회차 재생)")


# 글로벌 인스턴스
concurrent_streaming = None

def get_concurrent_streaming():
    """글로벌 동시 스트리밍 인스턴스 획득"""
    global concurrent_streaming
    
    if concurrent_streaming is None:
        # 첫 번째 available 세션 사용
        session = AriaStreamingSession.objects.filter(status='READY').first()
        if not session:
            raise Exception("No available streaming session")
        
        concurrent_streaming = ConcurrentAriaStreaming(session.vrs_file_path)
    
    return concurrent_streaming


@method_decorator(csrf_exempt, name='dispatch')
class ConcurrentStreamingControlView(View):
    """동시 4카메라 스트리밍 제어 API"""
    
    def post(self, request, action):
        """스트리밍 제어"""
        try:
            streaming = get_concurrent_streaming()
            
            if action == 'start':
                result = streaming.start_concurrent_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'method': '공식 deliver_queued_sensor_data + Observer',
                    'cameras': list(streaming.observer.camera_mappings.keys()),
                    'streaming': streaming.is_streaming
                })
                
            elif action == 'stop':
                result = streaming.stop_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': streaming.is_streaming
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


class ConcurrentLatestFrameView(View):
    """동시 4카메라 최신 프레임 API"""
    
    def get(self, request):
        """특정 카메라의 최신 프레임 반환"""
        try:
            streaming = get_concurrent_streaming()
            camera_type = request.GET.get('camera', 'rgb')
            
            if camera_type not in streaming.observer.camera_mappings:
                return HttpResponse(f"Invalid camera type: {camera_type}", status=400)
            
            latest_image = streaming.observer.get_latest_image(camera_type)
            
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
            response['X-Camera-Type'] = latest_image['camera_type']
            response['X-Source'] = 'concurrent-observer'
            
            return response
            
        except Exception as e:
            logger.error(f"최신 프레임 가져오기 실패: {e}")
            return HttpResponse(f"Frame error: {str(e)}", status=500)


class ConcurrentMultiFrameView(View):
    """동시 4카메라 다중 프레임 API"""
    
    def get(self, request):
        """모든 카메라의 최신 프레임을 JSON으로 반환"""
        try:
            streaming = get_concurrent_streaming()
            all_images = streaming.observer.get_all_latest_images()
            
            result = {}
            for camera_type, image_data in all_images.items():
                # Base64 인코딩
                import base64
                image_base64 = base64.b64encode(image_data['image_data']).decode('utf-8')
                
                result[camera_type] = {
                    'frame_number': image_data['frame_number'],
                    'timestamp_ns': image_data['timestamp_ns'],
                    'camera_type': image_data['camera_type'],
                    'image_base64': image_base64
                }
            
            return JsonResponse({
                'status': 'success',
                'method': '공식 Observer 패턴',
                'cameras': result,
                'camera_count': len(result),
                'total_frames': sum(streaming.observer.frame_counts.values())
            })
            
        except Exception as e:
            logger.error(f"다중 프레임 가져오기 실패: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class ConcurrentStreamingPageView(View):
    """동시 4카메라 스트리밍 페이지"""
    
    def get(self, request):
        """동시 4카메라 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 동시 4카메라 스트리밍</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
        }
        
        .container {
            max-width: 1600px;
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
        
        .cameras-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .camera-box {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .camera-title {
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: #ff6b6b;
        }
        
        .image-container {
            width: 100%;
            height: 300px;
            background: #000;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        .camera-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        
        .loading {
            color: #00ff00;
            font-size: 1rem;
        }
        
        .controls {
            text-align: center;
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
            margin: 0 10px;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(76,175,80,0.3);
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 동시 4카메라 스트리밍</h1>
            <p>Project Aria 공식 Observer 패턴 + deliver_queued_sensor_data</p>
        </div>
        
        <div class="cameras-grid">
            <div class="camera-box">
                <div class="camera-title">📷 RGB Camera</div>
                <div class="image-container">
                    <img id="rgbImage" class="camera-image" style="display: none;">
                    <div id="rgbLoading" class="loading">대기 중...</div>
                </div>
            </div>
            
            <div class="camera-box">
                <div class="camera-title">👁️ SLAM Left</div>
                <div class="image-container">
                    <img id="slam-leftImage" class="camera-image" style="display: none;">
                    <div id="slam-leftLoading" class="loading">대기 중...</div>
                </div>
            </div>
            
            <div class="camera-box">
                <div class="camera-title">👁️ SLAM Right</div>
                <div class="image-container">
                    <img id="slam-rightImage" class="camera-image" style="display: none;">
                    <div id="slam-rightLoading" class="loading">대기 중...</div>
                </div>
            </div>
            
            <div class="camera-box">
                <div class="camera-title">👀 Eye Tracking</div>
                <div class="image-container">
                    <img id="eye-trackingImage" class="camera-image" style="display: none;">
                    <div id="eye-trackingLoading" class="loading">대기 중...</div>
                </div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="startConcurrentStreaming()">🚀 동시 스트리밍 시작</button>
            <button class="btn stop-btn" onclick="stopStreaming()">🛑 스트리밍 중지</button>
        </div>
        
        <div class="status" id="status">준비됨 - 공식 Observer 패턴</div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value" id="totalFrames">0</div>
                <div class="stat-label">총 프레임</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="activeCameras">0</div>
                <div class="stat-label">활성 카메라</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="fps">0</div>
                <div class="stat-label">FPS</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="method">Observer</div>
                <div class="stat-label">방식</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="replayCount">0</div>
                <div class="stat-label">🔄 순환 재생</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="streamingTime">00:00</div>
                <div class="stat-label">⏱️ 재생 시간</div>
            </div>
        </div>
    </div>

    <script>
        let streamingInterval = null;
        let frameCount = 0;
        let lastFrameTime = Date.now();
        let cameras = ['rgb', 'slam-left', 'slam-right', 'eye-tracking'];
        let streamingStartTime = null;
        let replayCount = 0;
        
        function startConcurrentStreaming() {
            fetch('/api/v1/aria-sessions/concurrent-streaming/start/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('동시 스트리밍 시작:', data);
                
                if (data.status === 'success') {
                    document.getElementById('status').textContent = '🔥 동시 4카메라 스트리밍 활성화 (순환 재생)';
                    document.getElementById('method').textContent = '공식 Observer';
                    
                    // 스트리밍 시작 시간 기록
                    streamingStartTime = Date.now();
                    replayCount = 1;
                    document.getElementById('replayCount').textContent = replayCount;
                    
                    // 개별 카메라별 이미지 로딩 시작
                    streamingInterval = setInterval(loadAllCameraFrames, 100); // 100ms마다
                    loadAllCameraFrames();
                }
            })
            .catch(error => {
                console.error('스트리밍 시작 실패:', error);
            });
        }
        
        function loadAllCameraFrames() {
            cameras.forEach(camera => {
                loadCameraFrame(camera);
            });
        }
        
        function loadCameraFrame(cameraType) {
            fetch(`/api/v1/aria-sessions/concurrent-latest-frame/?camera=${cameraType}`)
            .then(response => {
                if (response.ok) {
                    const frameNumber = response.headers.get('X-Frame-Number');
                    const cameraTypeHeader = response.headers.get('X-Camera-Type');
                    
                    return response.blob();
                }
                throw new Error('No frame available');
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const imageEl = document.getElementById(cameraType + 'Image');
                const loadingEl = document.getElementById(cameraType + 'Loading');
                
                imageEl.src = url;
                imageEl.style.display = 'block';
                loadingEl.style.display = 'none';
                
                // 이전 URL 정리
                if (imageEl.dataset.oldUrl) {
                    URL.revokeObjectURL(imageEl.dataset.oldUrl);
                }
                imageEl.dataset.oldUrl = url;
                
                frameCount++;
            })
            .catch(error => {
                // 조용히 처리 (로그 스팸 방지)
            });
        }
        
        function stopStreaming() {
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
            
            fetch('/api/v1/aria-sessions/concurrent-streaming/stop/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('스트리밍 중지:', data);
                
                document.getElementById('status').textContent = '⏹️ 스트리밍 중지됨';
                
                cameras.forEach(camera => {
                    document.getElementById(camera + 'Image').style.display = 'none';
                    document.getElementById(camera + 'Loading').style.display = 'block';
                    document.getElementById(camera + 'Loading').textContent = '대기 중...';
                });
            });
        }
        
        // 통계 업데이트
        setInterval(() => {
            const now = Date.now();
            const timeDiff = now - lastFrameTime;
            
            if (timeDiff > 1000) {
                const fps = Math.round(frameCount * 1000 / timeDiff);
                document.getElementById('fps').textContent = fps;
                document.getElementById('totalFrames').textContent = frameCount;
                
                // 활성 카메라 수 계산
                let activeCameras = 0;
                cameras.forEach(camera => {
                    const imageEl = document.getElementById(camera + 'Image');
                    if (imageEl.style.display === 'block') {
                        activeCameras++;
                    }
                });
                document.getElementById('activeCameras').textContent = activeCameras;
                
                // 스트리밍 시간 업데이트
                if (streamingStartTime) {
                    const elapsed = Math.floor((now - streamingStartTime) / 1000);
                    const minutes = Math.floor(elapsed / 60);
                    const seconds = elapsed % 60;
                    document.getElementById('streamingTime').textContent = 
                        `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
                
                // 순환 재생 감지 (FPS가 갑자기 높아지면 새 사이클 시작)
                if (fps > 20 && frameCount > 50) {
                    const currentReplay = Math.floor((now - streamingStartTime) / 30000); // 대략 30초마다 사이클
                    if (currentReplay > replayCount - 1) {
                        replayCount = currentReplay + 1;
                        document.getElementById('replayCount').textContent = replayCount;
                        console.log(`🔄 순환 재생 ${replayCount}회차 감지`);
                    }
                }
                
                lastFrameTime = now;
                frameCount = 0;
            }
        }, 1000);
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)