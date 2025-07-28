import json
import time
from kafka import KafkaProducer
from kafka.errors import KafkaError
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AriaKafkaProducer:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            retries=3,
            acks='all'
        )
        
        self.topics = {
            'vrs_raw_stream': 'vrs-raw-stream',
            'mps_eye_gaze_general': 'mps-eye-gaze-general', 
            'mps_eye_gaze_personalized': 'mps-eye-gaze-personalized',
            'mps_hand_tracking': 'mps-hand-tracking',
            'mps_slam_trajectory': 'mps-slam-trajectory',
            'mps_slam_points': 'mps-slam-points',
            'mps_slam_calibration': 'mps-slam-calibration',
            'analytics_real_time': 'analytics-real-time'
        }
    
    def send_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'stream_id': stream_id,
            'frame_data': frame_data,
            'data_type': 'vrs_frame'
        }
        
        try:
            future = self.producer.send(
                self.topics['vrs_raw_stream'], 
                value=message,
                key=stream_id
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send VRS frame: {e}")
            raise
    
    def send_eye_gaze(self, gaze_data: Dict[str, Any], gaze_type: str = 'general'):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'gaze_vector': gaze_data.get('gaze_vector'),
            'depth': gaze_data.get('depth'),
            'confidence': gaze_data.get('confidence'),
            'device_timestamp_ns': gaze_data.get('tracking_timestamp_ns'),
            'data_type': f'eye_gaze_{gaze_type}'
        }
        
        topic = self.topics[f'mps_eye_gaze_{gaze_type}']
        try:
            future = self.producer.send(topic, value=message)
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send eye gaze data: {e}")
            raise
    
    def send_hand_tracking(self, hand_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'left_hand': hand_data.get('left_hand'),
            'right_hand': hand_data.get('right_hand'),
            'device_timestamp_ns': hand_data.get('tracking_timestamp_ns'),
            'data_type': 'hand_tracking'
        }
        
        try:
            future = self.producer.send(
                self.topics['mps_hand_tracking'], 
                value=message
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send hand tracking data: {e}")
            raise
    
    def send_slam_trajectory(self, trajectory_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'transform_world_device': trajectory_data.get('transform_world_device'),
            'device_timestamp_ns': trajectory_data.get('tracking_timestamp_ns'),
            'data_type': 'slam_trajectory'
        }
        
        try:
            future = self.producer.send(
                self.topics['mps_slam_trajectory'], 
                value=message
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send SLAM trajectory: {e}")
            raise
    
    def send_slam_points(self, points_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'points': points_data.get('points'),
            'data_type': 'slam_points'
        }
        
        try:
            future = self.producer.send(
                self.topics['mps_slam_points'], 
                value=message
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send SLAM points: {e}")
            raise
    
    def close(self):
        self.producer.close()
