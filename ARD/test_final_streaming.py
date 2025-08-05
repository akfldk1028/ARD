#!/usr/bin/env python3
"""
Final streaming test - 4 images + sensors simultaneously
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
sys.path.append(os.path.dirname(__file__))
django.setup()

from django.test import RequestFactory
from aria_sessions.general_views import general_unified_stream_realtime
import json

def test_final_streaming():
    print("=== Final Streaming Test (4 Images + Sensors) ===")
    
    # Create request like frontend
    factory = RequestFactory()
    request = factory.get('/api/v1/aria-sessions/unified-stream-realtime/?sample=5&max_samples=20&include_images=true')
    
    try:
        # Call API
        response = general_unified_stream_realtime(request)
        
        if response.status_code == 200:
            data = json.loads(response.content.decode('utf-8'))
            
            # Extract data
            images = data.get('unified_data', {}).get('images', [])
            sensors = data.get('unified_data', {}).get('sensors', [])
            stats = data.get('stats', {})
            
            print(f"SUCCESS: API returned {len(images)} images and {len(sensors)} sensors")
            
            # Check each camera
            expected_cameras = ['camera-rgb', 'camera-slam-left', 'camera-slam-right', 'camera-et']
            found_cameras = [img['stream_label'] for img in images]
            
            print("\nCamera Check:")
            for camera in expected_cameras:
                if camera in found_cameras:
                    img_data = next(img for img in images if img['stream_label'] == camera)
                    has_base64 = 'image_base64' in img_data and len(img_data['image_base64']) > 0
                    shape = img_data.get('image_shape', 'unknown')
                    print(f"  OK {camera}: {shape}, Base64: {has_base64}")
                else:
                    print(f"  MISSING {camera}")
            
            # Check sensors
            sensor_types = {}
            for sensor in sensors:
                sensor_type = sensor.get('stream_label', 'unknown')
                if sensor_type not in sensor_types:
                    sensor_types[sensor_type] = 0
                sensor_types[sensor_type] += 1
            
            print(f"\nSensor Check:")
            for sensor_type, count in sensor_types.items():
                print(f"  {sensor_type}: {count} samples")
            
            # Final verdict
            image_success = len(images) >= 4  # At least 4 images
            sensor_success = len(sensors) > 0  # At least some sensors
            
            if image_success and sensor_success:
                print(f"\nFINAL VERDICT: SUCCESS")
                print(f"- Images: {len(images)}/4 cameras working")
                print(f"- Sensors: {len(sensor_types)} types working")
                print(f"- Ready for frontend display!")
            else:
                print(f"\nFINAL VERDICT: PARTIAL")
                print(f"- Images: {'OK' if image_success else 'FAILED'}")
                print(f"- Sensors: {'OK' if sensor_success else 'FAILED'}")
        
        else:
            print(f"API ERROR: Status {response.status_code}")
            print(response.content.decode('utf-8'))
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_final_streaming()