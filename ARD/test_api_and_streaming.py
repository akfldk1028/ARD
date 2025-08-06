"""
리눅스 환경에서 API 테스트와 동시 스트리밍 확인
"""
import requests
import time
import asyncio
import json
from kafka import KafkaProducer, KafkaConsumer


def test_django_api():
    """Django API 엔드포인트 테스트"""
    print("=== Django API 테스트 (리눅스 환경) ===")
    
    base_url = "http://localhost:8000"
    
    # 주요 API 엔드포인트들
    endpoints = [
        "/api/v1/aria-sessions/api/sessions/",
        "/api/v1/aria-sessions/api/streaming/", 
        "/api/v1/aria-sessions/api/vrs-streams/",
        "/api/v1/aria-sessions/api/balanced-stream-data/",
        "/admin/"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\\n테스트: {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            
            if response.status_code == 200:
                print(f"  [OK] 200 - 정상 응답")
                if 'json' in response.headers.get('content-type', ''):
                    data = response.json()
                    if isinstance(data, dict) and 'results' in data:
                        print(f"    결과 개수: {len(data['results'])}")
                    elif isinstance(data, list):
                        print(f"    리스트 크기: {len(data)}")
            else:
                print(f"  [WARNING] {response.status_code} - {response.reason}")
                
        except requests.exceptions.ConnectionError:
            print(f"  [ERROR] 연결 실패 - Django 서버가 실행중인지 확인")
            return False
        except Exception as e:
            print(f"  [ERROR] API 오류: {e}")
    
    print("\\n[SUCCESS] Django API 테스트 완료")
    return True


async def test_concurrent_streaming():
    """동시 스트리밍 테스트"""
    print("\\n=== 동시 스트리밍 테스트 ===")
    
    # 1. Kafka Consumer 백그라운드 실행
    async def run_consumer():
        print("Consumer 백그라운드 시작...")
        try:
            consumer = KafkaConsumer(
                'stream-camera-rgb',
                'vrs-frames',
                'sensor-data',
                bootstrap_servers=['localhost:9092'],
                group_id='concurrent-test-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')) if len(m) < 1000000 else {"binary_size": len(m)},
                auto_offset_reset='latest',
                consumer_timeout_ms=2000
            )
            
            message_count = 0
            for message in consumer:
                data = message.value
                if isinstance(data, dict):
                    if 'stream_name' in data:
                        print(f"  [수신] {data['stream_name']}: {message.topic}:{message.offset}")
                    else:
                        print(f"  [수신] 데이터: {message.topic}:{message.offset}")
                
                message_count += 1
                if message_count >= 10:  # 최대 10개
                    break
            
            consumer.close()
            print(f"  Consumer 완료: {message_count}개 수신")
            
        except Exception as e:
            print(f"  [ERROR] Consumer 오류: {e}")
    
    # 2. Multiple Producer 동시 실행
    async def run_multiple_producers():
        print("Multiple Producer 시작...")
        
        try:
            # 3개의 다른 Producer 동시 실행
            producers = []
            
            for i in range(3):
                producer = KafkaProducer(
                    bootstrap_servers=['localhost:9092'],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    client_id=f'concurrent-producer-{i}'
                )
                producers.append(producer)
            
            # 동시에 다른 토픽으로 메시지 전송
            topics = ['stream-camera-rgb', 'vrs-frames', 'sensor-data']
            
            for round_num in range(5):  # 5라운드
                print(f"  Round {round_num + 1}: 동시 전송...")
                
                for i, producer in enumerate(producers):
                    topic = topics[i]
                    message = {
                        'producer_id': i,
                        'round': round_num,
                        'stream_type': f'concurrent_test_{i}',
                        'timestamp': time.time(),
                        'message': f'동시 스트리밍 테스트 P{i}R{round_num}'
                    }
                    
                    future = producer.send(topic, value=message, key=f'concurrent-{i}-{round_num}')
                    # 논블로킹으로 전송
                
                await asyncio.sleep(0.5)  # 500ms 간격
            
            # 모든 Producer flush
            for producer in producers:
                producer.flush()
                producer.close()
            
            print("  [OK] Multiple Producer 완료")
            
        except Exception as e:
            print(f"  [ERROR] Multiple Producer 오류: {e}")
    
    # 3. API 호출 동시 테스트
    async def test_concurrent_api():
        print("Concurrent API 호출 테스트...")
        
        try:
            # 동시에 여러 API 호출
            api_calls = [
                "http://localhost:8000/api/v1/aria-sessions/api/sessions/",
                "http://localhost:8000/api/v1/aria-sessions/api/vrs-streams/",
                "http://localhost:8000/api/v1/aria-sessions/api/streaming/"
            ]
            
            async def call_api(url):
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=5) as response:
                            return f"{url}: {response.status}"
                except:
                    # aiohttp 없으면 requests 사용
                    response = requests.get(url, timeout=3)
                    return f"{url}: {response.status_code}"
            
            # 동시 API 호출
            tasks = [call_api(url) for url in api_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    print(f"  [ERROR] API 오류: {result}")
                else:
                    print(f"  [OK] {result}")
            
        except Exception as e:
            print(f"  [ERROR] Concurrent API 오류: {e}")
    
    # 모든 작업 동시 실행
    print("Consumer, Producer, API 동시 실행...")
    
    tasks = [
        run_consumer(),
        run_multiple_producers(),
        test_concurrent_api()
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\\n[SUCCESS] 동시 스트리밍 테스트 완료")


async def main():
    """메인 테스트"""
    print("리눅스 환경 - API 및 동시 스트리밍 테스트")
    print("=" * 60)
    
    # 1. Django API 테스트
    api_success = test_django_api()
    
    if api_success:
        # 2. 동시 스트리밍 테스트
        await test_concurrent_streaming()
    else:
        print("\\n[WARNING] Django 서버가 실행되지 않음 - Kafka만 테스트")
        
        # Kafka만 테스트
        try:
            producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            test_data = {'test': 'linux_kafka', 'timestamp': time.time()}
            future = producer.send('vrs-frames', value=test_data)
            result = future.get(timeout=5)
            
            producer.close()
            print(f"[OK] Kafka 단독 테스트 성공: {result.topic}:{result.offset}")
            
        except Exception as e:
            print(f"[ERROR] Kafka 단독 테스트 실패: {e}")
    
    print("\\n" + "=" * 60)
    print("[COMPLETE] 리눅스 환경 테스트 완료")


if __name__ == "__main__":
    asyncio.run(main())