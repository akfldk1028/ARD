#!/usr/bin/env python3
"""
Test image streaming functionality
"""
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from aria_sessions.streaming_service import AriaUnifiedStreaming

def test_image_streaming():
    print("=== Image Streaming Test ===")
    
    # VRS 파일 경로
    vrs_file = r"D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\sample.vrs"
    
    try:
        # 스트리밍 서비스 초기화
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = vrs_file
        streaming.create_data_provider()
        
        # 4개 카메라 테스트
        camera_streams = ['camera-rgb', 'camera-slam-left', 'camera-slam-right', 'camera-eyetracking']
        
        print("Testing all 4 cameras...")
        results = streaming.process_unified_stream(
            active_streams=camera_streams,
            max_count=8,  # 8개 샘플 (카메라당 2개씩)
            include_images=True,  # 이미지 포함
            start_frame=0
        )
        
        print(f"Total results: {len(results)}")
        
        # 카메라별 통계
        camera_stats = {}
        for result in results:
            camera = result.get('stream_label', 'unknown')
            if camera not in camera_stats:
                camera_stats[camera] = {'count': 0, 'has_image': 0, 'errors': 0}
            
            camera_stats[camera]['count'] += 1
            
            if result.get('has_image_data'):
                camera_stats[camera]['has_image'] += 1
                print(f"OK {camera}: {result.get('image_shape')} - {len(result.get('image_data_base64', ''))//1000}KB")
            elif result.get('image_error'):
                camera_stats[camera]['errors'] += 1
                print(f"ERROR {camera}: {result.get('image_error')}")
            else:
                print(f"WARNING {camera}: No image data")
        
        print("\nCamera Statistics:")
        for camera, stats in camera_stats.items():
            print(f"  {camera}: {stats['has_image']}/{stats['count']} images, {stats['errors']} errors")
        
        # 성공적인 이미지가 있는지 확인
        successful_images = sum(stats['has_image'] for stats in camera_stats.values())
        print(f"\nTotal successful images: {successful_images}")
        
        if successful_images == 0:
            print("WARNING: No images were successfully processed!")
        else:
            print("SUCCESS: Image processing is working")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_image_streaming()