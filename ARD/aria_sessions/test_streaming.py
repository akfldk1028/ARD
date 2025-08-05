#!/usr/bin/env python3
"""
Test streaming service with actual sensor data
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
django.setup()

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_sensor_streaming():
    print("=== Testing Sensor Streaming ===")
    
    # VRS 파일 경로
    vrs_file = os.path.join(os.path.dirname(__file__), 'data', 'sample.vrs')
    print(f"VRS file: {vrs_file}")
    
    # 스트리밍 서비스 초기화
    streaming = AriaUnifiedStreaming()
    streaming.vrsfile = vrs_file
    
    if not streaming.create_data_provider():
        print("ERROR: Failed to create data provider")
        return
    
    print("OK: Data provider created")
    
    # 모든 센서 스트림 포함하여 테스트
    all_streams = ['imu-right', 'imu-left', 'magnetometer', 'barometer', 'camera-rgb']
    
    print(f"\nTesting with streams: {all_streams}")
    
    try:
        results = streaming.process_unified_stream(
            active_streams=all_streams,
            max_count=10,
            include_images=False,  # 센서 데이터만
            start_frame=0
        )
        
        print(f"\nResults: {len(results)} items")
        
        sensor_count = 0
        image_count = 0
        
        for i, result in enumerate(results):
            print(f"\n[{i+1}] {result['stream_label']} - {result['sensor_type']}")
            print(f"    Timestamp: {result['device_timestamp_ns']}")
            
            if result.get('has_sensor_data'):
                sensor_count += 1
                print(f"    OK HAS SENSOR DATA")
                
                # 센서별 데이터 출력
                if 'imu_data' in result:
                    imu = result['imu_data']
                    print(f"    IMU: accel=[{imu['accelerometer']['x']:.3f}, {imu['accelerometer']['y']:.3f}, {imu['accelerometer']['z']:.3f}]")
                    print(f"         gyro=[{imu['gyroscope']['x']:.4f}, {imu['gyroscope']['y']:.4f}, {imu['gyroscope']['z']:.4f}]")
                    print(f"         temp={imu['temperature']['value']:.1f}°C")
                    
                if 'magnetometer_data' in result:
                    mag = result['magnetometer_data']
                    print(f"    MAG: field=[{mag['magnetic_field']['x']:.8f}, {mag['magnetic_field']['y']:.8f}, {mag['magnetic_field']['z']:.8f}] T")
                    print(f"         temp={mag['temperature']['value']:.1f}°C")
                    
                if 'barometer_data' in result:
                    baro = result['barometer_data']
                    print(f"    BARO: pressure={baro['pressure']['value']:.0f} Pa")
                    print(f"          temp={baro['temperature']['value']:.1f}°C")
                    
            elif result.get('has_image_data'):
                image_count += 1
                print(f"    OK HAS IMAGE DATA: {result['image_shape']}")
            else:
                print(f"    X NO DATA")
                if 'sensor_error' in result:
                    print(f"    ERROR: {result['sensor_error']}")
        
        print(f"\n=== SUMMARY ===")
        print(f"Total items: {len(results)}")
        print(f"Sensor data items: {sensor_count}")
        print(f"Image data items: {image_count}")
        
        if sensor_count == 0:
            print("WARNING: NO SENSOR DATA FOUND - This explains why the API returns empty results")
        else:
            print("OK: SENSOR DATA FOUND - API should work")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sensor_streaming()