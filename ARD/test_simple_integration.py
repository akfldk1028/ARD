"""
간단한 VRS -> Kafka 통합 테스트
Django 없이 순수 테스트
"""
import os
import time
import json
import base64
from PIL import Image
import io

# kafka-python 라이브러리 (프로젝트 kafka와 구분)
try:
    from kafka import KafkaProducer, KafkaConsumer
    print("[OK] kafka-python 라이브러리 import 성공")
except ImportError as e:
    print(f"[ERROR] kafka-python import 실패: {e}")
    exit(1)

# Project Aria tools
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    print("[OK] projectaria_tools import 성공")
except ImportError as e:
    print(f"[ERROR] projectaria_tools import 실패: {e}")
    exit(1)


def test_kafka_basic():
    """기본 Kafka 연결 테스트"""
    print("\\n=== Kafka 기본 연결 테스트 ===")
    
    try:
        # Producer 테스트
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        test_data = {'test': 'basic_kafka', 'timestamp': time.time()}
        future = producer.send('vrs-frames', value=test_data)
        result = future.get(timeout=10)
        
        print(f"[OK] Producer: {result.topic}:{result.partition}:{result.offset}")
        producer.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Kafka 기본 테스트 실패: {e}")
        return False


def test_vrs_basic():
    """기본 VRS 데이터 읽기 테스트"""
    print("\\n=== VRS 기본 읽기 테스트 ===")
    
    vrs_file = "data/mps_samples/sample.vrs"
    
    if not os.path.exists(vrs_file):
        print(f"[ERROR] VRS 파일 없음: {vrs_file}")
        return False, None
    
    try:
        # ipynb 패턴
        provider = data_provider.create_vrs_data_provider(vrs_file)
        if not provider:
            print("Invalid vrs data provider")
            return False, None
        
        # RGB 스트림 테스트
        rgb_stream_id = StreamId("214-1")
        num_frames = provider.get_num_data(rgb_stream_id)
        
        if num_frames > 0:
            image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
            if image_data[0]:
                image_array = image_data[0].to_numpy_array()
                print(f"[OK] RGB 이미지: {image_array.shape}, 프레임: {num_frames}개")
                return True, provider
        
        print("[ERROR] RGB 이미지 데이터 없음")
        return False, None
        
    except Exception as e:
        print(f"[ERROR] VRS 기본 테스트 실패: {e}")
        return False, None


def test_integration(provider):
    """VRS -> Kafka 통합 테스트"""
    print("\\n=== VRS -> Kafka 통합 테스트 ===")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            max_request_size=10485760,
            compression_type='gzip'
        )
        
        # RGB 이미지 1개 전송
        rgb_stream_id = StreamId("214-1")
        image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
        
        if image_data[0]:
            image_array = image_data[0].to_numpy_array()
            
            # 작은 이미지로 압축
            pil_image = Image.fromarray(image_array)
            pil_image = pil_image.resize((200, 200))  # 크기 줄이기
            
            buffer = io.BytesIO()
            pil_image.save(buffer, format='JPEG', quality=30)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            kafka_data = {
                'stream_name': 'camera-rgb',
                'stream_id': str(rgb_stream_id),
                'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                'original_shape': list(image_array.shape),
                'compressed_shape': [200, 200],
                'image_data': image_base64,
                'compressed_size': len(image_base64),
                'test_type': 'integration',
                'timestamp': time.time()
            }
            
            future = producer.send('stream-camera-rgb', value=kafka_data, key=b'rgb-test')
            result = future.get(timeout=10)
            
            print(f"[OK] VRS RGB -> Kafka 성공!")
            print(f"  토픽: {result.topic}:{result.partition}:{result.offset}")
            print(f"  원본: {image_array.shape} -> 압축: 200x200 ({len(image_base64)} bytes)")
        
        producer.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] 통합 테스트 실패: {e}")
        return False


def main():
    """메인 테스트"""
    print("Project Aria VRS + Kafka 간단 통합 테스트")
    print("=" * 60)
    
    # 1. Kafka 기본 연결
    if not test_kafka_basic():
        print("\\nKafka 연결 실패 - Docker Kafka가 실행 중인지 확인하세요")
        return
    
    # 2. VRS 기본 읽기
    vrs_success, provider = test_vrs_basic()
    if not vrs_success:
        print("\\nVRS 데이터 읽기 실패")
        return
    
    # 3. 통합 테스트
    if test_integration(provider):
        print("\\n" + "=" * 60)
        print("[SUCCESS] 모든 테스트 통과! VRS 데이터가 Kafka로 정상 전송됨")
    else:
        print("\\n통합 테스트 실패")


if __name__ == "__main__":
    main()