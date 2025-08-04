from django.urls import path
from .simple_image_view import SimpleImageView, QuickImageGenerator

urlpatterns = [
    path('', SimpleImageView.as_view(), name='simple-image'),
    path('generate/', QuickImageGenerator.as_view(), name='quick-generate'),
]