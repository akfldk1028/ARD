from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WebcamSessionViewSet, WebcamFrameViewSet, WebcamAnalysisViewSet

router = DefaultRouter()
router.register(r'sessions', WebcamSessionViewSet)
router.register(r'frames', WebcamFrameViewSet)
router.register(r'analysis', WebcamAnalysisViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]