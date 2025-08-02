from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import binary_views

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

# Binary API router
binary_router = DefaultRouter()
binary_router.register(r'registry', binary_views.BinaryFrameRegistryViewSet, basename='binary-registry')
binary_router.register(r'metadata', binary_views.BinaryFrameMetadataViewSet, basename='binary-metadata')

urlpatterns = [
    # === ARD Aria Streams API v1 ===
    
    # HTML API Root page (for browser users)
    path('home/', views.api_root_html, name='api-home'),
    
    # API Root with all endpoints
    path('', views.api_root, name='api-root'),
    
    # Core processed data endpoints (DRF ViewSets)  
    path('api/', include(router.urls)),
    
    # Raw data endpoints (사용자 정의 형식 지원)
    path('raw/', include('aria_streams.raw_urls')),
    
    # Binary data endpoints (DRF ViewSets) - moved to specific path
    path('binary/api/', include(binary_router.urls)),
    
    # Binary streaming endpoints (high-performance direct access)
    path('binary/data/<str:frame_id>/', binary_views.BinaryDataAccessView.as_view(), name='binary-data-access'),
    path('binary/streaming/', binary_views.BinaryStreamingControlView.as_view(), name='binary-streaming'),
    path('binary/test-message/', binary_views.BinaryTestMessageView.as_view(), name='binary-test'),
    path('binary/analytics/', binary_views.BinaryAnalyticsView.as_view(), name='binary-analytics'),
    
    # Simple image viewing (direct from Kafka)
    path('simple-image/', views.SimpleImageView.as_view(), name='simple-image'),
    path('simple-image/generate/', views.QuickImageGenerator.as_view(), name='quick-generate'),
    
    # Direct image viewing (최단 경로)
    path('direct-image/', views.DirectImageView.as_view(), name='direct-image'),
    
    # Image metadata and individual image viewing
    path('image-list/', views.ImageMetadataListView.as_view(), name='image-list'),
    path('image-by-id/<str:frame_id>/', views.ImageByIdView.as_view(), name='image-by-id'),
    
    # Original streaming control (Base64 legacy - for compatibility)
    path('streaming/', views.StreamingControlView.as_view(), name='streaming_control'),
    path('test-message/', views.TestMessageView.as_view(), name='test_message'),
    
    # Direct MPS import (Kafka bypass)
    path('import-mps/', views.DirectMPSImportView.as_view(), name='direct_mps_import'),
    
    # DRF browsing interface
    path('api-auth/', include('rest_framework.urls')),
    
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
]