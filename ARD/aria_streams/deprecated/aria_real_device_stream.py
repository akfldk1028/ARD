"""
Real Project Aria Device Stream API Integration
진짜 Aria 장비에서 실시간 스트리밍 (바이너리 저장 없음)
"""

import asyncio
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import numpy as np

# Project Aria SDK imports
try:
    from projectaria_tools.core.stream_id import StreamId
    from projectaria_tools.core.calibration import CameraCalibration
    from projectaria_tools.core.sensor_data import ImageData, ImuData
    # Device Stream API imports (실제 SDK에서 import)
    from projectaria_tools.core.device import AriaDevice
    from projectaria_tools.core.streaming import StreamingManager, StreamingConfig, StreamingClient
    HAS_ARIA_SDK = True
except ImportError:
    HAS_ARIA_SDK = False
    print("Warning: Aria SDK not available. Using simulation mode.")

from common.kafka.binary_producer import BinaryKafkaProducer
from .producers import AriaKafkaProducer

logger = logging.getLogger(__name__)

class AriaRealDeviceStreamer:
    """
    실제 Project Aria Device Stream API를 사용한 실시간 스트리밍
    - 바이너리 저장 없음
    - 메모리에서 직접 Kafka로 스트리밍
    - 콜백 기반 실시간 처리
    """
    
    def __init__(self, 
                 kafka_bootstrap_servers='ARD_KAFKA:9092',
                 device_ip: Optional[str] = None,
                 streaming_mode='usb'):  # 'usb' or 'wifi'
        
        self.kafka_servers = kafka_bootstrap_servers
        self.device_ip = device_ip
        self.streaming_mode = streaming_mode
        self.is_streaming = False
        
        # Performance metrics
        self.frames_streamed = 0
        self.bytes_streamed = 0
        self.start_time = None
        
        # Kafka producers (바이너리 저장 안함, 직접 스트리밍)
        self.kafka_producer = AriaKafkaProducer(kafka_bootstrap_servers)
        
        # Aria Device & Streaming components
        self.device = None
        self.streaming_manager = None
        self.streaming_client = None
        self.streaming_config = None
        
        # Stream callbacks
        self.stream_callbacks = {
            'rgb': self._on_rgb_frame,
            'slam_left': self._on_slam_left_frame,
            'slam_right': self._on_slam_right_frame,
            'imu': self._on_imu_data,
            'eye_tracking': self._on_eye_tracking_frame
        }
        
    async def connect_to_device(self) -> bool:
        """
        Connect to real Aria device
        실제 Aria 장비에 연결
        """
        if not HAS_ARIA_SDK:
            logger.error("❌ Aria SDK not available. Cannot connect to real device.")
            return False
            
        try:
            logger.info(f"🔗 Connecting to Aria device via {self.streaming_mode.upper()}...")
            
            # Initialize Aria Device
            if self.streaming_mode == 'wifi' and self.device_ip:
                self.device = AriaDevice.connect_wifi(self.device_ip)
            else:
                self.device = AriaDevice.connect_usb()
            
            if not self.device:
                logger.error("❌ Failed to connect to Aria device")
                return False
                
            # Get streaming manager
            self.streaming_manager = self.device.streaming_manager
            
            # Configure streaming
            self.streaming_config = StreamingConfig()
            # 기본 설정 또는 커스텀 센서 프로필 사용
            
            # Create streaming client
            self.streaming_client = StreamingClient()
            
            logger.info("✅ Successfully connected to Aria device")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Aria device: {e}")
            return False
    
    async def start_real_time_streaming(self, duration_seconds: Optional[int] = None) -> None:
        """
        Start real-time streaming from Aria device
        실시간 스트리밍 시작 (바이너리 저장 없음)
        """
        if not await self.connect_to_device():
            logger.error("Cannot start streaming - device connection failed")
            return
            
        try:
            self.is_streaming = True
            self.start_time = time.time()
            
            logger.info("🚀 Starting real-time Aria device streaming...")
            
            # Register callbacks for each sensor stream
            self._register_stream_callbacks()
            
            # Start streaming
            self.streaming_manager.start_streaming()
            
            # Subscribe to data streams
            self.streaming_client.subscribe()
            
            logger.info("📡 Aria device streaming active - processing live data...")
            
            # Keep streaming for specified duration or indefinitely
            if duration_seconds:
                await asyncio.sleep(duration_seconds)
            else:
                # Stream until manually stopped
                while self.is_streaming:
                    await asyncio.sleep(1)
                    self._log_performance_stats()
                    
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
        finally:
            await self.stop_streaming()
    
    def _register_stream_callbacks(self):
        """
        Register callbacks for different sensor streams
        각 센서 스트림에 대한 콜백 등록
        """
        try:
            # RGB 카메라 콜백
            self.streaming_client.set_rgb_callback(self.stream_callbacks['rgb'])
            
            # SLAM 카메라 콜백
            self.streaming_client.set_slam_left_callback(self.stream_callbacks['slam_left'])
            self.streaming_client.set_slam_right_callback(self.stream_callbacks['slam_right'])
            
            # IMU 콜백
            self.streaming_client.set_imu_callback(self.stream_callbacks['imu'])
            
            # Eye tracking 콜백 (선택적)
            self.streaming_client.set_eye_tracking_callback(self.stream_callbacks['eye_tracking'])
            
            logger.info("✅ Stream callbacks registered")
            
        except Exception as e:
            logger.error(f"❌ Failed to register callbacks: {e}")
    
    def _on_rgb_frame(self, image_data: 'ImageData', device_timestamp_ns: int):
        """
        RGB 프레임 콜백 - 바이너리 저장 없이 바로 Kafka로 스트리밍
        """
        try:
            # numpy array로 변환
            numpy_image = image_data.to_numpy_array()
            
            # 바로 Kafka로 스트리밍 (저장 안함)
            asyncio.create_task(self._stream_frame_to_kafka(
                stream_type='rgb',
                numpy_image=numpy_image,
                device_timestamp_ns=device_timestamp_ns
            ))
            
        except Exception as e:
            logger.error(f"❌ RGB frame processing error: {e}")
    
    def _on_slam_left_frame(self, image_data: 'ImageData', device_timestamp_ns: int):
        """SLAM 왼쪽 카메라 콜백"""
        try:
            numpy_image = image_data.to_numpy_array()
            
            asyncio.create_task(self._stream_frame_to_kafka(
                stream_type='slam_left',
                numpy_image=numpy_image,
                device_timestamp_ns=device_timestamp_ns
            ))
            
        except Exception as e:
            logger.error(f"❌ SLAM left frame processing error: {e}")
    
    def _on_slam_right_frame(self, image_data: 'ImageData', device_timestamp_ns: int):
        """SLAM 오른쪽 카메라 콜백"""
        try:
            numpy_image = image_data.to_numpy_array()
            
            asyncio.create_task(self._stream_frame_to_kafka(
                stream_type='slam_right',
                numpy_image=numpy_image,
                device_timestamp_ns=device_timestamp_ns
            ))
            
        except Exception as e:
            logger.error(f"❌ SLAM right frame processing error: {e}")
    
    def _on_imu_data(self, imu_data: 'ImuData', device_timestamp_ns: int):
        """IMU 데이터 콜백"""
        try:
            imu_payload = {
                'session_id': 'aria-real-device-stream',
                'device_timestamp_ns': device_timestamp_ns,
                'accel_x': float(imu_data.accel_msec2[0]),
                'accel_y': float(imu_data.accel_msec2[1]),
                'accel_z': float(imu_data.accel_msec2[2]),
                'gyro_x': float(imu_data.gyro_radsec[0]),
                'gyro_y': float(imu_data.gyro_radsec[1]),
                'gyro_z': float(imu_data.gyro_radsec[2]),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # 바로 Kafka로 전송
            asyncio.create_task(self._stream_imu_to_kafka(imu_payload))
            
        except Exception as e:
            logger.error(f"❌ IMU data processing error: {e}")
    
    def _on_eye_tracking_frame(self, image_data: 'ImageData', device_timestamp_ns: int):
        """Eye tracking 콜백"""
        try:
            numpy_image = image_data.to_numpy_array()
            
            asyncio.create_task(self._stream_frame_to_kafka(
                stream_type='eye_tracking',
                numpy_image=numpy_image,
                device_timestamp_ns=device_timestamp_ns
            ))
            
        except Exception as e:
            logger.error(f"❌ Eye tracking frame processing error: {e}")
    
    async def _stream_frame_to_kafka(self, 
                                   stream_type: str, 
                                   numpy_image: np.ndarray, 
                                   device_timestamp_ns: int):
        """
        이미지 프레임을 바로 Kafka로 스트리밍 (저장 안함)
        """
        try:
            # JPEG 압축 (메모리에서만)
            import cv2
            success, buffer = cv2.imencode('.jpg', numpy_image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            if not success:
                logger.error(f"Failed to compress {stream_type} frame")
                return
                
            compressed_data = buffer.tobytes()
            
            # 메타데이터 준비
            metadata = {
                'stream_type': stream_type,
                'device_timestamp_ns': device_timestamp_ns,
                'timestamp': datetime.utcnow().isoformat(),
                'image_width': int(numpy_image.shape[1]),
                'image_height': int(numpy_image.shape[0]),
                'compressed_size': len(compressed_data),
                'compression_format': 'jpeg',
                'session_id': 'aria-real-device-stream'
            }
            
            # 바로 Kafka로 전송 (바이너리 저장 안함)
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.kafka_producer.send_real_time_frame,
                stream_type,
                compressed_data,
                metadata
            )
            
            # 성능 카운터 업데이트
            self.frames_streamed += 1
            self.bytes_streamed += len(compressed_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to stream {stream_type} frame: {e}")
    
    async def _stream_imu_to_kafka(self, imu_payload: Dict[str, Any]):
        """IMU 데이터를 바로 Kafka로 스트리밍"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.kafka_producer.send_imu_data,
                imu_payload
            )
        except Exception as e:
            logger.error(f"❌ Failed to stream IMU data: {e}")
    
    def _log_performance_stats(self):
        """성능 통계 로깅"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            fps = self.frames_streamed / elapsed if elapsed > 0 else 0
            throughput_mbps = (self.bytes_streamed * 8 / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            
            logger.info(f"📊 Real Device Stream: {fps:.1f} fps, "
                       f"{throughput_mbps:.2f} Mbps, "
                       f"{self.frames_streamed} frames")
    
    async def stop_streaming(self):
        """스트리밍 중지 및 리소스 정리"""
        self.is_streaming = False
        
        try:
            if self.streaming_client:
                self.streaming_client.unsubscribe()
                
            if self.streaming_manager:
                self.streaming_manager.stop_streaming()
                
            if self.device:
                self.device.disconnect()
                
            logger.info("🛑 Aria device streaming stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping streaming: {e}")
        finally:
            if self.kafka_producer:
                self.kafka_producer.close()
    
    def get_device_status(self) -> Dict[str, Any]:
        """장비 상태 조회"""
        return {
            'is_streaming': self.is_streaming,
            'frames_streamed': self.frames_streamed,
            'bytes_streamed': self.bytes_streamed,
            'streaming_mode': self.streaming_mode,
            'device_connected': self.device is not None
        }


# Convenience function for easy usage
async def start_aria_real_device_streaming(device_ip: Optional[str] = None,
                                         streaming_mode: str = 'usb',
                                         kafka_servers: str = 'ARD_KAFKA:9092',
                                         duration_seconds: Optional[int] = None):
    """
    실제 Aria 장비에서 실시간 스트리밍 시작
    
    Args:
        device_ip: Wi-Fi 모드일 때 장비 IP
        streaming_mode: 'usb' 또는 'wifi'
        kafka_servers: Kafka 서버 주소
        duration_seconds: 스트리밍 지속 시간 (None이면 무제한)
    """
    streamer = AriaRealDeviceStreamer(
        kafka_bootstrap_servers=kafka_servers,
        device_ip=device_ip,
        streaming_mode=streaming_mode
    )
    
    try:
        await streamer.start_real_time_streaming(duration_seconds)
    except KeyboardInterrupt:
        logger.info("Streaming interrupted by user")
    finally:
        await streamer.stop_streaming()