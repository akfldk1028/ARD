"""
VRS Binary Reader - Optimized for real-time streaming
Refactored from Base64 encoding to direct binary Kafka streaming
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import numpy as np
from projectaria_tools.core import data_provider, mps
from projectaria_tools.core.stream_id import StreamId, RecordableTypeId
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions

from common.kafka.binary_producer import BinaryKafkaProducer

logger = logging.getLogger(__name__)

class VRSBinaryStreamer:
    """
    High-performance VRS streamer using binary Kafka architecture
    
    Key improvements:
    - Direct binary transmission (no Base64 encoding)
    - Metadata/binary topic separation  
    - Configurable compression formats
    - Real-time optimized streaming
    """
    
    def __init__(self, 
                 vrs_file_path: str, 
                 mps_data_path: str, 
                 kafka_bootstrap_servers='kafka-all:9092',
                 compression_format='jpeg',
                 compression_quality=90):
        
        self.vrs_file_path = vrs_file_path
        self.mps_data_path = mps_data_path
        self.compression_format = compression_format
        self.compression_quality = compression_quality
        
        # Initialize binary producer
        self.producer = BinaryKafkaProducer(kafka_bootstrap_servers)
        
        # Initialize data providers
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            self.mps_provider = mps.MpsDataProvider(
                mps.MpsDataPathsProvider(mps_data_path).get_data_paths()
            )
            logger.info(f"Initialized VRS provider: {vrs_file_path}")
        except Exception as e:
            logger.error(f"Failed to initialize data providers: {e}")
            raise
        
        # Stream configurations
        self.stream_configs = {
            'rgb': {
                'stream_id': StreamId("214-1"),
                'name': 'camera-rgb',
                'priority': 1,  # Highest priority
                'sample_rate': 30,  # 30 FPS
                'format': compression_format
            },
            'slam_left': {
                'stream_id': StreamId("1201-1"),
                'name': 'camera-slam-left', 
                'priority': 2,
                'sample_rate': 20,  # 20 FPS
                'format': compression_format
            },
            'slam_right': {
                'stream_id': StreamId("1201-2"),
                'name': 'camera-slam-right',
                'priority': 2, 
                'sample_rate': 20,  # 20 FPS
                'format': compression_format
            },
            'eye_tracking': {
                'stream_id': StreamId("211-1"),
                'name': 'camera-eye-tracking',
                'priority': 3,
                'sample_rate': 10,  # 10 FPS
                'format': 'jpeg'  # Lower quality for eye tracking
            }
        }
        
        # Discover IMU streams dynamically
        self._discover_imu_streams()
        
        # Streaming state
        self.is_streaming = False
        self.stream_stats = {
            'frames_sent': 0,
            'sensors_sent': 0,
            'start_time': None,
            'last_frame_time': None,
            'errors': 0
        }
    
    def _discover_imu_streams(self):
        """Dynamically discover IMU streams from VRS file"""
        self.imu_configs = {}
        
        try:
            all_streams = self.vrs_provider.get_all_streams()
            
            for stream_id in all_streams:
                if stream_id.get_type_id() == RecordableTypeId.SLAM_IMU_DATA:
                    label = self.vrs_provider.get_label_from_stream_id(stream_id)
                    
                    self.imu_configs[label] = {
                        'stream_id': stream_id,
                        'name': f'imu-{label}',
                        'sample_rate': 100,  # 100 Hz for IMU
                        'priority': 4
                    }
                    
                    logger.info(f"Discovered IMU stream: {label} -> {stream_id}")
                    
        except Exception as e:
            logger.warning(f"IMU stream discovery failed: {e}")
            # Fallback to known IMU stream IDs
            self.imu_configs = {
                'imu-right': {
                    'stream_id': StreamId("1202-1"),
                    'name': 'imu-right',
                    'sample_rate': 1000,
                    'priority': 4
                },
                'imu-left': {
                    'stream_id': StreamId("1202-2"), 
                    'name': 'imu-left',
                    'sample_rate': 1000,
                    'priority': 4
                }
            }
    
    async def stream_vrs_frames(self, 
                               session_id: str,
                               duration_seconds: Optional[int] = None,
                               streams: Optional[list] = None) -> Dict[str, Any]:
        """
        Stream VRS image frames using binary architecture
        
        Args:
            session_id: Unique session identifier
            duration_seconds: Maximum streaming duration
            streams: List of streams to process (default: all)
            
        Returns:
            dict: Streaming results and statistics
        """
        
        if self.is_streaming:
            return {'error': 'Already streaming'}
        
        self.is_streaming = True
        self.stream_stats['start_time'] = asyncio.get_event_loop().time()
        
        streams_to_process = streams or list(self.stream_configs.keys())
        
        logger.info(f"Starting binary VRS streaming for session {session_id}")
        logger.info(f"Streams: {streams_to_process}, Duration: {duration_seconds}s")
        
        try:
            # Process each stream
            for stream_name in streams_to_process:
                if not self.is_streaming:
                    break
                
                await self._stream_single_vrs_stream(session_id, stream_name, duration_seconds)
            
            # Stream sensor data in parallel
            await self._stream_mps_sensors(session_id, duration_seconds)
            
            return {
                'success': True,
                'session_id': session_id,
                'stats': self.get_streaming_stats(),
                'streams_processed': streams_to_process
            }
            
        except Exception as e:
            logger.error(f"VRS streaming error: {e}")
            self.stream_stats['errors'] += 1
            return {
                'success': False,
                'error': str(e),
                'stats': self.get_streaming_stats()
            }
        finally:
            self.is_streaming = False
    
    async def _stream_single_vrs_stream(self, 
                                       session_id: str, 
                                       stream_name: str,
                                       duration_seconds: Optional[int] = None):
        """Stream frames from a single VRS stream"""
        
        if stream_name not in self.stream_configs:
            logger.warning(f"Unknown stream: {stream_name}")
            return
        
        config = self.stream_configs[stream_name]
        stream_id = config['stream_id']
        sample_rate = config['sample_rate']
        
        try:
            num_frames = self.vrs_provider.get_num_data(stream_id)
            logger.info(f"Processing {stream_name}: {num_frames} frames at {sample_rate} FPS")
            
            # Calculate frame sampling based on desired FPS
            frame_interval = max(1, num_frames // (sample_rate * (duration_seconds or 30)))
            
            start_time = asyncio.get_event_loop().time()
            
            for frame_idx in range(0, num_frames, frame_interval):
                if not self.is_streaming:
                    break
                
                # Check duration limit
                if duration_seconds:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > duration_seconds:
                        break
                
                try:
                    # Get image data from VRS
                    image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                    
                    if image_data[0] is None:
                        continue
                    
                    # Convert to numpy array
                    numpy_image = image_data[0].to_numpy_array()
                    capture_timestamp = image_data[1].capture_timestamp_ns
                    
                    # Send via binary producer
                    result = self.producer.send_vrs_frame_binary(
                        session_id=session_id,
                        stream_id=str(stream_id),
                        numpy_image=numpy_image,
                        frame_index=frame_idx,
                        capture_timestamp_ns=capture_timestamp,
                        format=config['format'],
                        quality=self.compression_quality
                    )
                    
                    if result['success']:
                        self.stream_stats['frames_sent'] += 1
                        self.stream_stats['last_frame_time'] = asyncio.get_event_loop().time()
                        
                        logger.debug(f"Sent {stream_name} frame {frame_idx}: "
                                   f"{result['compression']['compressed_size']} bytes")
                    else:
                        logger.error(f"Failed to send {stream_name} frame {frame_idx}: "
                                   f"{result.get('error', 'unknown')}")
                        self.stream_stats['errors'] += 1
                    
                    # Throttle based on sample rate
                    await asyncio.sleep(1.0 / sample_rate)
                    
                except Exception as e:
                    logger.error(f"Error processing {stream_name} frame {frame_idx}: {e}")
                    self.stream_stats['errors'] += 1
                    
        except Exception as e:
            logger.error(f"Stream {stream_name} processing failed: {e}")
            self.stream_stats['errors'] += 1
    
    async def _stream_mps_sensors(self, 
                                 session_id: str,
                                 duration_seconds: Optional[int] = None):
        """Stream MPS sensor data (eye gaze, SLAM, hand tracking)"""
        
        try:
            logger.info("Streaming MPS sensor data...")
            
            # Eye gaze data
            await self._stream_eye_gaze_data(session_id, duration_seconds)
            
            # SLAM trajectory data  
            await self._stream_slam_data(session_id, duration_seconds)
            
            # Hand tracking data
            await self._stream_hand_tracking_data(session_id, duration_seconds)
            
            # IMU data
            await self._stream_imu_data(session_id, duration_seconds)
            
        except Exception as e:
            logger.error(f"MPS sensor streaming error: {e}")
            self.stream_stats['errors'] += 1
    
    async def _stream_eye_gaze_data(self, session_id: str, duration_seconds: Optional[int]):
        """Stream eye gaze MPS data"""
        try:
            # General eye gaze
            general_gaze = self.mps_provider.get_general_eye_gaze()
            if general_gaze:
                for gaze_data in general_gaze[:100]:  # Sample first 100 points
                    sensor_data = {
                        'tracking_timestamp_us': gaze_data.tracking_timestamp.total_seconds() * 1_000_000,
                        'yaw_rads': (gaze_data.yaw.left + gaze_data.yaw.right) / 2,
                        'pitch_rads': gaze_data.pitch,
                        'depth_m': gaze_data.depth,
                        'gaze_type': 'general'
                    }
                    
                    success = self.producer.send_sensor_data(
                        session_id, 'eye_gaze', sensor_data
                    )
                    
                    if success:
                        self.stream_stats['sensors_sent'] += 1
                    
                    await asyncio.sleep(0.01)  # 100 Hz
                    
        except Exception as e:
            logger.error(f"Eye gaze streaming error: {e}")
    
    async def _stream_slam_data(self, session_id: str, duration_seconds: Optional[int]):
        """Stream SLAM trajectory data"""
        try:
            trajectory = self.mps_provider.get_closed_loop_trajectory()
            if trajectory:
                for pose_data in trajectory.get_trajectory_in_device_frame()[:100]:
                    sensor_data = {
                        'tracking_timestamp_us': pose_data.tracking_timestamp.total_seconds() * 1_000_000,
                        'transform_world_device': self._serialize_transform(pose_data.transform_world_device),
                        'quality_score': getattr(pose_data, 'quality_score', 1.0)
                    }
                    
                    success = self.producer.send_sensor_data(
                        session_id, 'slam_trajectory', sensor_data
                    )
                    
                    if success:
                        self.stream_stats['sensors_sent'] += 1
                    
                    await asyncio.sleep(0.05)  # 20 Hz
                    
        except Exception as e:
            logger.error(f"SLAM streaming error: {e}")
    
    async def _stream_hand_tracking_data(self, session_id: str, duration_seconds: Optional[int]):
        """Stream hand tracking data"""
        try:
            hand_tracking = self.mps_provider.get_hand_tracking()
            if hand_tracking:
                for hand_data in hand_tracking[:50]:  # Sample first 50 points
                    sensor_data = {
                        'tracking_timestamp_us': hand_data.tracking_timestamp.total_seconds() * 1_000_000,
                        'left_hand_landmarks': self._serialize_hand_landmarks(hand_data.left_hand) if hand_data.left_hand else None,
                        'right_hand_landmarks': self._serialize_hand_landmarks(hand_data.right_hand) if hand_data.right_hand else None
                    }
                    
                    success = self.producer.send_sensor_data(
                        session_id, 'hand_tracking', sensor_data
                    )
                    
                    if success:
                        self.stream_stats['sensors_sent'] += 1
                    
                    await asyncio.sleep(0.1)  # 10 Hz
                    
        except Exception as e:
            logger.error(f"Hand tracking streaming error: {e}")
    
    async def _stream_imu_data(self, session_id: str, duration_seconds: Optional[int]):
        """Stream IMU sensor data"""
        try:
            for imu_name, config in self.imu_configs.items():
                stream_id = config['stream_id']
                num_data = self.vrs_provider.get_num_data(stream_id)
                
                # Sample IMU data (every 10th sample for demo)
                for idx in range(0, min(num_data, 1000), 10):
                    imu_data = self.vrs_provider.get_imu_data_by_index(stream_id, idx)
                    
                    if imu_data:
                        sensor_data = {
                            'device_timestamp_ns': imu_data[1].capture_timestamp_ns,
                            'accel_x': imu_data[0].accel_msec2[0],
                            'accel_y': imu_data[0].accel_msec2[1], 
                            'accel_z': imu_data[0].accel_msec2[2],
                            'gyro_x': imu_data[0].gyro_radsec[0],
                            'gyro_y': imu_data[0].gyro_radsec[1],
                            'gyro_z': imu_data[0].gyro_radsec[2],
                            'temperature_c': getattr(imu_data[0], 'temperature', None),
                            'imu_name': imu_name
                        }
                        
                        success = self.producer.send_sensor_data(
                            session_id, 'imu_data', sensor_data
                        )
                        
                        if success:
                            self.stream_stats['sensors_sent'] += 1
                    
                    await asyncio.sleep(0.001)  # 1000 Hz
                    
        except Exception as e:
            logger.error(f"IMU streaming error: {e}")
    
    def _serialize_transform(self, transform) -> list:
        """Serialize SE3 transform to list"""
        try:
            return transform.to_matrix().tolist()
        except:
            return None
    
    def _serialize_hand_landmarks(self, hand_data) -> list:
        """Serialize hand landmarks to list"""
        try:
            if hasattr(hand_data, 'landmarks'):
                return [[pt.x, pt.y, pt.z] for pt in hand_data.landmarks]
            return None
        except:
            return None
    
    def send_test_binary_frame(self, session_id: str = 'test-binary-vrs') -> Dict[str, Any]:
        """Send test binary frame"""
        return self.producer.send_test_binary_frame(session_id)
    
    def stop_streaming(self):
        """Stop current streaming operation"""
        self.is_streaming = False
        logger.info("VRS binary streaming stopped")
    
    def get_streaming_stats(self) -> Dict[str, Any]:
        """Get current streaming statistics"""
        current_time = asyncio.get_event_loop().time()
        
        stats = dict(self.stream_stats)
        
        if stats['start_time']:
            stats['duration_seconds'] = current_time - stats['start_time']
            if stats['duration_seconds'] > 0:
                stats['frames_per_second'] = stats['frames_sent'] / stats['duration_seconds']
                stats['sensors_per_second'] = stats['sensors_sent'] / stats['duration_seconds']
        
        return stats
    
    def close(self):
        """Close VRS streamer and producer"""
        self.stop_streaming()
        self.producer.close()
        logger.info("VRS binary streamer closed")