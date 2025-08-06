"""
동시 스트리밍 테스트 - Kafka 중심
Django 서버 없이도 Kafka 동시 처리 확인
"""
import asyncio
import time
import json
import threading
from kafka import KafkaProducer, KafkaConsumer
from concurrent.futures import ThreadPoolExecutor


def concurrent_producer_test(producer_id: int, message_count: int = 10):
    """개별 Producer 스레드"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            client_id=f'concurrent-producer-{producer_id}',
            batch_size=1024,
            linger_ms=5
        )
        
        topics = ['stream-camera-rgb', 'vrs-frames', 'sensor-data']
        topic = topics[producer_id % len(topics)]
        
        for i in range(message_count):
            message = {
                'producer_id': producer_id,
                'sequence': i,
                'stream_type': f'concurrent_stream_{producer_id}',
                'timestamp': time.time(),
                'data': f'Producer {producer_id} - Message {i}'
            }
            
            future = producer.send(topic, value=message, key=f'p{producer_id}-{i}')
            result = future.get(timeout=5)
            
            print(f"[P{producer_id}] 메시지 {i} -> {topic}:{result.offset}")
            time.sleep(0.1)  # 100ms 간격
        
        producer.close()
        print(f"[OK] Producer {producer_id} 완료 - {message_count}개 전송")
        
    except Exception as e:
        print(f"[ERROR] Producer {producer_id} 오류: {e}")


def concurrent_consumer_test(consumer_id: int, duration_seconds: int = 15):
    """개별 Consumer 스레드"""
    try:
        topics = ['stream-camera-rgb', 'vrs-frames', 'sensor-data']
        topic = topics[consumer_id % len(topics)]
        
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=['localhost:9092'],
            group_id=f'concurrent-consumer-group-{consumer_id}',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            consumer_timeout_ms=2000
        )
        
        print(f"[C{consumer_id}] Consumer 시작 - {topic} 모니터링")
        
        message_count = 0
        start_time = time.time()
        
        for message in consumer:
            if time.time() - start_time > duration_seconds:
                break
                
            data = message.value
            if isinstance(data, dict):
                producer_id = data.get('producer_id', 'unknown')
                sequence = data.get('sequence', 'unknown')
                print(f"[C{consumer_id}] 수신: P{producer_id}-{sequence} from {topic}:{message.offset}")
            
            message_count += 1
            if message_count >= 20:  # 최대 20개
                break
        
        consumer.close()
        print(f"[OK] Consumer {consumer_id} 완료 - {message_count}개 수신")
        
    except Exception as e:
        print(f"[ERROR] Consumer {consumer_id} 오류: {e}")


def test_multi_threading_kafka():
    """멀티스레딩으로 동시 Kafka 처리 테스트"""
    print("=== 멀티스레딩 Kafka 동시 처리 테스트 ===")
    
    # ThreadPoolExecutor로 동시 실행
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        
        # 3개 Producer 시작
        for i in range(3):
            future = executor.submit(concurrent_producer_test, i, 8)
            futures.append(f"Producer {i}")
        
        # 잠시 대기 후 3개 Consumer 시작
        time.sleep(1)
        
        for i in range(3):
            future = executor.submit(concurrent_consumer_test, i, 10)
            futures.append(f"Consumer {i}")
        
        print("\\n모든 스레드 실행 중...")
        time.sleep(12)  # 12초 대기
        
        print("\\n[SUCCESS] 멀티스레딩 테스트 완료")


async def test_asyncio_kafka():
    """AsyncIO로 동시 Kafka 처리 테스트"""
    print("\\n=== AsyncIO Kafka 동시 처리 테스트 ===")
    
    async def async_producer(producer_id: int):
        """비동기 Producer"""
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            client_id=f'async-producer-{producer_id}'
        )
        
        for i in range(5):
            message = {
                'producer_id': producer_id,
                'type': 'async_test',
                'sequence': i,
                'timestamp': time.time()
            }
            
            producer.send('vrs-frames', value=message)
            print(f"[AsyncP{producer_id}] 메시지 {i} 전송")
            await asyncio.sleep(0.2)
        
        producer.close()
        print(f"[OK] Async Producer {producer_id} 완료")
    
    # 3개 Producer 동시 실행
    tasks = [async_producer(i) for i in range(3)]
    await asyncio.gather(*tasks)
    
    print("[SUCCESS] AsyncIO 테스트 완료")


async def main():
    """메인 테스트 함수"""
    print("리눅스 환경 - Kafka 동시 스트리밍 종합 테스트")
    print("=" * 70)
    
    # 1. 멀티스레딩 테스트
    test_multi_threading_kafka()
    
    # 2. AsyncIO 테스트  
    await test_asyncio_kafka()
    
    print("\\n" + "=" * 70)
    print("[FINAL] 모든 동시 스트리밍 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())