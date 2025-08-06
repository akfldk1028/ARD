"""
Kafka Consumer 테스트
전송된 VRS 데이터 수신 확인
"""
import time
import json
from kafka import KafkaConsumer

def test_kafka_consumer():
    """Kafka Consumer 테스트"""
    print("=== Kafka Consumer 테스트 ===")
    
    try:
        consumer = KafkaConsumer(
            'stream-camera-rgb',
            'vrs-frames', 
            'sensor-data',
            bootstrap_servers=['localhost:9092'],
            group_id='test-consumer-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',  # 처음부터 읽기
            consumer_timeout_ms=5000  # 5초 타임아웃
        )
        
        print("Consumer 시작 - 5초간 메시지 수신...")
        message_count = 0
        
        for message in consumer:
            print(f"\\n[수신] {message.topic}:{message.partition}:{message.offset}")
            
            data = message.value
            if isinstance(data, dict):
                # 이미지 데이터가 있는 경우 크기만 출력
                if 'image_data' in data:
                    image_size = len(data['image_data'])
                    print(f"  스트림: {data.get('stream_name', 'unknown')}")
                    print(f"  타임스탬프: {data.get('capture_timestamp_ns', 0)}")
                    print(f"  이미지 크기: {image_size} bytes")
                    print(f"  원본 shape: {data.get('original_shape', 'unknown')}")
                else:
                    print(f"  데이터: {data}")
            
            message_count += 1
            if message_count >= 3:  # 최대 3개 메시지
                break
        
        consumer.close()
        
        if message_count > 0:
            print(f"\\n[OK] Consumer 테스트 성공 - {message_count}개 메시지 수신")
        else:
            print("\\n[INFO] 수신된 메시지 없음 (이전 테스트 데이터 확인)")
        
    except Exception as e:
        print(f"[ERROR] Consumer 테스트 오류: {e}")


def main():
    test_kafka_consumer()

if __name__ == "__main__":
    main()