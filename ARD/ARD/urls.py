"""
URL configuration for ARD project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API v1 endpoints
    path('api/v1/aria-sessions/', include('aria_sessions.urls')),  # 통합 스트리밍 메인
    
    # Universal XR Devices - 다중 기기 지원 시스템 🚀
    path('api/xr-devices/', include('xr_devices.urls')),  # 통합 XR 기기 관리 (devices, aria_kafka 대체)
    
    # DRF browsable API
    path('api-auth/', include('rest_framework.urls')),
]
