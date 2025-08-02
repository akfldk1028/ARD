#!/usr/bin/env python3
"""
Kafka 데이터 로깅 시스템
프로듀서와 컨슈머의 모든 데이터를 상세히 로그 파일에 기록
"""

import json
import time
import csv
import os
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from datetime import datetime
import logging
import threading
import signal
from pathlib import Path

class KafkaDataLogger:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.running = True
        
        # 로그 디렉토리 생성
        self.log_dir = Path("kafka_logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 각 토픽별 로거 설정
        self.setup_loggers()
        
        self.topics = [
            'mps-eye-gaze-general',
            'mps-eye-gaze-personalized', 
            'mps-hand-tracking',
            'mps-slam-trajectory',
            'vrs-raw-stream',
            'test-topic'
        ]
        
        self.message_counts = {topic: 0 for topic in self.topics}
    
    def setup_loggers(self):
        """각 토픽별 로거 설정"""
        self.loggers = {}
        
        # 메인 로거 (전체 통계)
        main_logger = logging.getLogger('kafka_main')
        main_handler = logging.FileHandler(self.log_dir / 'kafka_main.log', encoding='utf-8')
        main_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        main_handler.setFormatter(main_formatter)
        main_logger.addHandler(main_handler)
        main_logger.setLevel(logging.INFO)
        self.loggers['main'] = main_logger
        
        # 각 토픽별 상세 로거
        topic_names = [
            'eye_gaze_general', 'eye_gaze_personalized', 
            'hand_tracking', 'slam_trajectory', 'vrs_raw', 'test'
        ]
        
        for topic_name in topic_names:
            logger = logging.getLogger(f'kafka_{topic_name}')
            handler = logging.FileHandler(self.log_dir / f'kafka_{topic_name}.log', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            self.loggers[topic_name] = logger
    
    def log_producer_data(self, topic_name, data, success=True):
        """프로듀서 데이터 로깅"""
        timestamp = datetime.now().isoformat()
        
        # 토픽 이름에서 로거 키 추출
        logger_key = self.get_logger_key(topic_name)
        
        if success:
            self.loggers['main'].info(f"✅ SENT [{topic_name}] - Size: {len(json.dumps(data))} bytes")
            self.loggers[logger_key].info(f"SENT DATA: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            self.loggers['main'].error(f"❌ FAILED [{topic_name}] - Data: {data}")
    
    def log_consumer_data(self, topic_name, data):
        """컨슈머 데이터 로깅"""
        logger_key = self.get_logger_key(topic_name)
        self.message_counts[topic_name] += 1
        
        self.loggers['main'].info(f"📨 RECEIVED [{topic_name}] #{self.message_counts[topic_name]} - Type: {data.get('data_type', 'Unknown')}")
        
        # 데이터 타입별로 상세 로깅
        if 'eye_gaze' in data.get('data_type', ''):
            self.log_eye_gaze_details(logger_key, data)
        elif 'hand_tracking' in data.get('data_type', ''):
            self.log_hand_tracking_details(logger_key, data)
        elif 'slam' in data.get('data_type', ''):
            self.log_slam_details(logger_key, data)
        else:
            self.loggers[logger_key].info(f"RECEIVED DATA: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    def log_eye_gaze_details(self, logger_key, data):
        """Eye gaze 데이터 상세 로깅"""
        sample_data = data.get('sample_data', {})
        
        details = f"""
=== EYE GAZE DATA ===
Timestamp: {data.get('timestamp')}
Data Type: {data.get('data_type')}
Sample Data Keys: {list(sample_data.keys())}
First 3 Sample Entries: {dict(list(sample_data.items())[:3])}
===========================
"""
        self.loggers[logger_key].info(details)
    
    def log_hand_tracking_details(self, logger_key, data):
        """Hand tracking 데이터 상세 로깅"""
        sample_data = data.get('sample_data', {})
        
        details = f"""
=== HAND TRACKING DATA ===
Timestamp: {data.get('timestamp')}
Data Type: {data.get('data_type')}
Sample Data Keys: {list(sample_data.keys())}
First 3 Sample Entries: {dict(list(sample_data.items())[:3])}
============================
"""
        self.loggers[logger_key].info(details)
    
    def log_slam_details(self, logger_key, data):
        """SLAM 데이터 상세 로깅"""
        details = f"""
=== SLAM DATA ===
Timestamp: {data.get('timestamp')}
Data Type: {data.get('data_type')}
Transform Matrix: {data.get('transform_world_device', 'N/A')}
Device Timestamp: {data.get('device_timestamp_ns', 'N/A')}
==================
"""
        self.loggers[logger_key].info(details)
    
    def get_logger_key(self, topic_name):
        """토픽 이름에서 로거 키 추출"""
        topic_map = {
            'mps-eye-gaze-general': 'eye_gaze_general',
            'mps-eye-gaze-personalized': 'eye_gaze_personalized',
            'mps-hand-tracking': 'hand_tracking',
            'mps-slam-trajectory': 'slam_trajectory',
            'vrs-raw-stream': 'vrs_raw',
            'test-topic': 'test'
        }
        return topic_map.get(topic_name, 'test')
    
    def enhanced_producer_test(self, duration=60):
        """로깅이 강화된 프로듀서 테스트"""
        self.loggers['main'].info(f"🚀 강화된 프로듀서 테스트 시작 - {duration}초 동안")
        
        try:
            producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            # Eye gaze 데이터 스트리밍
            self.stream_with_logging(producer, "ARD/data/mps_samples/eye_gaze/general_eye_gaze.csv", 
                                   "mps-eye-gaze-general", "eye_gaze_general", duration//2)
            
            # Hand tracking 데이터 스트리밍  
            self.stream_with_logging(producer, "ARD/data/mps_samples/hand_tracking/hand_tracking_results.csv",
                                   "mps-hand-tracking", "hand_tracking", duration//2)
            
            producer.close()
            self.loggers['main'].info("✅ 프로듀서 테스트 완료")
            
        except Exception as e:
            self.loggers['main'].error(f"❌ 프로듀서 테스트 실패: {e}")
    
    def stream_with_logging(self, producer, file_path, topic, data_type, duration):
        """파일에서 데이터를 읽어 로깅과 함께 스트리밍"""
        if not os.path.exists(file_path):
            self.loggers['main'].error(f"파일을 찾을 수 없음: {file_path}")
            return
        
        start_time = time.time()
        count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if time.time() - start_time > duration:
                    break
                
                data = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'data_type': data_type,
                    'sample_data': dict(row)
                }
                
                try:
                    producer.send(topic, value=data)
                    self.log_producer_data(topic, data, success=True)
                    count += 1
                    
                    if count % 100 == 0:
                        self.loggers['main'].info(f"📊 {topic}: {count}개 메시지 전송 완료")
                    
                    time.sleep(0.01)
                    
                except Exception as e:
                    self.log_producer_data(topic, data, success=False)
                    self.loggers['main'].error(f"전송 실패: {e}")
        
        self.loggers['main'].info(f"✅ {topic} 스트리밍 완료: 총 {count}개 메시지")
    
    def enhanced_consumer_test(self):
        """로깅이 강화된 컨슈머 테스트"""
        self.loggers['main'].info("🎧 강화된 컨슈머 테스트 시작")
        
        # 각 토픽별로 컨슈머 스레드 시작
        threads = []
        for topic in self.topics:
            thread = threading.Thread(target=self.consume_with_logging, args=(topic,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        try:
            while self.running:
                time.sleep(10)
                total = sum(self.message_counts.values())
                if total > 0:
                    self.loggers['main'].info(f"📈 전체 통계: {total}개 메시지 수신 - {self.message_counts}")
        
        except KeyboardInterrupt:
            self.loggers['main'].info("🛑 사용자 중단")
            self.running = False
        
        for thread in threads:
            thread.join(timeout=2)
        
        self.loggers['main'].info("🏁 컨슈머 테스트 완료")
    
    def consume_with_logging(self, topic):
        """로깅과 함께 메시지 소비"""
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[self.bootstrap_servers],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                consumer_timeout_ms=2000
            )
            
            for message in consumer:
                if not self.running:
                    break
                
                self.log_consumer_data(topic, message.value)
            
            consumer.close()
            
        except Exception as e:
            self.loggers['main'].error(f"❌ {topic} 컨슈머 오류: {e}")

def main():
    print("Kafka 데이터 로깅 시스템")
    print("로그 파일은 'kafka_logs/' 디렉토리에 저장됩니다")
    print("1: 프로듀서 + 로깅 테스트")
    print("2: 컨슈머 + 로깅 테스트") 
    print("3: 둘 다 동시에")
    
    choice = input("\n선택하세요 (1/2/3): ").strip()
    
    logger = KafkaDataLogger()
    
    def signal_handler(signum, frame):
        logger.running = False
        print("\n종료 중...")
    
    signal.signal(signal.SIGINT, signal_handler)
    
    if choice == '1':
        logger.enhanced_producer_test(60)
    elif choice == '2':
        logger.enhanced_consumer_test()
    elif choice == '3':
        # 프로듀서를 별도 스레드에서 실행
        import threading
        producer_thread = threading.Thread(target=lambda: logger.enhanced_producer_test(120))
        producer_thread.start()
        
        # 메인 스레드에서 컨슈머 실행
        logger.enhanced_consumer_test()
        
        producer_thread.join()
    else:
        print("잘못된 선택입니다.")

if __name__ == "__main__":
    main()