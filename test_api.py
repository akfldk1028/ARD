#!/usr/bin/env python
"""
API 테스트 스크립트
"""
import os
import sys
import django
import requests
import json

# Django 설정
sys.path.append(os.path.join(os.path.dirname(__file__), 'ARD'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
django.setup()

from aria_sessions.models import AriaStreamingSession

def test_api():
    base_url = "http://127.0.0.1:8000/api/v1/aria-sessions/api"
    
    # 1. 세션 생성
    vrs_file = os.path.join(os.path.dirname(__file__), 'ARD', 'aria_sessions', 'data', 'sample.vrs')
    session = AriaStreamingSession.objects.create(
        vrs_file_path=vrs_file,
        status='READY'
    )
    
    print(f"✅ 세션 생성: {session.session_id}")
    
    # 2. API 테스트 목록
    test_endpoints = [
        f"{base_url}/sessions/",
        f"{base_url}/sessions/{session.session_id}/",
        f"{base_url}/sessions/{session.session_id}/stream_info/",
        f"{base_url}/sessions/{session.session_id}/image_stream/?stream=camera-rgb&frame=0",
        f"{base_url}/sessions/{session.session_id}/all_streams_image/?frame=1",
        f"{base_url}/sessions/{session.session_id}/unified_stream/?streams=camera-rgb,camera-slam-left&count=5"
    ]
    
    print("\n=== API 엔드포인트 테스트 ===")
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            status = "✅ 성공" if response.status_code == 200 else f"❌ 실패 ({response.status_code})"
            print(f"{status}: {endpoint}")
            
            if response.status_code == 200:
                data = response.json()
                if 'streams' in data:
                    print(f"   → 스트림 수: {len(data['streams'])}")
                elif 'unified_data' in data:
                    print(f"   → 통합 데이터: {len(data['unified_data'])}개")
                elif 'image_shape' in data:
                    print(f"   → 이미지: {data['image_shape']}")
                    
        except requests.exceptions.ConnectionError:
            print(f"❌ 연결 실패: {endpoint} (서버가 실행 중인지 확인)")
        except Exception as e:
            print(f"❌ 오류: {endpoint} - {str(e)}")
    
    print(f"\n=== 테스트 완료 ===")
    print(f"세션 ID: {session.session_id}")
    print("서버 실행 명령어: python ARD/manage.py runserver 127.0.0.1:8000")

if __name__ == "__main__":
    test_api()