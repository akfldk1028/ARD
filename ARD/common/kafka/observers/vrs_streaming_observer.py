import asyncio
import logging
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
from django.utils import timezone
from .aria_streaming_observer import AriaStreamingObserver

logger = logging.getLogger(__name__)


class VRSStreamingObserver(AriaStreamingObserver):
    """
    VRS-specific streaming observer for Project Aria VRS file streaming
    Extends AriaStreamingObserver with VRS-specific data handling
    """
    
    def __init__(self, kafka_producer=None, session_id: str = None, vrs_file_path: str = None):
        super().__init__(kafka_producer, session_id)
        self.vrs_file_path = vrs_file_path
        self.frame_count = 0
        self.last_frame_time = None
        
        # VRS-specific data tracking
        self.stream_stats = {
            'rgb_frames': 0,
            'slam_left_frames': 0, 
            'slam_right_frames': 0,
            'imu_samples': 0,
            'audio_samples': 0,
            'eye_gaze_samples': 0
        }
        
        logger.info(f"VRSStreamingObserver initialized for VRS file: {vrs_file_path}")
    
    def on_image_received(self, image: np.array, record):
        """Handle VRS image data with stream-specific tracking"""
        try:
            camera_id = getattr(record, 'camera_id', 'unknown')
            
            # Update stream statistics
            if camera_id == '214-1':  # RGB
                self.stream_stats['rgb_frames'] += 1
            elif camera_id == '1201-1':  # SLAM Left
                self.stream_stats['slam_left_frames'] += 1
            elif camera_id == '1201-2':  # SLAM Right
                self.stream_stats['slam_right_frames'] += 1
            
            self.frame_count += 1
            self.last_frame_time = timezone.now()
            
            # Call parent implementation
            super().on_image_received(image, record)
            
            # Log VRS-specific info
            if self.frame_count % 100 == 0:
                logger.info(f"VRS streaming: {self.frame_count} frames processed from {self.vrs_file_path}")
                
        except Exception as e:
            logger.error(f"VRS image processing error: {e}")
    
    def on_imu_received(self, accel_data, gyro_data, mag_data, record):
        """Handle VRS IMU data with specific tracking"""
        try:
            self.stream_stats['imu_samples'] += 1
            
            # Call parent implementation
            super().on_imu_received(accel_data, gyro_data, mag_data, record)
            
        except Exception as e:
            logger.error(f"VRS IMU processing error: {e}")
    
    def on_audio_received(self, audio_data, record):
        """Handle VRS audio data with specific tracking"""
        try:
            self.stream_stats['audio_samples'] += 1
            
            # Call parent implementation
            super().on_audio_received(audio_data, record)
            
        except Exception as e:
            logger.error(f"VRS audio processing error: {e}")
    
    def on_eye_gaze_received(self, eye_gaze_data, record):
        """Handle VRS eye gaze data with specific tracking"""
        try:
            self.stream_stats['eye_gaze_samples'] += 1
            
            # Call parent implementation
            super().on_eye_gaze_received(eye_gaze_data, record)
            
        except Exception as e:
            logger.error(f"VRS eye gaze processing error: {e}")
    
    def get_vrs_statistics(self) -> Dict[str, Any]:
        """Get VRS-specific streaming statistics"""
        return {
            'vrs_file_path': self.vrs_file_path,
            'session_id': self.session_id,
            'total_frames': self.frame_count,
            'last_frame_time': self.last_frame_time.isoformat() if self.last_frame_time else None,
            'stream_stats': self.stream_stats.copy(),
            'is_streaming': self.is_streaming
        }
    
    def reset_statistics(self):
        """Reset streaming statistics"""
        self.frame_count = 0
        self.last_frame_time = None
        self.stream_stats = {
            'rgb_frames': 0,
            'slam_left_frames': 0,
            'slam_right_frames': 0, 
            'imu_samples': 0,
            'audio_samples': 0,
            'eye_gaze_samples': 0
        }
        logger.info("VRS streaming statistics reset")
    
    def start_observation(self):
        """Start VRS observation with statistics tracking"""
        super().start_observation()
        self.reset_statistics()
        logger.info(f"Started VRS observation for file: {self.vrs_file_path}")
    
    def stop_observation(self):
        """Stop VRS observation"""
        super().stop_observation()
        final_stats = self.get_vrs_statistics()
        logger.info(f"Stopped VRS observation. Final stats: {final_stats}")
        return final_stats