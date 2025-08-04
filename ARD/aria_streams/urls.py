from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import real_time_stream_view
from . import clean_vrs_kafka
from . import kafka_device_stream

try:
    from . import unity_views
    UNITY_VIEWS_AVAILABLE = True
except ImportError:
    UNITY_VIEWS_AVAILABLE = False

app_name = 'streams'

# DRF Router 설정 (클래스 기반 API)
router = DefaultRouter()
router.register(r'sessions', views.AriaSessionViewSet)
router.register(r'vrs-streams', views.VRSStreamViewSet)
router.register(r'imu-data', views.IMUDataViewSet)
router.register(r'eye-gaze', views.EyeGazeDataViewSet)
router.register(r'hand-tracking', views.HandTrackingDataViewSet)
router.register(r'slam-trajectory', views.SLAMTrajectoryDataViewSet)
router.register(r'kafka-status', views.KafkaConsumerStatusViewSet)

urlpatterns = [
    # === ARD Aria Streams API v1 ===
    
    # HTML API Root page (for browser users)
    path('home/', views.api_root_html, name='api-home'),
    
    # API Root with all endpoints
    path('', views.api_root, name='api-root'),
    
    # Core processed data endpoints (DRF ViewSets)  
    path('api/', include(router.urls)),
    
    # Raw data endpoints moved to deprecated - using clean pipeline
    # path('raw/', include('aria_streams.raw_urls')),
    
    # Unity Integration APIs (WebSocket-based - see routing.py for ws:// endpoints)
    # NEW: Use WebSocket for real-time streaming: ws://localhost:8000/ws/unity/stream/{session_id}/
]

# Unity Views가 있을 때만 추가
if UNITY_VIEWS_AVAILABLE:
    urlpatterns.extend([
        path('unity/websocket-info/', unity_views.UnityWebSocketInfoView.as_view(), name='unity-websocket-info'),
        path('unity/example/', unity_views.UnityExampleView.as_view(), name='unity-example'),
        
        # Legacy REST APIs (for compatibility)
        path('unity/latest-frame/', unity_views.UnityLatestFrameView.as_view(), name='unity-latest-frame'),
        path('unity/status/', unity_views.UnityStreamingStatusView.as_view(), name='unity-status'),
    ])

# 나머지 URL patterns
urlpatterns.extend([
    
    # Simple image viewing (direct from Kafka)
    path('simple-image/', views.SimpleImageView.as_view(), name='simple-image'),
    path('simple-image/generate/', views.QuickImageGenerator.as_view(), name='quick-generate'),
    
    # Direct image viewing (최단 경로)
    path('direct-image/', views.DirectImageView.as_view(), name='direct-image'),
    
    # Live streaming viewer with replay control (deprecated)
    # path('live-stream/', live_stream_view.LiveStreamView.as_view(), name='live-stream'),
    
    # Project Aria 공식 Device Stream API 기반 실시간 스트리밍
    path('device-stream/', real_time_stream_view.RealTimeStreamView.as_view(), name='device-stream'),
    path('device-stream/latest-frame/', real_time_stream_view.LatestFrameView.as_view(), name='latest-frame'),
    path('device-stream/<str:action>/', real_time_stream_view.DeviceStreamControlView.as_view(), name='device-stream-control'),
    
    # 깔끔한 VRS → Kafka → API 파이프라인  
    path('clean-kafka/<str:action>/', clean_vrs_kafka.CleanKafkaStreamAPI.as_view(), name='clean-kafka-control'),
    path('clean-kafka/latest-frame/', clean_vrs_kafka.CleanKafkaFrameAPI.as_view(), name='clean-kafka-frame'),
    
    # Project Aria 공식 Device Stream API + Kafka 통합
    path('kafka-device-stream/<str:action>/', kafka_device_stream.KafkaDeviceStreamControlView.as_view(), name='kafka-device-stream-control'),
    path('kafka-device-stream/latest-frame/', kafka_device_stream.KafkaLatestFrameView.as_view(), name='kafka-device-stream-frame'),
    
    # Image metadata and individual image viewing
    path('image-list/', views.ImageMetadataListView.as_view(), name='image-list'),
    path('image-by-id/<str:frame_id>/', views.ImageByIdView.as_view(), name='image-by-id'),
    
    # Original streaming control (Base64 legacy - for compatibility)
    path('streaming/', views.StreamingControlView.as_view(), name='streaming_control'),
    path('test-message/', views.TestMessageView.as_view(), name='test_message'),
    
    # Direct MPS import (Kafka bypass)
    path('import-mps/', views.DirectMPSImportView.as_view(), name='direct_mps_import'),
    
    
    # === Legacy 함수 기반 API (사용 중단 예정) ===
    # NOTE: 새로운 개발은 /api/ 경로의 클래스 기반 API를 사용하세요
    # 아래 함수 기반 API는 하위 호환성을 위해서만 유지됩니다
    
    # Legacy streaming endpoints - 대신 /api/streaming/ 사용 권장
    # path('status/', views_old_function_based.streaming_status_view, name='streaming_status_legacy'),
    # path('start/', views_old_function_based.start_vrs_streaming, name='start_vrs_streaming_legacy'),
    # path('stop/', views_old_function_based.stop_streaming, name='stop_streaming_legacy'),
    # path('eye-gaze/', views_old_function_based.stream_eye_gaze_data, name='stream_eye_gaze_legacy'),
    # path('hand-tracking/', views_old_function_based.stream_hand_tracking_data, name='stream_hand_tracking_legacy'),
    # path('test/', views_old_function_based.send_test_message, name='send_test_message_legacy'),
])