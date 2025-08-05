from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .simple_views import SimpleAriaSessionViewSet
from .general_views import (
    streaming_test_page, 
    general_streaming_sensor,
    general_unified_stream_realtime,
    general_streaming_frame
)

# 원래 복잡한 router (문제 있음)
router = DefaultRouter()
router.register(r'sessions', views.AriaStreamingSessionViewSet)
router.register(r'unified-data', views.UnifiedSensorDataViewSet)

# 간단한 테스트 router
simple_router = DefaultRouter()
simple_router.register(r'simple', SimpleAriaSessionViewSet)

urlpatterns = [
    path('test/', views.test_view, name='test'),  # 테스트 URL
    
    # 일반 스트리밍 페이지 및 API (세션 자동 선택)
    path('streaming-test/', streaming_test_page, name='streaming_test'),  # 메인 테스트 페이지
    path('streaming-sensor/', general_streaming_sensor, name='general_streaming_sensor'),  # 센서 데이터 API
    path('unified-stream-realtime/', general_unified_stream_realtime, name='general_unified_stream'),  # 통합 스트리밍 API  
    path('streaming-frame/', general_streaming_frame, name='general_streaming_frame'),  # 이미지 프레임 API
    
    path('', include(simple_router.urls)),  # 간단한 ViewSet (세션별)
    # path('', include(router.urls)),  # 복잡한 ViewSet은 일단 비활성화
]