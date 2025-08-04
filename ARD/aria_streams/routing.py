"""
WebSocket URL routing for streams app
Real-time Unity integration with direct Kafka streaming
"""

from django.urls import re_path, path
from . import websocket_consumers

websocket_urlpatterns = [
    # Unity real-time streaming WebSocket (NEW - direct Kafka to WebSocket)
    re_path(r'ws/unity/stream/(?P<session_id>\w+)/$', websocket_consumers.AriaRealTimeStreamConsumer.as_asgi()),
    
    # Aria device control WebSocket
    re_path(r'ws/aria/control/(?P<session_id>\w+)/$', websocket_consumers.AriaControlConsumer.as_asgi()),
    
    # Test WebSocket connection (for development)
    path('ws/unity/test/', websocket_consumers.AriaRealTimeStreamConsumer.as_asgi()),
    
    # Legacy WebSocket endpoints (compatibility)
    # NOTE: Use /ws/unity/stream/ for new Unity development
    re_path(r'ws/aria-realtime/(?P<session_id>\w+)/$', websocket_consumers.AriaRealTimeStreamConsumer.as_asgi()),
    re_path(r'ws/aria-stream/$', websocket_consumers.AriaRealTimeStreamConsumer.as_asgi()),
    re_path(r'ws/vrs-images/$', websocket_consumers.AriaRealTimeStreamConsumer.as_asgi()),
]