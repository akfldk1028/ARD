"""
Aria Stream Manager - Producer와 Consumer 통합 관리
"""
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from ..producers.vrs_producer import VRSKafkaProducer
from ..consumers.streaming_consumer import StreamingKafkaConsumer, get_global_consumer
from ..config.kafka_config import KafkaConfig, DEFAULT_CONFIG
from ..utils.data_controller import DataFlowController

logger = logging.getLogger(__name__)

@dataclass
class StreamInfo:
    """스트림 정보"""
    name: str
    type: str  # 'image', 'sensor'
    status: str  # 'active', 'inactive', 'error'
    producer_active: bool
    consumer_active: bool
    message_count: int
    last_update: float
    error_message: Optional[str] = None

class AriaStreamManager:
    """
    Aria 스트림 매니저 - Producer/Consumer 통합 관리
    """
    
    def __init__(self, 
                 config: KafkaConfig = None,
                 vrs_file_path: str = None):
        """
        초기화
        
        Args:
            config: Kafka 설정
            vrs_file_path: VRS 파일 경로
        """
        self.config = config or DEFAULT_CONFIG
        self.vrs_file_path = vrs_file_path
        
        # Producer 및 Consumer
        self.producer: Optional[VRSKafkaProducer] = None
        self.consumer: StreamingKafkaConsumer = get_global_consumer()
        
        # 스트림 정의
        self.supported_streams = {
            # 이미지 스트림
            'camera-rgb': {'type': 'image', 'priority': 2, 'sample_rate': 0.5},
            'camera-slam-left': {'type': 'image', 'priority': 3, 'sample_rate': 0.3},
            'camera-slam-right': {'type': 'image', 'priority': 3, 'sample_rate': 0.3},
            'camera-eyetracking': {'type': 'image', 'priority': 1, 'sample_rate': 0.2},
            
            # 센서 스트림
            'imu-right': {'type': 'sensor', 'priority': 3, 'sample_rate': 0.1},
            'imu-left': {'type': 'sensor', 'priority': 3, 'sample_rate': 0.1},
            'magnetometer': {'type': 'sensor', 'priority': 2, 'sample_rate': 0.05},
            'barometer': {'type': 'sensor', 'priority': 2, 'sample_rate': 0.05},
            'microphone': {'type': 'sensor', 'priority': 1, 'sample_rate': 0.02}
        }
        
        # 활성 스트림 추적
        self.active_producers: Dict[str, threading.Thread] = {}
        self.producer_stop_flags: Dict[str, threading.Event] = {}
        
        # 통계
        self.stats = {
            'start_time': time.time(),
            'total_messages': 0,
            'total_errors': 0
        }
        
        logger.info(f"AriaStreamManager 초기화: {len(self.supported_streams)} 스트림 지원")
    
    def start_producer_stream(self, stream_name: str, fps: float = 10.0, duration: Optional[float] = None) -> bool:
        """
        Producer 스트림 시작
        
        Args:
            stream_name: 스트림 이름
            fps: 초당 프레임 수
            duration: 지속 시간 (초, None이면 무한)
            
        Returns:
            시작 성공 여부
        """
        if stream_name not in self.supported_streams:
            logger.error(f"지원하지 않는 스트림: {stream_name}")
            return False
        
        if stream_name in self.active_producers:
            logger.warning(f"이미 실행 중인 스트림: {stream_name}")
            return True
        
        try:
            # Producer 초기화 (필요시)
            if not self.producer:
                self.producer = VRSKafkaProducer(
                    config=self.config,
                    vrs_file_path=self.vrs_file_path
                )
            
            # 중지 플래그 생성
            stop_flag = threading.Event()
            self.producer_stop_flags[stream_name] = stop_flag
            
            # Producer 스레드 시작
            producer_thread = threading.Thread(
                target=self._producer_loop,
                args=(stream_name, fps, duration, stop_flag),
                daemon=True,
                name=f"Producer-{stream_name}"
            )
            
            self.active_producers[stream_name] = producer_thread
            producer_thread.start()
            
            logger.info(f"Producer 스트림 시작: {stream_name} ({fps} FPS)")
            return True
            
        except Exception as e:
            logger.error(f"Producer 스트림 시작 실패 ({stream_name}): {e}")
            return False
    
    def stop_producer_stream(self, stream_name: str) -> bool:
        """
        Producer 스트림 중지
        
        Args:
            stream_name: 스트림 이름
            
        Returns:
            중지 성공 여부
        """
        if stream_name not in self.active_producers:
            logger.warning(f"실행 중이지 않은 스트림: {stream_name}")
            return True
        
        try:
            # 중지 신호
            if stream_name in self.producer_stop_flags:
                self.producer_stop_flags[stream_name].set()
            
            # 스레드 종료 대기
            thread = self.active_producers[stream_name]
            thread.join(timeout=5.0)
            
            # 정리
            del self.active_producers[stream_name]
            if stream_name in self.producer_stop_flags:
                del self.producer_stop_flags[stream_name]
            
            logger.info(f"Producer 스트림 중지: {stream_name}")
            return True
            
        except Exception as e:
            logger.error(f"Producer 스트림 중지 실패 ({stream_name}): {e}")
            return False
    
    def _producer_loop(self, stream_name: str, fps: float, duration: Optional[float], stop_flag: threading.Event):
        """Producer 루프 (별도 스레드)"""
        frame_interval = 1.0 / fps
        start_time = time.time()
        frame_index = 0
        
        logger.info(f"Producer 루프 시작: {stream_name} ({fps} FPS)")
        
        try:
            while not stop_flag.is_set():
                # 지속 시간 체크
                if duration and (time.time() - start_time) > duration:
                    logger.info(f"Producer 지속 시간 만료: {stream_name}")
                    break
                
                # VRS 데이터 전송
                success = self.producer.send_vrs_data(stream_name, frame_index)
                
                if success:
                    self.stats['total_messages'] += 1
                else:
                    self.stats['total_errors'] += 1
                
                # 다음 프레임
                frame_index = (frame_index + 1) % 1000  # 1000 프레임 순환
                
                # FPS 조절
                time.sleep(frame_interval)
                
        except Exception as e:
            logger.error(f"Producer 루프 오류 ({stream_name}): {e}")
            self.stats['total_errors'] += 1
        
        logger.info(f"Producer 루프 종료: {stream_name}")
    
    def get_latest_data(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """스트림의 최신 데이터 가져오기"""
        return self.consumer.get_latest_message(stream_name)
    
    def get_recent_data(self, stream_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """스트림의 최근 N개 데이터 가져오기"""
        return self.consumer.get_recent_messages(stream_name, count)
    
    def get_stream_info(self, stream_name: str) -> StreamInfo:
        """스트림 정보 조회"""
        if stream_name not in self.supported_streams:
            return StreamInfo(
                name=stream_name,
                type='unknown',
                status='not_supported',
                producer_active=False,
                consumer_active=False,
                message_count=0,
                last_update=0.0,
                error_message='Unsupported stream'
            )
        
        # Consumer 상태
        consumer_status = self.consumer.get_stream_status(stream_name)
        
        # Producer 상태
        producer_active = stream_name in self.active_producers
        
        # 전체 상태 결정
        if producer_active and consumer_status['status'] == 'active':
            status = 'active'
        elif producer_active or consumer_status['status'] == 'active':
            status = 'partial'
        else:
            status = 'inactive'
        
        return StreamInfo(
            name=stream_name,
            type=self.supported_streams[stream_name]['type'],
            status=status,
            producer_active=producer_active,
            consumer_active=consumer_status['status'] == 'active',
            message_count=consumer_status['message_count'],
            last_update=consumer_status['last_update']
        )
    
    def get_all_streams_info(self) -> Dict[str, StreamInfo]:
        """모든 스트림 정보 조회"""
        return {
            stream_name: self.get_stream_info(stream_name)
            for stream_name in self.supported_streams.keys()
        }
    
    def get_image_streams(self) -> List[str]:
        """이미지 스트림 목록"""
        return [
            name for name, info in self.supported_streams.items()
            if info['type'] == 'image'
        ]
    
    def get_sensor_streams(self) -> List[str]:
        """센서 스트림 목록"""
        return [
            name for name, info in self.supported_streams.items()
            if info['type'] == 'sensor'
        ]
    
    def start_all_streams(self, fps: float = 5.0) -> Dict[str, bool]:
        """모든 스트림 시작"""
        results = {}
        for stream_name in self.supported_streams.keys():
            results[stream_name] = self.start_producer_stream(stream_name, fps)
        return results
    
    def stop_all_streams(self) -> Dict[str, bool]:
        """모든 스트림 중지"""
        results = {}
        for stream_name in list(self.active_producers.keys()):
            results[stream_name] = self.stop_producer_stream(stream_name)
        return results
    
    def get_system_stats(self) -> Dict[str, Any]:
        """시스템 통계"""
        runtime = time.time() - self.stats['start_time']
        
        # Producer 통계
        producer_stats = self.producer.get_stats() if self.producer else {}
        
        # Consumer 통계
        consumer_stats = self.consumer.get_stats()
        
        return {
            'runtime_seconds': runtime,
            'supported_streams': len(self.supported_streams),
            'active_producers': len(self.active_producers),
            'total_messages': self.stats['total_messages'],
            'total_errors': self.stats['total_errors'],
            'messages_per_second': self.stats['total_messages'] / max(runtime, 1),
            'producer_stats': producer_stats,
            'consumer_stats': consumer_stats,
            'stream_breakdown': {
                'images': len(self.get_image_streams()),
                'sensors': len(self.get_sensor_streams())
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """헬스 체크"""
        try:
            # Producer 상태
            producer_healthy = self.producer is not None and self.producer.is_connected if self.producer else False
            
            # Consumer 상태
            consumer_healthy = self.consumer.is_consuming
            
            # 전체 상태
            overall_status = 'healthy' if producer_healthy and consumer_healthy else 'degraded'
            
            return {
                'status': overall_status,
                'producer_healthy': producer_healthy,
                'consumer_healthy': consumer_healthy,
                'active_streams': len(self.active_producers),
                'last_check': time.time(),
                'uptime_seconds': time.time() - self.stats['start_time']
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'last_check': time.time()
            }
    
    def close(self):
        """리소스 정리"""
        logger.info("AriaStreamManager 종료 중...")
        
        # 모든 Producer 스트림 중지
        self.stop_all_streams()
        
        # Producer 정리
        if self.producer:
            self.producer.close()
        
        # Consumer는 전역이므로 별도 정리하지 않음
        
        logger.info("AriaStreamManager 종료 완료")
    
    def __del__(self):
        """소멸자"""
        self.close()

# 전역 Stream Manager 인스턴스
_global_manager: Optional[AriaStreamManager] = None

def get_global_manager(vrs_file_path: str = None) -> AriaStreamManager:
    """전역 Stream Manager 가져오기"""
    global _global_manager
    
    if _global_manager is None:
        _global_manager = AriaStreamManager(vrs_file_path=vrs_file_path)
    
    return _global_manager

def close_global_manager():
    """전역 Stream Manager 종료"""
    global _global_manager
    
    if _global_manager:
        _global_manager.close()
        _global_manager = None