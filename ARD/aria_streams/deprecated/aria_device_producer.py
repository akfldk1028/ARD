"""
Project Aria Device Stream to Kafka Producer
실시간 Aria 장비 데이터를 Kafka로 스트리밍하는 Producer

Current Implementation: VRS-based simulation (for development)
Future: Real Device Stream API integration
"""

import asyncio
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from projectaria_tools.core import data_provider
from projectaria_tools.core.stream_id import StreamId, RecordableTypeId
from common.kafka.binary_producer import BinaryKafkaProducer
from .producers import AriaKafkaProducer

logger = logging.getLogger(__name__)

class AriaDeviceKafkaProducer:
    """
    Project Aria Device Stream to Kafka Producer
    
    Features:
    - Real-time RGB/SLAM/IMU streaming simulation
    - Adaptive quality based on performance
    - Frame dropping for latency control
    - Multiple stream support
    """
    
    def __init__(self, 
                 kafka_bootstrap_servers='ARD_KAFKA:9092',
                 vrs_file_path=None,  # For simulation, later replace with device connection
                 target_fps=30,
                 adaptive_quality=True,
                 replay_enabled=False,
                 replay_count=None,
                 replay_delay=2.0):
        
        self.kafka_servers = kafka_bootstrap_servers
        self.target_fps = target_fps
        self.adaptive_quality = adaptive_quality
        self.is_streaming = False
        
        # Replay configuration
        self.replay_enabled = replay_enabled
        self.replay_count = replay_count  # None = infinite replay
        self.replay_delay = replay_delay
        self.current_replay = 0
        
        # Performance metrics
        self.frames_sent = 0
        self.bytes_sent = 0
        self.last_fps_check = time.time()
        self.current_fps = 0
        
        # Kafka producers
        self.binary_producer = BinaryKafkaProducer(kafka_bootstrap_servers)
        self.metadata_producer = AriaKafkaProducer(kafka_bootstrap_servers)
        
        # Stream configuration
        self.stream_config = {
            'rgb': {
                'enabled': True,
                'target_fps': 30,
                'quality': 90,
                'max_size': (2048, 2048),
                'topic': 'aria-rgb-stream'
            },
            'slam_left': {
                'enabled': True,
                'target_fps': 30,
                'quality': 85,
                'max_size': (640, 480),
                'topic': 'aria-slam-stream'
            },
            'slam_right': {
                'enabled': True,
                'target_fps': 30,
                'quality': 85,
                'max_size': (640, 480),
                'topic': 'aria-slam-stream'
            },
            'imu': {
                'enabled': True,
                'target_hz': 1000,
                'topic': 'aria-sensor-stream'
            }
        }
        
        # Initialize data source (VRS simulation for now)
        if vrs_file_path:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            self.stream_ids = {
                'rgb': StreamId("214-1"),
                'slam_left': StreamId("1201-1"), 
                'slam_right': StreamId("1201-2"),
                'eye_tracking': StreamId("211-1")
            }
            
            # Get IMU streams dynamically
            self.imu_stream_ids = {}
            try:
                all_streams = self.vrs_provider.get_all_streams()
                for stream_id in all_streams:
                    if stream_id.get_type_id() == RecordableTypeId.SLAM_IMU_DATA:
                        label = self.vrs_provider.get_label_from_stream_id(stream_id)
                        self.imu_stream_ids[label] = stream_id
            except Exception as e:
                logger.warning(f"Could not get IMU streams: {e}")
                
        logger.info(f"AriaDeviceKafkaProducer initialized - Target FPS: {target_fps}")
    
    async def connect_to_device(self) -> bool:
        """
        Connect to Aria device (placeholder for real Device Stream API)
        Currently uses VRS file simulation
        """
        try:
            if hasattr(self, 'vrs_provider'):
                logger.info("✅ Connected to VRS data source (simulation mode)")
                return True
            else:
                logger.error("❌ No data source available")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to device: {e}")
            return False
    
    async def start_real_time_streaming(self, duration_seconds: Optional[int] = None) -> None:
        """
        Start real-time streaming to Kafka with replay support
        
        Args:
            duration_seconds: Optional duration limit per replay cycle
        """
        if not await self.connect_to_device():
            logger.error("Cannot start streaming - device connection failed")
            return
            
        self.current_replay = 0
        
        # Replay loop
        while self.replay_enabled or self.current_replay == 0:
            # Check replay count limit
            if self.replay_count is not None and self.current_replay >= self.replay_count:
                logger.info(f"🔄 Replay limit reached: {self.replay_count} cycles completed")
                break
            
            if self.current_replay > 0:
                logger.info(f"🔄 Starting VRS replay cycle #{self.current_replay + 1}")
                await asyncio.sleep(self.replay_delay)
                
            await self._run_single_streaming_cycle(duration_seconds)
            self.current_replay += 1
            
            # If replay is not enabled, break after first cycle
            if not self.replay_enabled:
                break
                
        logger.info(f"✅ VRS streaming completed - Total cycles: {self.current_replay}")
    
    async def _run_single_streaming_cycle(self, duration_seconds: Optional[int] = None) -> None:
        """
        Run a single streaming cycle (one complete VRS file playthrough)
        
        Args:
            duration_seconds: Optional duration limit for this cycle
        """
        self.is_streaming = True
        start_time = time.time()
        
        cycle_info = f"(cycle {self.current_replay + 1})" if self.replay_enabled else ""
        logger.info(f"🚀 Starting real-time Aria streaming to Kafka {cycle_info}")
        
        try:
            # Start parallel streaming tasks
            tasks = []
            
            if self.stream_config['rgb']['enabled']:
                tasks.append(self._stream_rgb_real_time(duration_seconds, start_time))
                
            if self.stream_config['slam_left']['enabled']:
                tasks.append(self._stream_slam_real_time('slam_left', duration_seconds, start_time))
                
            if self.stream_config['slam_right']['enabled']:
                tasks.append(self._stream_slam_real_time('slam_right', duration_seconds, start_time))
                
            if self.stream_config['imu']['enabled']:
                tasks.append(self._stream_imu_real_time(duration_seconds, start_time))
            
            # Performance monitoring task
            tasks.append(self._monitor_performance())
            
            # Run all streams in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Stream task {i} failed: {result}")
            
        except Exception as e:
            logger.error(f"❌ Streaming cycle error: {e}")
        finally:
            self.is_streaming = False
            cycle_info = f" (cycle {self.current_replay + 1})" if self.replay_enabled else ""
            logger.info(f"🛑 Streaming cycle completed{cycle_info}")
    
    async def _stream_rgb_real_time(self, duration_seconds: Optional[int], start_time: float):
        """Stream RGB camera data in real-time"""
        stream_name = 'rgb'
        stream_id = self.stream_ids[stream_name]
        config = self.stream_config[stream_name]
        
        num_frames = self.vrs_provider.get_num_data(stream_id)
        frame_interval = 1.0 / config['target_fps']  # Target interval between frames
        
        logger.info(f"📹 Starting RGB stream: {num_frames} frames @ {config['target_fps']}fps")
        
        frame_idx = 0
        last_frame_time = time.time()
        
        while self.is_streaming and frame_idx < num_frames:
            current_time = time.time()
            
            # Check duration limit
            if duration_seconds and (current_time - start_time) > duration_seconds:
                break
            
            # Frame rate control
            time_since_last = current_time - last_frame_time
            if time_since_last < frame_interval:
                await asyncio.sleep(frame_interval - time_since_last)
                continue
            
            try:
                # Get frame data
                image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                if image_data[0] is None:
                    frame_idx += 1
                    continue
                
                numpy_image = image_data[0].to_numpy_array()
                capture_timestamp = image_data[1].capture_timestamp_ns
                
                # Adaptive quality control
                quality = self._get_adaptive_quality(config, len(numpy_image.tobytes()))
                
                # Send to Kafka using binary producer
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.binary_producer.send_vrs_frame_binary,
                    'aria-real-time-session',
                    stream_name,
                    numpy_image,
                    frame_idx,
                    capture_timestamp,
                    'jpeg',
                    quality
                )
                
                if result['success']:
                    self.frames_sent += 1
                    self.bytes_sent += result.get('binary_size', 0)
                    
                    logger.debug(f"📤 RGB frame {frame_idx}: {result['compression']['compressed_size']} bytes "
                               f"(ratio: {result['compression']['compression_ratio']:.3f})")
                else:
                    logger.warning(f"❌ Failed to send RGB frame {frame_idx}: {result.get('error')}")
                
                frame_idx += 1
                last_frame_time = current_time
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.001)
                
            except Exception as e:
                logger.error(f"❌ Error processing RGB frame {frame_idx}: {e}")
                frame_idx += 1
    
    async def _stream_slam_real_time(self, stream_name: str, duration_seconds: Optional[int], start_time: float):
        """Stream SLAM camera data in real-time"""
        stream_id = self.stream_ids[stream_name]
        config = self.stream_config[stream_name]
        
        num_frames = self.vrs_provider.get_num_data(stream_id)
        frame_interval = 1.0 / config['target_fps']
        
        logger.info(f"📹 Starting {stream_name} stream: {num_frames} frames @ {config['target_fps']}fps")
        
        frame_idx = 0
        last_frame_time = time.time()
        
        while self.is_streaming and frame_idx < num_frames:
            current_time = time.time()
            
            if duration_seconds and (current_time - start_time) > duration_seconds:
                break
            
            time_since_last = current_time - last_frame_time
            if time_since_last < frame_interval:
                await asyncio.sleep(frame_interval - time_since_last)
                continue
            
            try:
                image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                if image_data[0] is None:
                    frame_idx += 1
                    continue
                
                numpy_image = image_data[0].to_numpy_array()
                capture_timestamp = image_data[1].capture_timestamp_ns
                
                quality = self._get_adaptive_quality(config, len(numpy_image.tobytes()))
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.binary_producer.send_vrs_frame_binary,
                    'aria-real-time-session',
                    stream_name,
                    numpy_image,
                    frame_idx,
                    capture_timestamp,
                    'jpeg',
                    quality
                )
                
                if result['success']:
                    self.frames_sent += 1
                    self.bytes_sent += result.get('binary_size', 0)
                    
                    logger.debug(f"📤 {stream_name} frame {frame_idx}: {result['compression']['compressed_size']} bytes")
                
                frame_idx += 1
                last_frame_time = current_time
                await asyncio.sleep(0.001)
                
            except Exception as e:
                logger.error(f"❌ Error processing {stream_name} frame {frame_idx}: {e}")
                frame_idx += 1
    
    async def _stream_imu_real_time(self, duration_seconds: Optional[int], start_time: float):
        """Stream IMU sensor data in real-time"""
        if not self.imu_stream_ids:
            logger.warning("No IMU streams available")
            return
        
        config = self.stream_config['imu']
        sample_interval = 1.0 / config['target_hz']  # Target interval between samples
        
        logger.info(f"📊 Starting IMU streams @ {config['target_hz']}Hz")
        
        for imu_name, imu_stream_id in self.imu_stream_ids.items():
            asyncio.create_task(self._stream_single_imu(imu_name, imu_stream_id, sample_interval, duration_seconds, start_time))
    
    async def _stream_single_imu(self, imu_name: str, imu_stream_id: StreamId, 
                                sample_interval: float, duration_seconds: Optional[int], start_time: float):
        """Stream single IMU sensor"""
        try:
            num_samples = self.vrs_provider.get_num_data(imu_stream_id)
            logger.info(f"📊 Starting {imu_name}: {num_samples} samples")
            
            sample_idx = 0
            last_sample_time = time.time()
            
            while self.is_streaming and sample_idx < num_samples:
                current_time = time.time()
                
                if duration_seconds and (current_time - start_time) > duration_seconds:
                    break
                
                time_since_last = current_time - last_sample_time
                if time_since_last < sample_interval:
                    await asyncio.sleep(sample_interval - time_since_last)
                    continue
                
                try:
                    imu_data = self.vrs_provider.get_imu_data_by_index(imu_stream_id, sample_idx)
                    if imu_data is None:
                        sample_idx += 1
                        continue
                    
                    accel_data = imu_data.accel_msec2
                    gyro_data = imu_data.gyro_radsec
                    
                    imu_payload = {
                        'imu_stream_id': str(imu_stream_id),
                        'imu_name': imu_name,
                        'device_timestamp_ns': imu_data.capture_timestamp_ns,
                        'accel_x': float(accel_data[0]),
                        'accel_y': float(accel_data[1]),
                        'accel_z': float(accel_data[2]),
                        'gyro_x': float(gyro_data[0]),
                        'gyro_y': float(gyro_data[1]),
                        'gyro_z': float(gyro_data[2]),
                        'temperature_c': float(imu_data.temperature) if hasattr(imu_data, 'temperature') else None
                    }
                    
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.metadata_producer.send_imu_data, imu_payload
                    )
                    
                    sample_idx += 1
                    last_sample_time = current_time
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {imu_name} sample {sample_idx}: {e}")
                    sample_idx += 1
                    
        except Exception as e:
            logger.error(f"❌ Error in {imu_name} streaming: {e}")
    
    async def _monitor_performance(self):
        """Monitor streaming performance"""
        while self.is_streaming:
            await asyncio.sleep(5)  # Report every 5 seconds
            
            current_time = time.time()
            time_elapsed = current_time - self.last_fps_check
            
            if time_elapsed >= 5.0:
                self.current_fps = self.frames_sent / time_elapsed
                throughput_mbps = (self.bytes_sent * 8 / (1024 * 1024)) / time_elapsed
                
                logger.info(f"📊 Performance: {self.current_fps:.1f} fps, "
                           f"{throughput_mbps:.2f} Mbps, "
                           f"{self.frames_sent} frames sent")
                
                # Reset counters
                self.frames_sent = 0
                self.bytes_sent = 0
                self.last_fps_check = current_time
    
    def _get_adaptive_quality(self, config: Dict[str, Any], frame_size: int) -> int:
        """Adaptive quality control based on performance"""
        if not self.adaptive_quality:
            return config['quality']
        
        base_quality = config['quality']
        
        # Reduce quality if FPS is falling behind
        if self.current_fps > 0 and self.current_fps < config['target_fps'] * 0.8:
            quality_reduction = min(20, int((config['target_fps'] - self.current_fps) * 2))
            return max(50, base_quality - quality_reduction)
        
        return base_quality
    
    def stop_streaming(self):
        """Stop all streaming operations"""
        self.is_streaming = False
        logger.info("🛑 Stopping Aria device streaming...")
    
    def close(self):
        """Close all connections and producers"""
        self.stop_streaming()
        if self.binary_producer:
            self.binary_producer.close()
        if self.metadata_producer:
            self.metadata_producer.close()
        logger.info("🔌 AriaDeviceKafkaProducer closed")
    
    def get_stream_status(self) -> Dict[str, Any]:
        """Get current streaming status"""
        return {
            'is_streaming': self.is_streaming,
            'current_fps': self.current_fps,
            'frames_sent': self.frames_sent,
            'bytes_sent': self.bytes_sent,
            'stream_config': self.stream_config
        }

# Convenience function for easy usage
async def start_aria_real_time_streaming(vrs_file_path: str, 
                                       kafka_servers: str = 'ARD_KAFKA:9092',
                                       duration_seconds: Optional[int] = None,
                                       target_fps: int = 30):
    """
    Start Aria real-time streaming (convenience function)
    
    Args:
        vrs_file_path: Path to VRS file (for simulation)
        kafka_servers: Kafka bootstrap servers
        duration_seconds: Optional duration limit
        target_fps: Target frames per second
    """
    producer = AriaDeviceKafkaProducer(
        kafka_bootstrap_servers=kafka_servers,
        vrs_file_path=vrs_file_path,
        target_fps=target_fps
    )
    
    try:
        await producer.start_real_time_streaming(duration_seconds)
    except KeyboardInterrupt:
        logger.info("Streaming interrupted by user")
    finally:
        producer.close()