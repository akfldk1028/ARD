# ARD/aria_streams/raw_models.py

from django.db import models
from .models import AriaSession
import uuid


class RawEyeGazeData(models.Model):
    """
    MPS Eye Gaze 원본 데이터 (general_eye_gaze.csv 필드 구조)
    정제되지 않은 원본 필드들을 모두 포함
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='raw_eye_gaze')
    
    # 원본 CSV 필드들 (Meta Project Aria MPS 원본)
    tracking_timestamp_us = models.BigIntegerField()
    left_yaw_rads_cpf = models.FloatField()
    right_yaw_rads_cpf = models.FloatField()
    pitch_rads_cpf = models.FloatField()
    depth_m = models.FloatField()
    left_yaw_low_rads_cpf = models.FloatField()
    right_yaw_low_rads_cpf = models.FloatField()
    pitch_low_rads_cpf = models.FloatField()
    left_yaw_high_rads_cpf = models.FloatField()
    right_yaw_high_rads_cpf = models.FloatField()
    pitch_high_rads_cpf = models.FloatField()
    tx_left_eye_cpf = models.FloatField()
    ty_left_eye_cpf = models.FloatField()
    tz_left_eye_cpf = models.FloatField()
    tx_right_eye_cpf = models.FloatField()
    ty_right_eye_cpf = models.FloatField()
    tz_right_eye_cpf = models.FloatField()
    session_uid = models.CharField(max_length=100)
    
    # 메타데이터
    data_source = models.CharField(max_length=50, default='mps_general_eye_gaze')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'raw_eye_gaze_data'
        ordering = ['tracking_timestamp_us']
        indexes = [
            models.Index(fields=['tracking_timestamp_us']),
            models.Index(fields=['session_uid']),
        ]
    
    def __str__(self):
        return f"Raw Eye Gaze {self.tracking_timestamp_us}"


class RawHandTrackingData(models.Model):
    """
    MPS Hand Tracking 원본 데이터 (hand_tracking_results.csv 필드 구조)
    정제되지 않은 원본 필드들을 모두 포함
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='raw_hand_tracking')
    
    # 원본 CSV 필드들 (Meta Project Aria MPS 원본)
    tracking_timestamp_us = models.BigIntegerField()
    left_tracking_confidence = models.FloatField()
    
    # Left hand landmarks (21개 landmarks x 3 coordinates = 63개 필드)
    tx_left_landmark_0_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_0_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_0_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_1_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_1_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_1_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_2_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_2_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_2_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_3_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_3_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_3_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_4_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_4_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_4_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_5_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_5_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_5_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_6_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_6_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_6_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_7_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_7_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_7_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_8_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_8_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_8_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_9_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_9_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_9_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_10_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_10_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_10_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_11_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_11_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_11_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_12_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_12_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_12_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_13_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_13_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_13_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_14_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_14_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_14_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_15_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_15_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_15_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_16_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_16_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_16_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_17_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_17_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_17_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_18_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_18_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_18_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_19_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_19_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_19_device = models.FloatField(null=True, blank=True)
    tx_left_landmark_20_device = models.FloatField(null=True, blank=True)
    ty_left_landmark_20_device = models.FloatField(null=True, blank=True)
    tz_left_landmark_20_device = models.FloatField(null=True, blank=True)
    
    # Right hand landmarks (21개 landmarks x 3 coordinates = 63개 필드)
    right_tracking_confidence = models.FloatField()
    tx_right_landmark_0_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_0_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_0_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_1_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_1_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_1_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_2_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_2_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_2_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_3_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_3_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_3_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_4_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_4_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_4_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_5_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_5_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_5_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_6_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_6_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_6_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_7_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_7_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_7_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_8_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_8_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_8_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_9_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_9_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_9_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_10_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_10_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_10_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_11_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_11_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_11_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_12_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_12_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_12_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_13_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_13_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_13_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_14_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_14_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_14_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_15_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_15_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_15_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_16_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_16_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_16_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_17_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_17_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_17_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_18_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_18_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_18_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_19_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_19_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_19_device = models.FloatField(null=True, blank=True)
    tx_right_landmark_20_device = models.FloatField(null=True, blank=True)
    ty_right_landmark_20_device = models.FloatField(null=True, blank=True)
    tz_right_landmark_20_device = models.FloatField(null=True, blank=True)
    
    # Wrist data (원본 필드들)
    tx_left_device_wrist = models.FloatField(null=True, blank=True)
    ty_left_device_wrist = models.FloatField(null=True, blank=True)
    tz_left_device_wrist = models.FloatField(null=True, blank=True)
    qx_left_device_wrist = models.FloatField(null=True, blank=True)
    qy_left_device_wrist = models.FloatField(null=True, blank=True)
    qz_left_device_wrist = models.FloatField(null=True, blank=True)
    qw_left_device_wrist = models.FloatField(null=True, blank=True)
    tx_right_device_wrist = models.FloatField(null=True, blank=True)
    ty_right_device_wrist = models.FloatField(null=True, blank=True)
    tz_right_device_wrist = models.FloatField(null=True, blank=True)
    qx_right_device_wrist = models.FloatField(null=True, blank=True)
    qy_right_device_wrist = models.FloatField(null=True, blank=True)
    qz_right_device_wrist = models.FloatField(null=True, blank=True)
    qw_right_device_wrist = models.FloatField(null=True, blank=True)
    
    # Palm and wrist normals (원본 필드들)
    nx_left_palm_device = models.FloatField(null=True, blank=True)
    ny_left_palm_device = models.FloatField(null=True, blank=True)
    nz_left_palm_device = models.FloatField(null=True, blank=True)
    nx_left_wrist_device = models.FloatField(null=True, blank=True)
    ny_left_wrist_device = models.FloatField(null=True, blank=True)
    nz_left_wrist_device = models.FloatField(null=True, blank=True)
    nx_right_palm_device = models.FloatField(null=True, blank=True)
    ny_right_palm_device = models.FloatField(null=True, blank=True)
    nz_right_palm_device = models.FloatField(null=True, blank=True)
    nx_right_wrist_device = models.FloatField(null=True, blank=True)
    ny_right_wrist_device = models.FloatField(null=True, blank=True)
    nz_right_wrist_device = models.FloatField(null=True, blank=True)
    
    # 메타데이터
    data_source = models.CharField(max_length=50, default='mps_hand_tracking')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'raw_hand_tracking_data'
        ordering = ['tracking_timestamp_us']
        indexes = [
            models.Index(fields=['tracking_timestamp_us']),
        ]
    
    def __str__(self):
        return f"Raw Hand Tracking {self.tracking_timestamp_us}"


