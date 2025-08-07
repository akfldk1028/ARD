"""
XR Devices URL 설정
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# DRF 라우터 설정
router = DefaultRouter()
router.register(r'devices', views.XRDeviceViewSet, basename='xr-devices')

urlpatterns = [
    # REST API
    path('api/', include(router.urls)),
    
    # 통합 스트리밍 제어
    path('api/streaming/<str:action>/', views.UniversalStreamingControlView.as_view(), name='universal_streaming_control'),
    
    # 관리 대시보드
    path('dashboard/', views.XRDeviceManagementDashboard.as_view(), name='xr_device_dashboard'),
]