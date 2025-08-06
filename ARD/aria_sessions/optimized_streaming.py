"""
최적화된 동시 스트리밍 - kafka_device_stream.py 패턴 기반
Observer 패턴 + Queue 캐싱 + 멀티스레드로 동시 4카메라 스트리밍 최적화
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
import time
import logging
import numpy as np
import threading
from queue import Queue, Empty
import base64
import cv2

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from .models import AriaStreamingSession

logger = logging.getLogger(__name__)

class MultiStreamObserver:
    """
    4카메라 동시 스트리밍을 위한 최적화된 Observer
    각 카메라별로 독립적인 Queue와 스레드 사용
    """
    def __init__(self):
        # 4개 카메라별 독립 큐 (kafka_device_stream 패턴)
        self.camera_queues = {
            'camera-rgb': Queue(maxsize=1),
            'camera-slam-left': Queue(maxsize=1), 
            'camera-slam-right': Queue(maxsize=1),
            'camera-et': Queue(maxsize=1)
        }
        
        # 프레임 카운터
        self.frame_counts = {
            'camera-rgb': 0,
            'camera-slam-left': 0,
            'camera-slam-right': 0, 
            'camera-et': 0
        }
        
        # 스트림 ID 매핑 (Meta 공식)
        self.stream_id_map = {
            "214-1": 'camera-rgb',
            "1201-1": 'camera-slam-left',
            "1201-2": 'camera-slam-right', 
            "211-1": 'camera-et'
        }
        
        logger.info("MultiStreamObserver initialized - 4 camera independent queues")
        
    def on_image_received(self, stream_label: str, image: np.array, timestamp_ns: int, frame_idx: int):
        """Meta 공식 Observer 패턴 기반 - 카메라별 독립 처리"""
        try:
            # JPEG 압축 (품질 85)
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            
            # 프레임 카운터 증가
            self.frame_counts[stream_label] += 1
            
            # 기존 프레임 제거 (최신 1개만 유지)
            queue = self.camera_queues[stream_label]
            if queue.full():
                try:
                    queue.get_nowait()
                except Empty:
                    pass
            
            # 새 프레임 추가
            frame_data = {
                'image_data': image_bytes,
                'timestamp_ns': timestamp_ns,
                'frame_number': self.frame_counts[stream_label],
                'stream_label': stream_label,
                'frame_idx': frame_idx,
                'content_type': 'image/jpeg',
                'shape': image.shape
            }
            
            queue.put(frame_data)
            
            print(f"OK {stream_label} Frame {self.frame_counts[stream_label]}, {len(image_bytes)} bytes")
            
        except Exception as e:
            logger.error(f"Observer {stream_label} 오류: {e}")
    
    def get_latest_frame(self, stream_label: str):
        """특정 카메라의 최신 프레임 가져오기"""
        try:
            queue = self.camera_queues.get(stream_label)
            if not queue:
                return None
                
            return queue.get_nowait()
        except Empty:
            return None
    
    def get_all_latest_frames(self):
        """모든 카메라의 최신 프레임을 동시에 가져오기"""
        frames = {}
        for stream_label in self.camera_queues:
            frame = self.get_latest_frame(stream_label)
            if frame:
                frames[stream_label] = frame
        return frames

class OptimizedSimultaneousStreamer:
    """
    최적화된 동시 스트리밍 - kafka_device_stream 패턴 적용
    """
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        self.observer = MultiStreamObserver()
        self.vrs_provider = None
        self.streaming_threads = {}
        
        # 스트림 설정 (Meta 공식)
        self.stream_configs = {
            'camera-rgb': {'stream_id': StreamId("214-1"), 'interval': 1.0/30.0},
            'camera-slam-left': {'stream_id': StreamId("1201-1"), 'interval': 1.0/30.0},
            'camera-slam-right': {'stream_id': StreamId("1201-2"), 'interval': 1.0/30.0},
            'camera-et': {'stream_id': StreamId("211-1"), 'interval': 1.0/30.0}
        }
        
        # VRS Provider 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            
            # 각 스트림 프레임 수 확인
            self.frame_counts = {}
            for stream_label, config in self.stream_configs.items():
                try:
                    frame_count = self.vrs_provider.get_num_data(config['stream_id'])
                    self.frame_counts[stream_label] = frame_count
                    print(f"OK {stream_label}: {frame_count} frames")
                except Exception as e:
                    print(f"ERROR {stream_label} load failed: {e}")
                    self.frame_counts[stream_label] = 0
                    
            logger.info("Optimized simultaneous streaming initialized")
            
        except Exception as e:
            logger.error(f"VRS 초기화 실패: {e}")
            self.frame_counts = {}
    
    def start_simultaneous_streaming(self):
        """4카메라 동시 스트리밍 시작"""
        if self.is_streaming:
            return "이미 스트리밍 중"
        
        if not self.vrs_provider:
            return "VRS Provider 없음"
        
        self.is_streaming = True
        
        # 각 카메라별로 독립 스레드 시작
        for stream_label, config in self.stream_configs.items():
            if self.frame_counts.get(stream_label, 0) > 0:
                thread = threading.Thread(
                    target=self._camera_streaming_loop,
                    args=(stream_label, config)
                )
                thread.start()
                self.streaming_threads[stream_label] = thread
                print(f"OK {stream_label} thread started")
        
        logger.info("4-camera simultaneous streaming started")
        return f"Simultaneous streaming started - {len(self.streaming_threads)} cameras"
    
    def stop_streaming(self):
        """모든 스트리밍 중지"""
        self.is_streaming = False
        
        # 모든 스레드 대기
        for thread in self.streaming_threads.values():
            thread.join()
        
        self.streaming_threads.clear()
        logger.info("All streaming stopped")
        return "All streaming stopped"
    
    def _camera_streaming_loop(self, stream_label: str, config: dict):
        """카메라별 독립 스트리밍 루프"""
        stream_id = config['stream_id']
        interval = config['interval']
        max_frames = self.frame_counts.get(stream_label, 0)
        frame_idx = 0
        
        print(f"START {stream_label} independent loop ({max_frames} frames)")
        
        while self.is_streaming and max_frames > 0:
            try:
                # VRS에서 직접 이미지 데이터 가져오기
                image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                
                if image_data[0] is not None:
                    numpy_image = image_data[0].to_numpy_array()
                    image_record = image_data[1]
                    timestamp_ns = image_record.capture_timestamp_ns
                    
                    # Observer 패턴 콜백 호출
                    self.observer.on_image_received(
                        stream_label, numpy_image, timestamp_ns, frame_idx
                    )
                
                frame_idx = (frame_idx + 1) % max_frames
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"{stream_label} 루프 오류: {e}")
                time.sleep(0.1)
        
        print(f"END {stream_label} independent loop")

# 글로벌 인스턴스
import os

# VRS 파일 경로 찾기
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

print(f"Optimized streaming instance creating... VRS: {vrs_path}")
optimized_streamer = OptimizedSimultaneousStreamer(vrs_path)
print("Optimized streaming instance created")

@csrf_exempt
@api_view(['POST'])
def start_optimized_streaming(request):
    """최적화된 동시 스트리밍 시작"""
    try:
        result = optimized_streamer.start_simultaneous_streaming()
        return JsonResponse({
            'status': 'success',
            'message': result,
            'streaming': optimized_streamer.is_streaming,
            'method': '4카메라 독립 스레드 + Observer + Queue',
            'active_cameras': list(optimized_streamer.streaming_threads.keys())
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)

@csrf_exempt 
@api_view(['POST'])
def stop_optimized_streaming(request):
    """최적화된 스트리밍 중지"""
    try:
        result = optimized_streamer.stop_streaming()
        return JsonResponse({
            'status': 'success',
            'message': result,
            'streaming': optimized_streamer.is_streaming
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
def optimized_unified_stream(request):
    """최적화된 통합 스트리밍 API - 4카메라 동시 반환"""
    try:
        # 모든 카메라의 최신 프레임 가져오기
        all_frames = optimized_streamer.observer.get_all_latest_frames()
        
        if not all_frames:
            return JsonResponse({
                'error': 'No frames available',
                'suggestion': 'Start streaming first'
            }, status=404)
        
        # 이미지 데이터 구성
        images = []
        for stream_label, frame_data in all_frames.items():
            # Base64 인코딩
            image_base64 = base64.b64encode(frame_data['image_data']).decode('utf-8')
            
            images.append({
                'stream_label': stream_label,
                'image_base64': image_base64,
                'timestamp_ns': frame_data['timestamp_ns'],
                'frame_number': frame_data['frame_number'],
                'frame_idx': frame_data['frame_idx'],
                'shape': frame_data['shape'],
                'data_source': 'optimized_observer'
            })
        
        # 센서 데이터 (임시 - 이미지 위주로 최적화)
        sensors = []
        
        return JsonResponse({
            'unified_data': {
                'images': images,
                'sensors': sensors
            },
            'stats': {
                'total_items': len(images),
                'image_count': len(images),
                'sensor_count': len(sensors),
                'active_cameras': list(all_frames.keys())
            },
            'streaming_status': optimized_streamer.is_streaming,
            'method': 'optimized_observer_pattern',
            'performance': 'fast_simultaneous'
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': f'Optimized stream error: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
def optimized_single_frame(request):
    """최적화된 단일 카메라 프레임 반환"""
    try:
        stream_label = request.GET.get('stream', 'camera-rgb')
        
        # 특정 카메라의 최신 프레임
        frame_data = optimized_streamer.observer.get_latest_frame(stream_label)
        
        if not frame_data:
            return HttpResponse(status=204)  # No Content
        
        response = HttpResponse(
            frame_data['image_data'],
            content_type=frame_data['content_type']
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Frame-Number'] = str(frame_data['frame_number'])
        response['X-Timestamp-NS'] = str(frame_data['timestamp_ns'])
        response['X-Stream-Label'] = stream_label
        response['X-Source'] = 'optimized-observer'
        response['X-Frame-Idx'] = str(frame_data['frame_idx'])
        
        return response
        
    except Exception as e:
        return HttpResponse(f"Frame error: {str(e)}", status=500)