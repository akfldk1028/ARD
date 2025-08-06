"""
가장 간단한 VRS -> Kafka 스트리밍 테스트
공식 ipynb 패턴 그대로 유지하면서 Kafka로 연결
"""
import os
import time
import json
import asyncio
from kafka import KafkaProducer, KafkaConsumer

# Project Aria (ipynb 패턴 그대로)
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import StreamId


async def simple_streaming_test():
    """가장 간단한 스트리밍 테스트"""
    print("=== 간단한 VRS -> Kafka 스트리밍 테스트 ===")
    
    # 1. VRS 데이터 로드 (ipynb 패턴 그대로)
    vrs_file = "data/mps_samples/sample.vrs"
    print(f"Creating data provider from {vrs_file}")
    provider = data_provider.create_vrs_data_provider(vrs_file)
    
    if not provider:
        print("Invalid vrs data provider")
        return
    
    # 2. Kafka Producer 생성
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
    )
    
    # 3. ipynb와 동일한 스트림 매핑
    stream_mappings = {
        "camera-slam-left": StreamId("1201-1"),
        "camera-slam-right": StreamId("1201-2"),
        "camera-rgb": StreamId("214-1"),
        "camera-eyetracking": StreamId("211-1"),
    }
    
    print("\\n연속 스트리밍 시작...")
    
    # 4. 각 스트림에서 몇 개씩 연속으로 보내기
    for stream_name, stream_id in stream_mappings.items():
        num_frames = provider.get_num_data(stream_id)
        if num_frames == 0:
            continue
            
        print(f"\\n{stream_name} 스트리밍 중... ({num_frames}개 프레임)")
        
        # 처음 5개 프레임 연속 전송
        for frame_idx in range(min(5, num_frames)):
            try:
                # ipynb 패턴: get_image_data_by_index
                image_data = provider.get_image_data_by_index(stream_id, frame_idx)
                if image_data and image_data[0]:
                    # 메타데이터만 전송 (이미지는 너무 크니까)
                    kafka_data = {
                        'stream_name': stream_name,
                        'stream_id': str(stream_id),
                        'frame_index': frame_idx,
                        'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                        'image_shape': list(image_data[0].to_numpy_array().shape),
                        'data_type': 'simple_streaming',
                        'sequence': frame_idx,
                        'timestamp': time.time()
                    }
                    
                    # 토픽 선택
                    if 'rgb' in stream_name:
                        topic = 'stream-camera-rgb'
                    else:
                        topic = 'vrs-frames'
                    
                    # Kafka 전송
                    future = producer.send(topic, value=kafka_data, key=stream_name.encode())
                    result = future.get(timeout=5)
                    
                    print(f"  [OK] 프레임 {frame_idx} -> {topic}:{result.partition}:{result.offset}")
                    
                    # 스트리밍 간격
                    await asyncio.sleep(0.2)  # 200ms 간격
                    
            except Exception as e:
                print(f"  [ERROR] 프레임 {frame_idx} 오류: {e}")
    
    producer.close()
    print("\\n[SUCCESS] 간단한 스트리밍 테스트 완료!")


def test_consumer_messages():
    """전송된 메시지 확인"""
    print("\\n=== Consumer로 전송된 메시지 확인 ===")
    
    try:
        consumer = KafkaConsumer(
            'stream-camera-rgb',
            'vrs-frames',
            bootstrap_servers=['localhost:9092'],
            group_id='simple-test-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            consumer_timeout_ms=3000
        )
        
        message_count = 0
        for message in consumer:
            print(f"\\n[수신] {message.topic}:{message.offset}")
            data = message.value
            print(f"  스트림: {data.get('stream_name')}")
            print(f"  프레임: {data.get('frame_index')}")
            print(f"  Shape: {data.get('image_shape')}")
            
            message_count += 1
            if message_count >= 5:  # 최대 5개
                break
        
        consumer.close()
        print(f"\\n[OK] {message_count}개 메시지 수신 완료")
        
    except Exception as e:
        print(f"[ERROR] Consumer 오류: {e}")


async def main():
    """메인 테스트"""
    # 1. 스트리밍 테스트
    await simple_streaming_test()
    
    # 2. Consumer 테스트
    test_consumer_messages()


if __name__ == "__main__":
    asyncio.run(main())