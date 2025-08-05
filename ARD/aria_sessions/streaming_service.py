"""
ipynb 패턴을 정확히 따른 통합 스트리밍 서비스
"""
import os
import sys
import urllib.request
import ssl
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId
import numpy as np

class AriaUnifiedStreaming:
    def __init__(self):
        self.provider = None
        self.vrsfile = None
        
    def setup_sample_data(self):
        """ipynb와 동일한 방식으로 샘플 데이터 설정"""
        # ipynb 코드 그대로
        google_colab_env = False  # 로컬 환경
        
        if google_colab_env:
            print("Running from Google Colab, installing projectaria_tools and getting sample data")
            # !pip install projectaria-tools
            # !curl -O -J -L "https://github.com/facebookresearch/projectaria_tools/raw/main/data/mps_sample/sample.vrs"
            self.vrsfile = "sample.vrs"
        else:
            print("Using pre-existing projectaria_tool github repository")
            # ipynb 패턴: aria_sessions/data/sample.vrs 사용
            self.vrsfile = os.path.join(os.path.dirname(__file__), 'data', 'sample.vrs')
            
            # 파일이 없으면 ipynb 패턴으로 다운로드
            if not os.path.exists(self.vrsfile):
                from .data_downloader import download_ipynb_sample_data
                self.vrsfile = download_ipynb_sample_data()
        
        return self.vrsfile
    
    def create_data_provider(self):
        """ipynb 패턴: 데이터 프로바이더 생성"""
        if not self.vrsfile:
            self.setup_sample_data()
            
        print(f"Creating data provider from {self.vrsfile}")
        self.provider = data_provider.create_vrs_data_provider(self.vrsfile)
        if not self.provider:
            print("Invalid vrs data provider")
            return False
        return True
    
    def get_all_available_streams(self):
        """ipynb 패턴: 실제 VRS 파일의 모든 스트림 확인 + RecordableTypeId별 검색"""
        if not self.provider:
            return {}
            
        stream_info = {}
        
        # 1. 기본 get_all_streams() 방법
        try:
            all_streams = self.provider.get_all_streams()
            print(f"Total streams found: {len(all_streams)}")
            
            for stream_id in all_streams:
                try:
                    label = self.provider.get_label_from_stream_id(stream_id)
                    data_count = self.provider.get_num_data(stream_id)
                    stream_info[label] = {
                        'stream_id': stream_id,
                        'data_count': data_count,
                        'available': data_count > 0
                    }
                    print(f"Found stream: {label} ({stream_id}) - {data_count} data points")
                except Exception as e:
                    print(f"Error processing stream {stream_id}: {e}")
        except Exception as e:
            print(f"Error getting all streams: {e}")
            
        # 2. ipynb 패턴: RecordableTypeId별로 검색
        try:
            # IMU 검색 (ipynb에서 사용한 방법)
            imu_stream_ids = self.provider.get_stream_ids(RecordableTypeId.SLAM_IMU_DATA)
            print(f"IMU streams found: {len(imu_stream_ids)}")
            for stream_id in imu_stream_ids:
                try:
                    label = self.provider.get_label_from_stream_id(stream_id)
                    data_count = self.provider.get_num_data(stream_id)
                    if label not in stream_info:
                        stream_info[label] = {
                            'stream_id': stream_id,
                            'data_count': data_count,
                            'available': data_count > 0
                        }
                        print(f"Found IMU stream: {label} ({stream_id}) - {data_count} data points")
                except Exception as e:
                    print(f"Error processing IMU stream {stream_id}: {e}")
                    
            # 다른 센서 타입들도 확인
            other_sensor_types = [
                RecordableTypeId.BAROMETER_DATA,
                RecordableTypeId.MAGNETOMETER_DATA,
                RecordableTypeId.AUDIO_DATA,
                RecordableTypeId.MOTION_IMU_DATA
            ]
            
            for sensor_type in other_sensor_types:
                try:
                    sensor_streams = self.provider.get_stream_ids(sensor_type)
                    print(f"{sensor_type} streams found: {len(sensor_streams)}")
                    for stream_id in sensor_streams:
                        try:
                            label = self.provider.get_label_from_stream_id(stream_id)
                            data_count = self.provider.get_num_data(stream_id)
                            if label not in stream_info:
                                stream_info[label] = {
                                    'stream_id': stream_id,
                                    'data_count': data_count,
                                    'available': data_count > 0
                                }
                                print(f"Found {sensor_type} stream: {label} ({stream_id}) - {data_count} data points")
                        except Exception as e:
                            print(f"Error processing {sensor_type} stream {stream_id}: {e}")
                except Exception as e:
                    print(f"Error getting {sensor_type} streams: {e}")
                    
        except Exception as e:
            print(f"Error searching by RecordableTypeId: {e}")
                
        return stream_info
    
    def get_stream_mappings(self):
        """VRS 파일의 모든 센서 스트림 매핑 (진단 결과 기반)"""
        return {
            # 카메라 스트림들
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"), 
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
            "camera-et": StreamId("211-1"),  # 별칭
            
            # 센서 스트림들
            "imu-right": StreamId("1202-1"),
            "imu-left": StreamId("1202-2"),
            "magnetometer": StreamId("1203-1"),
            "mag0": StreamId("1203-1"),  # 별칭
            "barometer": StreamId("247-1"),
            "baro0": StreamId("247-1"),  # 별칭
            
            # 오디오/기타
            "microphone": StreamId("231-1"),
            "mic": StreamId("231-1"),  # 별칭
            "audio": StreamId("231-1"),  # 별칭
            "gps": StreamId("281-1"),
            "wps": StreamId("282-1"),
            "bluetooth": StreamId("283-1"),
        }
    
    def setup_deliver_options(self, active_streams=None):
        """ipynb 패턴: deliver_queued_sensor_data 옵션 설정"""
        if not self.provider:
            raise Exception("Provider not initialized")
            
        # Step 1: ipynb와 동일한 기본 옵션
        options = self.provider.get_default_deliver_queued_options()
        
        # Step 2: ipynb 패턴으로 옵션 설정
        options.set_truncate_first_device_time_ns(int(1e8))  # 0.1 secs after vrs first timestamp
        options.set_truncate_last_device_time_ns(int(1e9))   # 1 sec before vrs last timestamp
        
        # 모든 센서 비활성화 후 원하는 것만 활성화
        options.deactivate_stream_all()
        
        if active_streams:
            stream_mappings = self.get_stream_mappings()
            for stream_name in active_streams:
                if stream_name in stream_mappings:
                    stream_id = stream_mappings[stream_name]
                    options.activate_stream(stream_id)
                    options.set_subsample_rate(stream_id, 1)  # 모든 데이터 샘플링
        else:
            # 기본값: SLAM 카메라들만 활성화 (ipynb 예제처럼)
            slam_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_CAMERA_DATA)
            for stream_id in slam_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 1)
        
        return options
    
    def create_unified_iterator(self, active_streams=None):
        """ipynb 패턴: 통합 스트림 이터레이터 생성"""
        if not self.provider:
            self.create_data_provider()
            
        options = self.setup_deliver_options(active_streams)
        
        # Step 3: ipynb와 동일한 이터레이터 생성
        return self.provider.deliver_queued_sensor_data(options)
    
    def process_unified_stream(self, active_streams=None, max_count=None, include_images=False, start_frame=0):
        """통합 스트림 처리 - 모든 센서 타입 지원 (이미지, IMU, 자력계, 기압계, 오디오)"""
        iterator = self.create_unified_iterator(active_streams)
        
        results = []
        count = 0
        skip_count = 0
        
        for sensor_data in iterator:
            # start_frame까지 스킵
            if skip_count < start_frame:
                skip_count += 1
                continue
                
            if max_count and count >= max_count:
                break
                
            # ipynb 패턴으로 기본 데이터 추출
            label = self.provider.get_label_from_stream_id(sensor_data.stream_id())
            sensor_type = sensor_data.sensor_data_type()
            device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
            host_timestamp = sensor_data.get_time_ns(TimeDomain.HOST_TIME)
            
            data_item = {
                'stream_id': str(sensor_data.stream_id()),
                'stream_label': label,
                'sensor_type': str(sensor_type),
                'device_timestamp_ns': device_timestamp,
                'host_timestamp_ns': host_timestamp,
                'sequence': count
            }
            
            # 센서 타입별 데이터 처리
            sensor_type_str = str(sensor_type)
            
            if sensor_type_str == 'SensorDataType.IMAGE':
                # 이미지 데이터 처리 (카메라들)
                if include_images:
                    try:
                        image_data, record = sensor_data.image_data_and_record()
                        image_array = image_data.to_numpy_array()
                        
                        data_item.update({
                            'image_shape': list(image_array.shape),
                            'image_dtype': str(image_array.dtype),
                            'capture_timestamp_ns': record.capture_timestamp_ns,
                            'frame_number': getattr(record, 'frame_number', None),
                            'has_image_data': True
                        })
                        
                        # Base64 인코딩된 이미지 
                        import base64
                        import cv2
                        _, buffer = cv2.imencode('.jpg', image_array, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        image_bytes = buffer.tobytes()
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        data_item['image_data_base64'] = image_base64
                        
                    except Exception as e:
                        data_item['image_error'] = str(e)
                        data_item['has_image_data'] = False
                        
            elif sensor_type_str == 'SensorDataType.IMU':
                # IMU 데이터 처리 (가속도계, 자이로스코프, 온도)
                try:
                    imu_data = sensor_data.imu_data()  # 올바른 메서드 이름
                    
                    # IMU 데이터 추출 (ipynb 패턴)
                    accel = imu_data.accel_msec2  # 가속도 (m/s²)
                    gyro = imu_data.gyro_radsec   # 각속도 (rad/s)
                    temp = imu_data.temperature   # 온도 (°C)
                    
                    # NaN 값 처리 (JSON 직렬화 문제 방지)
                    import math
                    try:
                        temp_value = float(temp) if temp is not None and not math.isnan(float(temp)) else None
                    except (ValueError, TypeError):
                        temp_value = None
                    
                    data_item.update({
                        'imu_data': {
                            'accelerometer': {
                                'x': float(accel[0]),
                                'y': float(accel[1]),
                                'z': float(accel[2]),
                                'unit': 'm/s²'
                            },
                            'gyroscope': {
                                'x': float(gyro[0]),
                                'y': float(gyro[1]),
                                'z': float(gyro[2]),
                                'unit': 'rad/s'
                            },
                            'temperature': {
                                'value': temp_value,
                                'unit': '°C'
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    
            elif sensor_type_str == 'SensorDataType.MAGNETOMETER':
                # 자력계 데이터 처리
                try:
                    mag_data = sensor_data.magnetometer_data()  # 올바른 메서드 이름
                    
                    # 자력계 데이터 추출
                    mag_field = mag_data.mag_tesla  # 자기장 (Tesla)
                    temp = mag_data.temperature     # 온도 (°C)
                    
                    data_item.update({
                        'magnetometer_data': {
                            'magnetic_field': {
                                'x': float(mag_field[0]),
                                'y': float(mag_field[1]), 
                                'z': float(mag_field[2]),
                                'unit': 'Tesla'
                            },
                            'temperature': {
                                'value': float(temp),
                                'unit': '°C'
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    
            elif sensor_type_str == 'SensorDataType.BAROMETER':
                # 기압계 데이터 처리
                try:
                    baro_data = sensor_data.barometer_data()  # 올바른 메서드 이름
                    
                    # 기압계 데이터 추출 (실제 속성 이름)
                    pressure = baro_data.pressure     # 압력 (Pascal) - 올바른 속성명
                    temp = baro_data.temperature      # 온도 (°C)
                    
                    data_item.update({
                        'barometer_data': {
                            'pressure': {
                                'value': float(pressure),
                                'unit': 'Pascal'
                            },
                            'temperature': {
                                'value': float(temp),
                                'unit': '°C'
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    
            elif sensor_type_str == 'SensorDataType.AUDIO':
                # 오디오 데이터 처리
                try:
                    audio_data, record = sensor_data.audio_data_and_record()
                    
                    # 오디오 데이터 추출 (메타데이터만, 실제 오디오는 크기가 큼)
                    audio_blocks = audio_data.audio_blocks
                    
                    data_item.update({
                        'audio_data': {
                            'num_blocks': len(audio_blocks),
                            'sample_info': {
                                'total_samples': sum(len(block.data) for block in audio_blocks),
                                'channels': audio_blocks[0].num_channels if audio_blocks else 0,
                            }
                        },
                        'capture_timestamp_ns': record.capture_timestamp_ns,
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
            
            elif sensor_type_str == 'SensorDataType.GPS' or 'GPS' in sensor_type_str.upper():
                # GPS 데이터 처리
                try:
                    gps_data = sensor_data.gps_data()  # GPS 데이터 추출
                    
                    # GPS 데이터 구조 (속성들 확인 필요)
                    data_item.update({
                        'gps_data': {
                            'status': 'active',
                            'location': {
                                'latitude': getattr(gps_data, 'latitude', 0.0),
                                'longitude': getattr(gps_data, 'longitude', 0.0),
                                'altitude': getattr(gps_data, 'altitude', 0.0),
                                'unit': 'degrees/meters'
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    data_item['gps_detected'] = True  # 감지되었지만 처리 실패
                    
            elif sensor_type_str == 'SensorDataType.WPS' or 'WPS' in sensor_type_str.upper():
                # WPS (WiFi Positioning System) 데이터 처리
                try:
                    wps_data = sensor_data.wps_data()  # WPS 데이터 추출
                    
                    data_item.update({
                        'wps_data': {
                            'status': 'active',
                            'signal_info': {
                                'strength': getattr(wps_data, 'signal_strength', 0),
                                'quality': getattr(wps_data, 'signal_quality', 0),
                                'networks': getattr(wps_data, 'network_count', 0)
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    data_item['wps_detected'] = True  # 감지되었지만 처리 실패
                    
            elif sensor_type_str == 'SensorDataType.BLUETOOTH' or 'BLUETOOTH' in sensor_type_str.upper():
                # 블루투스 데이터 처리
                try:
                    bt_data = sensor_data.bluetooth_data()  # 블루투스 데이터 추출
                    
                    data_item.update({
                        'bluetooth_data': {
                            'status': 'active',
                            'connection_info': {
                                'devices': getattr(bt_data, 'device_count', 0),
                                'signal_strength': getattr(bt_data, 'signal_strength', 0),
                                'connection_state': getattr(bt_data, 'state', 'unknown')
                            }
                        },
                        'has_sensor_data': True
                    })
                    
                except Exception as e:
                    data_item['sensor_error'] = str(e)
                    data_item['has_sensor_data'] = False
                    data_item['bluetooth_detected'] = True  # 감지되었지만 처리 실패
            
            results.append(data_item)
            count += 1
            
            # 진행 상황 로그
            if data_item.get('has_image_data'):
                print(f"[{count}] {label} - {sensor_type} @ {device_timestamp}ns - Image: {data_item.get('image_shape')}")
            elif data_item.get('has_sensor_data'):
                print(f"[{count}] {label} - {sensor_type} @ {device_timestamp}ns - Sensor data")
            else:
                print(f"[{count}] {label} - {sensor_type} @ {device_timestamp}ns")
        
        return results
    
    def get_balanced_stream_data(self, max_images=4, max_sensors=10, start_offset=0):
        """
        균형있는 스트림 데이터 수집 - 이미지와 센서 데이터를 각각 보장
        """
        # 이미지 스트림과 센서 스트림 분리
        image_streams = ['camera-rgb', 'camera-slam-left', 'camera-slam-right', 'camera-eyetracking']
        sensor_streams = ['imu-right', 'imu-left', 'magnetometer', 'barometer', 'microphone', 'gps', 'wps', 'bluetooth']
        
        results = []
        
        # 1. 이미지 데이터 수집
        if max_images > 0:
            try:
                print(f"Collecting {max_images} images from cameras...")
                image_results = self.process_unified_stream(
                    active_streams=image_streams,
                    max_count=max_images,
                    include_images=True,
                    start_frame=start_offset
                )
                results.extend(image_results)
                print(f"Collected {len(image_results)} image items")
            except Exception as e:
                print(f"Error collecting images: {e}")
        
        # 2. 센서 데이터 수집
        if max_sensors > 0:
            try:
                print(f"Collecting {max_sensors} sensor data...")
                sensor_results = self.process_unified_stream(
                    active_streams=sensor_streams,
                    max_count=max_sensors,
                    include_images=False,
                    start_frame=start_offset
                )
                results.extend(sensor_results)
                print(f"Collected {len(sensor_results)} sensor items")
            except Exception as e:
                print(f"Error collecting sensors: {e}")
        
        # 타임스탬프로 정렬
        results.sort(key=lambda x: x.get('device_timestamp_ns', 0))
        
        print(f"Total balanced results: {len(results)} items")
        return results

def test_unified_streaming():
    """테스트 함수"""
    streaming = AriaUnifiedStreaming()
    
    # RGB와 SLAM 카메라 활성화
    active_streams = ["camera-rgb", "camera-slam-left", "camera-slam-right"]
    
    # 통합 스트리밍 테스트 (처음 10개)
    results = streaming.process_unified_stream(
        active_streams=active_streams,
        max_count=10
    )
    
    print(f"\n=== 처리 완료: {len(results)}개 항목 ===")
    return results

if __name__ == "__main__":
    test_unified_streaming()