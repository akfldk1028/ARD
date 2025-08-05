#!/usr/bin/env python3
"""
Test what methods are available on sensor_data objects
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
django.setup()

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_sensor_methods():
    print("=== Testing Sensor Data Methods ===")
    
    # VRS 파일 경로
    vrs_file = os.path.join(os.path.dirname(__file__), 'data', 'sample.vrs')
    print(f"VRS file: {vrs_file}")
    
    # 스트리밍 서비스 초기화
    streaming = AriaUnifiedStreaming()
    streaming.vrsfile = vrs_file
    
    if not streaming.create_data_provider():
        print("ERROR: Failed to create data provider")
        return
        
    # 이터레이터 생성 (모든 센서 활성화)
    iterator = streaming.create_unified_iterator(['imu-right', 'barometer', 'magnetometer'])
    
    # 첫 번째 센서 데이터 몇 개만 확인
    count = 0
    for sensor_data in iterator:
        if count >= 5:
            break
            
        label = streaming.provider.get_label_from_stream_id(sensor_data.stream_id())
        sensor_type = sensor_data.sensor_data_type()
        
        print(f"\n[{count+1}] {label} - {sensor_type}")
        
        # 사용 가능한 메서드들 확인
        methods = [method for method in dir(sensor_data) if not method.startswith('_')]
        print(f"Available methods: {methods}")
        
        # 센서 타입별로 시도해볼 메서드들
        sensor_type_str = str(sensor_type)
        
        if 'IMU' in sensor_type_str:
            print("Testing IMU methods...")
            # 가능한 IMU 메서드들 시도
            for method_name in ['imu_data', 'get_imu_data', 'as_imu_data', 'imu_data_and_record']:
                if hasattr(sensor_data, method_name):
                    print(f"  ✓ Found method: {method_name}")
                    try:
                        result = getattr(sensor_data, method_name)()
                        print(f"    Result type: {type(result)}")
                        if hasattr(result, '__dict__'):
                            print(f"    Result attributes: {list(result.__dict__.keys()) if hasattr(result, '__dict__') else 'No dict'}")
                    except Exception as e:
                        print(f"    Error calling {method_name}: {e}")
                else:
                    print(f"  ✗ No method: {method_name}")
                    
        elif 'BAROMETER' in sensor_type_str:
            print("Testing BAROMETER methods...")
            for method_name in ['barometer_data', 'get_barometer_data', 'as_barometer_data', 'barometer_data_and_record']:
                if hasattr(sensor_data, method_name):
                    print(f"  ✓ Found method: {method_name}")
                    try:
                        result = getattr(sensor_data, method_name)()
                        print(f"    Result type: {type(result)}")
                    except Exception as e:
                        print(f"    Error calling {method_name}: {e}")
                else:
                    print(f"  ✗ No method: {method_name}")
                    
        elif 'MAGNETOMETER' in sensor_type_str:
            print("Testing MAGNETOMETER methods...")
            for method_name in ['magnetometer_data', 'get_magnetometer_data', 'as_magnetometer_data', 'magnetometer_data_and_record']:
                if hasattr(sensor_data, method_name):
                    print(f"  ✓ Found method: {method_name}")
                    try:
                        result = getattr(sensor_data, method_name)()
                        print(f"    Result type: {type(result)}")
                    except Exception as e:
                        print(f"    Error calling {method_name}: {e}")
                else:
                    print(f"  ✗ No method: {method_name}")
        
        count += 1

if __name__ == "__main__":
    test_sensor_methods()