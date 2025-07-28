import asyncio
from projectaria_tools.core import data_provider, mps
from projectaria_tools.core.stream_id import StreamId
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions
from .producers import AriaKafkaProducer
import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class VRSKafkaStreamer:
    def __init__(self, vrs_file_path: str, mps_data_path: str, kafka_bootstrap_servers='localhost:9092'):
        self.vrs_file_path = vrs_file_path
        self.mps_data_path = mps_data_path
        self.producer = AriaKafkaProducer(kafka_bootstrap_servers)
        
        # Initialize data providers
        self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
        self.mps_provider = mps.MpsDataProvider(
            mps.MpsDataPathsProvider(mps_data_path).get_data_paths()
        )
        
        # Stream configurations
        self.stream_ids = {
            'rgb': StreamId("214-1"),
            'slam_left': StreamId("1201-1"), 
            'slam_right': StreamId("1201-2"),
            'eye_tracking': StreamId("211-1")
        }
        
        self.is_streaming = False
    
    def serialize_transform_matrix(self, transform):
        """Convert SE3 transform to serializable format"""
        try:
            matrix = transform.to_matrix()
            return matrix.tolist() if hasattr(matrix, 'tolist') else matrix
        except Exception as e:
            logger.error(f"Failed to serialize transform: {e}")
            return None
    
    def serialize_vector(self, vector):
        """Convert numpy vector to serializable format"""
        try:
            return vector.tolist() if hasattr(vector, 'tolist') else list(vector)
        except Exception as e:
            logger.error(f"Failed to serialize vector: {e}")
            return None
    
    async def stream_vrs_data(self, duration_seconds: Optional[int] = None):
        """Stream VRS image data to Kafka"""
        self.is_streaming = True
        start_time = asyncio.get_event_loop().time()
        
        try:
            for stream_name, stream_id in self.stream_ids.items():
                num_frames = self.vrs_provider.get_num_data(stream_id)
                logger.info(f"Starting {stream_name} stream with {num_frames} frames")
                
                for frame_idx in range(0, num_frames, 10):  # Sample every 10th frame
                    if not self.is_streaming:
                        break
                        
                    if duration_seconds and (asyncio.get_event_loop().time() - start_time) > duration_seconds:
                        break
                    
                    try:
                        image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                        if image_data[0] is None:
                            continue
                            
                        frame_data = {
                            'frame_index': frame_idx,
                            'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                            'stream_name': stream_name,
                            'image_shape': list(image_data[0].to_numpy_array().shape),
                            'pixel_format': str(image_data[0].pixel_format())
                        }
                        
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.producer.send_vrs_frame, stream_name, frame_data
                        )
                        
                        logger.debug(f"Sent {stream_name} frame {frame_idx}")
                        await asyncio.sleep(0.001)  # Small delay to prevent overwhelming
                        
                    except Exception as e:
                        logger.error(f"Error processing {stream_name} frame {frame_idx}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in VRS streaming: {e}")
        finally:
            self.is_streaming = False
    
    async def stream_mps_data(self, duration_seconds: Optional[int] = None):
        """Stream MPS processed data to Kafka"""
        self.is_streaming = True
        
        try:
            # Stream eye gaze data
            if self.mps_provider.has_general_eyegaze():
                await self._stream_eye_gaze_data('general')
            
            if self.mps_provider.has_personalized_eyegaze():
                await self._stream_eye_gaze_data('personalized')
            
            # Stream hand tracking data
            if self.mps_provider.has_hand_tracking_results():
                await self._stream_hand_tracking_data()
            
            # Stream SLAM data
            if self.mps_provider.has_closed_loop_poses():
                await self._stream_slam_trajectory_data()
                
        except Exception as e:
            logger.error(f"Error in MPS streaming: {e}")
        finally:
            self.is_streaming = False
    
    async def _stream_eye_gaze_data(self, gaze_type: str):
        """Stream eye gaze data"""
        try:
            if gaze_type == 'general':
                eye_gazes = mps.read_eyegaze(f"{self.mps_data_path}/eye_gaze/general_eye_gaze.csv")
            else:
                eye_gazes = mps.read_eyegaze(f"{self.mps_data_path}/eye_gaze/personalized_eye_gaze.csv")
            
            for i, gaze in enumerate(eye_gazes[::100]):  # Sample every 100th
                if not self.is_streaming:
                    break
                    
                gaze_data = {
                    'gaze_vector': self.serialize_vector(gaze.gaze_direction),
                    'depth': float(gaze.depth) if gaze.depth else None,
                    'tracking_timestamp_ns': int(gaze.tracking_timestamp.total_seconds() * 1e9)
                }
                
                await asyncio.get_event_loop().run_in_executor(
                    None, self.producer.send_eye_gaze, gaze_data, gaze_type
                )
                
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error streaming {gaze_type} eye gaze: {e}")
    
    async def _stream_hand_tracking_data(self):
        """Stream hand tracking data"""
        try:
            hand_results = mps.hand_tracking.read_hand_tracking_results(
                f"{self.mps_data_path}/hand_tracking/hand_tracking_results.csv"
            )
            
            for i, result in enumerate(hand_results[::50]):  # Sample every 50th
                if not self.is_streaming:
                    break
                    
                hand_data = {
                    'left_hand': self._serialize_hand_data(result.left_hand) if result.left_hand else None,
                    'right_hand': self._serialize_hand_data(result.right_hand) if result.right_hand else None,
                    'tracking_timestamp_ns': int(result.tracking_timestamp.total_seconds() * 1e9)
                }
                
                await asyncio.get_event_loop().run_in_executor(
                    None, self.producer.send_hand_tracking, hand_data
                )
                
                await asyncio.sleep(0.02)
                
        except Exception as e:
            logger.error(f"Error streaming hand tracking: {e}")
    
    def _serialize_hand_data(self, hand):
        """Serialize single hand data"""
        if not hand:
            return None
            
        return {
            'landmarks': [self.serialize_vector(landmark) for landmark in hand.landmark_positions_device],
            'wrist_palm_normal': {
                'wrist_normal': self.serialize_vector(hand.wrist_and_palm_normal_device.wrist_normal_device) if hand.wrist_and_palm_normal_device else None,
                'palm_normal': self.serialize_vector(hand.wrist_and_palm_normal_device.palm_normal_device) if hand.wrist_and_palm_normal_device else None,
            } if hand.wrist_and_palm_normal_device else None
        }
    
    async def _stream_slam_trajectory_data(self):
        """Stream SLAM trajectory data"""
        try:
            trajectory = mps.read_closed_loop_trajectory(
                f"{self.mps_data_path}/slam/closed_loop_trajectory.csv"
            )
            
            for i, pose in enumerate(trajectory[::1000]):  # Sample every 1000th
                if not self.is_streaming:
                    break
                    
                trajectory_data = {
                    'transform_world_device': self.serialize_transform_matrix(pose.transform_world_device),
                    'tracking_timestamp_ns': int(pose.tracking_timestamp.total_seconds() * 1e9)
                }
                
                await asyncio.get_event_loop().run_in_executor(
                    None, self.producer.send_slam_trajectory, trajectory_data
                )
                
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logger.error(f"Error streaming SLAM trajectory: {e}")
    
    def stop_streaming(self):
        """Stop all streaming operations"""
        self.is_streaming = False
    
    def close(self):
        """Close producer connection"""
        self.producer.close()
