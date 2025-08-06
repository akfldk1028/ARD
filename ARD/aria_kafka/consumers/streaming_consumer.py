"""
최적화된 Kafka Consumer - 실시간 스트리밍용
"""
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque
from dataclasses import dataclass
import logging
import json
from queue import Queue, Empty, Full

# Kafka 라이브러리
try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

from ..config.kafka_config import KafkaConfig, DEFAULT_CONFIG
from ..utils.data_controller import DataFlowController

logger = logging.getLogger(__name__)

@dataclass
class ConsumedMessage:
    """소비된 메시지 구조"""
    topic: str
    partition: int
    offset: int
    key: str
    value: Dict[str, Any]
    timestamp: int
    received_at: float

class StreamBuffer:
    """스트림별 버퍼"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.messages = deque(maxlen=max_size)
        self.latest_message = None
        self.message_count = 0
        self.last_update = 0.0
    
    def add_message(self, message: ConsumedMessage):
        """메시지 추가"""
        self.messages.append(message)
        self.latest_message = message
        self.message_count += 1
        self.last_update = time.time()
    
    def get_latest(self) -> Optional[ConsumedMessage]:
        """최근 메시지 가져오기"""
        return self.latest_message
    
    def get_recent(self, count: int = 10) -> List[ConsumedMessage]:
        """최근 N개 메시지 가져오기"""
        return list(self.messages)[-count:]
    
    def clear(self):
        """버퍼 비우기"""
        self.messages.clear()
        self.latest_message = None

class StreamingKafkaConsumer:
    """
    실시간 스트리밍용 Kafka Consumer
    - 스트림별 버퍼링
    - 비동기 처리
    - 백프레셔 처리
    """
    
    def __init__(self, 
                 config: KafkaConfig = None,
                 data_controller: DataFlowController = None,
                 topics: List[str] = None):
        """
        초기화
        
        Args:
            config: Kafka 설정
            data_controller: 데이터 플로우 컨트롤러
            topics: 구독할 토픽 목록
        """
        self.config = config or DEFAULT_CONFIG
        self.data_controller = data_controller or DataFlowController()
        
        # 구독할 토픽들
        self.topics = topics or [
            self.config.topics['vrs_frames']['name'],
            self.config.topics['sensor_data']['name'],
            self.config.topics['image_metadata']['name']
        ]
        
        # Kafka Consumer
        self.consumer: Optional[KafkaConsumer] = None
        self.is_consuming = False
        self.consumer_thread = None
        
        # 스트림별 버퍼
        self.stream_buffers: Dict[str, StreamBuffer] = defaultdict(lambda: StreamBuffer(100))
        
        # 메시지 핸들러
        self.message_handlers: Dict[str, Callable] = {}
        
        # 통계
        self.stats = {
            'messages_consumed': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'bytes_consumed': 0,
            'start_time': time.time(),
            'last_message_time': 0.0
        }
        
        # 초기화
        if KAFKA_AVAILABLE:
            self._init_kafka_consumer()
        else:
            logger.warning("Kafka 라이브러리 없음 - Consumer 비활성화")
        
        logger.info(f"StreamingKafkaConsumer 초기화 완료: {len(self.topics)} 토픽 구독")
    
    def _init_kafka_consumer(self):
        """Kafka Consumer 초기화"""
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                **self.config.consumer_config
            )
            logger.info(f"Kafka Consumer 연결 성공: {self.topics}")
        except Exception as e:
            logger.error(f"Kafka Consumer 연결 실패: {e}")
            self.consumer = None
    
    def start_consuming(self):
        """소비 시작"""
        if not self.consumer:
            logger.error("Kafka Consumer 없음")
            return False
        
        if self.is_consuming:
            logger.warning("이미 소비 중")
            return True
        
        self.is_consuming = True
        self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.consumer_thread.start()
        
        logger.info("Kafka 소비 시작")
        return True
    
    def stop_consuming(self):
        """소비 중지"""
        if not self.is_consuming:
            return
        
        self.is_consuming = False
        
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5.0)
        
        if self.consumer:
            try:
                self.consumer.close()
            except Exception as e:
                logger.error(f"Consumer 종료 오류: {e}")
        
        logger.info("Kafka 소비 중지")
    
    def _consume_loop(self):
        """소비 루프 (별도 스레드)"""
        while self.is_consuming:
            try:
                # 메시지 배치 가져오기
                message_batch = self.consumer.poll(timeout_ms=1000, max_records=100)
                
                if not message_batch:
                    continue
                
                # 배치 처리
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        self._process_message(message)
                
                # 오프셋 커밋
                try:
                    self.consumer.commit()
                except Exception as e:
                    logger.warning(f"오프셋 커밋 실패: {e}")
                
            except Exception as e:
                logger.error(f"소비 루프 오류: {e}")
                time.sleep(1.0)
        
        logger.info("소비 루프 종료")
    
    def _process_message(self, kafka_message):
        """메시지 처리"""
        try:
            # 메시지 파싱
            consumed_message = ConsumedMessage(
                topic=kafka_message.topic,
                partition=kafka_message.partition,
                offset=kafka_message.offset,
                key=kafka_message.key.decode('utf-8') if kafka_message.key else None,
                value=kafka_message.value,  # 이미 역직렬화됨
                timestamp=kafka_message.timestamp,
                received_at=time.time()
            )
            
            # 스트림 이름 추출
            stream_name = consumed_message.key or 'unknown'
            
            # 버퍼에 추가
            self.stream_buffers[stream_name].add_message(consumed_message)
            
            # 커스텀 핸들러 실행
            if stream_name in self.message_handlers:
                try:
                    self.message_handlers[stream_name](consumed_message)
                except Exception as e:
                    logger.error(f"메시지 핸들러 오류 ({stream_name}): {e}")
                    self.stats['messages_failed'] += 1
            
            # 통계 업데이트
            self.stats['messages_consumed'] += 1
            self.stats['messages_processed'] += 1
            self.stats['bytes_consumed'] += len(str(consumed_message.value))
            self.stats['last_message_time'] = time.time()
            
            logger.debug(f"메시지 처리 완료: {stream_name} ({consumed_message.topic})")
            
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            self.stats['messages_failed'] += 1
    
    def register_handler(self, stream_name: str, handler: Callable[[ConsumedMessage], None]):
        """스트림별 메시지 핸들러 등록"""
        self.message_handlers[stream_name] = handler
        logger.info(f"핸들러 등록: {stream_name}")
    
    def get_latest_message(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """스트림의 최근 메시지 가져오기"""
        buffer = self.stream_buffers.get(stream_name)
        if not buffer:
            return None
        
        latest = buffer.get_latest()
        if not latest:
            return None
        
        return {
            'stream_name': stream_name,
            'data': latest.value,
            'timestamp': latest.timestamp,
            'received_at': latest.received_at,
            'topic': latest.topic,
            'offset': latest.offset
        }
    
    def get_recent_messages(self, stream_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """스트림의 최근 N개 메시지 가져오기"""
        buffer = self.stream_buffers.get(stream_name)
        if not buffer:
            return []
        
        recent = buffer.get_recent(count)
        return [
            {
                'stream_name': stream_name,
                'data': msg.value,
                'timestamp': msg.timestamp,
                'received_at': msg.received_at,
                'topic': msg.topic,
                'offset': msg.offset
            }
            for msg in recent
        ]
    
    def get_stream_status(self, stream_name: str) -> Dict[str, Any]:
        """스트림 상태 조회"""
        buffer = self.stream_buffers.get(stream_name)
        if not buffer:
            return {
                'stream_name': stream_name,
                'status': 'not_found',
                'message_count': 0,
                'last_update': 0.0
            }
        
        return {
            'stream_name': stream_name,
            'status': 'active' if time.time() - buffer.last_update < 10 else 'inactive',
            'message_count': buffer.message_count,
            'buffer_size': len(buffer.messages),
            'last_update': buffer.last_update,
            'has_latest': buffer.latest_message is not None
        }
    
    def get_all_stream_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 스트림 상태 조회"""
        return {
            stream_name: self.get_stream_status(stream_name)
            for stream_name in self.stream_buffers.keys()
        }
    
    def clear_stream_buffer(self, stream_name: str):
        """스트림 버퍼 비우기"""
        if stream_name in self.stream_buffers:
            self.stream_buffers[stream_name].clear()
            logger.info(f"스트림 버퍼 비움: {stream_name}")
    
    def clear_all_buffers(self):
        """모든 스트림 버퍼 비우기"""
        for buffer in self.stream_buffers.values():
            buffer.clear()
        logger.info("모든 스트림 버퍼 비움")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        runtime = time.time() - self.stats['start_time']
        stats = self.stats.copy()
        stats.update({
            'runtime_seconds': runtime,
            'messages_per_second': self.stats['messages_consumed'] / max(runtime, 1),
            'bytes_per_second': self.stats['bytes_consumed'] / max(runtime, 1),
            'active_streams': len([s for s in self.stream_buffers.values() if time.time() - s.last_update < 10]),
            'total_streams': len(self.stream_buffers),
            'is_consuming': self.is_consuming,
            'topics': self.topics
        })
        return stats
    
    def close(self):
        """리소스 정리"""
        logger.info("StreamingKafkaConsumer 종료 중...")
        self.stop_consuming()
        self.clear_all_buffers()
        logger.info("StreamingKafkaConsumer 종료 완료")
    
    def __del__(self):
        """소멸자"""
        self.close()

# 전역 Consumer 인스턴스 (싱글톤 패턴)
_global_consumer: Optional[StreamingKafkaConsumer] = None

def get_global_consumer() -> StreamingKafkaConsumer:
    """전역 Consumer 가져오기 (싱글톤)"""
    global _global_consumer
    
    if _global_consumer is None:
        _global_consumer = StreamingKafkaConsumer()
        _global_consumer.start_consuming()
    
    return _global_consumer

def close_global_consumer():
    """전역 Consumer 종료"""
    global _global_consumer
    
    if _global_consumer:
        _global_consumer.close()
        _global_consumer = None