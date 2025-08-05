#!/usr/bin/env python3
"""
Basic streaming test without Django
"""
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_basic_streaming():
    print("=== Basic Streaming Test (No Django) ===")
    
    # VRS 파일 경로
    vrs_file = r"D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\sample.vrs"
    print(f"VRS file: {vrs_file}")
    print(f"VRS exists: {os.path.exists(vrs_file)}")
    
    if not os.path.exists(vrs_file):
        print("ERROR: VRS file not found!")
        return
    
    try:
        # 스트리밍 서비스 초기화
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = vrs_file
        
        print("Creating data provider...")
        if not streaming.create_data_provider():
            print("ERROR: Failed to create data provider")
            return
        
        print("Provider created successfully!")
        
        # 간단한 스트림 테스트 (IMU만)
        print("Testing IMU streaming...")
        results = streaming.process_unified_stream(
            active_streams=['imu-right'],
            max_count=3,
            include_images=False,
            start_frame=0
        )
        
        print(f"Results: {len(results)} items")
        for i, result in enumerate(results):
            print(f"[{i}] {result.get('stream_label')} - {result.get('sensor_type')}")
            if 'imu_data' in result:
                imu = result['imu_data']
                print(f"    Accel: {imu['accelerometer']}")
                print(f"    Gyro: {imu['gyroscope']}")
                print(f"    Temp: {imu['temperature']}")
            if result.get('sensor_error'):
                print(f"    ERROR: {result['sensor_error']}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_streaming()