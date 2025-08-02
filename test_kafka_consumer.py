
#!/usr/bin/env python3
"""
Kafka 컨슈머 테스트 스크립트
각 토픽에서 메시지를 수신하고 실시간으로 출력
"""

import json
import signal
import sys
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import logging
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaConsumerTest:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.running = True
        
        # 각 토픽별 메시지 카운터
        self.message_counts = {
            'vrs-raw-stream': 0,
            'mps-eye-gaze-general': 0,
            'mps-hand-tracking': 0,
            'mps-slam-trajectory': 0,
            'test-topic': 0
        }
    
    def signal_handler(self, signum, frame):
        """Ctrl+C 처리"""
        logger.info("\n🛑 종료 신호 받음. 컨슈머를 종료합니다...")
        self.running = False
    
    def consume_topic(self, topic_name):
        """특정 토픽의 메시지를 소비"""
        try:
            consumer = KafkaConsumer(
                topic_name,
                bootstrap_servers=[self.bootstrap_servers],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # 새로운 메시지만 수신
                consumer_timeout_ms=1000
            )
            
            logger.info(f"🎧 {topic_name} 토픽 컨슈머 시작")
            
            for message in consumer:
                if not self.running:
                    break
                
                self.message_counts[topic_name] += 1
                data = message.value
                
                # 메시지 타입별로 다른 출력 형식
                if 'vrs' in topic_name:
                    logger.info(f"🎥 [{topic_name}] VRS Frame #{self.message_counts[topic_name]}: {data.get('stream_name', 'N/A')} - {data.get('frame_index', 'N/A')}")
                elif 'eye_gaze' in data.get('data_type', ''):
                    logger.info(f"👁️  [{topic_name}] Eye Gaze #{self.message_counts[topic_name]}: {data.get('timestamp', 'N/A')}")
                elif 'hand_tracking' in data.get('data_type', ''):
                    logger.info(f"✋ [{topic_name}] Hand Tracking #{self.message_counts[topic_name]}: {data.get('timestamp', 'N/A')}")
                elif 'slam' in topic_name:
                    logger.info(f"🗺️  [{topic_name}] SLAM #{self.message_counts[topic_name]}: {data.get('tracking_timestamp_ns', 'N/A')}")
                elif 'test' in data.get('data_type', ''):
                    logger.info(f"🧪 [{topic_name}] Test Message #{self.message_counts[topic_name]}: {data.get('message', 'N/A')}")
                else:
                    logger.info(f"📨 [{topic_name}] Message #{self.message_counts[topic_name]}: {data.get('data_type', 'Unknown')}")
                
                # 매 50개 메시지마다 통계 출력
                if self.message_counts[topic_name] % 50 == 0:
                    logger.info(f"📊 {topic_name}: 총 {self.message_counts[topic_name]}개 메시지 수신")
            
            consumer.close()
            
        except Exception as e:
            logger.error(f"❌ {topic_name} 컨슈머 오류: {e}")
    
    def start_multiple_consumers(self):
        """여러 토픽에 대해 동시에 컨슈머 실행"""
        topics = ['vrs-raw-stream', 'mps-eye-gaze-general', 'mps-hand-tracking', 'mps-slam-trajectory', 'test-topic']
        threads = []
        
        # 각 토픽에 대해 별도 스레드로 컨슈머 실행
        for topic in topics:
            thread = threading.Thread(target=self.consume_topic, args=(topic,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
            logger.info(f"🚀 {topic} 컨슈머 스레드 시작")
        
        try:
            # 메인 스레드에서 대기하면서 통계 출력
            while self.running:
                import time
                time.sleep(10)
                total_messages = sum(self.message_counts.values())
                if total_messages > 0:
                    logger.info(f"📈 통계 요약: {self.message_counts} (총 {total_messages}개)")
        
        except KeyboardInterrupt:
            logger.info("\n🛑 키보드 인터럽트로 종료")
            self.running = False
        
        # 모든 스레드 종료 대기
        for thread in threads:
            thread.join(timeout=2)
        
        logger.info("🏁 모든 컨슈머 종료 완료")

def main():
    logger.info("🎧 Kafka 컨슈머 테스트 시작")
    logger.info("📝 다음 토픽들을 실시간으로 모니터링합니다:")
    logger.info("   - mps-eye-gaze-general")
    logger.info("   - mps-hand-tracking") 
    logger.info("   - test-topic")
    logger.info("🔄 다른 터미널에서 test_kafka_connection.py를 실행하여 데이터를 스트리밍하세요!")
    logger.info("⏹️  종료하려면 Ctrl+C를 누르세요.\n")
    
    consumer_test = KafkaConsumerTest()
    
    # Ctrl+C 핸들러 설정
    signal.signal(signal.SIGINT, consumer_test.signal_handler)
    
    try:
        consumer_test.start_multiple_consumers()
    except Exception as e:
        logger.error(f"❌ 컨슈머 테스트 오류: {e}")

if __name__ == "__main__":
    main()