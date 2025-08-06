"""
Kafka에 전송된 메시지 최종 확인
"""
from kafka import KafkaConsumer
import json


def check_all_topics():
    """모든 토픽의 메시지 확인"""
    print("=== Kafka 전송된 메시지 최종 확인 ===")
    
    # 모든 토픽 확인
    topics = [
        'stream-camera-rgb',
        'vrs-frames', 
        'vrs-metadata-stream',
        'vrs-binary-stream',
        'vrs-frame-registry',
        'sensor-data',
        'image-metadata',
        'stream-imu-right'
    ]
    
    for topic in topics:
        print(f"\\n--- {topic} 확인 ---")
        
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=['localhost:9092'],
                group_id=f'check-{topic}-group',
                value_deserializer=lambda m: m.decode('utf-8') if len(m) < 1000 else f"[Binary {len(m)} bytes]",
                auto_offset_reset='earliest',
                consumer_timeout_ms=2000
            )
            
            message_count = 0
            for message in consumer:
                try:
                    if isinstance(message.value, str) and message.value.startswith('[Binary'):
                        print(f"  {message.offset}: {message.value}")
                    else:
                        data = json.loads(message.value)
                        if 'frame_id' in data:
                            print(f"  {message.offset}: Frame {data.get('frame_id')}")
                        elif 'stream_name' in data:
                            print(f"  {message.offset}: {data.get('stream_name')} - {data.get('message', 'data')}")
                        else:
                            print(f"  {message.offset}: {type(data)} 데이터")
                            
                except json.JSONDecodeError:
                    print(f"  {message.offset}: Non-JSON 데이터")
                except Exception as e:
                    print(f"  {message.offset}: 파싱 오류 - {e}")
                
                message_count += 1
                if message_count >= 5:  # 토픽당 최대 5개
                    break
            
            consumer.close()
            
            if message_count > 0:
                print(f"  [OK] {message_count}개 메시지 확인")
            else:
                print(f"  [INFO] 메시지 없음")
                
        except Exception as e:
            print(f"  [ERROR] 토픽 확인 오류: {e}")
    
    print("\\n=== 최종 확인 완료 ===")


if __name__ == "__main__":
    check_all_topics()