import asyncio
import json
import logging
import base64
import cv2
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from django.utils import timezone
from .base_producer import BaseKafkaProducer

logger = logging.getLogger(__name__)


class VRSKafkaProducer(BaseKafkaProducer):
    """
    VRS-focused Kafka producer for Project Aria sensor streaming
    Handles all VRS sensor data types following official documentation patterns
    """
    
    def __init__(self, bootstrap_servers: str = 'kafka-all:9092'):
        super().__init__('vrs-streaming', bootstrap_servers)
        
        # VRS-specific topics for all sensor streams
        self.topics = {
            # Image streams
            'camera_rgb': 'vrs-camera-rgb',
            'camera_slam_left': 'vrs-camera-slam-left',
            'camera_slam_right': 'vrs-camera-slam-right',
            'camera_eyetracking': 'vrs-camera-eyetracking',
            
            # Sensor streams
            'imu_right': 'vrs-imu-right',
            'imu_left': 'vrs-imu-left',
            'magnetometer': 'vrs-magnetometer',
            'barometer': 'vrs-barometer',
            'audio': 'vrs-audio',
            'gps': 'vrs-gps',
            'wps': 'vrs-wps',
            'bluetooth': 'vrs-bluetooth',
            
            # Unified streams
            'unified_sensor': 'vrs-unified-sensor',
            'session_events': 'vrs-session-events'
        }
        
        # Stream ID mappings from aria_sessions
        self.stream_id_mappings = {
            "camera-slam-left": "1201-1",
            "camera-slam-right": "1201-2", 
            "camera-rgb": "214-1",
            "camera-eyetracking": "211-1",
            "imu-right": "1202-1",
            "imu-left": "1202-2",
            "magnetometer": "1203-1",
            "barometer": "247-1",
            "microphone": "231-1",
            "gps": "281-1",
            "wps": "282-1",
            "bluetooth": "283-1"
        }
        
        logger.info("VRSKafkaProducer initialized for VRS sensor streaming")
    
    async def send_message(self, topic_key: str, message: Dict[str, Any], key: Optional[str] = None):
        """Async wrapper for VRS message sending"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, super().send_message, topic_key, message, key)
    
    async def stream_vrs_image(self, stream_name: str, image_data: Dict[str, Any], session_id: str):
        """Stream VRS image data to appropriate camera topic"""
        try:
            # Convert image array to base64 for Kafka transport
            image_array = image_data.get('image_array')
            if image_array is not None:
                # Compress to JPEG for efficient streaming
                _, buffer = cv2.imencode('.jpg', image_array, [cv2.IMWRITE_JPEG_QUALITY, 85])
                image_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            else:
                image_base64 = None
            
            # Prepare streamlined data for Kafka
            kafka_data = {
                'session_id': session_id,
                'stream_name': stream_name,
                'stream_id': image_data.get('stream_id'),
                'frame_index': image_data.get('frame_index'),
                'image_shape': image_data.get('image_shape'),
                'capture_timestamp_ns': image_data.get('capture_timestamp_ns'),
                'frame_number': image_data.get('frame_number'),
                'image_base64': image_base64,
                'streaming_timestamp': timezone.now().isoformat(),
                'data_type': 'image'
            }
            
            # Map stream name to topic
            topic_map = {
                'camera-rgb': 'camera_rgb',
                'camera-slam-left': 'camera_slam_left', 
                'camera-slam-right': 'camera_slam_right',
                'camera-eyetracking': 'camera_eyetracking'
            }
            
            topic_key = topic_map.get(stream_name, 'unified_sensor')
            message_key = f"{session_id}-{stream_name}-{image_data.get('frame_index', 0)}"
            
            success = await self.send_message(topic_key, kafka_data, message_key)
            
            if success:
                logger.debug(f"Streamed {stream_name} image frame {image_data.get('frame_index')} to {self.topics[topic_key]}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error streaming VRS image data: {e}")
            return False
    
    async def stream_vrs_sensor(self, sensor_data: Dict[str, Any], session_id: str):
        """Stream VRS sensor data (IMU, magnetometer, barometer, etc.)"""
        try:
            sensor_type = sensor_data.get('sensor_type', '')
            stream_label = sensor_data.get('stream_label', '')
            
            # Prepare sensor data for Kafka
            kafka_data = {
                'session_id': session_id,
                'stream_id': sensor_data.get('stream_id'),
                'stream_label': stream_label,
                'sensor_type': sensor_type,
                'device_timestamp_ns': sensor_data.get('device_timestamp_ns'),
                'host_timestamp_ns': sensor_data.get('host_timestamp_ns'),
                'sequence': sensor_data.get('sequence'),
                'streaming_timestamp': timezone.now().isoformat(),
                'data_type': 'sensor'
            }
            
            # Include sensor-specific data
            if 'imu_data' in sensor_data:
                kafka_data['imu_data'] = sensor_data['imu_data']
                topic_key = 'imu_right' if 'right' in stream_label.lower() else 'imu_left'
            elif 'magnetometer_data' in sensor_data:
                kafka_data['magnetometer_data'] = sensor_data['magnetometer_data']
                topic_key = 'magnetometer'
            elif 'barometer_data' in sensor_data:
                kafka_data['barometer_data'] = sensor_data['barometer_data']
                topic_key = 'barometer'
            elif 'audio_data' in sensor_data:
                kafka_data['audio_data'] = sensor_data['audio_data']
                topic_key = 'audio'
            elif 'gps_data' in sensor_data:
                kafka_data['gps_data'] = sensor_data['gps_data']
                topic_key = 'gps'
            elif 'wps_data' in sensor_data:
                kafka_data['wps_data'] = sensor_data['wps_data']
                topic_key = 'wps'
            elif 'bluetooth_data' in sensor_data:
                kafka_data['bluetooth_data'] = sensor_data['bluetooth_data']
                topic_key = 'bluetooth'
            else:
                topic_key = 'unified_sensor'
            
            message_key = f"{session_id}-{stream_label}-{sensor_data.get('sequence', 0)}"
            
            success = await self.send_message(topic_key, kafka_data, message_key)
            
            if success:
                logger.debug(f"Streamed {sensor_type} sensor data from {stream_label}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error streaming VRS sensor data: {e}")
            return False
    
    async def stream_vrs_unified(self, unified_data: List[Dict[str, Any]], session_id: str):
        """Stream unified VRS data (both images and sensors) efficiently"""
        try:
            success_count = 0
            error_count = 0
            
            for data_item in unified_data:
                try:
                    # Route based on data type
                    if data_item.get('has_image_data'):
                        # Stream as image
                        success = await self.stream_vrs_image(
                            data_item.get('stream_label', 'unknown'),
                            data_item,
                            session_id
                        )
                    elif data_item.get('has_sensor_data'):
                        # Stream as sensor data
                        success = await self.stream_vrs_sensor(data_item, session_id)
                    else:
                        # Stream as unified sensor data
                        success = await self.send_message(
                            'unified_sensor',
                            {
                                **data_item,
                                'session_id': session_id,
                                'streaming_timestamp': timezone.now().isoformat()
                            },
                            f"{session_id}-unified-{data_item.get('sequence', 0)}"
                        )
                    
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Error streaming unified data item: {e}")
                    error_count += 1
            
            logger.info(f"Unified streaming completed: {success_count} success, {error_count} errors")
            return {'success_count': success_count, 'error_count': error_count}
            
        except Exception as e:
            logger.error(f"Error in unified VRS streaming: {e}")
            return {'success_count': 0, 'error_count': len(unified_data)}
    
    async def send_session_event(self, event_type: str, session_id: str, event_data: Dict[str, Any] = None):
        """Send VRS session events"""
        try:
            event_message = {
                'event_type': event_type,
                'session_id': session_id,
                'timestamp': timezone.now().isoformat(),
                'event_data': event_data or {},
                'service_type': 'vrs_streaming'
            }
            
            success = await self.send_message(
                'session_events', 
                event_message, 
                f"{session_id}-{event_type}"
            )
            
            if success:
                logger.info(f"Sent VRS session event '{event_type}' for session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending VRS session event: {e}")
            return False
    
    def get_vrs_topics(self) -> Dict[str, str]:
        """Get VRS-specific topic mappings"""
        return self.topics.copy()
    
    def get_stream_id_mappings(self) -> Dict[str, str]:
        """Get VRS stream ID mappings"""
        return self.stream_id_mappings.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check VRS producer health"""
        try:
            test_message = {
                'test': True,
                'timestamp': timezone.now().isoformat(),
                'service': self.service_name,
                'vrs_topics': len(self.topics)
            }
            
            success = await self.send_message('session_events', test_message, 'vrs-health-check')
            
            return {
                'service': self.service_name,
                'producer_status': 'healthy' if success else 'unhealthy',
                'bootstrap_servers': self.bootstrap_servers,
                'vrs_topics_configured': len(self.topics),
                'stream_mappings_count': len(self.stream_id_mappings),
                'last_check': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"VRS producer health check failed: {e}")
            return {
                'service': self.service_name,
                'producer_status': 'error',
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }