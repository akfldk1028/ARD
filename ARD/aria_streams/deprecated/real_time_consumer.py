"""
Real-Time Kafka Consumer for Direct Unity Streaming
바이너리 저장 없이 Kafka → WebSocket → Unity 직접 스트리밍
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import threading

logger = logging.getLogger(__name__)

class AriaRealTimeConsumer:
    """
    실시간 Kafka Consumer - 바이너리 저장 없이 바로 Unity로 스트리밍
    """
    
    def __init__(self, bootstrap_servers='ARD_KAFKA:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.is_consuming = False
        self.consumer_thread = None
        self.channel_layer = get_channel_layer()
        
        # 실시간 스트리밍 토픽들
        self.streaming_topics = {
            'vrs-binary-stream': self.handle_binary_frame,
            'vrs-metadata-stream': self.handle_frame_metadata,
            'aria-rgb-real-time': self.handle_real_time_frame,
            'aria-slam-real-time': self.handle_real_time_frame,
            'aria-et-real-time': self.handle_real_time_frame
        }
        
        # 성능 메트릭
        self.frames_processed = 0
        self.start_time = None
        
    def start_consuming(self):
        """실시간 소비 시작"""
        if self.is_consuming:
            logger.warning("Consumer already running")
            return
            
        self.is_consuming = True
        self.start_time = time.time()
        
        # 별도 스레드에서 Kafka 소비
        self.consumer_thread = threading.Thread(target=self._consume_loop)
        self.consumer_thread.daemon = True
        self.consumer_thread.start()
        
        logger.info("🚀 Real-time Kafka consumer started")
    
    def stop_consuming(self):
        """소비 중지"""
        self.is_consuming = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5)
        logger.info("🛑 Real-time Kafka consumer stopped")
    
    def _consume_loop(self):
        """메인 소비 루프"""
        try:
            consumer = KafkaConsumer(
                *list(self.streaming_topics.keys()),
                bootstrap_servers=[self.bootstrap_servers],
                group_id='aria-real-time-consumer',
                auto_offset_reset='latest',  # 실시간 스트리밍이므로 최신만
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=self._smart_deserializer,
                key_deserializer=lambda k: k.decode('utf-8') if k else None
            )
            
            logger.info(f"📡 Subscribed to topics: {list(self.streaming_topics.keys())}")
            
            for message in consumer:
                if not self.is_consuming:
                    break
                    
                topic = message.topic
                handler = self.streaming_topics.get(topic)
                
                if handler:
                    try:
                        # 비동기 핸들러를 동기적으로 실행
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            handler(message.value, message.key, message.offset)
                        )
                        loop.close()
                        
                        self.frames_processed += 1
                        
                        # 성능 로깅
                        if self.frames_processed % 10 == 0:
                            self._log_performance()
                            
                    except Exception as e:
                        logger.error(f"❌ Error processing message from {topic}: {e}")
                        
            consumer.close()
            
        except Exception as e:
            logger.error(f"❌ Consumer loop error: {e}")
    
    def _smart_deserializer(self, value):
        """스마트 역직렬화 - JSON 또는 바이너리"""
        if value is None:
            return None
        try:
            return json.loads(value.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return value  # 바이너리 데이터 그대로 반환
    
    async def handle_binary_frame(self, data: bytes, key: str, offset: int):
        """바이너리 프레임 처리 - 바로 Unity로 스트리밍"""
        try:
            if isinstance(data, bytes):
                # 바이너리 이미지 데이터를 base64로 인코딩
                import base64
                
                frame_data = {
                    'type': 'binary_frame',
                    'frame_id': key,
                    'timestamp': datetime.now().isoformat(),
                    'data_size': len(data),
                    'image_data': base64.b64encode(data).decode('utf-8'),
                    'format': 'jpeg'
                }
                
                # WebSocket을 통해 Unity에 직접 전송
                await self._send_to_unity_clients(frame_data)
                
                logger.debug(f"📤 Binary frame streamed to Unity: {key} ({len(data)} bytes)")
                
        except Exception as e:
            logger.error(f"❌ Error handling binary frame: {e}")
    
    async def handle_frame_metadata(self, data: dict, key: str, offset: int):
        """프레임 메타데이터 처리"""
        try:
            if isinstance(data, dict):
                metadata = {
                    'type': 'frame_metadata',
                    'frame_id': key,
                    'timestamp': datetime.now().isoformat(),
                    'metadata': data
                }
                
                await self._send_to_unity_clients(metadata)
                logger.debug(f"📤 Metadata streamed to Unity: {key}")
                
        except Exception as e:
            logger.error(f"❌ Error handling frame metadata: {e}")
    
    async def handle_real_time_frame(self, data: dict, key: str, offset: int):
        """실시간 프레임 처리 (새로운 Device Stream API 방식)"""
        try:
            if isinstance(data, dict) and 'image_data' in data:
                # hex string을 바이너리로 변환
                image_hex = data.get('image_data', '')
                image_binary = bytes.fromhex(image_hex)
                
                import base64
                frame_data = {
                    'type': 'real_time_frame',
                    'frame_id': key,
                    'timestamp': datetime.now().isoformat(),
                    'metadata': data.get('metadata', {}),
                    'data_size': len(image_binary),
                    'image_data': base64.b64encode(image_binary).decode('utf-8'),
                    'format': 'jpeg'
                }
                
                await self._send_to_unity_clients(frame_data)
                logger.debug(f"📤 Real-time frame streamed to Unity: {key}")
                
        except Exception as e:
            logger.error(f"❌ Error handling real-time frame: {e}")
    
    async def _send_to_unity_clients(self, frame_data: dict):
        """WebSocket을 통해 Unity 클라이언트들에게 전송"""
        try:
            if self.channel_layer:
                # 모든 Unity 클라이언트에게 브로드캐스트
                await self.channel_layer.group_send(
                    'aria_real_time_stream',  # WebSocket 그룹
                    {
                        'type': 'send_frame_data',
                        'frame_data': frame_data
                    }
                )
        except Exception as e:
            logger.error(f"❌ Error sending to Unity clients: {e}")
    
    def _log_performance(self):
        """성능 로깅"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            fps = self.frames_processed / elapsed if elapsed > 0 else 0
            
            logger.info(f"📊 Real-time streaming: {fps:.1f} fps, "
                       f"{self.frames_processed} frames processed")
    
    def get_status(self) -> Dict[str, Any]:
        """소비자 상태 반환"""
        return {
            'is_consuming': self.is_consuming,
            'frames_processed': self.frames_processed,
            'topics': list(self.streaming_topics.keys()),
            'uptime_seconds': time.time() - self.start_time if self.start_time else 0
        }


