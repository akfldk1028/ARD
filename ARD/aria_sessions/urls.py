"""
URLs for working Aria streaming components
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Working streaming components (moved to working_streaming folder)
from .working_streaming.concurrent_streaming_views import (
    ConcurrentStreamingControlView,
    ConcurrentLatestFrameView, 
    ConcurrentMultiFrameView,
    ConcurrentStreamingPageView
)
from .working_streaming.concurrent_sensor_streaming import (
    ConcurrentSensorControlView,
    ConcurrentSensorDataView,
    ConcurrentSensorPageView
)
from .working_streaming.main_dashboard import MainDashboardView

# Main router for core ViewSets
router = DefaultRouter()
router.register(r'sessions', views.AriaStreamingSessionViewSet)

urlpatterns = [
    # Test endpoint
    path('test/', views.test_view, name='test'),
    
    # 🏆 메인 대시보드 (통합 페이지)
    path('main-dashboard/', MainDashboardView.as_view(), name='main_dashboard'),
    
    # 🔥 동시 4카메라 스트리밍 (공식 Observer 패턴)
    path('concurrent-streaming/<str:action>/', ConcurrentStreamingControlView.as_view(), name='concurrent_streaming_control'),
    path('concurrent-latest-frame/', ConcurrentLatestFrameView.as_view(), name='concurrent_latest_frame'),
    path('concurrent-multi-frames/', ConcurrentMultiFrameView.as_view(), name='concurrent_multi_frames'),
    path('concurrent-streaming-page/', ConcurrentStreamingPageView.as_view(), name='concurrent_streaming_page'),
    
    # 🧭 동시 센서 스트리밍 (공식 Observer 패턴)
    path('concurrent-sensor/<str:action>/', ConcurrentSensorControlView.as_view(), name='concurrent_sensor_control'),
    path('concurrent-sensor-data/', ConcurrentSensorDataView.as_view(), name='concurrent_sensor_data'),
    path('concurrent-sensor-page/', ConcurrentSensorPageView.as_view(), name='concurrent_sensor_page'),
    
    # Core ViewSets
    path('', include(router.urls)),
]