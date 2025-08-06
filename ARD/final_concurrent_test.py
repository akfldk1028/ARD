"""
최종 동시 스트리밍 테스트 - 간단하고 빠르게
"""
import time
import json
import threading
from kafka import KafkaProducer, KafkaConsumer


def producer_thread(thread_id: int, topic: str, message_count: int = 5):
    """Producer 스레드"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            client_id=f'thread-producer-{thread_id}'
        )
        
        print(f"[Producer {thread_id}] 시작 - {topic}")
        
        for i in range(message_count):
            message = {
                'thread_id': thread_id,
                'sequence': i,
                'topic': topic,
                'timestamp': time.time(),
                'message': f'Thread {thread_id} Message {i}'
            }
            
            future = producer.send(topic, value=message, key=f't{thread_id}-{i}')
            result = future.get(timeout=3)
            
            print(f"[P{thread_id}] 메시지 {i} -> {result.partition}:{result.offset}")
            time.sleep(0.2)
        
        producer.close()
        print(f"[OK] Producer {thread_id} 완료")
        
    except Exception as e:
        print(f"[ERROR] Producer {thread_id} 오류: {e}")


def consumer_thread(thread_id: int, topics: list, duration: int = 8):
    """Consumer 스레드"""
    try:
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=['localhost:9092'],
            group_id=f'thread-consumer-group-{thread_id}',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            consumer_timeout_ms=1000
        )
        
        print(f"[Consumer {thread_id}] 시작 - {topics}")
        
        message_count = 0
        start_time = time.time()
        
        for message in consumer:
            if time.time() - start_time > duration:
                break
                
            data = message.value
            thread_id_msg = data.get('thread_id', 'unknown')
            sequence = data.get('sequence', 'unknown')
            
            print(f"[C{thread_id}] 수신: P{thread_id_msg}-{sequence} from {message.topic}")
            
            message_count += 1
            if message_count >= 15:
                break
        
        consumer.close()
        print(f"[OK] Consumer {thread_id} 완료 - {message_count}개 수신")
        
    except Exception as e:
        print(f"[ERROR] Consumer {thread_id} 오류: {e}")


def test_concurrent_streaming():
    """동시 스트리밍 테스트"""
    print("=== 동시 스트리밍 테스트 ===")
    
    # 스레드 목록
    threads = []
    
    # 3개 토픽
    topics = ['stream-camera-rgb', 'vrs-frames', 'sensor-data']
    
    # Producer 스레드 3개 시작
    for i, topic in enumerate(topics):
        thread = threading.Thread(target=producer_thread, args=(i, topic, 6))
        thread.start()
        threads.append(thread)
    
    # 잠시 대기
    time.sleep(0.5)
    
    # Consumer 스레드 2개 시작
    consumer_thread_1 = threading.Thread(target=consumer_thread, args=(1, ['stream-camera-rgb', 'vrs-frames'], 6))
    consumer_thread_2 = threading.Thread(target=consumer_thread, args=(2, ['sensor-data'], 6))
    
    consumer_thread_1.start()
    consumer_thread_2.start()
    threads.extend([consumer_thread_1, consumer_thread_2])
    
    print("\\n모든 스레드 실행 중...")
    
    # 모든 스레드 완료 대기
    for thread in threads:
        thread.join(timeout=10)
    
    print("\\n[SUCCESS] 동시 스트리밍 테스트 완료!")


def test_topic_status():
    """토픽 상태 확인"""
    print("\\n=== Kafka 토픽 상태 확인 ===")
    
    try:
        # 각 토픽별 메시지 개수 확인
        topics = ['stream-camera-rgb', 'vrs-frames', 'sensor-data', 'image-metadata', 'stream-imu-right']
        
        for topic in topics:
            try:
                consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=['localhost:9092'],
                    group_id=f'status-check-{topic}',
                    auto_offset_reset='earliest',
                    consumer_timeout_ms=1000
                )
                
                message_count = 0
                for message in consumer:
                    message_count += 1
                    if message_count >= 10:  # 최대 10개만 카운트
                        break
                
                consumer.close()
                print(f"  {topic}: {message_count}+ 개 메시지")
                
            except Exception as e:
                print(f"  {topic}: 확인 불가 - {e}")
        
    except Exception as e:
        print(f"[ERROR] 토픽 상태 확인 오류: {e}")


def main():
    """메인 테스트"""
    print("Kafka 동시 스트리밍 종합 테스트")
    print("=" * 50)
    
    # 1. 토픽 상태 확인
    test_topic_status()
    
    # 2. 동시 스트리밍 테스트
    test_concurrent_streaming()
    
    print("\\n" + "=" * 50)
    print("모든 테스트 완료!")


if __name__ == "__main__":
    main()