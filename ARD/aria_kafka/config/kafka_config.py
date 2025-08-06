"""
Kafka 설정 관리 - 데이터 처리량 최적화
"""
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class KafkaConfig:
    """Kafka 설정 클래스"""
    
    # 기본 연결 설정
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "aria-kafka-client"
    
    # Producer 최적화 설정 (데이터 터짐 방지)
    producer_config: Dict = None
    
    # Consumer 최적화 설정
    consumer_config: Dict = None
    
    # Topic 설정
    topics: Dict = None
    
    # 데이터 제어 설정
    max_batch_size: int = 100           # 배치당 최대 메시지 수
    max_message_size: int = 10485760    # 10MB
    compression_type: str = "gzip"       # 압축 사용
    buffer_memory: int = 33554432       # 32MB 버퍼
    
    def __post_init__(self):
        """초기화 후 설정 완료"""
        if self.producer_config is None:
            self.producer_config = self._get_optimized_producer_config()
        
        if self.consumer_config is None:
            self.consumer_config = self._get_optimized_consumer_config()
            
        if self.topics is None:
            self.topics = self._get_default_topics()
    
    def _get_optimized_producer_config(self) -> Dict:
        """Producer 최적화 설정 - 데이터 터짐 방지"""
        return {
            'bootstrap_servers': [self.bootstrap_servers],
            'client_id': f"{self.client_id}-producer",
            
            # 메시지 크기 제한
            'max_request_size': self.max_message_size,
            'message_max_bytes': self.max_message_size,
            
            # 배치 처리 최적화 (처리량 개선)
            'batch_size': 32768,          # 32KB 배치
            'linger_ms': 10,              # 10ms 대기로 배치 효율성 증대
            'buffer_memory': self.buffer_memory,
            
            # 압축 사용 (네트워크 부하 감소)
            'compression_type': self.compression_type,
            
            # 안정성 설정
            'acks': 1,                    # 리더만 확인 (성능 우선)
            'retries': 3,                 # 재시도
            'retry_backoff_ms': 100,
            
            # 직렬화
            'value_serializer': lambda v: self._serialize_message(v),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
            
            # 타임아웃
            'request_timeout_ms': 30000,  # 30초
            'delivery_timeout_ms': 120000, # 2분
        }
    
    def _get_optimized_consumer_config(self) -> Dict:
        """Consumer 최적화 설정"""
        return {
            'bootstrap_servers': [self.bootstrap_servers],
            'client_id': f"{self.client_id}-consumer",
            'group_id': 'aria-streaming-group',
            
            # 메시지 크기 제한
            'max_partition_fetch_bytes': self.max_message_size,
            'fetch_max_bytes': self.max_message_size * 5,  # 50MB
            
            # 자동 커밋 (간편함)
            'enable_auto_commit': True,
            'auto_commit_interval_ms': 1000,
            
            # 오프셋 설정
            'auto_offset_reset': 'latest',  # 최신 메시지부터
            
            # 역직렬화
            'value_deserializer': lambda m: self._deserialize_message(m),
            'key_deserializer': lambda k: k.decode('utf-8') if k else None,
            
            # 세션 타임아웃
            'session_timeout_ms': 30000,   # 30초
            'heartbeat_interval_ms': 3000,  # 3초
            
            # 폴링 설정
            'max_poll_records': self.max_batch_size,  # 배치 크기 제한
            'max_poll_interval_ms': 300000,  # 5분
        }
    
    def _get_default_topics(self) -> Dict:
        """기본 토픽 설정"""
        return {
            # VRS 원본 데이터 (압축됨)
            'vrs_frames': {
                'name': 'aria-vrs-frames-v2',
                'partitions': 3,
                'replication_factor': 1,
                'config': {
                    'compression.type': 'gzip',
                    'max.message.bytes': str(self.max_message_size),
                    'retention.ms': '86400000',  # 24시간
                }
            },
            
            # 실시간 센서 데이터 (경량화)
            'sensor_data': {
                'name': 'aria-sensors-v2',
                'partitions': 2,
                'replication_factor': 1,
                'config': {
                    'compression.type': 'gzip',
                    'max.message.bytes': '1048576',  # 1MB
                    'retention.ms': '3600000',  # 1시간
                }
            },
            
            # 이미지 메타데이터만 (실제 이미지는 별도 저장)
            'image_metadata': {
                'name': 'aria-images-meta-v2',
                'partitions': 2,
                'replication_factor': 1,
                'config': {
                    'compression.type': 'gzip',
                    'max.message.bytes': '1048576',  # 1MB
                    'retention.ms': '7200000',  # 2시간
                }
            },
            
            # 제어 메시지
            'control': {
                'name': 'aria-control-v2',
                'partitions': 1,
                'replication_factor': 1,
                'config': {
                    'retention.ms': '3600000',  # 1시간
                }
            }
        }
    
    def _serialize_message(self, value):
        """메시지 직렬화 - 압축 및 최적화"""
        import json
        import gzip
        
        if value is None:
            return None
            
        try:
            # JSON 직렬화
            json_data = json.dumps(value, ensure_ascii=False)
            json_bytes = json_data.encode('utf-8')
            
            # 큰 메시지는 압축
            if len(json_bytes) > 1024:  # 1KB 이상이면 압축
                return gzip.compress(json_bytes)
            else:
                return json_bytes
                
        except Exception as e:
            print(f"직렬화 오류: {e}")
            return json.dumps({'error': str(e)}).encode('utf-8')
    
    def _deserialize_message(self, message):
        """메시지 역직렬화"""
        import json
        import gzip
        
        if message is None:
            return None
            
        try:
            # 압축 해제 시도
            try:
                decompressed = gzip.decompress(message)
                return json.loads(decompressed.decode('utf-8'))
            except (gzip.BadGzipFile, OSError):
                # 압축되지 않은 데이터
                return json.loads(message.decode('utf-8'))
                
        except Exception as e:
            print(f"역직렬화 오류: {e}")
            return {'error': str(e)}
    
    @classmethod
    def from_environment(cls) -> 'KafkaConfig':
        """환경변수에서 설정 로드"""
        return cls(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
            client_id=os.getenv('KAFKA_CLIENT_ID', 'aria-kafka-client'),
            max_batch_size=int(os.getenv('KAFKA_MAX_BATCH_SIZE', '100')),
            max_message_size=int(os.getenv('KAFKA_MAX_MESSAGE_SIZE', '10485760')),
            compression_type=os.getenv('KAFKA_COMPRESSION_TYPE', 'gzip'),
        )

# 전역 설정 인스턴스
DEFAULT_CONFIG = KafkaConfig()

# 개발용 설정 (더 작은 배치, 더 빠른 응답)
DEV_CONFIG = KafkaConfig(
    max_batch_size=20,
    buffer_memory=16777216,  # 16MB
    compression_type="none"   # 압축 안함
)

# 운영용 설정 (더 큰 배치, 높은 처리량)
PROD_CONFIG = KafkaConfig(
    max_batch_size=500,
    buffer_memory=67108864,   # 64MB
    compression_type="gzip"   # 압축 사용
)