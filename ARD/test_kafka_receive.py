"""
Kafka로 전송된 VRS 데이터 수신 테스트
기존 common/kafka에서 보낸 데이터 확인
"""
import json
import time
from kafka import KafkaConsumer


def test_receive_messages():
    """Kafka에서 전송된 메시지 수신"""
    print("=== Kafka 메시지 수신 테스트 ===")
    
    # 기존 모듈에서 사용하는 토픽들
    topics = [
        'stream-camera-rgb',      # RGB 스트림
        'vrs-frames',             # SLAM 프레임
        'vrs-metadata-stream',    # 바이너리 메타데이터
        'vrs-binary-stream',      # 바이너리 데이터
        'vrs-frame-registry',     # 프레임 레지스트리
        'sensor-data'             # 센서 데이터
    ]
    
    try:
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=['localhost:9092'],
            group_id='receive-test-group',
            value_deserializer=lambda m: m.decode('utf-8'),  # Raw 먼저
            auto_offset_reset='earliest',
            consumer_timeout_ms=5000  # 5초 타임아웃
        )
        
        print(f"Consumer 시작 - 토픽: {topics}")
        print("5초간 메시지 수신 중...")
        
        message_count = 0
        topic_counts = {}
        
        for message in consumer:
            try:
                topic = message.topic
                
                # 토픽별 카운트
                if topic not in topic_counts:
                    topic_counts[topic] = 0
                topic_counts[topic] += 1
                
                # 메시지 내용 파싱
                if topic == 'vrs-binary-stream':
                    # 바이너리 데이터
                    print(f"[수신] {topic}:{message.offset} - 바이너리 데이터 ({len(message.value)} bytes)")
                else:
                    # JSON 데이터
                    try:
                        data = json.loads(message.value)
                        print(f"[수신] {topic}:{message.offset}")
                        
                        if 'stream_name' in data:
                            print(f"  스트림: {data['stream_name']}")
                        if 'frame_index' in data:
                            print(f"  프레임: {data['frame_index']}")
                        if 'compression' in data:
                            comp = data['compression']
                            print(f"  압축: {comp['format']} {comp['compressed_size']} bytes")
                        if 'message' in data:
                            print(f"  메시지: {data['message']}")
                            
                    except json.JSONDecodeError:
                        print(f"[수신] {topic}:{message.offset} - Non-JSON 데이터")
                
                message_count += 1
                if message_count >= 20:  # 최대 20개
                    break
                    
            except Exception as e:
                print(f"[ERROR] 메시지 처리 오류: {e}")
        
        consumer.close()
        
        print(f"\\n=== 수신 결과 ===")
        print(f"총 메시지: {message_count}개")
        for topic, count in topic_counts.items():
            print(f"  {topic}: {count}개")
        
        if message_count > 0:
            print("\\n[SUCCESS] Kafka 데이터 수신 성공!")
        else:
            print("\\n[INFO] 수신된 메시지 없음")
        
    except Exception as e:
        print(f"[ERROR] Consumer 오류: {e}")


def main():
    test_receive_messages()


if __name__ == "__main__":
    main()