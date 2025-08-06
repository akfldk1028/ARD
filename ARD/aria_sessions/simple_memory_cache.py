"""
Simple Memory Cache - 간단한 이미지 메모리 캐시
문제 해결을 위한 클린 버전
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import base64
import cv2
import time

# Project Aria SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    ARIA_AVAILABLE = True
except ImportError:
    ARIA_AVAILABLE = False

class SimpleImageCache:
    def __init__(self, vrs_file_path):
        self.vrs_path = vrs_file_path
        self.cache = {}
        self.loaded = False
        
        try:
            self.provider = data_provider.create_vrs_data_provider(vrs_file_path)
            print(f"Simple cache initialized: {vrs_file_path}")
        except Exception as e:
            print(f"Simple cache init error: {e}")
            self.provider = None
    
    def load_images(self):
        if self.loaded:
            return "Already loaded"
            
        if not self.provider:
            return "No provider"
        
        print("Loading images to simple cache...")
        start_time = time.time()
        
        streams = {
            'camera-rgb': StreamId("214-1"),
            'camera-slam-left': StreamId("1201-1"), 
            'camera-slam-right': StreamId("1201-2"),
            'camera-et': StreamId("211-1")
        }
        
        total_loaded = 0
        
        for name, stream_id in streams.items():
            try:
                count = self.provider.get_num_data(stream_id)
                print(f"Loading {name}: {count} frames")
                
                self.cache[name] = []
                
                for i in range(count):
                    try:
                        image_data = self.provider.get_image_data_by_index(stream_id, i)
                        if image_data[0] is not None:
                            img = image_data[0].to_numpy_array()
                            timestamp = image_data[1].capture_timestamp_ns
                            
                            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            
                            self.cache[name].append({
                                'bytes': buffer.tobytes(),
                                'base64': base64.b64encode(buffer.tobytes()).decode('utf-8'),
                                'timestamp': timestamp,
                                'idx': i,
                                'shape': img.shape
                            })
                            total_loaded += 1
                            
                        if i % 50 == 0:
                            print(f"  {name}: {i}/{count}")
                            
                    except Exception as e:
                        print(f"Error loading {name}[{i}]: {e}")
                        
                print(f"OK {name}: {len(self.cache[name])} cached")
                        
            except Exception as e:
                print(f"Error with {name}: {e}")
                self.cache[name] = []
        
        load_time = time.time() - start_time
        self.loaded = True
        
        print(f"Simple cache complete: {total_loaded} frames in {load_time:.1f}s")
        return f"Loaded {total_loaded} frames"
    
    def get_frame(self, stream, idx):
        if not self.loaded or stream not in self.cache:
            return None
        frames = self.cache[stream]
        if len(frames) == 0:
            return None
        return frames[idx % len(frames)]
    
    def get_all_frames(self, idx):
        result = {}
        for stream in self.cache:
            frame = self.get_frame(stream, idx)
            if frame:
                result[stream] = frame
        return result

# 글로벌 인스턴스
import os
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

simple_cache = SimpleImageCache(vrs_path)

@csrf_exempt
@api_view(['POST'])
def load_simple_cache(request):
    """간단한 캐시 로드"""
    try:
        result = simple_cache.load_images()
        return JsonResponse({
            'status': 'success',
            'message': result,
            'loaded': simple_cache.loaded,
            'cache_size': len(simple_cache.cache)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def simple_cache_stream(request):
    """간단한 캐시 스트리밍"""
    try:
        if not simple_cache.loaded:
            return JsonResponse({'error': 'Cache not loaded'}, status=400)
        
        frame_idx = int(request.GET.get('frame', 0))
        all_frames = simple_cache.get_all_frames(frame_idx)
        
        images = []
        for stream, frame in all_frames.items():
            images.append({
                'stream_label': stream,
                'image_base64': frame['base64'],
                'timestamp_ns': frame['timestamp'],
                'frame_idx': frame['idx'], 
                'shape': frame['shape'],
                'data_source': 'simple_cache'
            })
        
        return JsonResponse({
            'unified_data': {'images': images, 'sensors': []},
            'stats': {'image_count': len(images), 'frame_idx': frame_idx},
            'method': 'SIMPLE_CACHE'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET']) 
def simple_cache_frame(request):
    """간단한 캐시 단일 프레임"""
    try:
        if not simple_cache.loaded:
            return HttpResponse("Cache not loaded", status=400)
            
        stream = request.GET.get('stream', 'camera-rgb')
        frame_idx = int(request.GET.get('frame', 0))
        
        frame = simple_cache.get_frame(stream, frame_idx)
        if not frame:
            return HttpResponse(status=204)
        
        response = HttpResponse(frame['bytes'], content_type='image/jpeg')
        response['X-Frame-Idx'] = str(frame['idx'])
        response['X-Stream'] = stream
        response['X-Source'] = 'simple-cache'
        return response
        
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=500)