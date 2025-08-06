"""
Sensor Memory Cache - 센서 데이터 전용 메모리 캐시
이미지와 분리해서 센서만 "좌르르륽" 스트리밍
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
import time
import logging

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    from projectaria_tools.core.sensor_data import TimeDomain
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)

class SensorMemoryCache:
    """센서 데이터 전용 메모리 캐시"""
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.vrs_provider = None
        self.sensor_cache = {}
        self.cache_loaded = False
        
        # 센서 설정 (Meta 공식)
        self.sensor_configs = {
            'imu-right': {'stream_id': StreamId("1202-1")},
            'imu-left': {'stream_id': StreamId("1202-2")},
            'magnetometer': {'stream_id': StreamId("1203-1")},
            'barometer': {'stream_id': StreamId("247-1")},
            'microphone': {'stream_id': StreamId("231-1")}
        }
        
        # VRS Provider 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            print(f"Sensor VRS Provider initialized: {vrs_file_path}")
        except Exception as e:
            logger.error(f"Sensor VRS initialization failed: {e}")
    
    def preload_sensors_to_memory(self):
        """센서 데이터만 메모리에 로드"""
        if self.cache_loaded:
            return "Sensors already loaded"
            
        if not self.vrs_provider:
            return "VRS Provider not available"
        
        print("Loading sensors to memory...")
        start_time = time.time()
        total_sensors = 0
        
        for sensor_label, config in self.sensor_configs.items():
            stream_id = config['stream_id']
            
            try:
                sensor_count = self.vrs_provider.get_num_data(stream_id)
                print(f"Loading {sensor_label}: {sensor_count} sensors...")
                
                self.sensor_cache[sensor_label] = []
                
                for sensor_idx in range(sensor_count):
                    try:
                        sensor_data = self.vrs_provider.get_sensor_data_by_index(stream_id, sensor_idx)
                        
                        if sensor_data is not None:
                            timestamp_ns = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                            
                            sensor_cache = {
                                'timestamp_ns': timestamp_ns,
                                'sensor_idx': sensor_idx,
                                'stream_label': sensor_label,
                                'data_source': 'sensor_memory_cache'
                            }
                            
                            # 센서 타입별 데이터 추출
                            if 'imu' in sensor_label:
                                accel = sensor_data.get_accel_msec2()
                                gyro = sensor_data.get_gyro_radsec() 
                                temp = sensor_data.get_temperature()
                                
                                sensor_cache['imu'] = {
                                    'accelerometer': {'x': float(accel[0]), 'y': float(accel[1]), 'z': float(accel[2])},
                                    'gyroscope': {'x': float(gyro[0]), 'y': float(gyro[1]), 'z': float(gyro[2])},
                                    'temperature': {'value': float(temp)}
                                }
                            elif 'magnetometer' in sensor_label:
                                mag_field = sensor_data.get_magnetic_field()
                                temp = sensor_data.get_temperature()
                                
                                sensor_cache['magnetometer'] = {
                                    'magnetic_field': {'x': float(mag_field[0]), 'y': float(mag_field[1]), 'z': float(mag_field[2])},
                                    'temperature': {'value': float(temp)}
                                }
                            elif 'barometer' in sensor_label:
                                pressure = sensor_data.get_pressure()
                                temp = sensor_data.get_temperature()
                                
                                sensor_cache['barometer'] = {
                                    'pressure': {'value': float(pressure)},
                                    'temperature': {'value': float(temp)}
                                }
                            elif 'microphone' in sensor_label:
                                audio_blocks = sensor_data.get_audio_blocks()
                                
                                sensor_cache['audio'] = {
                                    'num_blocks': len(audio_blocks) if audio_blocks else 0,
                                    'sample_info': {
                                        'total_samples': sum(len(block) for block in audio_blocks) if audio_blocks else 0,
                                        'channels': 1
                                    }
                                }
                            
                            self.sensor_cache[sensor_label].append(sensor_cache)
                            total_sensors += 1
                            
                            if sensor_idx % 100 == 0:
                                print(f"  {sensor_label}: {sensor_idx+1}/{sensor_count} loaded...")
                                
                    except Exception as e:
                        print(f"  ERROR loading {sensor_label} sensor {sensor_idx}: {e}")
                        
                print(f"OK {sensor_label}: {len(self.sensor_cache[sensor_label])} sensors cached")
                
            except Exception as e:
                print(f"ERROR loading {sensor_label}: {e}")
                self.sensor_cache[sensor_label] = []
        
        load_time = time.time() - start_time
        self.cache_loaded = True
        
        print(f"SENSOR MEMORY CACHE COMPLETE!")
        print(f"   Total sensors loaded: {total_sensors}")
        print(f"   Load time: {load_time:.2f} seconds")
        
        return f"Sensor cache loaded: {total_sensors} sensors in {load_time:.2f}s"
    
    def get_sensor_from_cache(self, sensor_label: str, sensor_idx: int):
        """메모리에서 센서 데이터 가져오기"""
        if not self.cache_loaded:
            return None
            
        if sensor_label not in self.sensor_cache:
            return None
            
        sensors = self.sensor_cache[sensor_label]
        if len(sensors) == 0:
            return None
            
        if sensor_idx >= len(sensors):
            sensor_idx = sensor_idx % len(sensors)
            
        return sensors[sensor_idx]
    
    def get_all_sensors_from_cache(self, sensor_idx: int):
        """모든 센서 데이터 가져오기"""
        result = {}
        for sensor_label in self.sensor_configs:
            sensor = self.get_sensor_from_cache(sensor_label, sensor_idx)
            if sensor:
                result[sensor_label] = sensor
        return result
    
    def get_cache_stats(self):
        """센서 캐시 통계"""
        if not self.cache_loaded:
            return {"status": "not_loaded"}
            
        return {
            "status": "loaded",
            "total_sensors": len(self.sensor_cache),
            "sensors_per_stream": {
                sensor: len(data) for sensor, data in self.sensor_cache.items()
            },
            "total_sensor_data": sum(len(data) for data in self.sensor_cache.values())
        }

# 글로벌 센서 캐시 인스턴스
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

print(f"Creating Sensor Memory Cache: {vrs_path}")
sensor_memory_cache = SensorMemoryCache(vrs_path)

@csrf_exempt
@api_view(['POST'])
def preload_sensors_to_memory(request):
    """센서 데이터를 메모리에 로드"""
    try:
        result = sensor_memory_cache.preload_sensors_to_memory()
        stats = sensor_memory_cache.get_cache_stats()
        
        return JsonResponse({
            'status': 'success',
            'message': result,
            'sensor_stats': stats,
            'method': 'SENSOR_MEMORY_PRELOAD'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
def sensor_memory_cached_stream(request):
    """메모리에서 센서 데이터 스트리밍"""
    try:
        if not sensor_memory_cache.cache_loaded:
            return JsonResponse({
                'error': 'Sensor cache not loaded',
                'suggestion': 'Call /preload-sensors-to-memory/ first'
            }, status=400)
        
        sensor_idx = int(request.GET.get('sensor', 0))
        sensor_types = request.GET.get('sensors', 'imu-right,imu-left,magnetometer,barometer').split(',')
        
        # 요청된 센서들만 메모리에서 가져오기
        sensors = []
        for sensor_type in sensor_types:
            sensor_data = sensor_memory_cache.get_sensor_from_cache(sensor_type, sensor_idx)
            if sensor_data:
                sensors.append(sensor_data)
        
        return JsonResponse({
            'sensor_data': sensors,
            'stats': {
                'sensor_count': len(sensors),
                'sensor_idx': sensor_idx,
                'requested_sensors': sensor_types
            },
            'method': 'SENSOR_MEMORY_CACHE_FAST'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Sensor cache error: {str(e)}'
        }, status=500)

@api_view(['GET'])
def sensor_memory_cache_status(request):
    """센서 메모리 캐시 상태"""
    try:
        return JsonResponse({
            'sensor_cache_stats': sensor_memory_cache.get_cache_stats(),
            'vrs_file_path': sensor_memory_cache.vrs_file_path
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)