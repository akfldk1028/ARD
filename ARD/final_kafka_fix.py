"""
최종 해결: 작동하는 패턴을 Kafka에 적용
"""

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import time
import logging
import numpy as np
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

logger = logging.getLogger(__name__)

class SimpleKafkaObserver:
    """단순한 Kafka Observer - 작동하는 패턴 사용"""
    def __init__(self):
        self.latest_image_queue = Queue(maxsize=1)
        self.frame_count = 0
        self.kafka_producer = AriaKafkaProducer('ARD_KAFKA:9092')
        
    def on_image_received(self, image: np.array, timestamp_ns: int):
        """Observer 콜백 - 작동하는 패턴과 동일"""
        try:
            self.frame_count += 1
            
            # JPEG로 압축
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            
            # Kafka로 전송
            try:
                self.kafka_producer.send_real_time_frame(
                    stream_type='rgb',
                    compressed_data=image_bytes,
                    metadata={'frame_number': self.frame_count, 'timestamp_ns': timestamp_ns}
                )
                kafka_sent = True
            except:
                kafka_sent = False
                
            # 캐시 업데이트 (작동하는 패턴과 동일)
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
            
            logger.info(f"✅ 이미지 처리 완료: Frame {self.frame_count}, 크기: {len(image_bytes)} bytes, Kafka: {kafka_sent}")
            
        except Exception as e:
            logger.error(f"Observer 오류: {e}")
    
    def get_latest_image(self):
        """최신 이미지 가져오기"""
        try:
            return self.latest_image_queue.get_nowait()
        except Empty:
            return None

class SimpleKafkaStreamer:
    """단순한 Kafka Streamer - 작동하는 패턴 사용"""
    def __init__(self, vrs_file_path='data/mps_samples/sample.vrs'):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False  # 작동하는 패턴과 동일
        self.observer = None
        self.vrs_provider = None
        self.streaming_thread = None
        
        # VRS 데이터 소스 초기화 (작동하는 패턴과 동일)
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            self.rgb_stream_id = StreamId("214-1")
            self.total_frames = self.vrs_provider.get_num_data(self.rgb_stream_id)
            logger.info(f"✅ SimpleKafka 시뮬레이터 초기화: {self.total_frames} 프레임")
        except Exception as e:
            logger.error(f"VRS 파일 로드 실패: {e}")
            
    def set_streaming_client_observer(self, observer):
        """Observer 등록 (작동하는 패턴과 동일)"""
        self.observer = observer
        
    def start_streaming(self):
        """스트리밍 시작 (작동하는 패턴과 동일)"""
        if self.is_streaming:
            return "이미 스트리밍 중"
            
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop)
        self.streaming_thread.start()
        logger.info("✅ SimpleKafka 스트리밍 시작")
        return "스트리밍 시작됨"
        
    def stop_streaming(self):
        """스트리밍 중지 (작동하는 패턴과 동일)"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join()
        logger.info("✅ SimpleKafka 스트리밍 중지")
        return "스트리밍 중지됨"
        
    def _streaming_loop(self):
        """스트리밍 루프 (작동하는 패턴과 동일)"""
        if not self.vrs_provider or not self.observer:
            logger.error("VRS Provider 또는 Observer 없음")
            return
            
        frame_interval = 1.0 / 30.0
        frame_idx = 0
        
        logger.info(f"🚀 스트리밍 루프 시작 ({self.total_frames} 프레임)")
        
        while self.is_streaming:  # 작동하는 패턴과 동일
            try:
                image_data = self.vrs_provider.get_image_data_by_index(self.rgb_stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    timestamp_ns = image_data[1].capture_timestamp_ns
                    
                    # Observer 콜백 호출 (작동하는 패턴과 동일)
                    self.observer.on_image_received(numpy_image, timestamp_ns)
                
                frame_idx = (frame_idx + 1) % self.total_frames
                time.sleep(frame_interval)
                
            except Exception as e:
                logger.error(f"스트리밍 루프 오류: {e}")
                time.sleep(0.1)
        
        logger.info("✅ 스트리밍 루프 종료")

# 글로벌 인스턴스 (작동하는 패턴과 동일)
simple_kafka_observer = SimpleKafkaObserver()
simple_kafka_streamer = SimpleKafkaStreamer()
simple_kafka_streamer.set_streaming_client_observer(simple_kafka_observer)

@method_decorator(csrf_exempt, name='dispatch')
class SimpleKafkaControlView(View):
    """단순한 Kafka 제어 API"""
    
    def post(self, request, action):
        try:
            if action == 'start':
                result = simple_kafka_streamer.start_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': simple_kafka_streamer.is_streaming
                })
            elif action == 'stop':
                result = simple_kafka_streamer.stop_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': simple_kafka_streamer.is_streaming
                })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class SimpleKafkaFrameView(View):
    """단순한 Kafka 프레임 API"""
    
    def get(self, request):
        try:
            latest_image = simple_kafka_observer.get_latest_image()
            
            if latest_image is None:
                return HttpResponse(status=204, headers={'Cache-Control': 'no-cache'})
            
            response = HttpResponse(
                latest_image['image_data'],
                content_type=latest_image['content_type']
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Frame-Number'] = str(latest_image['frame_number'])
            response['X-Timestamp-NS'] = str(latest_image['timestamp_ns'])
            response['X-Kafka-Sent'] = 'true' if latest_image.get('kafka_sent') else 'false'
            response['X-Source'] = 'simple-kafka-observer'
            
            return response
            
        except Exception as e:
            logger.error(f"프레임 가져오기 실패: {e}")
            return HttpResponse(status=500, content=f"Frame error: {str(e)}")