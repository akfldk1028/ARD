import json
import time
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AriaKafkaProducer:
    def __init__(self, bootstrap_servers=None):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.producer = None
        self.topics = {
            'vrs_raw_stream': 'vrs-raw-stream',
            'imu_data': 'imu-data',
            'magnetometer_data': 'magnetometer-data',
            'barometer_data': 'barometer-data',
            'audio_data': 'audio-data',
            'mps_eye_gaze_general': 'mps-eye-gaze-general', 
            'mps_eye_gaze_personalized': 'mps-eye-gaze-personalized',
            'mps_hand_tracking': 'mps-hand-tracking',
            'mps_slam_trajectory': 'mps-slam-trajectory',
            'mps_slam_points': 'mps-slam-points',
            'mps_slam_calibration': 'mps-slam-calibration',
            'analytics_real_time': 'analytics-real-time',
            # Real-time sensor streaming topics
            'aria_imu_real_time': 'aria-imu-real-time',
            'aria_mag_real_time': 'aria-mag-real-time',
            'aria_baro_real_time': 'aria-baro-real-time',
            'aria_audio_real_time': 'aria-audio-real-time',
            'aria_sensor_fusion': 'aria-sensor-fusion',
        }
    
    def _get_producer(self):
        """Lazy initialization of producer"""
        if self.producer is None:
            self.producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                # Performance optimization
                compression_type=None,  # No compression for compatibility
                batch_size=32768,          # 32KB batches for efficiency
                linger_ms=5,               # Small delay for batching
                buffer_memory=67108864,    # 64MB buffer
                # Large message support
                max_request_size=10485760, # 10MB max message
                # Reliability
                retries=3,
                acks=1,
                request_timeout_ms=30000,  # Increased timeout
                metadata_max_age_ms=300000,  # 5 minutes
                # Connection management
                connections_max_idle_ms=300000,
                reconnect_backoff_ms=50,
                reconnect_backoff_max_ms=1000
            )
        return self.producer
    
    def send_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'stream_id': stream_id,
            'frame_data': frame_data,
            'data_type': 'vrs_frame'
        }
        
        try:
            future = self._get_producer().send(
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
            future = self._get_producer().send(topic, value=message)
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
            future = self._get_producer().send(
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
            future = self._get_producer().send(
                self.topics['mps_slam_trajectory'], 
                value=message
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send SLAM trajectory: {e}")
            raise
    
    def send_imu_data(self, imu_data: Dict[str, Any]):
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'imu_stream_id': imu_data.get('imu_stream_id'),
            'imu_name': imu_data.get('imu_name'),
            'device_timestamp_ns': imu_data.get('device_timestamp_ns'),
            'accel_x': imu_data.get('accel_x'),
            'accel_y': imu_data.get('accel_y'),
            'accel_z': imu_data.get('accel_z'),
            'gyro_x': imu_data.get('gyro_x'),
            'gyro_y': imu_data.get('gyro_y'),
            'gyro_z': imu_data.get('gyro_z'),
            'temperature_c': imu_data.get('temperature_c'),
            'data_type': 'imu_data'
        }
        
        try:
            future = self._get_producer().send(
                self.topics['imu_data'], 
                value=message,
                key=imu_data.get('imu_name', 'unknown')
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send IMU data: {e}")
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
    
    async def send_aria_command(self, session_id: str, command: Dict[str, Any]):
        """Send command to Aria device"""
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'command': command,
            'data_type': 'aria_command'
        }
        
        try:
            # Use a command topic for Aria device commands
            topic = 'aria-commands'
            future = self._get_producer().send(
                topic, 
                value=message,
                key=session_id
            )
            return future.get(timeout=10)
        except KafkaError as e:
            logger.error(f"Failed to send Aria command: {e}")
            raise
    
    def send_real_time_frame(self, stream_type: str, compressed_data: bytes, metadata: dict) -> bool:
        """
        실시간 프레임 데이터 전송 (바이너리 저장 없음)
        Real-time frame streaming without binary storage
        """
        try:
            # 메타데이터에 스트림 정보 추가
            frame_metadata = {
                **metadata,
                'data_type': 'real_time_frame',
                'stream_type': stream_type,
                'frame_size': len(compressed_data)
            }
            
            producer = self._get_producer()
            
            # 메타데이터와 압축된 이미지를 하나의 메시지로 전송
            real_time_message = {
                'metadata': frame_metadata,
                'image_data': compressed_data.hex()  # 바이너리를 hex string으로 변환
            }
            
            # 적절한 토픽으로 전송
            topic_map = {
                'rgb': 'aria-rgb-real-time',
                'slam_left': 'aria-slam-real-time', 
                'slam_right': 'aria-slam-real-time',
                'eye_tracking': 'aria-et-real-time'
            }
            
            topic = topic_map.get(stream_type, 'aria-general-real-time')
            
            future = producer.send(topic, real_time_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Real-time {stream_type} frame sent: {len(compressed_data)} bytes to {topic}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send real-time {stream_type} frame: {e}")
            return False

    def send_test_message(self, session_id: str = 'test-aria-session'):
        """Send test VRS frame message for debugging"""
        
        # Create test VRS frame message
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'stream_id': '214-1',  # RGB camera
            'stream_name': 'camera-rgb',
            'device_timestamp_ns': int(time.time() * 1_000_000_000),
            'frame_index': 1,
            'image_shape': [480, 640, 3],
            'pixel_format': 'RGB24',
            'image_data': 'test_frame_data_base64',
            'image_width': 640,
            'image_height': 480,
            'original_size_bytes': 921600,
            'compressed_size_bytes': 45000,
            'compression_quality': 90
        }
        
        try:
            producer = self._get_producer()
            future = producer.send(
                self.topics['vrs_raw_stream'],
                value=message,
                key=session_id
            )
            
            record_metadata = future.get(timeout=10)
            logger.info(f"Test VRS message sent: partition={record_metadata.partition}, offset={record_metadata.offset}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test VRS message: {e}")
            return False
    
    def send_real_time_imu(self, stream_id: str, imu_data: dict, metadata: dict) -> bool:
        """실시간 IMU 데이터 전송 (가속도계 + 자이로스코프)"""
        try:
            imu_message = {
                'metadata': {
                    **metadata,
                    'data_type': 'real_time_imu',
                    'stream_id': stream_id
                },
                'imu_data': {
                    'accel_x': imu_data.get('accel_x', 0.0),
                    'accel_y': imu_data.get('accel_y', 0.0), 
                    'accel_z': imu_data.get('accel_z', 0.0),
                    'gyro_x': imu_data.get('gyro_x', 0.0),
                    'gyro_y': imu_data.get('gyro_y', 0.0),
                    'gyro_z': imu_data.get('gyro_z', 0.0),
                    'temperature': imu_data.get('temperature', 0.0)
                }
            }
            
            producer = self._get_producer()
            future = producer.send(self.topics['aria_imu_real_time'], imu_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Real-time IMU data sent: {stream_id}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send real-time IMU data: {e}")
            return False

    def send_real_time_magnetometer(self, stream_id: str, mag_data: dict, metadata: dict) -> bool:
        """실시간 자력계 데이터 전송"""
        try:
            mag_message = {
                'metadata': {
                    **metadata,
                    'data_type': 'real_time_magnetometer',
                    'stream_id': stream_id
                },
                'magnetometer_data': {
                    'mag_x': mag_data.get('mag_x', 0.0),
                    'mag_y': mag_data.get('mag_y', 0.0),
                    'mag_z': mag_data.get('mag_z', 0.0),
                    'temperature': mag_data.get('temperature', 0.0)
                }
            }
            
            producer = self._get_producer()
            future = producer.send(self.topics['aria_mag_real_time'], mag_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Real-time magnetometer data sent: {stream_id}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send real-time magnetometer data: {e}")
            return False

    def send_real_time_barometer(self, stream_id: str, baro_data: dict, metadata: dict) -> bool:
        """실시간 기압계 데이터 전송"""
        try:
            baro_message = {
                'metadata': {
                    **metadata,
                    'data_type': 'real_time_barometer',
                    'stream_id': stream_id
                },
                'barometer_data': {
                    'pressure': baro_data.get('pressure', 0.0),
                    'temperature': baro_data.get('temperature', 0.0)
                }
            }
            
            producer = self._get_producer()
            future = producer.send(self.topics['aria_baro_real_time'], baro_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Real-time barometer data sent: {stream_id}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send real-time barometer data: {e}")
            return False

    def send_real_time_audio(self, stream_id: str, audio_data: dict, metadata: dict) -> bool:
        """실시간 오디오 데이터 전송"""
        try:
            audio_message = {
                'metadata': {
                    **metadata,
                    'data_type': 'real_time_audio',
                    'stream_id': stream_id
                },
                'audio_data': {
                    'sample_rate': audio_data.get('sample_rate', 48000),
                    'channels': audio_data.get('channels', 7),
                    'audio_samples': audio_data.get('audio_samples', []),
                    'rms_level': audio_data.get('rms_level', 0.0),
                    'peak_level': audio_data.get('peak_level', 0.0)
                }
            }
            
            producer = self._get_producer()
            future = producer.send(self.topics['aria_audio_real_time'], audio_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Real-time audio data sent: {stream_id}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send real-time audio data: {e}")
            return False

    def send_sensor_fusion_data(self, fusion_data: dict, metadata: dict) -> bool:
        """센서 융합 데이터 전송 (IMU + 자력계 + 기압계 조합으로 6DOF 포즈)"""
        try:
            fusion_message = {
                'metadata': {
                    **metadata,
                    'data_type': 'sensor_fusion',
                    'fusion_timestamp': datetime.utcnow().isoformat()
                },
                'fusion_data': {
                    # 6DOF 포즈 정보
                    'position': {
                        'x': fusion_data.get('pos_x', 0.0),
                        'y': fusion_data.get('pos_y', 0.0),
                        'z': fusion_data.get('pos_z', 0.0)
                    },
                    'rotation': {
                        'quaternion': {
                            'w': fusion_data.get('quat_w', 1.0),
                            'x': fusion_data.get('quat_x', 0.0),
                            'y': fusion_data.get('quat_y', 0.0),
                            'z': fusion_data.get('quat_z', 0.0)
                        },
                        'euler': {
                            'roll': fusion_data.get('roll', 0.0),
                            'pitch': fusion_data.get('pitch', 0.0),
                            'yaw': fusion_data.get('yaw', 0.0)
                        }
                    },
                    # 센서 원본 데이터
                    'raw_sensors': {
                        'imu_accel': fusion_data.get('imu_accel', [0.0, 0.0, 0.0]),
                        'imu_gyro': fusion_data.get('imu_gyro', [0.0, 0.0, 0.0]),
                        'magnetometer': fusion_data.get('magnetometer', [0.0, 0.0, 0.0]),
                        'barometer': fusion_data.get('barometer', 0.0)
                    },
                    # 센서 품질 정보
                    'quality': {
                        'confidence': fusion_data.get('confidence', 0.0),
                        'accuracy': fusion_data.get('accuracy', 0.0),
                        'sensor_health': fusion_data.get('sensor_health', 'unknown')
                    }
                }
            }
            
            producer = self._get_producer()
            future = producer.send(self.topics['aria_sensor_fusion'], fusion_message)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Sensor fusion data sent")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send sensor fusion data: {e}")
            return False

    def close(self):
        if self.producer:
            self.producer.close()
