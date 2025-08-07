"""
XR Devices Django Admin 설정
"""

from django.contrib import admin
from .models import (
    XRDevice, DeviceSensorCapability, DataParser, 
    StreamingSession, StreamingData,
    AriaSpecificData, GoogleGlassSpecificData, AppleVisionSpecificData
)


@admin.register(XRDevice)
class XRDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'device_type', 'manufacturer', 'model_version', 'preferred_protocol', 'is_active']
    list_filter = ['device_type', 'manufacturer', 'preferred_protocol', 'is_active']
    search_fields = ['name', 'manufacturer', 'model_version']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'device_type', 'manufacturer', 'model_version')
        }),
        ('기술 사양', {
            'fields': ('supported_formats', 'preferred_protocol', 'device_config')
        }),
        ('상태', {
            'fields': ('is_active',)
        }),
        ('메타데이터', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DeviceSensorCapability)
class DeviceSensorCapabilityAdmin(admin.ModelAdmin):
    list_display = ['device', 'sensor_type', 'resolution', 'frequency_hz', 'is_enabled']
    list_filter = ['device__device_type', 'sensor_type', 'is_enabled']
    search_fields = ['device__name', 'sensor_type']


@admin.register(DataParser)
class DataParserAdmin(admin.ModelAdmin):
    list_display = ['device_type', 'data_format', 'parser_class', 'parser_version', 'is_active']
    list_filter = ['device_type', 'data_format', 'is_active']
    search_fields = ['parser_class']


@admin.register(StreamingSession)
class StreamingSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'device', 'user_id', 'status', 'start_time', 'total_frames_processed']
    list_filter = ['status', 'device__device_type', 'streaming_protocol']
    search_fields = ['session_id', 'user_id', 'session_name']
    readonly_fields = ['start_time', 'end_time']
    
    fieldsets = (
        ('세션 정보', {
            'fields': ('session_id', 'device', 'user_id', 'session_name')
        }),
        ('스트리밍 설정', {
            'fields': ('streaming_protocol', 'data_format', 'active_sensors')
        }),
        ('상태 및 통계', {
            'fields': ('status', 'total_frames_processed', 'total_data_size_mb')
        }),
        ('시간 정보', {
            'fields': ('start_time', 'end_time'),
            'classes': ('collapse',)
        })
    )


@admin.register(StreamingData)
class StreamingDataAdmin(admin.ModelAdmin):
    list_display = ['session', 'sensor_type', 'frame_number', 'data_size_bytes', 'created_at']
    list_filter = ['sensor_type', 'data_format', 'session__device__device_type']
    search_fields = ['session__session_id']
    readonly_fields = ['created_at', 'data_size_bytes']
    
    # 대용량 데이터를 위한 페이지네이션
    list_per_page = 50
    
    def has_change_permission(self, request, obj=None):
        # 스트리밍 데이터는 읽기 전용으로 처리
        return False


# 기기별 특화 데이터 모델들
@admin.register(AriaSpecificData)
class AriaSpecificDataAdmin(admin.ModelAdmin):
    list_display = ['vrs_file_path', 'stream_id', 'eye_gaze_confidence', 'hand_tracking_presence']
    search_fields = ['vrs_file_path', 'stream_id']


@admin.register(GoogleGlassSpecificData)
class GoogleGlassSpecificDataAdmin(admin.ModelAdmin):
    list_display = ['glass_model', 'android_version']
    search_fields = ['glass_model']


@admin.register(AppleVisionSpecificData)
class AppleVisionSpecificDataAdmin(admin.ModelAdmin):
    list_display = ['vision_os_version']
    search_fields = ['vision_os_version']