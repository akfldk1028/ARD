#!/usr/bin/env python
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'ARD'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
django.setup()

from aria_sessions.models import AriaStreamingSession

# 기존 세션들 확인
print("=== Existing Sessions ===")
sessions = AriaStreamingSession.objects.all()
for session in sessions:
    print(f"Session: {session.session_id} - Status: {session.status}")

# 새 세션 생성
vrs_file = os.path.join(os.path.dirname(__file__), 'ARD', 'aria_sessions', 'data', 'sample.vrs')
new_session = AriaStreamingSession.objects.create(
    vrs_file_path=vrs_file,
    status='READY'
)

print(f"\n=== New Session Created ===")
print(f"Session ID: {new_session.session_id}")

# 테스트 URL들
base_url = "http://127.0.0.1:8000/api/v1/aria-sessions"
session_id = str(new_session.session_id)

test_urls = [
    f"{base_url}/sessions/",
    f"{base_url}/sessions/{session_id}/",
    f"{base_url}/sessions/{session_id}/stream_info/",
    f"{base_url}/sessions/{session_id}/image_stream/?stream=camera-rgb&frame=0",
    f"{base_url}/sessions/{session_id}/all_streams_image/?frame=1",
    f"{base_url}/sessions/{session_id}/unified_stream/?count=5"
]

print(f"\n=== Test URLs ===")
for i, url in enumerate(test_urls, 1):
    print(f"{i}. {url}")

print(f"\n=== Copy and paste these URLs in your browser ===")