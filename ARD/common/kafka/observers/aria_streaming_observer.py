import asyncio
import json
import logging
import numpy as np
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


class AriaStreamingObserver:
    """
    Project Aria streaming observer following official documentation pattern
    Implements observer pattern for real-time VRS data streaming to Kafka
    """
    
    def __init__(self, kafka_producer=None, session_id: str = None):
        self.kafka_producer = kafka_producer
        self.session_id = session_id
        self.is_streaming = False
        
        # Data storage following official pattern
        self.rgb_images = {}
        self.slam_images = {}
        self.imu_data = {}
        self.eye_gaze_data = {}
        self.audio_data = {}
        
        # Callbacks for external handlers
        self.callbacks = {
            'image': [],
            'imu': [],
            'audio': [],
            'eye_gaze': []
        }
        
        logger.info(f"AriaStreamingObserver initialized for session: {session_id}")
    
    def register_callback(self, data_type: str, callback: Callable):
        """Register callback for specific data type"""
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)
            logger.info(f"Registered {data_type} callback")
    
    def on_image_received(self, image: np.array, record):
        """Handle received image data following official pattern"""
        try:
            camera_id = getattr(record, 'camera_id', 'unknown')
            timestamp_ns = getattr(record, 'capture_timestamp_ns', 0)
            
            # Store image following official pattern
            if camera_id == '214-1':  # RGB camera
                self.rgb_images[camera_id] = image
            elif camera_id in ['1201-1', '1201-2']:  # SLAM cameras
                self.slam_images[camera_id] = image
            
            # Prepare data for Kafka
            image_data = {
                'session_id': self.session_id,
                'camera_id': camera_id,
                'timestamp_ns': timestamp_ns,
                'timestamp_utc': timezone.now().isoformat(),
                'image_shape': image.shape,
                'data_type': 'image'
            }
            
            # Send to Kafka if producer available
            if self.kafka_producer:
                asyncio.create_task(self._send_to_kafka('vrs-image-stream', image_data))
            
            # Execute callbacks
            for callback in self.callbacks['image']:
                try:
                    callback(image, record, image_data)
                except Exception as e:
                    logger.error(f"Image callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing image: {e}")
    
    def on_imu_received(self, accel_data, gyro_data, mag_data, record):
        """Handle IMU data following official pattern"""
        try:
            timestamp_ns = getattr(record, 'capture_timestamp_ns', 0)
            
            imu_data = {
                'session_id': self.session_id,
                'timestamp_ns': timestamp_ns,
                'timestamp_utc': timezone.now().isoformat(),
                'accel_x': float(accel_data[0]) if accel_data is not None else None,
                'accel_y': float(accel_data[1]) if accel_data is not None else None,
                'accel_z': float(accel_data[2]) if accel_data is not None else None,
                'gyro_x': float(gyro_data[0]) if gyro_data is not None else None,
                'gyro_y': float(gyro_data[1]) if gyro_data is not None else None,
                'gyro_z': float(gyro_data[2]) if gyro_data is not None else None,
                'mag_x': float(mag_data[0]) if mag_data is not None else None,
                'mag_y': float(mag_data[1]) if mag_data is not None else None,
                'mag_z': float(mag_data[2]) if mag_data is not None else None,
                'data_type': 'imu'
            }
            
            self.imu_data[timestamp_ns] = imu_data
            
            # Send to Kafka
            if self.kafka_producer:
                asyncio.create_task(self._send_to_kafka('vrs-imu-stream', imu_data))
            
            # Execute callbacks
            for callback in self.callbacks['imu']:
                try:
                    callback(accel_data, gyro_data, mag_data, record, imu_data)
                except Exception as e:
                    logger.error(f"IMU callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing IMU data: {e}")
    
    def on_audio_received(self, audio_data, record):
        """Handle audio data following official pattern"""
        try:
            timestamp_ns = getattr(record, 'capture_timestamp_ns', 0)
            
            audio_info = {
                'session_id': self.session_id,
                'timestamp_ns': timestamp_ns,
                'timestamp_utc': timezone.now().isoformat(),
                'audio_shape': audio_data.shape if hasattr(audio_data, 'shape') else None,
                'sample_rate': getattr(record, 'sample_rate', None),
                'data_type': 'audio'
            }
            
            self.audio_data[timestamp_ns] = audio_info
            
            # Send to Kafka
            if self.kafka_producer:
                asyncio.create_task(self._send_to_kafka('vrs-audio-stream', audio_info))
            
            # Execute callbacks
            for callback in self.callbacks['audio']:
                try:
                    callback(audio_data, record, audio_info)
                except Exception as e:
                    logger.error(f"Audio callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
    
    def on_eye_gaze_received(self, eye_gaze_data, record):
        """Handle eye gaze data following official pattern"""
        try:
            timestamp_ns = getattr(record, 'capture_timestamp_ns', 0)
            
            gaze_data = {
                'session_id': self.session_id,
                'timestamp_ns': timestamp_ns,
                'timestamp_utc': timezone.now().isoformat(),
                'eye_gaze_x': float(eye_gaze_data[0]) if eye_gaze_data is not None else None,
                'eye_gaze_y': float(eye_gaze_data[1]) if eye_gaze_data is not None else None,
                'eye_gaze_z': float(eye_gaze_data[2]) if eye_gaze_data is not None else None,
                'confidence': getattr(record, 'confidence', None),
                'data_type': 'eye_gaze'
            }
            
            self.eye_gaze_data[timestamp_ns] = gaze_data
            
            # Send to Kafka
            if self.kafka_producer:
                asyncio.create_task(self._send_to_kafka('vrs-eye-gaze-stream', gaze_data))
            
            # Execute callbacks
            for callback in self.callbacks['eye_gaze']:
                try:
                    callback(eye_gaze_data, record, gaze_data)
                except Exception as e:
                    logger.error(f"Eye gaze callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing eye gaze data: {e}")
    
    async def _send_to_kafka(self, topic: str, data: Dict[str, Any]):
        """Send data to Kafka topic asynchronously"""
        try:
            if self.kafka_producer:
                await self.kafka_producer.send_message(topic, data)
                logger.debug(f"Sent {data['data_type']} data to topic '{topic}'")
        except Exception as e:
            logger.error(f"Failed to send data to Kafka topic '{topic}': {e}")
    
    def start_observation(self):
        """Start observing streaming data"""
        self.is_streaming = True
        logger.info(f"Started observation for session: {self.session_id}")
    
    def stop_observation(self):
        """Stop observing streaming data"""
        self.is_streaming = False
        logger.info(f"Stopped observation for session: {self.session_id}")
    
    def get_latest_data(self) -> Dict[str, Any]:
        """Get latest received data"""
        return {
            'rgb_images': dict(list(self.rgb_images.items())[-5:]) if self.rgb_images else {},
            'slam_images': dict(list(self.slam_images.items())[-5:]) if self.slam_images else {},
            'imu_data': dict(list(self.imu_data.items())[-10:]) if self.imu_data else {},
            'eye_gaze_data': dict(list(self.eye_gaze_data.items())[-10:]) if self.eye_gaze_data else {},
            'audio_data': dict(list(self.audio_data.items())[-5:]) if self.audio_data else {}
        }