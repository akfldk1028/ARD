"""
깔끔한 VRS → Kafka → API 파이프라인
Facebook 공식 Observer 패턴 + Kafka 분산처리
"""

import json
import time
import logging
import numpy as np
import threading
from queue import Queue, Empty
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from .producers import AriaKafkaProducer

logger = logging.getLogger(__name__)

class CleanVRSKafkaObserver:
    """
    깔끔한 VRS → Kafka 파이프라인
    Observer 패턴으로 VRS 이미지를 받아서 Kafka로 전송
    """
    def __init__(self, kafka_servers='ARD_KAFKA:9092'):
        self.kafka_servers = kafka_servers
        self.frame_counts = {'rgb': 0, 'slam-left': 0, 'slam-right': 0}
        
        # Kafka Producer (단순함)
        self.producer = AriaKafkaProducer(kafka_servers)
        
        # 최신 이미지 캐시 (API용)
        self.latest_images = {
            'rgb': Queue(maxsize=1),
            'slam-left': Queue(maxsize=1), 
            'slam-right': Queue(maxsize=1)
        }
        
        logger.info("✅ Clean VRS→Kafka Observer 초기화")
        
    def on_image_received(self, image: np.array, timestamp_ns: int, stream_type: str = 'rgb'):
        """
        VRS Observer 콜백 → Kafka 전송 (단순하고 깔끔하게)
        """
        try:
            self.frame_counts[stream_type] += 1
            
            # 이미지 압축
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            image_bytes = buffer.tobytes()
            
            # Kafka로 전송할 데이터 (이미지 + 메타데이터)
            kafka_data = {
                'stream_type': stream_type,
                'frame_number': self.frame_counts[stream_type],
                'timestamp_ns': timestamp_ns,
                'image_width': image.shape[1],
                'image_height': image.shape[0],
                'image_size': len(image_bytes),
                'processing_time': time.time()
            }
            
            # Kafka 전송 (send_real_time_frame 사용)
            success = self.producer.send_real_time_frame(
                stream_type=stream_type,
                compressed_data=image_bytes,
                metadata=kafka_data
            )
            
            if success:
                logger.info(f"🚀 VRS→Kafka: {stream_type} Frame {self.frame_counts[stream_type]} ({len(image_bytes)} bytes)")
            
            # API용 캐시 업데이트
            cache = self.latest_images[stream_type]
            if not cache.empty():
                try:
                    cache.get_nowait()
                except Empty:
                    pass
            
            cache.put({
                'image_data': image_bytes,
                'frame_number': self.frame_counts[stream_type],
                'timestamp_ns': timestamp_ns,
                'stream_type': stream_type,
                'kafka_sent': success
            })
            
        except Exception as e:
            logger.error(f"❌ VRS Observer 오류: {e}")
    
    def get_latest_image(self, stream_type: str = 'rgb'):
        """API용 최신 이미지 가져오기"""
        try:
            return self.latest_images[stream_type].get_nowait()
        except Empty:
            return None

class CleanVRSKafkaStreamer:
    """
    깔끔한 VRS 스트리밍 시뮬레이터
    VRS 파일을 읽어서 Observer로 전송
    """
    def __init__(self, vrs_file='../data/mps_samples/sample.vrs'):
        self.vrs_file = vrs_file
        self.active_streams = set()
        self.observer = None
        self.threads = {}
        
        # VRS 데이터 소스
        self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file)
        self.stream_configs = {
            'rgb': StreamId("214-1"),
            'slam-left': StreamId("1201-1"),
            'slam-right': StreamId("1201-2")
        }
        
        logger.info("✅ Clean VRS Streamer 초기화")
    
    def set_observer(self, observer):
        """Observer 등록"""
        self.observer = observer
    
    def start_stream(self, stream_type: str):
        """특정 스트림 시작"""
        if stream_type in self.active_streams or stream_type not in self.stream_configs:
            return False
            
        self.active_streams.add(stream_type)
        thread = threading.Thread(target=self._stream_loop, args=(stream_type,))
        self.threads[stream_type] = thread
        thread.start()
        
        logger.info(f"🎬 VRS 스트리밍 시작: {stream_type}")
        return True
    
    def stop_stream(self, stream_type: str):
        """특정 스트림 중지"""
        if stream_type in self.active_streams:
            self.active_streams.discard(stream_type)
        if stream_type in self.threads:
            self.threads[stream_type].join()
            del self.threads[stream_type]
        logger.info(f"⏹️ VRS 스트리밍 중지: {stream_type}")
    
    def _stream_loop(self, stream_type: str):
        """VRS 스트리밍 루프 (30 FPS)"""
        if not self.observer:
            return
            
        stream_id = self.stream_configs[stream_type]
        total_frames = self.vrs_provider.get_num_data(stream_id)
        frame_idx = 0
        
        logger.info(f"📡 {stream_type} 스트리밍 시작 ({total_frames} 프레임)")
        
        while stream_type in self.active_streams:
            try:
                image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    timestamp_ns = image_data[1].capture_timestamp_ns
                    
                    # Observer 콜백 → Kafka 전송
                    self.observer.on_image_received(numpy_image, timestamp_ns, stream_type)
                
                frame_idx = (frame_idx + 1) % total_frames
                time.sleep(1.0 / 30.0)  # 30 FPS
                
            except Exception as e:
                logger.error(f"❌ {stream_type} 스트리밍 오류: {e}")
                time.sleep(0.1)

# 글로벌 인스턴스 (단순함)
vrs_observer = CleanVRSKafkaObserver()
vrs_streamer = CleanVRSKafkaStreamer()
vrs_streamer.set_observer(vrs_observer)

@method_decorator(csrf_exempt, name='dispatch')
class CleanKafkaStreamAPI(View):
    """깔끔한 Kafka 스트림 제어 API"""
    
    def post(self, request, action):
        try:
            data = json.loads(request.body) if request.body else {}
            stream_type = data.get('stream_type', 'rgb')
            
            if action == 'start':
                success = vrs_streamer.start_stream(stream_type)
                return JsonResponse({
                    'status': 'success' if success else 'error',
                    'message': f'{stream_type} 스트리밍 시작' if success else f'{stream_type} 시작 실패',
                    'stream_type': stream_type,
                    'active_streams': list(vrs_streamer.active_streams)
                })
            
            elif action == 'stop':
                vrs_streamer.stop_stream(stream_type)
                return JsonResponse({
                    'status': 'success',
                    'message': f'{stream_type} 스트리밍 중지',
                    'active_streams': list(vrs_streamer.active_streams)
                })
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class CleanKafkaFrameAPI(View):
    """깔끔한 최신 프레임 API"""
    
    def get(self, request):
        try:
            stream_type = request.GET.get('stream_type', 'rgb')
            latest = vrs_observer.get_latest_image(stream_type)
            
            if not latest:
                return HttpResponse(status=204)
            
            response = HttpResponse(latest['image_data'], content_type='image/jpeg')
            response['Cache-Control'] = 'no-cache'
            response['X-Frame-Number'] = str(latest['frame_number'])
            response['X-Stream-Type'] = stream_type
            response['X-Kafka-Sent'] = 'true' if latest['kafka_sent'] else 'false'
            
            return response
            
        except Exception as e:
            return HttpResponse(status=500, content=str(e))