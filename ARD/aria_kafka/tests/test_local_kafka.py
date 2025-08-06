"""
로컬 Kafka 연결 테스트
"""
import time
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError
import json

def test_kafka_connection():
    """Kafka 연결 테스트"""
    print("=== 로컬 Kafka 연결 테스트 ===\n")
    
    # 1. Producer 테스트
    print("1. Producer 연결 테스트...")
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            max_request_size=10485760  # 10MB
        )
        print("[OK] Producer 연결 성공")
        
        # 테스트 메시지 전송
        test_data = {
            'stream': 'test',
            'timestamp': time.time(),
            'data': 'Hello Kafka!'
        }
        
        future = producer.send('vrs-frames', value=test_data, key=b'test-key')
        result = future.get(timeout=10)
        print(f"[OK] 메시지 전송 성공: {result.topic}:{result.partition}:{result.offset}")
        
        producer.close()
        
    except Exception as e:
        print(f"[ERROR] Producer 오류: {e}")
        print("\nKafka가 실행 중인지 확인하세요:")
        print("1. Kafka 시작: start-kafka-windows.bat")
        print("2. 토픽 생성: create-topics-windows.bat")
        return False
    
    # 2. Consumer 테스트
    print("\n2. Consumer 연결 테스트...")
    try:
        consumer = KafkaConsumer(
            'vrs-frames',
            bootstrap_servers=['localhost:9092'],
            auto_offset_reset='latest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=5000  # 5초 타임아웃
        )
        print("[OK] Consumer 연결 성공")
        
        print("최근 메시지 확인 중...")
        message_count = 0
        for message in consumer:
            print(f"[OK] 수신: {message.topic}:{message.partition}:{message.offset}")
            print(f"     데이터: {message.value}")
            message_count += 1
            if message_count >= 1:
                break
        
        consumer.close()
        
    except Exception as e:
        print(f"[ERROR] Consumer 오류: {e}")
        return False
    
    # 3. Admin 테스트
    print("\n3. Admin Client 테스트...")
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=['localhost:9092'],
            client_id='test-admin'
        )
        
        # 토픽 목록
        topics = admin.list_topics()
        print(f"[OK] 토픽 개수: {len(topics)}")
        print("토픽 목록:")
        for topic in sorted(topics):
            if not topic.startswith('__'):  # 내부 토픽 제외
                print(f"  - {topic}")
        
        admin.close()
        
    except Exception as e:
        print(f"[ERROR] Admin 오류: {e}")
        return False
    
    print("\n=== 테스트 완료: Kafka 정상 작동 중 ===")
    return True

def test_stream_topics():
    """개별 스트림 토픽 테스트"""
    print("\n=== 스트림 토픽 테스트 ===\n")
    
    streams = [
        'stream-camera-rgb',
        'stream-camera-slam-left',
        'stream-imu-right',
        'stream-magnetometer'
    ]
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        for stream in streams:
            test_data = {
                'stream_name': stream,
                'timestamp': time.time(),
                'test': True
            }
            
            future = producer.send(stream, value=test_data)
            result = future.get(timeout=5)
            print(f"[OK] {stream}: 메시지 전송 성공")
        
        producer.close()
        print("\n모든 스트림 토픽 정상!")
        
    except Exception as e:
        print(f"[ERROR] 스트림 토픽 오류: {e}")

if __name__ == "__main__":
    # Kafka 연결 테스트
    if test_kafka_connection():
        # 스트림 토픽 테스트
        test_stream_topics()
    else:
        print("\nKafka 시작 방법:")
        print("1. cd %USERPROFILE%\\kafka\\kafka_2.13-3.6.0")
        print("2. start-kafka-windows.bat")
        print("3. create-topics-windows.bat (새 창에서)")