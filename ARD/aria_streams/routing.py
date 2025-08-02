"""
WebSocket URL routing for streams app
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket endpoint for real-time Aria data streaming
    re_path(r'ws/aria-realtime/(?P<session_id>\w+)/$', consumers.AriaRealtimeConsumer.as_asgi()),
    
    # WebSocket endpoint for general Aria streaming (without session)
    re_path(r'ws/aria-stream/$', consumers.AriaStreamConsumer.as_asgi()),
    
    # WebSocket endpoint for VRS image streaming
    re_path(r'ws/vrs-images/$', consumers.VRSImageConsumer.as_asgi()),
]