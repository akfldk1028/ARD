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
from direct_image_view import DirectImageView, VRSImageView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 직접 이미지 보기 - 가장 간단한 방법
    path('image/', DirectImageView.as_view(), name='direct-image'),
    path('vrs-image/', VRSImageView.as_view(), name='vrs-image'),
    
    # API v1 endpoints
    path('api/v1/aria/', include('aria_streams.urls')),
    path('api/v1/webcam/', include('webcam_streams.urls')),
    path('api/v1/smartwatch/', include('smartwatch_streams.urls')),
    
    # Deprecated - redirect to v1
    path('api/aria/', include('aria_streams.urls')),
]
