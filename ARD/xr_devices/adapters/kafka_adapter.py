"""
Kafka 스트리밍 어댑터
"""

from typing import Dict, Any, List
import asyncio
import json
import logging
from . import BaseStreamingAdapter, AdapterFactory

logger = logging.getLogger(__name__)


class KafkaStreamingAdapter(BaseStreamingAdapter):
    """Kafka 스트리밍 어댑터"""
    
    def __init__(self, protocol_type: str, config: Dict[str, Any]):
        super().__init__(protocol_type, config)
        self.bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')
        self.producer = None
        self.consumer = None
        self.topics = config.get('topics', {})
        
        # 기기별 토픽 매핑
        self.device_topics = {
            'meta_aria': {
                'camera_rgb': 'aria-camera-rgb',
                'camera_fisheye': 'aria-camera-slam',
                'eye_tracking': 'aria-eye-tracking',
                'imu': 'aria-imu',
                'gps': 'aria-gps',
                'sensors': 'aria-sensors-general'
            },
            'google_glass': {
                'camera_rgb': 'glass-camera-rgb',
                'voice': 'glass-voice-recognition',
                'sensors': 'glass-sensors-general'
            },
            'apple_vision': {
                'camera_rgb': 'vision-camera-rgb',
                'camera_depth': 'vision-camera-depth',
                'eye_tracking': 'vision-eye-tracking',
                'hand_tracking': 'vision-hand-tracking',
                'lidar': 'vision-lidar',
                'sensors': 'vision-sensors-general'
            }
        }
    
    async def connect(self) -> bool:
        """Kafka 연결 설정"""
        try:
            from kafka import KafkaProducer, KafkaConsumer
            
            # Producer 설정
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                retry_backoff_ms=100,
                request_timeout_ms=30000
            )
            
            # Consumer는 필요할 때 생성
            self.connected = True
            logger.info(f"Kafka adapter connected to {self.bootstrap_servers}")
            return True
            
        except ImportError:
            logger.error("kafka-python library not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Kafka 연결 종료"""
        try:
            if self.producer:
                self.producer.close()
                self.producer = None
            
            if self.consumer:
                self.consumer.close()
                self.consumer = None
            
            self.connected = False
            logger.info("Kafka adapter disconnected")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect from Kafka: {e}")
            return False
    
    async def send_data(self, data: Dict[str, Any], topic: str = None) -> bool:
        """Kafka로 데이터 전송"""
        if not self.connected or not self.producer:
            return False
        
        try:
            # 토픽 결정
            if not topic:
                device_type = data.get('device_type', 'unknown')
                sensor_type = data.get('sensor_type', 'unknown')
                topic = self._get_topic_for_sensor(device_type, sensor_type)
            
            # 메시지 키 생성 (파티셔닝을 위해)
            message_key = f"{data.get('device_type', 'unknown')}_{data.get('sensor_type', 'unknown')}"
            
            # 비동기 전송
            future = self.producer.send(topic, value=data, key=message_key)
            
            # 전송 결과 확인 (타임아웃 설정)
            record_metadata = await asyncio.to_thread(future.get, timeout=10)
            
            logger.debug(f"Data sent to Kafka topic '{topic}', partition {record_metadata.partition}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send data to Kafka: {e}")
            return False
    
    async def receive_data(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        """Kafka에서 데이터 수신"""
        if not self.connected:
            return []
        
        try:
            if not self.consumer:
                from kafka import KafkaConsumer
                import uuid
                
                # 모든 토픽 구독
                all_topics = []
                for device_topics in self.device_topics.values():
                    all_topics.extend(device_topics.values())
                
                self.consumer = KafkaConsumer(
                    *all_topics,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=f'xr-devices-consumer-{uuid.uuid4().hex[:8]}',
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    consumer_timeout_ms=timeout_ms
                )
            
            messages = []
            for message in self.consumer:
                messages.append({
                    'topic': message.topic,
                    'partition': message.partition,
                    'offset': message.offset,
                    'key': message.key.decode('utf-8') if message.key else None,
                    'value': message.value,
                    'timestamp': message.timestamp
                })
                
                if len(messages) >= 10:  # 한 번에 최대 10개 메시지
                    break
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to receive data from Kafka: {e}")
            return []
    
    def _get_topic_for_sensor(self, device_type: str, sensor_type: str) -> str:
        """센서 타입에 맞는 토픽 반환"""
        device_topics = self.device_topics.get(device_type, {})
        
        # 센서별 매핑
        sensor_topic_mapping = {
            'camera_rgb': 'camera_rgb',
            'camera_fisheye': 'camera_fisheye',
            'camera_depth': 'camera_depth',
            'eye_tracking': 'eye_tracking',
            'hand_tracking': 'hand_tracking',
            'imu': 'imu',
            'gps': 'gps',
            'voice_recognition': 'voice',
            'lidar': 'lidar'
        }
        
        mapped_sensor = sensor_topic_mapping.get(sensor_type, 'sensors')
        return device_topics.get(mapped_sensor, f'{device_type}-{sensor_type}')
    
    async def create_topics_if_needed(self, device_type: str) -> bool:
        """필요한 토픽들을 자동 생성"""
        try:
            from kafka.admin import KafkaAdminClient, NewTopic
            
            admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='xr_devices_admin'
            )
            
            # 기기별 필요한 토픽들
            device_topics = self.device_topics.get(device_type, {})
            
            topics_to_create = []
            for topic_name in device_topics.values():
                topic = NewTopic(
                    name=topic_name,
                    num_partitions=3,  # 3개 파티션
                    replication_factor=1  # 단일 브로커용
                )
                topics_to_create.append(topic)
            
            # 토픽 생성
            if topics_to_create:
                result = admin_client.create_topics(topics_to_create, validate_only=False)
                logger.info(f"Created topics for device type '{device_type}': {list(device_topics.values())}")
            
            admin_client.close()
            return True
            
        except Exception as e:
            logger.warning(f"Failed to create topics: {e}")
            return False


class WebSocketAdapter(BaseStreamingAdapter):
    """WebSocket 스트리밍 어댑터 (미래 기기용)"""
    
    async def connect(self) -> bool:
        # WebSocket 연결 로직
        self.connected = True
        return True
    
    async def disconnect(self) -> bool:
        self.connected = False
        return True
    
    async def send_data(self, data: Dict[str, Any], topic: str = None) -> bool:
        # WebSocket 전송 로직
        return True
    
    async def receive_data(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        # WebSocket 수신 로직
        return []


class MQTTAdapter(BaseStreamingAdapter):
    """MQTT 스트리밍 어댑터 (IoT 기기용)"""
    
    async def connect(self) -> bool:
        # MQTT 연결 로직
        self.connected = True
        return True
    
    async def disconnect(self) -> bool:
        self.connected = False
        return True
    
    async def send_data(self, data: Dict[str, Any], topic: str = None) -> bool:
        # MQTT 발행 로직
        return True
    
    async def receive_data(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        # MQTT 구독 로직
        return []


# 어댑터 등록
AdapterFactory.register_adapter('kafka', KafkaStreamingAdapter)
AdapterFactory.register_adapter('websocket', WebSocketAdapter)
AdapterFactory.register_adapter('mqtt', MQTTAdapter)