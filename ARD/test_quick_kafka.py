"""
빠른 Kafka 테스트 - VRS 로딩 최소화
"""
import time
import json
from kafka import KafkaProducer, KafkaConsumer


def quick_producer_test():
    """빠른 Producer 테스트"""
    print("=== 빠른 Producer 테스트 ===")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # 5개 테스트 메시지 전송
        for i in range(5):
            test_data = {
                'test_id': i,
                'stream_name': f'test-stream-{i}',
                'timestamp': time.time(),
                'message': f'테스트 메시지 {i}',
                'data_type': 'quick_test'
            }
            
            topic = 'stream-camera-rgb' if i % 2 == 0 else 'vrs-frames'
            future = producer.send(topic, value=test_data, key=f'test-{i}'.encode())
            result = future.get(timeout=5)
            
            print(f"[OK] 메시지 {i} -> {topic}:{result.partition}:{result.offset}")
            time.sleep(0.1)  # 100ms 간격
        
        producer.close()
        print("[SUCCESS] Producer 테스트 완료")
        return True
        
    except Exception as e:
        print(f"[ERROR] Producer 오류: {e}")
        return False


def quick_consumer_test():
    """빠른 Consumer 테스트"""
    print("\\n=== 빠른 Consumer 테스트 ===")
    
    try:
        consumer = KafkaConsumer(
            'stream-camera-rgb',
            'vrs-frames',
            bootstrap_servers=['localhost:9092'],
            group_id='quick-test-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            consumer_timeout_ms=3000
        )
        
        print("3초간 메시지 수신...")
        message_count = 0
        
        for message in consumer:
            data = message.value
            print(f"[수신] {message.topic}:{message.offset} - {data.get('message', 'no message')}")
            
            message_count += 1
            if message_count >= 10:  # 최대 10개
                break
        
        consumer.close()
        print(f"[OK] Consumer 완료 - {message_count}개 수신")
        
    except Exception as e:
        print(f"[ERROR] Consumer 오류: {e}")


def main():
    """빠른 테스트"""
    print("Kafka 빠른 연결 테스트")
    print("=" * 40)
    
    if quick_producer_test():
        quick_consumer_test()
        print("\\n[SUCCESS] Kafka 연결 확인 완료!")
    else:
        print("\\n[FAIL] Kafka 연결 실패")


if __name__ == "__main__":
    main()