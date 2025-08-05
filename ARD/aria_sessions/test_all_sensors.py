#!/usr/bin/env python3
"""
Test all sensor types and their data structure
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
django.setup()

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_all_sensors():
    print("=== Testing All Sensor Types ===")
    
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
    all_streams = ['camera-rgb', 'imu-right', 'imu-left', 'magnetometer', 'barometer', 'microphone', 'gps', 'wps', 'bluetooth']
    iterator = streaming.create_unified_iterator(all_streams)
    
    # 센서별 샘플 수집
    sensor_samples = {}
    count = 0
    
    for sensor_data in iterator:
        if count >= 50:  # 50개 샘플만 수집
            break
            
        label = streaming.provider.get_label_from_stream_id(sensor_data.stream_id())
        sensor_type = str(sensor_data.sensor_data_type())
        
        if label not in sensor_samples:
            sensor_samples[label] = []
        
        # 센서 데이터 정보 수집
        sample_info = {
            'sensor_type': sensor_type,
            'timestamp': 'N/A',
            'methods': [method for method in dir(sensor_data) if not method.startswith('_') and 'data' in method]
        }
        
        # 센서별 데이터 추출 시도
        if 'BAROMETER' in sensor_type:
            try:
                baro_data = sensor_data.barometer_data()
                sample_info['data_methods'] = [attr for attr in dir(baro_data) if not attr.startswith('_')]
                
                # 속성들 확인
                for attr in ['pressure_pa', 'pressure_pascal', 'pressure', 'temperature']:
                    if hasattr(baro_data, attr):
                        try:
                            value = getattr(baro_data, attr)
                            sample_info[f'attr_{attr}'] = str(value)
                        except Exception as e:
                            sample_info[f'attr_{attr}'] = f'ERROR: {e}'
                            
            except Exception as e:
                sample_info['error'] = str(e)
                
        elif 'MAGNETOMETER' in sensor_type:
            try:
                mag_data = sensor_data.magnetometer_data()
                sample_info['data_methods'] = [attr for attr in dir(mag_data) if not attr.startswith('_')]
                
                # 속성들 확인  
                for attr in ['mag_tesla', 'magnetic_field', 'temperature']:
                    if hasattr(mag_data, attr):
                        try:
                            value = getattr(mag_data, attr)
                            sample_info[f'attr_{attr}'] = str(value)[:100]  # 첫 100자만
                        except Exception as e:
                            sample_info[f'attr_{attr}'] = f'ERROR: {e}'
                            
            except Exception as e:
                sample_info['error'] = str(e)
                
        elif 'AUDIO' in sensor_type:
            try:
                audio_data, record = sensor_data.audio_data_and_record()
                sample_info['data_methods'] = [attr for attr in dir(audio_data) if not attr.startswith('_')]
                sample_info['has_audio_data_and_record'] = True
            except Exception as e:
                sample_info['error'] = str(e)
        
        sensor_samples[label].append(sample_info)
        count += 1
    
    # 결과 출력
    print(f"\n=== Collected {count} samples from {len(sensor_samples)} sensors ===")
    
    for label in sorted(sensor_samples.keys()):
        samples = sensor_samples[label]
        print(f"\n{label} ({len(samples)} samples):")
        
        # 첫 번째 샘플의 상세 정보
        if samples:
            sample = samples[0]
            print(f"  Sensor Type: {sample['sensor_type']}")
            print(f"  Methods: {sample.get('methods', [])}")
            
            if 'data_methods' in sample:
                print(f"  Data Methods: {sample['data_methods']}")
                
            if 'error' in sample:
                print(f"  Error: {sample['error']}")
            else:
                # 속성 값들 출력
                for key, value in sample.items():
                    if key.startswith('attr_'):
                        print(f"  {key[5:]}: {value}")

if __name__ == "__main__":
    test_all_sensors()