# Unity용 WebSocket Consumer
class UnityStreamConsumer:
    """
    Unity WebSocket Consumer - 실시간 프레임 수신
    """
    
    async def connect(self):
        """WebSocket 연결"""
        await self.accept()
        await self.channel_layer.group_add('aria_real_time_stream', self.channel_name)
        logger.info("Unity client connected to real-time stream")
    
    async def disconnect(self, close_code):
        """WebSocket 연결 해제"""
        await self.channel_layer.group_discard('aria_real_time_stream', self.channel_name)
        logger.info("Unity client disconnected from real-time stream")
    
    async def send_frame_data(self, event):
        """Unity에 프레임 데이터 전송"""
        frame_data = event['frame_data']
        await self.send(text_data=json.dumps(frame_data))


# 전역 실시간 소비자 인스턴스
_real_time_consumer = None

def start_real_time_consumer():
    """전역 실시간 소비자 시작"""
    global _real_time_consumer
    
    if _real_time_consumer is None:
        _real_time_consumer = AriaRealTimeConsumer()
    
    if not _real_time_consumer.is_consuming:
        _real_time_consumer.start_consuming()
        return True
    return False

def stop_real_time_consumer():
    """전역 실시간 소비자 중지"""
    global _real_time_consumer
    
    if _real_time_consumer and _real_time_consumer.is_consuming:
        _real_time_consumer.stop_consuming()
        return True
    return False

def get_real_time_consumer_status():
    """실시간 소비자 상태 반환"""
    global _real_time_consumer
    
    if _real_time_consumer:
        return _real_time_consumer.get_status()
    return {'is_consuming': False, 'frames_processed': 0}