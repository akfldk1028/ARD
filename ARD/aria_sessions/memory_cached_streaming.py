"""
Memory-Cached VRS Streaming - Meta 공식 패턴
VRS 파일을 한번에 메모리에 로드하고 캐시에서 "좌르르륽" 스트리밍
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
import gc

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    from projectaria_tools.core.sensor_data import TimeDomain
    from projectaria_tools.core import sensor_data_type
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from .models import AriaStreamingSession

logger = logging.getLogger(__name__)

class MemoryCachedVRSLoader:
    """
    VRS 전체를 한번에 메모리에 로드하는 Meta 공식 패턴
    초기화 시 한번만 디스크 I/O, 이후엔 메모리에서 "좌르르륽" 스트리밍
    """
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.vrs_provider = None
        self.memory_cache = {}
        self.cache_loaded = False
        self.loading_progress = {}
        
        # 스트림 설정 (Meta 공식)
        self.stream_configs = {
            'camera-rgb': {'stream_id': StreamId("214-1"), 'type': 'image'},
            'camera-slam-left': {'stream_id': StreamId("1201-1"), 'type': 'image'},
            'camera-slam-right': {'stream_id': StreamId("1201-2"), 'type': 'image'},
            'camera-et': {'stream_id': StreamId("211-1"), 'type': 'image'}
        }
        
        # 센서 설정 (Meta 공식)
        self.sensor_configs = {
            'imu-right': {'stream_id': StreamId("1202-1"), 'type': 'sensor'},
            'imu-left': {'stream_id': StreamId("1202-2"), 'type': 'sensor'},
            'magnetometer': {'stream_id': StreamId("1203-1"), 'type': 'sensor'},
            'barometer': {'stream_id': StreamId("247-1"), 'type': 'sensor'},
            'microphone': {'stream_id': StreamId("231-1"), 'type': 'sensor'}
        }
        
        # VRS Provider 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            print(f"VRS Provider initialized: {vrs_file_path}")
        except Exception as e:
            logger.error(f"VRS initialization failed: {e}")
            
    def preload_all_frames_to_memory(self, force_reload=False):
        """
        VRS 전체를 한번에 메모리에 로드 (Meta 공식 패턴)
        이미지만 먼저 구현 (간단히)
        """
        # 강제 초기화
        self.memory_cache = {}
        self.cache_loaded = False
        self.loading_progress = {}
            
        if not self.vrs_provider:
            return "VRS Provider not available"
        
        # 강제 리로드시 캐시 초기화
        if force_reload:
            self.memory_cache = {}
            self.cache_loaded = False
            self.loading_progress = {}
            print("Forced reload - cache cleared")
        
        print("Starting VRS image memory preload...")
        start_time = time.time()
        total_frames_loaded = 0
        
        # 이미지 데이터만 로드
        for stream_label, config in self.stream_configs.items():
            stream_id = config['stream_id']
            
            try:
                frame_count = self.vrs_provider.get_num_data(stream_id)
                print(f"Loading {stream_label}: {frame_count} frames to memory...")
                
                self.memory_cache[stream_label] = []
                self.loading_progress[stream_label] = 0
                
                for frame_idx in range(frame_count):
                    try:
                        image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                        
                        if image_data[0] is not None:
                            numpy_image = image_data[0].to_numpy_array()
                            image_record = image_data[1]
                            timestamp_ns = image_record.capture_timestamp_ns
                            
                            _, buffer = cv2.imencode('.jpg', numpy_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            
                            frame_cache = {
                                'image_bytes': buffer.tobytes(),
                                'image_base64': base64.b64encode(buffer.tobytes()).decode('utf-8'),
                                'timestamp_ns': timestamp_ns,
                                'frame_idx': frame_idx,
                                'shape': numpy_image.shape,
                                'stream_label': stream_label,
                                'content_type': 'image/jpeg'
                            }
                            
                            self.memory_cache[stream_label].append(frame_cache)
                            total_frames_loaded += 1
                            self.loading_progress[stream_label] = frame_idx + 1
                            
                            if frame_idx % 20 == 0:
                                print(f"  {stream_label}: {frame_idx+1}/{frame_count} loaded...")
                                
                    except Exception as e:
                        print(f"  ERROR loading {stream_label} frame {frame_idx}: {e}")
                        
                print(f"OK {stream_label}: {len(self.memory_cache[stream_label])} frames cached")
                
            except Exception as e:
                print(f"ERROR loading {stream_label}: {e}")
                self.memory_cache[stream_label] = []
        
        # 로딩 완료
        load_time = time.time() - start_time
        self.cache_loaded = True
        
        print(f"VRS IMAGE MEMORY CACHE COMPLETE!")
        print(f"   Total frames loaded: {total_frames_loaded}")
        print(f"   Load time: {load_time:.2f} seconds")
        
        # 메모리 사용량 정보
        image_size_mb = sum(
            sum(len(frame['image_bytes']) for frame in frames) 
            for frames in self.memory_cache.values()
        ) / (1024 * 1024)
        print(f"   Memory usage: {image_size_mb:.1f} MB")
        
        return f"Image cache loaded: {total_frames_loaded} frames in {load_time:.2f}s"
    
    def get_frame_from_memory(self, stream_label: str, frame_idx: int):
        """
        메모리 캐시에서 프레임 가져오기 (디스크 I/O 없음)
        "좌르르륽" 빠른 접근
        """
        if not self.cache_loaded:
            return None
            
        if stream_label not in self.memory_cache:
            return None
            
        frames = self.memory_cache[stream_label]
        if len(frames) == 0:  # 프레임이 없으면
            return None
            
        if frame_idx >= len(frames):
            frame_idx = frame_idx % len(frames)  # 순환
            
        return frames[frame_idx]
    
    def get_sensor_from_memory(self, sensor_label: str, sensor_idx: int):
        """
        메모리 캐시에서 센서 데이터 가져오기 (디스크 I/O 없음)
        """
        if not self.cache_loaded:
            return None
            
        if sensor_label not in self.memory_cache:
            return None
            
        sensors = self.memory_cache[sensor_label]
        if len(sensors) == 0:  # 센서 데이터가 없으면
            return None
            
        if sensor_idx >= len(sensors):
            sensor_idx = sensor_idx % len(sensors)  # 순환
            
        return sensors[sensor_idx]
    
    def get_all_frames_from_memory(self, frame_idx: int):
        """
        모든 카메라의 동일 인덱스 프레임을 메모리에서 가져오기
        """
        result = {}
        for stream_label, config in self.stream_configs.items():
            frame = self.get_frame_from_memory(stream_label, frame_idx)
            if frame:
                result[stream_label] = frame
        return result
    
    def get_all_sensors_from_memory(self, sensor_idx: int):
        """
        모든 센서의 동일 인덱스 데이터를 메모리에서 가져오기
        """
        result = {}
        for sensor_label, config in self.sensor_configs.items():
            sensor = self.get_sensor_from_memory(sensor_label, sensor_idx)
            if sensor:
                result[sensor_label] = sensor
        return result
    
    def get_cache_stats(self):
        """메모리 캐시 통계"""
        if not self.cache_loaded:
            return {"status": "not_loaded"}
            
        stats = {
            "status": "loaded",
            "total_streams": len(self.memory_cache),
            "frames_per_stream": {
                stream: len(frames) for stream, frames in self.memory_cache.items()
            },
            "total_frames": sum(len(frames) for frames in self.memory_cache.values()),
            "memory_size_mb": sum(
                sum(len(frame['image_bytes']) for frame in frames) 
                for frames in self.memory_cache.values()
            ) / (1024 * 1024)
        }
        return stats

# 글로벌 메모리 캐시 인스턴스
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

print(f"Creating Memory-Cached VRS Loader: {vrs_path}")
memory_cached_vrs = MemoryCachedVRSLoader(vrs_path)
print("Memory-Cached VRS Loader created")

def reset_memory_cache():
    """글로벌 메모리 캐시 리셋"""
    global memory_cached_vrs
    memory_cached_vrs = MemoryCachedVRSLoader(vrs_path)
    return "Memory cache reset"

@csrf_exempt
@api_view(['POST'])
def preload_vrs_to_memory(request):
    """VRS 전체를 메모리에 한번에 로드"""
    try:
        # 강제 리로드 활성화
        force_reload = True
        
        result = memory_cached_vrs.preload_all_frames_to_memory(force_reload=force_reload)
        stats = memory_cached_vrs.get_cache_stats()
        
        return JsonResponse({
            'status': 'success',
            'message': result,
            'cache_stats': stats,
            'method': 'VRS_FULL_MEMORY_PRELOAD'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
def memory_cached_unified_stream(request):
    """
    메모리 캐시에서 초고속 통합 스트리밍
    디스크 I/O 없음 - "좌르르륽" 빠름
    """
    try:
        if not memory_cached_vrs.cache_loaded:
            return JsonResponse({
                'error': 'Memory cache not loaded',
                'suggestion': 'Call /preload-vrs-to-memory/ first'
            }, status=400)
        
        # 프레임 인덱스
        frame_idx = int(request.GET.get('frame', 0))
        
        # 메모리에서 모든 카메라 프레임 가져오기 (디스크 I/O 없음)
        all_frames = memory_cached_vrs.get_all_frames_from_memory(frame_idx)
        
        if not all_frames:
            return JsonResponse({
                'error': 'No frames in memory cache',
                'frame_idx': frame_idx
            }, status=404)
        
        # 이미지 데이터 구성
        images = []
        for stream_label, frame_data in all_frames.items():
            images.append({
                'stream_label': stream_label,
                'image_base64': frame_data['image_base64'],
                'timestamp_ns': frame_data['timestamp_ns'],
                'frame_idx': frame_data['frame_idx'],
                'shape': frame_data['shape'],
                'data_source': 'memory_cache'
            })
        
        # 센서 데이터는 일단 빈 배열 (이미지 먼저 수정)
        sensors = []

        return JsonResponse({
            'unified_data': {
                'images': images,
                'sensors': sensors
            },
            'stats': {
                'total_items': len(images) + len(sensors),
                'image_count': len(images),
                'sensor_count': len(sensors),
                'frame_idx': frame_idx,
                'cache_hits': len(all_frames)
            },
            'method': 'MEMORY_CACHE_FAST',
            'cache_stats': memory_cached_vrs.get_cache_stats()
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': f'Memory cache stream error: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
def memory_cached_single_frame(request):
    """메모리 캐시에서 단일 프레임 반환 (초고속)"""
    try:
        if not memory_cached_vrs.cache_loaded:
            return HttpResponse("Memory cache not loaded", status=400)
        
        stream_label = request.GET.get('stream', 'camera-rgb')
        frame_idx = int(request.GET.get('frame', 0))
        
        # 메모리에서 프레임 가져오기 (디스크 I/O 없음)
        frame_data = memory_cached_vrs.get_frame_from_memory(stream_label, frame_idx)
        
        if not frame_data:
            return HttpResponse(status=204)  # No Content
        
        response = HttpResponse(
            frame_data['image_bytes'],
            content_type=frame_data['content_type']
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Frame-Idx'] = str(frame_data['frame_idx'])
        response['X-Timestamp-NS'] = str(frame_data['timestamp_ns'])
        response['X-Stream-Label'] = stream_label
        response['X-Source'] = 'memory-cache'
        response['X-Shape'] = f"{frame_data['shape'][0]}x{frame_data['shape'][1]}"
        
        return response
        
    except Exception as e:
        return HttpResponse(f"Memory cache frame error: {str(e)}", status=500)

@api_view(['GET'])
def memory_cache_status(request):
    """메모리 캐시 상태 확인"""
    try:
        stats = memory_cached_vrs.get_cache_stats()
        return JsonResponse({
            'cache_stats': stats,
            'vrs_file_path': memory_cached_vrs.vrs_file_path,
            'loading_progress': memory_cached_vrs.loading_progress
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def memory_cached_sensor_stream(request):
    """메모리 캐시에서 센서 데이터 초고속 스트리밍"""
    try:
        if not memory_cached_vrs.cache_loaded:
            return JsonResponse({
                'error': 'Memory cache not loaded',
                'suggestion': 'Call /preload-vrs-to-memory/ first'
            }, status=400)
        
        # 센서 인덱스
        sensor_idx = int(request.GET.get('sensor', 0))
        sensor_types = request.GET.get('sensors', 'imu-right,imu-left,magnetometer,barometer').split(',')
        
        # 요청된 센서들만 메모리에서 가져오기
        sensors = []
        for sensor_type in sensor_types:
            sensor_data = memory_cached_vrs.get_sensor_from_memory(sensor_type, sensor_idx)
            if sensor_data:
                sensors.append(sensor_data)
        
        if not sensors:
            return JsonResponse({
                'error': 'No sensor data in memory cache',
                'sensor_idx': sensor_idx,
                'requested_sensors': sensor_types
            }, status=404)
        
        return JsonResponse({
            'sensor_data': sensors,
            'stats': {
                'sensor_count': len(sensors),
                'sensor_idx': sensor_idx,
                'requested_sensors': sensor_types,
                'cache_hits': len(sensors)
            },
            'method': 'SENSOR_MEMORY_CACHE_FAST',
            'cache_stats': memory_cached_vrs.get_cache_stats()
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': f'Sensor memory cache error: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

@csrf_exempt
@api_view(['POST'])
def reset_memory_cache_api(request):
    """메모리 캐시 완전 리셋"""
    try:
        global memory_cached_vrs
        
        # 기존 캐시 정리
        if hasattr(memory_cached_vrs, 'memory_cache'):
            memory_cached_vrs.memory_cache.clear()
        memory_cached_vrs.cache_loaded = False
        memory_cached_vrs.loading_progress = {}
        
        # 새 인스턴스 생성
        memory_cached_vrs = MemoryCachedVRSLoader(vrs_path)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Memory cache reset complete',
            'cache_stats': memory_cached_vrs.get_cache_stats()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)