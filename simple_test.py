#!/usr/bin/env python
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'ARD'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
django.setup()

from aria_sessions.models import AriaStreamingSession

# 세션 생성
vrs_file = os.path.join(os.path.dirname(__file__), 'ARD', 'aria_sessions', 'data', 'sample.vrs')
session = AriaStreamingSession.objects.create(
    vrs_file_path=vrs_file,
    status='READY'
)

print(f"Session created: {session.session_id}")
print("Test URLs:")
print(f"1. Sessions list: /api/v1/aria-sessions/api/sessions/")
print(f"2. Session detail: /api/v1/aria-sessions/api/sessions/{session.session_id}/")
print(f"3. Stream info: /api/v1/aria-sessions/api/sessions/{session.session_id}/stream_info/")
print(f"4. Image stream: /api/v1/aria-sessions/api/sessions/{session.session_id}/image_stream/?stream=camera-rgb&frame=0")
print(f"5. All streams: /api/v1/aria-sessions/api/sessions/{session.session_id}/all_streams_image/?frame=1")
print(f"6. Unified stream: /api/v1/aria-sessions/api/sessions/{session.session_id}/unified_stream/?count=5")

print("\nStart server with: python ARD/manage.py runserver 127.0.0.1:8000")