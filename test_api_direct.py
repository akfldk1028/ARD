#!/usr/bin/env python3
"""
Direct API endpoint test
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

def test_api_direct():
    print("=== Direct API Test ===")
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/api/v1/aria-sessions/unified-stream-realtime/?sample=0&max_samples=5&include_images=true')
    
    try:
        # Call the view directly
        response = general_unified_stream_realtime(request)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.get('Content-Type', 'Unknown')}")
        
        if hasattr(response, 'content'):
            content = response.content.decode('utf-8')
            print(f"Content Length: {len(content)}")
            print(f"Content Preview: {content[:500]}...")
            
            if content.startswith('<'):
                print("ERROR: Receiving HTML instead of JSON!")
            elif content.startswith('{'):
                print("SUCCESS: Receiving JSON response")
            else:
                print(f"UNKNOWN: Content starts with: {content[:50]}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_direct()