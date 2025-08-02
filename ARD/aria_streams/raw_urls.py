# ARD/aria_streams/raw_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import raw_views

app_name = 'raw'

# Raw 데이터 전용 Router 설정 (MPS 원본 데이터)
raw_router = DefaultRouter()
raw_router.register(r'eye-gaze', raw_views.RawEyeGazeViewSet, basename='raw-eye-gaze')
raw_router.register(r'hand-tracking', raw_views.RawHandTrackingViewSet, basename='raw-hand-tracking')
raw_router.register(r'slam-trajectory', raw_views.RawSlamTrajectoryViewSet, basename='raw-slam-trajectory')

urlpatterns = [
    # === MPS 원본 데이터 API ===
    
    # Core raw data endpoints (DRF ViewSets)
    path('', include(raw_router.urls)),
    
    # Raw 데이터 통합 통계
    path('statistics/', raw_views.RawDataStatsView.as_view(), name='raw-data-stats'),
]

"""
MPS 원본 데이터 API 엔드포인트 목록:

=== Eye Gaze 원본 데이터 ===
GET    /api/v1/aria/raw/eye-gaze/                     # Eye Gaze 원본 데이터 목록
GET    /api/v1/aria/raw/eye-gaze/{id}/                # Eye Gaze 원본 데이터 상세
GET    /api/v1/aria/raw/eye-gaze/summary/             # Eye Gaze 데이터 요약 통계
POST   /api/v1/aria/raw/eye-gaze/query/               # Eye Gaze 고급 쿼리

=== Hand Tracking 원본 데이터 ===
GET    /api/v1/aria/raw/hand-tracking/                # Hand Tracking 원본 데이터 목록
GET    /api/v1/aria/raw/hand-tracking/{id}/           # Hand Tracking 원본 데이터 상세
GET    /api/v1/aria/raw/hand-tracking/summary/        # Hand Tracking 데이터 요약 통계
POST   /api/v1/aria/raw/hand-tracking/query/          # Hand Tracking 고급 쿼리

=== SLAM Trajectory 원본 데이터 ===
GET    /api/v1/aria/raw/slam-trajectory/              # SLAM Trajectory 원본 데이터 목록
GET    /api/v1/aria/raw/slam-trajectory/{id}/         # SLAM Trajectory 원본 데이터 상세
GET    /api/v1/aria/raw/slam-trajectory/summary/      # SLAM Trajectory 데이터 요약 통계
POST   /api/v1/aria/raw/slam-trajectory/query/        # SLAM Trajectory 고급 쿼리
GET    /api/v1/aria/raw/slam-trajectory/trajectory_path/ # 전체 궤적 경로 데이터

=== 통합 통계 ===
GET    /api/v1/aria/raw/statistics/                   # 전체 Raw 데이터 통계

사용 예시:

1. Eye Gaze 원본 데이터 조회:
GET /api/v1/aria/raw/eye-gaze/
응답 예시:
{
  "id": "uuid",
  "tracking_timestamp_us": 1762509261,
  "left_yaw_rads_cpf": -0.047912582755088806,
  "right_yaw_rads_cpf": 0.0936531126499176,
  "pitch_rads_cpf": -0.21153444051742554,
  "depth_m": 0.4542842905544307,
  "tx_left_eye_cpf": 0.0315,
  "session_uid": "dfd2b9a5-a57b-41e1-989f-01a5d2059860",
  "data_source": "mps_general_eye_gaze"
}

2. Hand Tracking 원본 데이터 조회:
GET /api/v1/aria/raw/hand-tracking/
응답 예시:
{
  "id": "uuid",
  "tracking_timestamp_us": 1762609162,
  "left_tracking_confidence": 0.999297,
  "tx_left_landmark_0_device": 0.0645505,
  "ty_left_landmark_0_device": -0.248817,
  "tz_left_landmark_0_device": 0.250956,
  "tx_left_device_wrist": 0.187328,
  "qx_left_device_wrist": -0.184384,
  "data_source": "mps_hand_tracking"
}

3. SLAM Trajectory 원본 데이터 조회:
GET /api/v1/aria/raw/slam-trajectory/
응답 예시:
{
  "id": "uuid",
  "graph_uid": "31ebacab-fcac-b027-908f-880f29dc7b64",
  "tracking_timestamp_us": 1763475767,
  "tx_world_device": 0.962793,
  "ty_world_device": 0.596484,
  "tz_world_device": 0.031522,
  "qx_world_device": 0.575435558,
  "quality_score": 1.0,
  "geo_available": 0,
  "data_source": "mps_slam_trajectory"
}

4. 고급 쿼리 사용:
POST /api/v1/aria/raw/eye-gaze/query/
{
  "start_timestamp_us": 1762500000,
  "end_timestamp_us": 1762600000,
  "session_uid": "dfd2b9a5-a57b-41e1-989f-01a5d2059860",
  "limit": 50
}

5. 전체 궤적 경로 가져오기:
GET /api/v1/aria/raw/slam-trajectory/trajectory_path/
응답:
{
  "total_points": 100,
  "trajectory": [
    {
      "timestamp_us": 1763475767,
      "position": {"x": 0.962793, "y": 0.596484, "z": 0.031522},
      "quality_score": 1.0
    }
  ]
}

6. 전체 통계 조회:
GET /api/v1/aria/raw/statistics/
응답:
{
  "eye_gaze": {"total": 150, "unique_sessions": 1},
  "hand_tracking": {"total": 50},
  "slam_trajectory": {"total": 100, "unique_graphs": 1},
  "total_records": 300,
  "session_count": 1
}

필터링 및 검색:
- ?data_source=mps_general_eye_gaze
- ?session_uid=dfd2b9a5-a57b-41e1-989f-01a5d2059860
- ?graph_uid=31ebacab-fcac-b027-908f-880f29dc7b64
- ?ordering=tracking_timestamp_us
- ?search=dfd2b9a5

페이지네이션:
- ?page=1&page_size=20
"""