#!/usr/bin/env python3
"""
Test actual API response that frontend receives
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

def test_api_response():
    print("=== API Response Test ===")
    
    # Create a mock request like frontend makes
    factory = RequestFactory()
    request = factory.get('/api/v1/aria-sessions/unified-stream-realtime/?sample=0&max_samples=10&include_images=true')
    
    try:
        # Call the view directly
        response = general_unified_stream_realtime(request)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Parse JSON response
            content = response.content.decode('utf-8')
            data = json.loads(content)
            
            print(f"Response keys: {list(data.keys())}")
            
            if 'unified_data' in data:
                unified = data['unified_data']
                print(f"Images: {len(unified.get('images', []))}")
                print(f"Sensors: {len(unified.get('sensors', []))}")
                
                # Check first image
                if unified.get('images'):
                    img = unified['images'][0]
                    print(f"First image: {img.get('stream_label')} - {img.get('image_shape')}")
                    has_base64 = 'image_base64' in img
                    print(f"Has base64 data: {has_base64}")
                    if has_base64:
                        print(f"Base64 length: {len(img['image_base64'])}")
                
                # Check first sensor
                if unified.get('sensors'):
                    sensor = unified['sensors'][0]
                    print(f"First sensor: {sensor.get('stream_label')} - {sensor.get('sensor_type')}")
            
            if 'stats' in data:
                stats = data['stats']
                print(f"Stats: total={stats.get('total_items')}, images={stats.get('image_count')}, sensors={stats.get('sensor_count')}")
        
        else:
            # Error response
            content = response.content.decode('utf-8')
            print(f"Error response: {content}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_response()