class RawSlamTrajectoryData(models.Model):
    """
    MPS SLAM Trajectory 원본 데이터 (closed_loop_trajectory.csv 필드 구조)
    정제되지 않은 원본 필드들을 모두 포함
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='raw_slam_trajectory')
    
    # 원본 CSV 필드들 (Meta Project Aria MPS 원본)
    graph_uid = models.CharField(max_length=100)
    tracking_timestamp_us = models.BigIntegerField()
    utc_timestamp_ns = models.BigIntegerField()
    
    # World device transform (원본 필드들)
    tx_world_device = models.FloatField()
    ty_world_device = models.FloatField()
    tz_world_device = models.FloatField()
    qx_world_device = models.FloatField()
    qy_world_device = models.FloatField()
    qz_world_device = models.FloatField()
    qw_world_device = models.FloatField()
    
    # Device velocity (원본 필드들)
    device_linear_velocity_x_device = models.FloatField()
    device_linear_velocity_y_device = models.FloatField()
    device_linear_velocity_z_device = models.FloatField()
    angular_velocity_x_device = models.FloatField()
    angular_velocity_y_device = models.FloatField()
    angular_velocity_z_device = models.FloatField()
    
    # Gravity world (원본 필드들)
    gravity_x_world = models.FloatField()
    gravity_y_world = models.FloatField()
    gravity_z_world = models.FloatField()
    
    # Quality and geo data (원본 필드들)
    quality_score = models.FloatField()
    geo_available = models.IntegerField()
    
    # ECEF device transform (원본 필드들)
    tx_ecef_device = models.FloatField()
    ty_ecef_device = models.FloatField()
    tz_ecef_device = models.FloatField()
    qx_ecef_device = models.FloatField()
    qy_ecef_device = models.FloatField()
    qz_ecef_device = models.FloatField()
    qw_ecef_device = models.FloatField()
    
    # 메타데이터
    data_source = models.CharField(max_length=50, default='mps_slam_trajectory')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'raw_slam_trajectory_data'
        ordering = ['tracking_timestamp_us']
        indexes = [
            models.Index(fields=['tracking_timestamp_us']),
            models.Index(fields=['graph_uid']),
        ]
    
    def __str__(self):
        return f"Raw SLAM Trajectory {self.tracking_timestamp_us}"