"""
WebSocket routing for Aria streaming
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/aria-sessions/(?P<session_id>[^/]+)/stream/$', consumers.AriaStreamingConsumer.as_asgi()),
]