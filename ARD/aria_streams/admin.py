from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from .models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData,
    SLAMPointCloud, AnalyticsResult, KafkaConsumerStatus,
    IMUData
)


@admin.register(AriaSession)
class AriaSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'device_serial', 'status', 'started_at', 
        'duration_display', 'data_counts_display', 'actions_display'
    ]
    list_filter = ['status', 'device_serial', 'started_at']
    search_fields = ['session_id', 'device_serial', 'session_uid']
    readonly_fields = ['session_uid', 'started_at', 'data_summary_display']
    fieldsets = (
        ('기본 정보', {
            'fields': ('session_id', 'session_uid', 'device_serial', 'status')
        }),
        ('시간 정보', {
            'fields': ('started_at', 'ended_at')
        }),
        ('메타데이터', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('데이터 요약', {
            'fields': ('data_summary_display',),
            'classes': ('collapse',)
        })
    )
    actions = ['end_selected_sessions']
    
    def duration_display(self, obj):
        """세션 지속 시간 표시"""
        end_time = obj.ended_at or timezone.now()
        duration = end_time - obj.started_at
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    duration_display.short_description = '지속 시간'
    
    def data_counts_display(self, obj):
        """데이터 수 요약 표시"""
        counts = {
            'VRS': obj.vrs_streams.count(),
            'IMU': obj.imu_data.count(),
            'Eye': obj.eye_gaze_data.count(),
            'Hand': obj.hand_tracking_data.count(),
            'SLAM': obj.slam_trajectory_data.count()
        }
        return format_html(
            '<div style="font-size: 11px;">'
            'VRS: <b>{}</b> | IMU: <b>{}</b><br>'
            'Eye: <b>{}</b> | Hand: <b>{}</b> | SLAM: <b>{}</b>'
            '</div>',
            counts['VRS'], counts['IMU'], counts['Eye'], counts['Hand'], counts['SLAM']
        )
    data_counts_display.short_description = '데이터 수'
    
    def actions_display(self, obj):
        """액션 링크 표시"""
        if obj.pk:
            return format_html(
                '<a href="{}" class="button">상세 보기</a>',
                reverse('admin:streams_ariasession_change', args=[obj.pk])
            )
        return '-'
    actions_display.short_description = '액션'
    
    def data_summary_display(self, obj):
        """데이터 상세 요약"""
        if not obj.pk:
            return "세션을 저장한 후 데이터 요약을 확인할 수 있습니다."
        
        vrs_streams = obj.vrs_streams.values('stream_name').annotate(count=Count('id'))
        gaze_types = obj.eye_gaze_data.values('gaze_type').annotate(count=Count('id'))
        
        summary_html = '<div style="font-family: monospace; font-size: 12px;">'
        summary_html += '<h4>VRS 스트림:</h4><ul>'
        for stream in vrs_streams:
            summary_html += f'<li>{stream["stream_name"]}: {stream["count"]}개</li>'
        summary_html += '</ul><h4>Eye Gaze:</h4><ul>'
        for gaze in gaze_types:
            summary_html += f'<li>{gaze["gaze_type"]}: {gaze["count"]}개</li>'
        summary_html += '</ul></div>'
        
        return format_html(summary_html)
    data_summary_display.short_description = '데이터 상세 요약'
    
    def end_selected_sessions(self, request, queryset):
        """선택된 세션들 종료"""
        count = 0
        for session in queryset.filter(status='ACTIVE'):
            session.ended_at = timezone.now()
            session.status = 'COMPLETED'
            session.save()
            count += 1
        
        self.message_user(request, f'{count}개의 세션이 종료되었습니다.')
    end_selected_sessions.short_description = '선택된 세션 종료'


@admin.register(VRSStream)
class VRSStreamAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'stream_name', 'frame_index', 
        'timestamp', 'image_info_display', 'kafka_offset'
    ]
    list_filter = ['stream_name', 'pixel_format', 'timestamp']
    search_fields = ['session__session_id', 'stream_name', 'stream_id']
    readonly_fields = ['timestamp', 'image_info_display']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        """세션 링크"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'
    
    def image_info_display(self, obj):
        """이미지 정보 표시"""
        if obj.image_shape:
            shape_str = ' × '.join(map(str, obj.image_shape))
            return f"{shape_str} ({obj.pixel_format})"
        return f"({obj.pixel_format})"
    image_info_display.short_description = '이미지 정보'


@admin.register(EyeGazeData)
class EyeGazeDataAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'gaze_type', 'yaw', 'pitch', 
        'depth_m', 'confidence', 'timestamp'
    ]
    list_filter = ['gaze_type', 'timestamp']
    search_fields = ['session__session_id']
    readonly_fields = ['timestamp', 'gaze_direction_display']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'
    
    def gaze_direction_display(self, obj):
        """시선 방향 시각화"""
        import math
        yaw_rad = math.radians(obj.yaw)
        pitch_rad = math.radians(obj.pitch)
        
        x = math.cos(pitch_rad) * math.sin(yaw_rad)
        y = math.sin(pitch_rad)
        z = math.cos(pitch_rad) * math.cos(yaw_rad)
        
        return format_html(
            '<div style="font-family: monospace;">'
            'Direction Vector:<br>'
            'X: {:.3f}<br>'
            'Y: {:.3f}<br>'
            'Z: {:.3f}<br>'
            'Magnitude: {:.3f}'
            '</div>',
            x, y, z, math.sqrt(x*x + y*y + z*z)
        )
    gaze_direction_display.short_description = '방향 벡터'


@admin.register(HandTrackingData)
class HandTrackingDataAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'timestamp', 'hands_detected_display', 
        'landmarks_count_display'
    ]
    list_filter = ['timestamp']
    search_fields = ['session__session_id']
    readonly_fields = ['timestamp', 'hand_summary_display']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'
    
    def hands_detected_display(self, obj):
        """감지된 손 표시"""
        left = '✓' if obj.left_hand_landmarks else '✗'
        right = '✓' if obj.right_hand_landmarks else '✗'
        return format_html(
            '<span style="color: {};">L: {}</span> | '
            '<span style="color: {};">R: {}</span>',
            'green' if obj.left_hand_landmarks else 'red', left,
            'green' if obj.right_hand_landmarks else 'red', right
        )
    hands_detected_display.short_description = '손 감지'
    
    def landmarks_count_display(self, obj):
        """랜드마크 수 표시"""
        left_count = len(obj.left_hand_landmarks) if obj.left_hand_landmarks else 0
        right_count = len(obj.right_hand_landmarks) if obj.right_hand_landmarks else 0
        return f"L: {left_count} | R: {right_count}"
    landmarks_count_display.short_description = '랜드마크 수'
    
    def hand_summary_display(self, obj):
        """손 정보 요약"""
        summary = '<div style="font-family: monospace; font-size: 12px;">'
        
        if obj.left_hand_landmarks:
            summary += f'<h4>왼손: {len(obj.left_hand_landmarks)}개 랜드마크</h4>'
            if obj.left_hand_wrist_normal:
                summary += f'손목 노멀: {obj.left_hand_wrist_normal}<br>'
            if obj.left_hand_palm_normal:
                summary += f'손바닥 노멀: {obj.left_hand_palm_normal}<br>'
        
        if obj.right_hand_landmarks:
            summary += f'<h4>오른손: {len(obj.right_hand_landmarks)}개 랜드마크</h4>'
            if obj.right_hand_wrist_normal:
                summary += f'손목 노멀: {obj.right_hand_wrist_normal}<br>'
            if obj.right_hand_palm_normal:
                summary += f'손바닥 노멀: {obj.right_hand_palm_normal}<br>'
        
        summary += '</div>'
        return format_html(summary)
    hand_summary_display.short_description = '손 정보 요약'


@admin.register(SLAMTrajectoryData)
class SLAMTrajectoryDataAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'timestamp', 'position_display', 'kafka_offset'
    ]
    list_filter = ['timestamp']
    search_fields = ['session__session_id']
    readonly_fields = ['timestamp', 'position_x', 'position_y', 'position_z', 'transform_display']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'
    
    def position_display(self, obj):
        """위치 정보 표시"""
        return format_html(
            '<div style="font-family: monospace; font-size: 11px;">'
            'X: {:.3f}<br>Y: {:.3f}<br>Z: {:.3f}'
            '</div>',
            obj.position_x, obj.position_y, obj.position_z
        )
    position_display.short_description = '위치'
    
    def transform_display(self, obj):
        """변환 행렬 표시"""
        if obj.transform_matrix:
            matrix_html = '<table style="font-family: monospace; font-size: 10px; border-collapse: collapse;">'
            for row in obj.transform_matrix:
                matrix_html += '<tr>'
                for cell in row:
                    matrix_html += f'<td style="border: 1px solid #ccc; padding: 2px; text-align: right;">{cell:.3f}</td>'
                matrix_html += '</tr>'
            matrix_html += '</table>'
            return format_html(matrix_html)
        return "변환 행렬 없음"
    transform_display.short_description = '변환 행렬'


@admin.register(KafkaConsumerStatus)
class KafkaConsumerStatusAdmin(admin.ModelAdmin):
    list_display = [
        'consumer_group', 'topic', 'partition', 'last_offset', 
        'status_display', 'last_processed_ago', 'last_processed_at'
    ]
    list_filter = ['status', 'consumer_group', 'topic']
    search_fields = ['consumer_group', 'topic']
    readonly_fields = ['last_processed_at', 'last_processed_ago_display']
    
    def status_display(self, obj):
        """상태 색상 표시"""
        colors = {
            'ACTIVE': 'green',
            'PAUSED': 'orange', 
            'ERROR': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.status
        )
    status_display.short_description = '상태'
    
    def last_processed_ago(self, obj):
        """마지막 처리 후 경과 시간"""
        if obj.last_processed_at:
            diff = timezone.now() - obj.last_processed_at
            seconds = diff.total_seconds()
            if seconds < 60:
                return f"{int(seconds)}초 전"
            elif seconds < 3600:
                return f"{int(seconds/60)}분 전"
            else:
                return f"{int(seconds/3600)}시간 전"
        return "없음"
    last_processed_ago.short_description = '마지막 처리'
    
    def last_processed_ago_display(self, obj):
        """상세 경과 시간 표시"""
        return self.last_processed_ago(obj)
    last_processed_ago_display.short_description = '마지막 처리 후 경과시간'


@admin.register(SLAMPointCloud)
class SLAMPointCloudAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_link', 'timestamp', 'point_count', 'kafka_offset']
    list_filter = ['timestamp', 'point_count']
    search_fields = ['session__session_id']
    readonly_fields = ['timestamp', 'point_count']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'


@admin.register(AnalyticsResult)
class AnalyticsResultAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'analysis_type', 'confidence_score', 
        'timestamp', 'kafka_offset'
    ]
    list_filter = ['analysis_type', 'timestamp', 'confidence_score']
    search_fields = ['session__session_id', 'analysis_type']
    readonly_fields = ['timestamp']
    raw_id_fields = ['session']
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'


@admin.register(IMUData)
class IMUDataAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_link', 'imu_type', 'timestamp', 
        'acceleration_display', 'gyroscope_display', 'temperature_c', 'kafka_offset'
    ]
    list_filter = ['imu_type', 'timestamp', 'imu_stream_id']
    search_fields = ['session__session_id', 'imu_type', 'imu_stream_id']
    readonly_fields = ['timestamp', 'acceleration_magnitude', 'angular_velocity_magnitude']
    raw_id_fields = ['session']
    fieldsets = (
        ('기본 정보', {
            'fields': ('session', 'device_timestamp_ns', 'imu_stream_id', 'imu_type')
        }),
        ('가속도계 (m/s²)', {
            'fields': ('accel_x', 'accel_y', 'accel_z', 'acceleration_magnitude'),
            'classes': ('wide',)
        }),
        ('자이로스코프 (rad/s)', {
            'fields': ('gyro_x', 'gyro_y', 'gyro_z', 'angular_velocity_magnitude'),
            'classes': ('wide',)
        }),
        ('기타', {
            'fields': ('temperature_c', 'kafka_offset', 'timestamp'),
            'classes': ('collapse',)
        })
    )
    
    def session_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:streams_ariasession_change', args=[obj.session.pk]),
            obj.session.session_id
        )
    session_link.short_description = '세션'
    
    def acceleration_display(self, obj):
        """가속도 벡터 시각적 표시"""
        import math
        magnitude = math.sqrt(obj.accel_x**2 + obj.accel_y**2 + obj.accel_z**2)
        return format_html(
            '<div style="font-size: 11px;">'
            'X: <b>{:.3f}</b><br>'
            'Y: <b>{:.3f}</b><br>'
            'Z: <b>{:.3f}</b><br>'
            '|a|: <b>{:.3f}</b> m/s²'
            '</div>',
            obj.accel_x, obj.accel_y, obj.accel_z, magnitude
        )
    acceleration_display.short_description = '가속도'
    
    def gyroscope_display(self, obj):
        """자이로스코프 벡터 시각적 표시"""
        import math
        magnitude = math.sqrt(obj.gyro_x**2 + obj.gyro_y**2 + obj.gyro_z**2)
        return format_html(
            '<div style="font-size: 11px;">'
            'X: <b>{:.3f}</b><br>'
            'Y: <b>{:.3f}</b><br>'
            'Z: <b>{:.3f}</b><br>'
            '|ω|: <b>{:.3f}</b> rad/s'
            '</div>',
            obj.gyro_x, obj.gyro_y, obj.gyro_z, magnitude
        )
    gyroscope_display.short_description = '자이로스코프'
    
    def acceleration_magnitude(self, obj):
        """가속도 벡터 크기"""
        import math
        return round(math.sqrt(obj.accel_x**2 + obj.accel_y**2 + obj.accel_z**2), 4)
    acceleration_magnitude.short_description = '가속도 크기 (m/s²)'
    
    def angular_velocity_magnitude(self, obj):
        """각속도 벡터 크기"""
        import math
        return round(math.sqrt(obj.gyro_x**2 + obj.gyro_y**2 + obj.gyro_z**2), 4)
    angular_velocity_magnitude.short_description = '각속도 크기 (rad/s)'


# Admin 사이트 커스터마이징
admin.site.site_header = "ARD - Aria Real-time Data 관리"
admin.site.site_title = "ARD Admin"
admin.site.index_title = "ARD 데이터 관리 시스템"
