# core/mps/loaders.py - 튜토리얼 코드 그대로 활용
import os
import numpy as np
from projectaria_tools.core import mps
from projectaria_tools.core.mps.utils import filter_points_from_confidence
from django.conf import settings


def load_sample_mps_data():
    """MPS 튜토리얼 샘플 데이터 로드"""
    mps_path = settings.MPS_SAMPLE_DATA_PATH

    # 튜토리얼 코드 그대로
    trajectory_path = os.path.join(mps_path, "slam", "closed_loop_trajectory.csv")
    points_path = os.path.join(mps_path, "slam", "semidense_points.csv.gz")
    eye_gaze_path = os.path.join(mps_path, "eye_gaze", "general_eye_gaze.csv")
    hand_tracking_path = os.path.join(mps_path, "hand_tracking", "hand_tracking_results.csv")

    # MPS 데이터 로드
    trajectory = mps.read_closed_loop_trajectory(trajectory_path)
    points = mps.read_global_point_cloud(points_path)
    eye_gazes = mps.read_eyegaze(eye_gaze_path)
    hand_tracking = mps.hand_tracking.read_hand_tracking_results(hand_tracking_path)

    return {
        'trajectory': trajectory,
        'points': points,
        'eye_gazes': eye_gazes,
        'hand_tracking': hand_tracking
    }


def get_trajectory_points():
    """3D 궤적 포인트 추출 (튜토리얼 코드)"""
    data = load_sample_mps_data()
    trajectory = data['trajectory']

    # 튜토리얼 코드 그대로
    traj = np.empty([len(trajectory), 3])
    for i in range(len(trajectory)):
        traj[i, :] = trajectory[i].transform_world_device.translation()

    return traj


def get_filtered_point_cloud():
    """필터링된 포인트 클라우드 (튜토리얼 코드)"""
    data = load_sample_mps_data()
    points = data['points']

    # 튜토리얼 코드 그대로
    filtered_points = filter_points_from_confidence(points)
    point_cloud = np.stack([it.position_world for it in filtered_points])

    return point_cloud