#!/usr/bin/env python3
"""
Kafka 연결 테스트 스크립트
샘플 데이터를 Kafka로 스트리밍하는 테스트
"""

import json
import time
import csv
import os
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaConnectionTest:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.topics = [
            'vrs-raw-stream',
            'mps-eye-gaze-general', 
            'mps-eye-gaze-personalized',
            'mps-hand-tracking',
            'mps-slam-trajectory'
        ]
    
    def test_producer_connection(self):
        """Kafka 프로듀서 연결 테스트"""
        try:
            producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            
            # 테스트 메시지 전송
            test_message = {
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'Kafka connection test',
                'data_type': 'test'
            }
            
            future = producer.send('test-topic', value=test_message)
            result = future.get(timeout=10)
            
            logger.info(f"✅ Kafka Producer 연결 성공: {result}")
            producer.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Kafka Producer 연결 실패: {e}")
            return False
    
    def test_consumer_connection(self):
        """Kafka 컨슈머 연결 테스트"""
        try:
            consumer = KafkaConsumer(
                'test-topic',
                bootstrap_servers=[self.bootstrap_servers],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=5000
            )
            
            logger.info("✅ Kafka Consumer 연결 성공")
            consumer.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Kafka Consumer 연결 실패: {e}")
            return False
    
    def stream_sample_eye_gaze_data(self, duration=30):
        """샘플 eye gaze 데이터 스트리밍"""
        eye_gaze_file = "ARD/data/mps_samples/eye_gaze/general_eye_gaze.csv"
        
        if not os.path.exists(eye_gaze_file):
            logger.error(f"Eye gaze 파일을 찾을 수 없습니다: {eye_gaze_file}")
            return False
        
        try:
            producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            start_time = time.time()
            count = 0
            
            with open(eye_gaze_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if time.time() - start_time > duration:
                        break
                    
                    # 간단한 eye gaze 데이터 구조
                    gaze_data = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'data_type': 'eye_gaze_general',
                        'sample_data': dict(row)
                    }
                    
                    producer.send('mps-eye-gaze-general', value=gaze_data)
                    count += 1
                    
                    if count % 100 == 0:
                        logger.info(f"Eye gaze 데이터 {count}개 전송 완료")
                    
                    time.sleep(0.01)  # 10ms 간격
            
            producer.close()
            logger.info(f"✅ Eye gaze 데이터 스트리밍 완료: 총 {count}개 메시지")
            return True
            
        except Exception as e:
            logger.error(f"❌ Eye gaze 데이터 스트리밍 실패: {e}")
            return False
    
    def stream_sample_hand_tracking_data(self, duration=30):
        """샘플 hand tracking 데이터 스트리밍"""
        hand_file = "ARD/data/mps_samples/hand_tracking/hand_tracking_results.csv"
        
        if not os.path.exists(hand_file):
            logger.error(f"Hand tracking 파일을 찾을 수 없습니다: {hand_file}")
            return False
        
        try:
            producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            start_time = time.time()
            count = 0
            
            with open(hand_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if time.time() - start_time > duration:
                        break
                    
                    # 간단한 hand tracking 데이터 구조
                    hand_data = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'data_type': 'hand_tracking',
                        'sample_data': dict(row)
                    }
                    
                    producer.send('mps-hand-tracking', value=hand_data)
                    count += 1
                    
                    if count % 50 == 0:
                        logger.info(f"Hand tracking 데이터 {count}개 전송 완료")
                    
                    time.sleep(0.02)  # 20ms 간격
            
            producer.close()
            logger.info(f"✅ Hand tracking 데이터 스트리밍 완료: 총 {count}개 메시지")
            return True
            
        except Exception as e:
            logger.error(f"❌ Hand tracking 데이터 스트리밍 실패: {e}")
            return False

def main():
    logger.info("🚀 Kafka 연결 및 데이터 스트리밍 테스트 시작")
    
    tester = KafkaConnectionTest()
    
    # 1. Kafka 연결 테스트
    logger.info("\n1️⃣ Kafka Producer 연결 테스트")
    if not tester.test_producer_connection():
        logger.error("Kafka Producer 연결 실패. 도커 컨테이너를 확인해주세요.")
        return
    
    logger.info("\n2️⃣ Kafka Consumer 연결 테스트")
    if not tester.test_consumer_connection():
        logger.error("Kafka Consumer 연결 실패. 도커 컨테이너를 확인해주세요.")
        return
    
    # 2. 샘플 데이터 스트리밍 테스트
    logger.info("\n3️⃣ Eye Gaze 샘플 데이터 스트리밍 (30초)")
    tester.stream_sample_eye_gaze_data(30)
    
    logger.info("\n4️⃣ Hand Tracking 샘플 데이터 스트리밍 (30초)")
    tester.stream_sample_hand_tracking_data(30)
    
    logger.info("\n✅ 모든 테스트 완료!")

if __name__ == "__main__":
    main()