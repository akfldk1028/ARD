"""
Observer Pattern VRS Streamer
실시간 VRS 데이터 스트리밍을 위한 Observer 패턴 구현
Kafka 없이도 동작하며, 나중에 Kafka Producer를 Observer로 추가 가능
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from projectaria_tools.core import data_provider, mps
from projectaria_tools.core.stream_id import StreamId, RecordableTypeId
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions
import numpy as np
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# Observer 인터페이스
class VRSStreamObserver(ABC):
    """VRS 스트림 데이터를 관찰하는 Observer 인터페이스"""
    
    @abstractmethod
    async def on_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        """VRS 프레임 데이터 수신"""
        pass
    
    @abstractmethod
    async def on_mps_data(self, data_type: str, mps_data: Dict[str, Any]):
        """MPS 데이터 수신"""
        pass
    
    @abstractmethod
    async def on_stream_start(self, stream_info: Dict[str, Any]):
        """스트림 시작"""
        pass
    
    @abstractmethod
    async def on_stream_end(self, stream_info: Dict[str, Any]):
        """스트림 종료"""
        pass

# 구체적인 Observer 구현들
class DatabaseObserver(VRSStreamObserver):
    """데이터베이스에 데이터를 저장하는 Observer"""
    
    def __init__(self):
        self.session_id = None
    
    async def on_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        """VRS 프레임을 데이터베이스에 저장"""
        from .models import VRSStream
        try:
            vrs_stream = VRSStream(
                session_id=self.session_id,
                stream_id=stream_id,
                timestamp=frame_data.get('timestamp'),
                frame_number=frame_data.get('frame_number'),
                width=frame_data.get('width'),
                height=frame_data.get('height'),
                raw_data=frame_data.get('raw_data', b''),
                metadata=frame_data.get('metadata', {})
            )
            await asyncio.get_event_loop().run_in_executor(None, vrs_stream.save)
            logger.debug(f"VRS frame saved to database: {stream_id} frame {frame_data.get('frame_number')}")
        except Exception as e:
            logger.error(f"Database save error: {e}")
    
    async def on_mps_data(self, data_type: str, mps_data: Dict[str, Any]):
        """MPS 데이터를 데이터베이스에 저장"""
        try:
            if data_type == 'eye_gaze':
                from .models import EyeGazeData
                eye_gaze = EyeGazeData(
                    session_id=self.session_id,
                    timestamp=mps_data.get('timestamp'),
                    gaze_type=mps_data.get('gaze_type', 'general'),
                    yaw=mps_data.get('yaw'),
                    pitch=mps_data.get('pitch'),
                    depth=mps_data.get('depth'),
                    confidence=mps_data.get('confidence')
                )
                await asyncio.get_event_loop().run_in_executor(None, eye_gaze.save)
            
            elif data_type == 'hand_tracking':
                from .models import HandTrackingData
                hand_tracking = HandTrackingData(
                    session_id=self.session_id,
                    timestamp=mps_data.get('timestamp'),
                    has_left_hand=mps_data.get('has_left_hand', False),
                    has_right_hand=mps_data.get('has_right_hand', False),
                    left_hand_landmarks=mps_data.get('left_hand_landmarks', []),
                    right_hand_landmarks=mps_data.get('right_hand_landmarks', [])
                )
                await asyncio.get_event_loop().run_in_executor(None, hand_tracking.save)
            
            elif data_type == 'slam_trajectory':
                from .models import SLAMTrajectoryData
                slam_data = SLAMTrajectoryData(
                    session_id=self.session_id,
                    timestamp=mps_data.get('timestamp'),
                    position_x=mps_data.get('position_x'),
                    position_y=mps_data.get('position_y'),
                    position_z=mps_data.get('position_z'),
                    rotation_w=mps_data.get('rotation_w'),
                    rotation_x=mps_data.get('rotation_x'),
                    rotation_y=mps_data.get('rotation_y'),
                    rotation_z=mps_data.get('rotation_z')
                )
                await asyncio.get_event_loop().run_in_executor(None, slam_data.save)
            
            logger.debug(f"MPS data saved to database: {data_type}")
        except Exception as e:
            logger.error(f"MPS database save error: {e}")
    
    async def on_stream_start(self, stream_info: Dict[str, Any]):
        """스트림 시작 시 세션 ID 설정"""
        self.session_id = stream_info.get('session_id')
        logger.info(f"Database observer started for session {self.session_id}")
    
    async def on_stream_end(self, stream_info: Dict[str, Any]):
        """스트림 종료"""
        logger.info(f"Database observer ended for session {self.session_id}")

class LoggingObserver(VRSStreamObserver):
    """로깅을 위한 Observer"""
    
    async def on_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        logger.info(f"VRS Frame - Stream: {stream_id}, Frame: {frame_data.get('frame_number')}")
    
    async def on_mps_data(self, data_type: str, mps_data: Dict[str, Any]):
        logger.info(f"MPS Data - Type: {data_type}, Timestamp: {mps_data.get('timestamp')}")
    
    async def on_stream_start(self, stream_info: Dict[str, Any]):
        logger.info(f"Stream started: {stream_info}")
    
    async def on_stream_end(self, stream_info: Dict[str, Any]):
        logger.info(f"Stream ended: {stream_info}")

class KafkaObserver(VRSStreamObserver):
    """Kafka로 데이터를 전송하는 Observer (나중에 Kafka 연결 시 사용)"""
    
    def __init__(self, kafka_producer=None):
        self.kafka_producer = kafka_producer
        self.enabled = kafka_producer is not None
    
    async def on_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        if not self.enabled:
            return
        
        try:
            topic = f"aria-{stream_id.replace('/', '-')}-frames"
            message = {
                'stream_id': stream_id,
                'timestamp': frame_data.get('timestamp'),
                'frame_number': frame_data.get('frame_number'),
                'width': frame_data.get('width'),
                'height': frame_data.get('height'),
                'metadata': frame_data.get('metadata', {})
            }
            # Kafka 전송 로직 (나중에 구현)
            logger.debug(f"Would send to Kafka topic {topic}: {message}")
        except Exception as e:
            logger.error(f"Kafka send error: {e}")
    
    async def on_mps_data(self, data_type: str, mps_data: Dict[str, Any]):
        if not self.enabled:
            return
        
        try:
            topic = f"mps-{data_type}"
            # Kafka 전송 로직 (나중에 구현)
            logger.debug(f"Would send to Kafka topic {topic}: {mps_data}")
        except Exception as e:
            logger.error(f"Kafka MPS send error: {e}")
    
    async def on_stream_start(self, stream_info: Dict[str, Any]):
        if self.enabled:
            logger.info(f"Kafka observer started: {stream_info}")
    
    async def on_stream_end(self, stream_info: Dict[str, Any]):
        if self.enabled:
            logger.info(f"Kafka observer ended: {stream_info}")

# Subject (Observable)
class ObserverVRSStreamer:
    """
    Observer 패턴을 사용한 VRS 스트리머
    여러 Observer들에게 실시간으로 데이터를 전달
    """
    
    def __init__(self, vrs_file_path: str, mps_data_path: str = None):
        self.vrs_file_path = vrs_file_path
        self.mps_data_path = mps_data_path
        self.observers: List[VRSStreamObserver] = []
        self.data_provider = None
        self.mps_data_provider = None
        self.is_streaming = False
        self.session_id = None
        
        # Stream IDs
        self.stream_ids = {
            'rgb': StreamId("214-1"),  # RGB camera
            'slam_left': StreamId("1201-1"),  # SLAM left camera
            'slam_right': StreamId("1201-2"),  # SLAM right camera
            'eye_tracking': StreamId("211-1"),  # Eye tracking
            'imu_right': StreamId("1202-1"),  # IMU right
            'imu_left': StreamId("1202-2"),  # IMU left
        }
    
    def add_observer(self, observer: VRSStreamObserver):
        """Observer 추가"""
        self.observers.append(observer)
        logger.info(f"Observer added: {observer.__class__.__name__}")
    
    def remove_observer(self, observer: VRSStreamObserver):
        """Observer 제거"""
        if observer in self.observers:
            self.observers.remove(observer)
            logger.info(f"Observer removed: {observer.__class__.__name__}")
    
    async def notify_vrs_frame(self, stream_id: str, frame_data: Dict[str, Any]):
        """모든 Observer에게 VRS 프레임 알림"""
        tasks = []
        for observer in self.observers:
            tasks.append(observer.on_vrs_frame(stream_id, frame_data))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def notify_mps_data(self, data_type: str, mps_data: Dict[str, Any]):
        """모든 Observer에게 MPS 데이터 알림"""
        tasks = []
        for observer in self.observers:
            tasks.append(observer.on_mps_data(data_type, mps_data))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def notify_stream_start(self, stream_info: Dict[str, Any]):
        """모든 Observer에게 스트림 시작 알림"""
        tasks = []
        for observer in self.observers:
            tasks.append(observer.on_stream_start(stream_info))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def notify_stream_end(self, stream_info: Dict[str, Any]):
        """모든 Observer에게 스트림 종료 알림"""
        tasks = []
        for observer in self.observers:
            tasks.append(observer.on_stream_end(stream_info))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def initialize(self):
        """데이터 프로바이더 초기화"""
        try:
            # VRS 데이터 프로바이더 초기화
            self.data_provider = data_provider.create_vrs_data_provider(self.vrs_file_path)
            
            # MPS 데이터 프로바이더 초기화 (선택적)
            if self.mps_data_path:
                self.mps_data_provider = mps.get_eyegaze_reader(self.mps_data_path)
            
            logger.info(f"VRS data provider initialized: {self.vrs_file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize data providers: {e}")
            return False
    
    async def start_streaming(self, 
                            session_id: int,
                            duration_seconds: int = 60,
                            frame_skip: int = 5,
                            include_mps: bool = True):
        """
        VRS 스트리밍 시작
        
        Args:
            session_id: 세션 ID
            duration_seconds: 스트리밍 지속 시간 (초)
            frame_skip: 프레임 스킵 간격 (성능 최적화)
            include_mps: MPS 데이터 포함 여부
        """
        if self.is_streaming:
            logger.warning("Already streaming")
            return
        
        self.session_id = session_id
        self.is_streaming = True
        
        # 스트림 시작 알림
        stream_info = {
            'session_id': session_id,
            'vrs_file': self.vrs_file_path,
            'duration_seconds': duration_seconds,
            'frame_skip': frame_skip,
            'include_mps': include_mps,
            'start_time': datetime.now().isoformat()
        }
        await self.notify_stream_start(stream_info)
        
        try:
            # VRS 프레임 스트리밍
            await self.stream_vrs_frames(duration_seconds, frame_skip)
            
            # MPS 데이터 스트리밍 (선택적)
            if include_mps and self.mps_data_path:
                await self.stream_mps_data(duration_seconds)
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
        finally:
            self.is_streaming = False
            stream_info['end_time'] = datetime.now().isoformat()
            await self.notify_stream_end(stream_info)
    
    async def stream_vrs_frames(self, duration_seconds: int, frame_skip: int):
        """VRS 프레임 스트리밍"""
        start_time = time.time()
        frame_count = 0
        
        for stream_name, stream_id in self.stream_ids.items():
            if not self.data_provider.get_image_data_by_index(stream_id, 0):
                continue
            
            logger.info(f"Streaming {stream_name} frames...")
            
            # 프레임 스트리밍
            index = 0
            while time.time() - start_time < duration_seconds and self.is_streaming:
                try:
                    image_data = self.data_provider.get_image_data_by_index(stream_id, index)
                    if not image_data:
                        break
                    
                    # 프레임 스킵 적용
                    if index % frame_skip == 0:
                        # 프레임 데이터 준비
                        frame_data = {
                            'timestamp': float(image_data.capture_timestamp_ns) / 1e9,
                            'frame_number': index,
                            'width': image_data.image_data_and_record[0].width,
                            'height': image_data.image_data_and_record[0].height,
                            'raw_data': image_data.image_data_and_record[0].bytes(),
                            'metadata': {
                                'capture_timestamp_ns': image_data.capture_timestamp_ns,
                                'arrival_timestamp_ns': image_data.arrival_timestamp_ns,
                                'stream_name': stream_name
                            }
                        }
                        
                        # Observer들에게 알림
                        await self.notify_vrs_frame(str(stream_id), frame_data)
                        frame_count += 1
                    
                    index += 1
                    
                    # CPU 부하 조절을 위한 작은 지연
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Frame streaming error for {stream_name}: {e}")
                    break
        
        logger.info(f"VRS frame streaming completed. Total frames: {frame_count}")
    
    async def stream_mps_data(self, duration_seconds: int):
        """MPS 데이터 스트리밍"""
        if not self.mps_data_provider:
            return
        
        logger.info("Streaming MPS data...")
        start_time = time.time()
        
        try:
            # Eye gaze 데이터 스트리밍
            for gaze_data in self.mps_data_provider:
                if time.time() - start_time > duration_seconds:
                    break
                
                mps_data = {
                    'timestamp': float(gaze_data.timestamp_ns) / 1e9,
                    'gaze_type': 'general',
                    'yaw': gaze_data.yaw,
                    'pitch': gaze_data.pitch,
                    'depth': getattr(gaze_data, 'depth', None),
                    'confidence': getattr(gaze_data, 'confidence', None)
                }
                
                await self.notify_mps_data('eye_gaze', mps_data)
                await asyncio.sleep(0.01)  # CPU 부하 조절
        
        except Exception as e:
            logger.error(f"MPS data streaming error: {e}")
        
        logger.info("MPS data streaming completed")
    
    def stop_streaming(self):
        """스트리밍 중지"""
        self.is_streaming = False
        logger.info("Streaming stop requested")

# 편의 함수
async def create_default_streamer(vrs_file_path: str, mps_data_path: str = None) -> ObserverVRSStreamer:
    """기본 Observer들을 포함한 스트리머 생성"""
    streamer = ObserverVRSStreamer(vrs_file_path, mps_data_path)
    
    # 기본 Observer들 추가
    streamer.add_observer(DatabaseObserver())
    streamer.add_observer(LoggingObserver())
    streamer.add_observer(KafkaObserver())  # Kafka 비활성화 상태
    
    # 초기화
    if await streamer.initialize():
        return streamer
    else:
        raise Exception("Failed to initialize VRS streamer")