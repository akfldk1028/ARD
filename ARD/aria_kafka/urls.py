"""
Kafka Streaming API URLs - 체계적인 스트림별 URL 구조
"""

from django.urls import path, include
from .views.kafka_streaming_views import (
    ImageStreamView,
    ImageFrameView,
    SensorStreamView,
    StreamControlView,
    UnifiedStreamView,
    AdminView
)

app_name = 'kafka'

urlpatterns = [
    # ================== 이미지 스트림 API ==================
    # 개별 이미지 스트림 데이터 (JSON)
    path('api/v2/kafka-streams/images/<str:stream_name>/latest/', 
         ImageStreamView.as_view(), 
         {'action': 'latest'}, 
         name='image_stream_latest'),
    
    path('api/v2/kafka-streams/images/<str:stream_name>/recent/<int:count>/', 
         ImageStreamView.as_view(), 
         {'action': 'recent'}, 
         name='image_stream_recent'),
    
    # 이미지 프레임 직접 반환 (JPEG)
    path('api/v2/kafka-streams/images/<str:stream_name>/frame/', 
         ImageFrameView.as_view(), 
         name='image_frame_direct'),
    
    # ================== 센서 스트림 API ==================
    # 개별 센서 스트림 데이터
    path('api/v2/kafka-streams/sensors/<str:stream_name>/latest/', 
         SensorStreamView.as_view(), 
         {'action': 'latest'}, 
         name='sensor_stream_latest'),
    
    path('api/v2/kafka-streams/sensors/<str:stream_name>/recent/<int:count>/', 
         SensorStreamView.as_view(), 
         {'action': 'recent'}, 
         name='sensor_stream_recent'),
    
    # ================== 스트림 제어 API ==================
    # Producer 제어
    path('api/v2/kafka-streams/control/producer/start/<str:stream_name>/', 
         StreamControlView.as_view(), 
         {'action': 'start'}, 
         name='producer_start_stream'),
    
    path('api/v2/kafka-streams/control/producer/stop/<str:stream_name>/', 
         StreamControlView.as_view(), 
         {'action': 'stop'}, 
         name='producer_stop_stream'),
    
    path('api/v2/kafka-streams/control/producer/start-all/', 
         StreamControlView.as_view(), 
         {'action': 'start-all'}, 
         name='producer_start_all'),
    
    path('api/v2/kafka-streams/control/producer/stop-all/', 
         StreamControlView.as_view(), 
         {'action': 'stop-all'}, 
         name='producer_stop_all'),
    
    # ================== 통합 스트림 API ==================
    # 실시간 통합 데이터 (모든 스트림의 최신 데이터)
    path('api/v2/kafka-streams/unified/realtime/', 
         UnifiedStreamView.as_view(), 
         {'mode': 'realtime'}, 
         name='unified_realtime'),
    
    # 배치 통합 데이터 (최근 N개)
    path('api/v2/kafka-streams/unified/batch/', 
         UnifiedStreamView.as_view(), 
         {'mode': 'batch'}, 
         name='unified_batch'),
    
    # ================== 관리자 API ==================
    # 시스템 상태
    path('api/v2/kafka-streams/admin/status/', 
         AdminView.as_view(), 
         {'info_type': 'status'}, 
         name='admin_status'),
    
    # 시스템 통계
    path('api/v2/kafka-streams/admin/stats/', 
         AdminView.as_view(), 
         {'info_type': 'stats'}, 
         name='admin_stats'),
    
    # 헬스 체크
    path('api/v2/kafka-streams/admin/health/', 
         AdminView.as_view(), 
         {'info_type': 'health'}, 
         name='admin_health'),
    
    # 지원되는 스트림 목록
    path('api/v2/kafka-streams/admin/streams/', 
         AdminView.as_view(), 
         {'info_type': 'streams'}, 
         name='admin_streams'),
]

# =================== URL 패턴 설명 ===================
"""
지원되는 스트림 이름:

**이미지 스트림:**
- camera-rgb: RGB 카메라 (214-1)
- camera-slam-left: SLAM 좌측 카메라 (1201-1)
- camera-slam-right: SLAM 우측 카메라 (1201-2)  
- camera-eyetracking: 아이트래킹 카메라 (211-1)

**센서 스트림:**
- imu-right: 우측 IMU (1202-1)
- imu-left: 좌측 IMU (1202-2)
- magnetometer: 자력계 (1203-1)
- barometer: 기압계 (247-1)
- microphone: 마이크 (231-1)

**URL 사용 예시:**

# 이미지 스트림
GET /api/v2/kafka-streams/images/camera-rgb/latest/
GET /api/v2/kafka-streams/images/camera-slam-left/recent/10/
GET /api/v2/kafka-streams/images/camera-eyetracking/frame/

# 센서 스트림
GET /api/v2/kafka-streams/sensors/imu-right/latest/
GET /api/v2/kafka-streams/sensors/magnetometer/recent/5/

# 스트림 제어
POST /api/v2/kafka-streams/control/producer/start/camera-rgb/
    Body: {"fps": 10.0, "duration": 60}
POST /api/v2/kafka-streams/control/producer/stop/camera-rgb/
POST /api/v2/kafka-streams/control/producer/start-all/
    Body: {"fps": 5.0}

# 통합 데이터
GET /api/v2/kafka-streams/unified/realtime/
GET /api/v2/kafka-streams/unified/batch/?count=20

# 관리자
GET /api/v2/kafka-streams/admin/status/
GET /api/v2/kafka-streams/admin/health/
GET /api/v2/kafka-streams/admin/streams/
"""