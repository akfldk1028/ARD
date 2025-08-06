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
from .kafka_streaming_views import VRSKafkaStreamingViewSet, streaming_test_endpoint, kafka_topics_info
from .fast_streaming_views import fast_streaming_frame, fast_unified_stream_realtime, fast_streaming_sensor, streaming_performance_monitor, start_background_streaming, debug_cache_keys, test_meta_direct_vrs
from .simple_fast_api import simple_fast_unified_stream
from .optimized_streaming import start_optimized_streaming, stop_optimized_streaming, optimized_unified_stream, optimized_single_frame
from .memory_cached_streaming import preload_vrs_to_memory, memory_cached_unified_stream, memory_cached_single_frame, memory_cache_status, memory_cached_sensor_stream, reset_memory_cache_api
from .simple_memory_cache import load_simple_cache, simple_cache_stream, simple_cache_frame

# 원래 복잡한 router (문제 있음)
router = DefaultRouter()
router.register(r'sessions', views.AriaStreamingSessionViewSet)
router.register(r'unified-data', views.UnifiedSensorDataViewSet)

# 간단한 테스트 router
simple_router = DefaultRouter()
simple_router.register(r'simple', SimpleAriaSessionViewSet)

# VRS Kafka 스트리밍 router
kafka_router = DefaultRouter()
kafka_router.register(r'sessions', VRSKafkaStreamingViewSet)

urlpatterns = [
    path('test/', views.test_view, name='test'),  # 테스트 URL
    
    # 기존 HTML 템플릿 페이지 (원래 기능 복구)
    path('streaming-test/', streaming_test_page, name='streaming_test'),  # 메인 HTML 테스트 페이지
    
    # VRS Kafka 스트리밍 API 엔드포인트  
    path('kafka-streaming-test/', streaming_test_endpoint, name='kafka_streaming_test'),  # Kafka API 테스트
    path('kafka-topics/', kafka_topics_info, name='kafka_topics_info'),  # Kafka 토픽 정보
    
    # 🚀 빠른 스트리밍 API (Kafka 캐시 기반 - 10-100배 빠름)
    path('fast-streaming-frame/', fast_streaming_frame, name='fast_streaming_frame'),  # 빠른 이미지 프레임
    path('fast-unified-stream/', fast_unified_stream_realtime, name='fast_unified_stream'),  # 빠른 통합 스트리밍
    path('fast-streaming-sensor/', fast_streaming_sensor, name='fast_streaming_sensor'),  # 빠른 센서 데이터
    path('streaming-performance/', streaming_performance_monitor, name='streaming_performance'),  # 성능 모니터
    path('start-background-streaming/', start_background_streaming, name='start_background_streaming'),  # 백그라운드 시작
    path('debug-cache-keys/', debug_cache_keys, name='debug_cache_keys'),  # 캐시 키 디버깅
    path('test-meta-direct/', test_meta_direct_vrs, name='test_meta_direct'),  # Meta 공식 VRS 테스트
    path('simple-fast-stream/', simple_fast_unified_stream, name='simple_fast_stream'),  # 간단한 빠른 API
    
    # 🚀 최적화된 동시 스트리밍 (Observer + Queue + 멀티스레드)
    path('start-optimized-streaming/', start_optimized_streaming, name='start_optimized_streaming'),  # 최적화된 스트리밍 시작
    path('stop-optimized-streaming/', stop_optimized_streaming, name='stop_optimized_streaming'),  # 최적화된 스트리밍 중지
    path('optimized-unified-stream/', optimized_unified_stream, name='optimized_unified_stream'),  # 최적화된 통합 API
    path('optimized-single-frame/', optimized_single_frame, name='optimized_single_frame'),  # 최적화된 단일 프레임
    
    # 🏆 메모리 캐시 스트리밍 (Meta 공식 패턴 - 한번 로드, 좌르르륽 스트리밍)
    path('preload-vrs-to-memory/', preload_vrs_to_memory, name='preload_vrs_to_memory'),  # VRS 전체 메모리 로드
    path('memory-cached-stream/', memory_cached_unified_stream, name='memory_cached_stream'),  # 메모리 캐시 통합 스트리밍
    path('memory-cached-frame/', memory_cached_single_frame, name='memory_cached_frame'),  # 메모리 캐시 단일 프레임
    path('memory-cached-sensors/', memory_cached_sensor_stream, name='memory_cached_sensors'),  # 메모리 캐시 센서 데이터
    path('memory-cache-status/', memory_cache_status, name='memory_cache_status'),  # 메모리 캐시 상태
    path('reset-memory-cache/', reset_memory_cache_api, name='reset_memory_cache'),  # 메모리 캐시 리셋
    
    # 간단한 메모리 캐시 (문제 해결용)
    path('load-simple-cache/', load_simple_cache, name='load_simple_cache'),
    path('simple-cache-stream/', simple_cache_stream, name='simple_cache_stream'),
    path('simple-cache-frame/', simple_cache_frame, name='simple_cache_frame'),
    
    # 기존 스트리밍 API (디스크 기반 - 호환성용)
    path('streaming-sensor/', general_streaming_sensor, name='general_streaming_sensor'),  # 센서 데이터 API
    path('unified-stream-realtime/', general_unified_stream_realtime, name='general_unified_stream'),  # 통합 스트리밍 API  
    path('streaming-frame/', general_streaming_frame, name='general_streaming_frame'),  # 이미지 프레임 API
    
    # ViewSet 라우터들
    path('kafka/', include(kafka_router.urls)),  # VRS Kafka 스트리밍 ViewSet
    path('simple/', include(simple_router.urls)),  # 간단한 ViewSet (세션별)
    # path('', include(router.urls)),  # 복잡한 ViewSet은 일단 비활성화
]