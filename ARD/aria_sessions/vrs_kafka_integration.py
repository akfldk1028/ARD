"""
VRS와 Kafka 통합 스트리밍 서비스 - Observer 패턴 적용
공식 문서 패턴을 따라 VRS 데이터를 Kafka로 실시간 스트리밍
"""
import asyncio
import logging
import numpy as np
from typing import Dict, Any, Optional, List
from django.utils import timezone
import sys
import os
# Add ARD directory to path
ard_path = os.path.dirname(os.path.dirname(__file__))
if ard_path not in sys.path:
    sys.path.append(ard_path)

from common.kafka.vrs_kafka_producer import VRSKafkaProducer
from common.kafka.observers import VRSStreamingObserver
from .streaming_service import AriaUnifiedStreaming

logger = logging.getLogger(__name__)


class VRSKafkaStreamingService:
    """
    VRS 데이터를 Kafka로 실시간 스트리밍하는 서비스
    Observer 패턴으로 공식 문서 패턴 준수
    """
    
    def __init__(self, session_id: str, vrs_file_path: str = None):
        self.session_id = session_id
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        
        # Kafka components
        self.kafka_producer = VRSKafkaProducer()
        self.observer = VRSStreamingObserver(
            kafka_producer=self.kafka_producer,
            session_id=session_id,
            vrs_file_path=vrs_file_path
        )
        
        # VRS streaming service
        self.vrs_service = AriaUnifiedStreaming()
        
        # Streaming control
        self.streaming_task = None
        self.streaming_stats = {
            'frames_streamed': 0,
            'sensors_streamed': 0,
            'errors': 0,
            'start_time': None,
            'last_activity': None
        }
        
        logger.info(f"VRSKafkaStreamingService initialized for session: {session_id}")
    
    async def start_streaming(self, stream_config: Dict[str, Any] = None):
        """시작 VRS to Kafka 스트리밍"""
        if self.is_streaming:
            logger.warning(f"Streaming already active for session {self.session_id}")
            return False
        
        try:
            # Initialize VRS provider
            if not self.vrs_service.create_data_provider():
                raise Exception("Failed to create VRS data provider")
            
            # Send session start event
            await self.kafka_producer.send_session_event(
                'vrs_streaming_started',
                self.session_id,
                {
                    'vrs_file': self.vrs_file_path,
                    'config': stream_config or {},
                    'available_streams': self.vrs_service.get_stream_mappings()
                }
            )
            
            # Start observer
            self.observer.start_observation()
            
            # Configure streaming parameters
            active_streams = stream_config.get('active_streams') if stream_config else None
            max_frames = stream_config.get('max_frames', 1000) if stream_config else 1000
            include_images = stream_config.get('include_images', True) if stream_config else True
            
            # Start streaming task
            self.streaming_task = asyncio.create_task(
                self._stream_vrs_data(active_streams, max_frames, include_images)
            )
            
            self.is_streaming = True
            self.streaming_stats['start_time'] = timezone.now().isoformat()
            
            logger.info(f"Started VRS streaming for session {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start VRS streaming: {e}")
            await self.stop_streaming()
            return False
    
    async def _stream_vrs_data(self, active_streams: List[str] = None, max_frames: int = 1000, include_images: bool = True):
        """실제 VRS 데이터 스트리밍 루프"""
        try:
            # Get unified stream data using aria_sessions pattern
            unified_data = self.vrs_service.get_balanced_stream_data(
                max_images=max_frames if include_images else 0,
                max_sensors=max_frames,
                start_offset=0
            )
            
            logger.info(f"Processing {len(unified_data)} VRS data items for streaming")
            
            for data_item in unified_data:
                if not self.is_streaming:
                    break
                
                try:
                    # Update statistics
                    self.streaming_stats['last_activity'] = timezone.now().isoformat()
                    
                    # Process through observer pattern
                    await self._process_data_through_observer(data_item)
                    
                    # Also send directly to Kafka
                    if data_item.get('has_image_data'):
                        await self.kafka_producer.stream_vrs_image(
                            data_item.get('stream_label', 'unknown'),
                            data_item,
                            self.session_id
                        )
                        self.streaming_stats['frames_streamed'] += 1
                    elif data_item.get('has_sensor_data'):
                        await self.kafka_producer.stream_vrs_sensor(data_item, self.session_id)
                        self.streaming_stats['sensors_streamed'] += 1
                    
                    # Small delay to prevent overwhelming
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error processing VRS data item: {e}")
                    self.streaming_stats['errors'] += 1
            
            logger.info(f"VRS streaming completed for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"VRS streaming loop error: {e}")
            self.streaming_stats['errors'] += 1
        finally:
            await self.stop_streaming()
    
    async def _process_data_through_observer(self, data_item: Dict[str, Any]):
        """Observer 패턴으로 데이터 처리"""
        try:
            sensor_type = data_item.get('sensor_type', '')
            
            # Create mock record object for observer
            class MockRecord:
                def __init__(self, data):
                    self.capture_timestamp_ns = data.get('device_timestamp_ns', 0)
                    self.camera_id = data.get('stream_id', 'unknown')
                    self.confidence = 1.0
            
            record = MockRecord(data_item)
            
            # Route to appropriate observer method
            if 'IMAGE' in sensor_type and data_item.get('has_image_data'):
                # Create mock image array
                image_shape = data_item.get('image_shape', [480, 640, 3])
                mock_image = np.zeros(image_shape, dtype=np.uint8)
                self.observer.on_image_received(mock_image, record)
                
            elif 'IMU' in sensor_type and data_item.get('imu_data'):
                imu_data = data_item['imu_data']
                accel = np.array([
                    imu_data['accelerometer']['x'],
                    imu_data['accelerometer']['y'],
                    imu_data['accelerometer']['z']
                ])
                gyro = np.array([
                    imu_data['gyroscope']['x'],
                    imu_data['gyroscope']['y'],
                    imu_data['gyroscope']['z']
                ])
                self.observer.on_imu_received(accel, gyro, None, record)
                
            elif 'AUDIO' in sensor_type and data_item.get('audio_data'):
                # Mock audio array
                mock_audio = np.zeros((1024,), dtype=np.float32)
                self.observer.on_audio_received(mock_audio, record)
                
        except Exception as e:
            logger.error(f"Observer processing error: {e}")
    
    async def stop_streaming(self):
        """중지 VRS 스트리밍"""
        self.is_streaming = False
        
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
        
        # Stop observer
        final_stats = self.observer.stop_observation()
        
        # Send session end event
        await self.kafka_producer.send_session_event(
            'vrs_streaming_stopped',
            self.session_id,
            {
                'final_stats': final_stats,
                'streaming_stats': self.streaming_stats
            }
        )
        
        logger.info(f"Stopped VRS streaming for session {self.session_id}")
        return final_stats
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """현재 스트리밍 상태 조회"""
        return {
            'session_id': self.session_id,
            'is_streaming': self.is_streaming,
            'vrs_file_path': self.vrs_file_path,
            'streaming_stats': self.streaming_stats.copy(),
            'observer_stats': self.observer.get_vrs_statistics() if self.observer else None,
            'kafka_topics': self.kafka_producer.get_vrs_topics()
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """전체 시스템 건강 상태 확인"""
        try:
            kafka_health = await self.kafka_producer.health_check()
            
            return {
                'service': 'vrs_kafka_streaming',
                'session_id': self.session_id,
                'streaming_status': self.get_streaming_status(),
                'kafka_health': kafka_health,
                'overall_status': 'healthy' if kafka_health.get('producer_status') == 'healthy' else 'unhealthy',
                'last_check': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                'service': 'vrs_kafka_streaming',
                'session_id': self.session_id,
                'overall_status': 'error',
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }