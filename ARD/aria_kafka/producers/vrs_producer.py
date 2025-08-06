"""
최적화된 VRS Kafka Producer - 데이터 터짐 방지 및 성능 최적화
"""
import time
import threading
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from queue import Queue, Full, Empty
import logging
import uuid
import cv2
import numpy as np
import base64

# Kafka 라이브러리
try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError, KafkaTimeoutError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Project Aria 라이브러리
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    from projectaria_tools.core.sensor_data import TimeDomain
    ARIA_AVAILABLE = True
except ImportError:
    ARIA_AVAILABLE = False

from ..config.kafka_config import KafkaConfig, DEFAULT_CONFIG
from ..utils.data_controller import DataFlowController, SmartSampler

logger = logging.getLogger(__name__)

@dataclass
class VRSMessage:
    """VRS 메시지 구조"""
    stream_id: str
    stream_name: str
    timestamp_ns: int
    data_type: str  # 'image', 'imu', 'magnetometer', 'barometer', 'audio'
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    priority: int = 1  # 1=낮음, 2=보통, 3=높음

class VRSKafkaProducer:
    """
    최적화된 VRS Kafka Producer
    - 데이터 처리량 제어
    - 스마트 샘플링
    - 백프레셔 처리
    - 배치 최적화
    """
    
    def __init__(self, 
                 config: KafkaConfig = None,
                 data_controller: DataFlowController = None,
                 vrs_file_path: str = None):
        """
        초기화
        
        Args:
            config: Kafka 설정
            data_controller: 데이터 플로우 컨트롤러
            vrs_file_path: VRS 파일 경로
        """
        self.config = config or DEFAULT_CONFIG
        self.data_controller = data_controller or DataFlowController()
        self.vrs_file_path = vrs_file_path
        
        # Kafka Producer
        self.producer: Optional[KafkaProducer] = None
        self.is_connected = False
        
        # VRS Provider
        self.vrs_provider = None
        self.stream_configs = {}
        
        # 처리 큐 (백프레셔 방지)
        self.message_queue = Queue(maxsize=1000)  # 1000개 메시지 버퍼
        self.processing_thread = None
        self.is_processing = False
        
        # 스마트 샘플러
        self.image_sampler = SmartSampler(sample_rate=0.3)  # 이미지 30% 샘플링
        self.sensor_sampler = SmartSampler(sample_rate=0.1) # 센서 10% 샘플링
        
        # 통계
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'messages_dropped': 0,
            'start_time': time.time()
        }
        
        # 초기화
        if KAFKA_AVAILABLE:
            self._init_kafka_producer()
        else:
            logger.warning("Kafka 라이브러리 없음 - Producer 비활성화")
        
        if ARIA_AVAILABLE and vrs_file_path:
            self._init_vrs_provider()
        else:
            logger.warning("Project Aria 라이브러리 없음 또는 VRS 파일 없음")
        
        # 처리 스레드 시작
        self._start_processing_thread()
        
        logger.info("VRSKafkaProducer 초기화 완료")
    
    def _init_kafka_producer(self):
        """Kafka Producer 초기화"""
        try:
            self.producer = KafkaProducer(**self.config.producer_config)
            self.is_connected = True
            logger.info(f"Kafka Producer 연결 성공: {self.config.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Kafka Producer 연결 실패: {e}")
            self.is_connected = False
    
    def _init_vrs_provider(self):
        """VRS Provider 초기화"""
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(self.vrs_file_path)
            
            # 스트림 설정 매핑
            self.stream_configs = {
                # 이미지 스트림
                'camera-rgb': {
                    'stream_id': StreamId("214-1"),
                    'type': 'image',
                    'topic': self.config.topics['image_metadata']['name'],
                    'priority': 2
                },
                'camera-slam-left': {
                    'stream_id': StreamId("1201-1"),
                    'type': 'image',
                    'topic': self.config.topics['image_metadata']['name'],
                    'priority': 3
                },
                'camera-slam-right': {
                    'stream_id': StreamId("1201-2"),
                    'type': 'image',
                    'topic': self.config.topics['image_metadata']['name'],
                    'priority': 3
                },
                'camera-eyetracking': {
                    'stream_id': StreamId("211-1"),
                    'type': 'image',
                    'topic': self.config.topics['image_metadata']['name'],
                    'priority': 1
                },
                
                # 센서 스트림
                'imu-right': {
                    'stream_id': StreamId("1202-1"),
                    'type': 'imu',
                    'topic': self.config.topics['sensor_data']['name'],
                    'priority': 3
                },
                'imu-left': {
                    'stream_id': StreamId("1202-2"),
                    'type': 'imu',
                    'topic': self.config.topics['sensor_data']['name'],
                    'priority': 3
                },
                'magnetometer': {
                    'stream_id': StreamId("1203-1"),
                    'type': 'magnetometer',
                    'topic': self.config.topics['sensor_data']['name'],
                    'priority': 2
                },
                'barometer': {
                    'stream_id': StreamId("247-1"),
                    'type': 'barometer',
                    'topic': self.config.topics['sensor_data']['name'],
                    'priority': 2
                },
                'microphone': {
                    'stream_id': StreamId("231-1"),
                    'type': 'audio',
                    'topic': self.config.topics['sensor_data']['name'],
                    'priority': 1
                }
            }
            
            logger.info(f"VRS Provider 초기화 완료: {len(self.stream_configs)} 스트림")
            
        except Exception as e:
            logger.error(f"VRS Provider 초기화 실패: {e}")
            self.vrs_provider = None
    
    def _start_processing_thread(self):
        """메시지 처리 스레드 시작"""
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._process_messages_loop, daemon=True)
        self.processing_thread.start()
        logger.info("메시지 처리 스레드 시작")
    
    def _process_messages_loop(self):
        """메시지 처리 루프 (별도 스레드)"""
        while self.is_processing:
            try:
                # 큐에서 메시지 가져오기 (1초 타임아웃)
                try:
                    message = self.message_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # 메시지 처리
                self._send_message_to_kafka(message)
                
            except Exception as e:
                logger.error(f"메시지 처리 루프 오류: {e}")
                time.sleep(0.1)
        
        logger.info("메시지 처리 루프 종료")
    
    def send_vrs_data(self, stream_name: str, frame_index: int = 0, force_send: bool = False) -> bool:
        """
        VRS 데이터 전송
        
        Args:
            stream_name: 스트림 이름 ('camera-rgb', 'imu-right' 등)
            frame_index: 프레임 인덱스
            force_send: 강제 전송 (샘플링 무시)
            
        Returns:
            전송 성공 여부
        """
        if not self.vrs_provider or stream_name not in self.stream_configs:
            logger.warning(f"알 수 없는 스트림: {stream_name}")
            return False
        
        stream_config = self.stream_configs[stream_name]
        stream_id = stream_config['stream_id']
        data_type = stream_config['type']
        
        try:
            # 데이터 타입별 처리
            if data_type == 'image':
                return self._send_image_data(stream_name, stream_id, frame_index, force_send)
            elif data_type == 'imu':
                return self._send_imu_data(stream_name, stream_id, frame_index, force_send)
            elif data_type == 'magnetometer':
                return self._send_magnetometer_data(stream_name, stream_id, frame_index, force_send)
            elif data_type == 'barometer':
                return self._send_barometer_data(stream_name, stream_id, frame_index, force_send)
            elif data_type == 'audio':
                return self._send_audio_data(stream_name, stream_id, frame_index, force_send)
            else:
                logger.warning(f"지원하지 않는 데이터 타입: {data_type}")
                return False
            
        except Exception as e:
            logger.error(f"VRS 데이터 전송 오류 ({stream_name}): {e}")
            return False
    
    def _send_image_data(self, stream_name: str, stream_id: StreamId, frame_index: int, force_send: bool) -> bool:
        """이미지 데이터 전송"""
        try:
            # 이미지 데이터 가져오기
            image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_index)
            
            if not image_data or image_data[0] is None:
                return False
            
            image_array = image_data[0].to_numpy_array()
            image_record = image_data[1]
            
            # 스마트 샘플링 확인
            if not force_send and not self.image_sampler.should_sample(stream_name, image_array.shape):
                self.stats['messages_dropped'] += 1
                return False
            
            # 이미지 압축 (메모리 절약)
            _, buffer = cv2.imencode('.jpg', image_array, [cv2.IMWRITE_JPEG_QUALITY, 75])
            compressed_data = buffer.tobytes()
            
            # 메타데이터만 Kafka로 전송 (실제 이미지는 별도 저장소 사용 권장)
            message = VRSMessage(
                stream_id=str(stream_id),
                stream_name=stream_name,
                timestamp_ns=image_record.capture_timestamp_ns,
                data_type='image',
                data={
                    'shape': list(image_array.shape),
                    'dtype': str(image_array.dtype),
                    'compressed_size': len(compressed_data),
                    'image_base64': base64.b64encode(compressed_data).decode('utf-8') if len(compressed_data) < 1048576 else None,  # 1MB 이하만 포함
                    'frame_index': frame_index
                },
                metadata={
                    'capture_timestamp_ns': image_record.capture_timestamp_ns,
                    'stream_name': stream_name,
                    'compression_quality': 75
                },
                priority=self.stream_configs[stream_name]['priority']
            )
            
            return self._queue_message(message)
            
        except Exception as e:
            logger.error(f"이미지 데이터 처리 오류 ({stream_name}): {e}")
            return False
    
    def _send_imu_data(self, stream_name: str, stream_id: StreamId, frame_index: int, force_send: bool) -> bool:
        """IMU 데이터 전송"""
        try:
            # IMU 데이터 가져오기
            imu_data = self.vrs_provider.get_imu_data_by_index(stream_id, frame_index)
            
            if not imu_data or imu_data[0] is None:
                return False
            
            imu_sensor_data = imu_data[0]
            imu_record = imu_data[1]
            
            # 센서 데이터 추출
            sensor_values = {
                'accel_x': float(imu_sensor_data.accel_msec2[0]),
                'accel_y': float(imu_sensor_data.accel_msec2[1]),
                'accel_z': float(imu_sensor_data.accel_msec2[2]),
                'gyro_x': float(imu_sensor_data.gyro_radsec[0]),
                'gyro_y': float(imu_sensor_data.gyro_radsec[1]),
                'gyro_z': float(imu_sensor_data.gyro_radsec[2]),
                'temperature': float(getattr(imu_sensor_data, 'temperature', 0.0))
            }
            
            # 스마트 샘플링 확인
            if not force_send and not self.sensor_sampler.should_sample(stream_name, sensor_values):
                self.stats['messages_dropped'] += 1
                return False
            
            message = VRSMessage(
                stream_id=str(stream_id),
                stream_name=stream_name,
                timestamp_ns=imu_record.capture_timestamp_ns,
                data_type='imu',
                data=sensor_values,
                metadata={
                    'capture_timestamp_ns': imu_record.capture_timestamp_ns,
                    'stream_name': stream_name,
                    'frame_index': frame_index,
                    'units': {
                        'acceleration': 'm/s²',
                        'angular_velocity': 'rad/s',
                        'temperature': '°C'
                    }
                },
                priority=self.stream_configs[stream_name]['priority']
            )
            
            return self._queue_message(message)
            
        except Exception as e:
            logger.error(f"IMU 데이터 처리 오류 ({stream_name}): {e}")
            return False
    
    def _send_magnetometer_data(self, stream_name: str, stream_id: StreamId, frame_index: int, force_send: bool) -> bool:
        """자력계 데이터 전송"""
        try:
            mag_data = self.vrs_provider.get_magnetometer_data_by_index(stream_id, frame_index)
            
            if not mag_data or mag_data[0] is None:
                return False
            
            mag_sensor_data = mag_data[0]
            mag_record = mag_data[1]
            
            sensor_values = {
                'mag_x': float(mag_sensor_data.mag_tesla[0]),
                'mag_y': float(mag_sensor_data.mag_tesla[1]),
                'mag_z': float(mag_sensor_data.mag_tesla[2]),
                'temperature': float(getattr(mag_sensor_data, 'temperature', 0.0))
            }
            
            if not force_send and not self.sensor_sampler.should_sample(stream_name, sensor_values):
                self.stats['messages_dropped'] += 1
                return False
            
            message = VRSMessage(
                stream_id=str(stream_id),
                stream_name=stream_name,
                timestamp_ns=mag_record.capture_timestamp_ns,
                data_type='magnetometer',
                data=sensor_values,
                metadata={
                    'capture_timestamp_ns': mag_record.capture_timestamp_ns,
                    'stream_name': stream_name,
                    'frame_index': frame_index,
                    'units': {'magnetic_field': 'Tesla', 'temperature': '°C'}
                },
                priority=self.stream_configs[stream_name]['priority']
            )
            
            return self._queue_message(message)
            
        except Exception as e:
            logger.error(f"자력계 데이터 처리 오류 ({stream_name}): {e}")
            return False
    
    def _send_barometer_data(self, stream_name: str, stream_id: StreamId, frame_index: int, force_send: bool) -> bool:
        """기압계 데이터 전송"""
        try:
            baro_data = self.vrs_provider.get_barometer_data_by_index(stream_id, frame_index)
            
            if not baro_data or baro_data[0] is None:
                return False
            
            baro_sensor_data = baro_data[0]
            baro_record = baro_data[1]
            
            sensor_values = {
                'pressure': float(baro_sensor_data.pressure),
                'temperature': float(baro_sensor_data.temperature)
            }
            
            if not force_send and not self.sensor_sampler.should_sample(stream_name, sensor_values):
                self.stats['messages_dropped'] += 1
                return False
            
            message = VRSMessage(
                stream_id=str(stream_id),
                stream_name=stream_name,
                timestamp_ns=baro_record.capture_timestamp_ns,
                data_type='barometer',
                data=sensor_values,
                metadata={
                    'capture_timestamp_ns': baro_record.capture_timestamp_ns,
                    'stream_name': stream_name,
                    'frame_index': frame_index,
                    'units': {'pressure': 'Pascal', 'temperature': '°C'}
                },
                priority=self.stream_configs[stream_name]['priority']
            )
            
            return self._queue_message(message)
            
        except Exception as e:
            logger.error(f"기압계 데이터 처리 오류 ({stream_name}): {e}")
            return False
    
    def _send_audio_data(self, stream_name: str, stream_id: StreamId, frame_index: int, force_send: bool) -> bool:
        """오디오 데이터 전송 (메타데이터만)"""
        try:
            audio_data = self.vrs_provider.get_audio_data_by_index(stream_id, frame_index)
            
            if not audio_data or audio_data[0] is None:
                return False
            
            audio_blocks = audio_data[0].audio_blocks
            audio_record = audio_data[1]
            
            # 오디오 메타데이터만 전송 (실제 오디오는 크기가 큼)
            audio_metadata = {
                'num_blocks': len(audio_blocks),
                'total_samples': sum(len(block.data) for block in audio_blocks),
                'channels': audio_blocks[0].num_channels if audio_blocks else 0,
                'sample_rate': 48000  # Project Aria 기본값
            }
            
            if not force_send and not self.sensor_sampler.should_sample(stream_name, audio_metadata):
                self.stats['messages_dropped'] += 1
                return False
            
            message = VRSMessage(
                stream_id=str(stream_id),
                stream_name=stream_name,
                timestamp_ns=audio_record.capture_timestamp_ns,
                data_type='audio',
                data=audio_metadata,
                metadata={
                    'capture_timestamp_ns': audio_record.capture_timestamp_ns,
                    'stream_name': stream_name,
                    'frame_index': frame_index
                },
                priority=self.stream_configs[stream_name]['priority']
            )
            
            return self._queue_message(message)
            
        except Exception as e:
            logger.error(f"오디오 데이터 처리 오류 ({stream_name}): {e}")
            return False
    
    def _queue_message(self, message: VRSMessage) -> bool:
        """메시지 큐에 추가"""
        try:
            # 큐가 가득 찬경우 처리
            try:
                self.message_queue.put(message, timeout=0.1)  # 100ms 타임아웃
                return True
            except Full:
                # 우선순위가 높은 메시지면 기존 메시지 제거 후 추가
                if message.priority >= 3:
                    try:
                        self.message_queue.get_nowait()  # 기존 메시지 제거
                        self.message_queue.put(message, timeout=0.1)
                        self.stats['messages_dropped'] += 1
                        return True
                    except Empty:
                        pass
                
                logger.warning(f"메시지 큐 가득참: {message.stream_name}")
                self.stats['messages_dropped'] += 1
                return False
                
        except Exception as e:
            logger.error(f"메시지 큐 추가 오류: {e}")
            return False
    
    def _send_message_to_kafka(self, message: VRSMessage):
        """Kafka로 메시지 전송"""
        if not self.is_connected or not self.producer:
            logger.warning("Kafka Producer 연결 안됨")
            return False
        
        try:
            stream_config = self.stream_configs.get(message.stream_name, {})
            topic = stream_config.get('topic', self.config.topics['vrs_frames']['name'])
            
            # 메시지 크기 계산
            message_dict = {
                'stream_id': message.stream_id,
                'stream_name': message.stream_name,
                'timestamp_ns': message.timestamp_ns,
                'data_type': message.data_type,
                'data': message.data,
                'metadata': message.metadata,
                'message_id': str(uuid.uuid4()),
                'producer_timestamp': time.time()
            }
            
            # 직렬화된 크기 추정
            estimated_size = len(str(message_dict))
            
            # 데이터 플로우 제어
            if self.data_controller.can_send_message(message.stream_name, estimated_size):
                # Kafka로 전송
                future = self.producer.send(
                    topic=topic,
                    key=message.stream_name,
                    value=message_dict
                )
                
                # 비동기 콜백 설정
                future.add_callback(lambda metadata: self._on_send_success(message, metadata, estimated_size))
                future.add_errback(lambda exception: self._on_send_error(message, exception))
                
                # 메트릭스 기록
                self.data_controller.record_message_sent(message.stream_name, estimated_size, True)
                
                return True
            else:
                # 레이트 리미트 대기
                wait_time = self.data_controller.wait_if_needed(message.stream_name, estimated_size)
                if wait_time > 0:
                    logger.debug(f"레이트 리미트 대기: {wait_time:.2f}s")
                
                self.stats['messages_dropped'] += 1
                return False
                
        except Exception as e:
            logger.error(f"Kafka 메시지 전송 오류: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    def _on_send_success(self, message: VRSMessage, metadata, message_size: int):
        """전송 성공 콜백"""
        self.stats['messages_sent'] += 1
        self.stats['bytes_sent'] += message_size
        logger.debug(f"메시지 전송 성공: {message.stream_name} -> {metadata.topic}")
    
    def _on_send_error(self, message: VRSMessage, exception):
        """전송 실패 콜백"""
        self.stats['messages_failed'] += 1
        logger.error(f"메시지 전송 실패: {message.stream_name} - {exception}")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        runtime = time.time() - self.stats['start_time']
        stats = self.stats.copy()
        stats.update({
            'runtime_seconds': runtime,
            'messages_per_second': self.stats['messages_sent'] / max(runtime, 1),
            'bytes_per_second': self.stats['bytes_sent'] / max(runtime, 1),
            'queue_size': self.message_queue.qsize(),
            'is_connected': self.is_connected,
            'controller_metrics': self.data_controller.get_all_metrics()
        })
        return stats
    
    def close(self):
        """리소스 정리"""
        logger.info("VRSKafkaProducer 종료 중...")
        
        # 처리 스레드 종료
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        
        # 남은 메시지 처리
        if self.producer:
            try:
                self.producer.flush(timeout=10)  # 10초 대기
                self.producer.close()
            except Exception as e:
                logger.error(f"Producer 종료 오류: {e}")
        
        logger.info("VRSKafkaProducer 종료 완료")
    
    def __del__(self):
        """소멸자"""
        self.close()