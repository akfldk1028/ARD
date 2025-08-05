#!/usr/bin/env python3
"""
Test all sensor types basic functionality
"""
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_all_sensors():
    print("=== All Sensors Test ===")
    
    # VRS 파일 경로
    vrs_file = r"D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\sample.vrs"
    
    try:
        # 스트리밍 서비스 초기화
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = vrs_file
        streaming.create_data_provider()
        
        # 모든 센서 타입 테스트
        all_sensors = ['imu-right', 'imu-left', 'magnetometer', 'barometer', 'microphone', 'gps', 'wps', 'bluetooth']
        
        print("Testing all sensor types...")
        results = streaming.process_unified_stream(
            active_streams=all_sensors,
            max_count=20,  # 20개 샘플
            include_images=False,
            start_frame=0
        )
        
        print(f"Total results: {len(results)}")
        
        # 센서별 통계
        sensor_stats = {}
        for result in results:
            sensor_type = result.get('stream_label', 'unknown')
            if sensor_type not in sensor_stats:
                sensor_stats[sensor_type] = 0
            sensor_stats[sensor_type] += 1
        
        print("\nSensor Statistics:")
        for sensor, count in sensor_stats.items():
            print(f"  {sensor}: {count} samples")
        
        # 각 센서별 샘플 데이터 확인
        print("\nSample Data:")
        for result in results[:10]:  # 처음 10개만
            label = result.get('stream_label')
            sensor_type = result.get('sensor_type')
            
            print(f"\n[{label}] {sensor_type}")
            
            # 센서별 데이터 확인
            if 'imu_data' in result:
                print(f"  IMU: accel=({result['imu_data']['accelerometer']['x']:.3f}, {result['imu_data']['accelerometer']['y']:.3f}, {result['imu_data']['accelerometer']['z']:.3f})")
            elif 'magnetometer_data' in result:
                print(f"  MAG: field=({result['magnetometer_data']['magnetic_field']['x']:.8f}, {result['magnetometer_data']['magnetic_field']['y']:.8f}, {result['magnetometer_data']['magnetic_field']['z']:.8f})")
            elif 'barometer_data' in result:
                print(f"  BARO: pressure={result['barometer_data']['pressure']['value']:.0f} Pa")
            elif 'audio_data' in result:
                print(f"  AUDIO: blocks={result['audio_data']['num_blocks']}")
            elif 'gps_data' in result:
                print(f"  GPS: lat={result['gps_data']['location']['latitude']}, lon={result['gps_data']['location']['longitude']}")
            elif 'wps_data' in result:
                print(f"  WPS: status={result['wps_data']['status']}")
            elif 'bluetooth_data' in result:
                print(f"  BT: status={result['bluetooth_data']['status']}")
            elif result.get('sensor_error'):
                print(f"  ERROR: {result['sensor_error']}")
            else:
                print(f"  No data extracted")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_sensors()