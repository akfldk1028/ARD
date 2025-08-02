from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'smartwatch_streams'

# DRF Router 설정
router = DefaultRouter()
router.register(r'sessions', views.SmartwatchSessionViewSet)
router.register(r'sensor-data', views.SensorDataViewSet)
router.register(r'health-metrics', views.HealthMetricsViewSet)

urlpatterns = [
    # DRF ViewSet URLs
    path('api/', include(router.urls)),
    
    # 스트리밍 제어
    path('api/streaming/', views.StreamingControlView.as_view(), name='streaming_control'),
    
    # 테스트 메시지 전송
    path('api/test-message/', views.TestMessageView.as_view(), name='test_message'),
    
    # DRF 브라우징 인터페이스
    path('api-auth/', include('rest_framework.urls')),
]