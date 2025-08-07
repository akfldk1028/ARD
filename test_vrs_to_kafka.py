"""
Project Aria VRS 데이터를 Kafka로 스트리밍하는 단순 테스트
패키지 충돌 문제 해결을 위한 독립 스크립트
"""
import os
import sys
import time
import json
import base64
from pathlib import Path

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
import django
django.setup()

# kafka-python 라이브러리 import (프로젝트 kafka 폴더와 구분)
import kafka as kafka_lib
from kafka_lib import KafkaProducer, KafkaConsumer

# Project Aria tools import
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId
from PIL import Image
import io
import numpy as np


def test_vrs_data_access():
    """VRS 데이터 접근 테스트 (ipynb 패턴)"""
    print("=== VRS 데이터 접근 테스트 ===")
    
    # VRS 파일 경로
    vrs_file = "ARD/data/mps_samples/sample.vrs"
    
    if not os.path.exists(vrs_file):
        print(f"[ERROR] VRS 파일 없음: {vrs_file}")
        return False
    
    try:
        # ipynb 패턴: 데이터 프로바이더 생성
        print(f"Creating data provider from {vrs_file}")
        provider = data_provider.create_vrs_data_provider(vrs_file)
        
        if not provider:
            print("Invalid vrs data provider")
            return False
        
        # ipynb와 동일한 스트림 매핑
        stream_mappings = {
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"),
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
        }
        
        print("\\n스트림 정보:")
        for stream_name, stream_id in stream_mappings.items():
            num_frames = provider.get_num_data(stream_id)
            if num_frames > 0:
                config = provider.get_image_configuration(stream_id)
                print(f"  {stream_name}: {num_frames}프레임, {config.image_width}x{config.image_height}")
                
                # 첫 번째 이미지 테스트 (ipynb 패턴)
                image_data = provider.get_image_data_by_index(stream_id, 0)
                if image_data[0]:
                    image_array = image_data[0].to_numpy_array()
                    print(f"    첫 이미지: {image_array.shape}, timestamp: {image_data[1].capture_timestamp_ns}")
            else:
                print(f"  {stream_name}: 데이터 없음")
        
        print("[OK] VRS 데이터 접근 성공")
        return True, provider
        
    except Exception as e:
        print(f"[ERROR] VRS 테스트 오류: {e}")
        return False, None


def test_kafka_connection():
    """Kafka 연결 테스트"""
    print("\\n=== Kafka 연결 테스트 ===")
    
    try:
        # Producer 테스트
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            max_request_size=10485760  # 10MB
        )
        
        test_data = {
            'test': 'connection',
            'timestamp': time.time(),
            'message': 'VRS-Kafka 연결 테스트'
        }
        
        future = producer.send('vrs-frames', value=test_data)
        result = future.get(timeout=10)
        print(f"[OK] Producer: {result.topic}:{result.partition}:{result.offset}")
        
        producer.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Kafka 연결 오류: {e}")
        return False


def test_vrs_to_kafka_integration(provider):
    """VRS 데이터를 Kafka로 전송하는 통합 테스트"""
    print("\\n=== VRS -> Kafka 통합 테스트 ===")
    
    try:
        # Kafka Producer 생성
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            max_request_size=10485760,
            compression_type='gzip'
        )
        
        # RGB 이미지 1개 테스트
        rgb_stream_id = StreamId("214-1")
        if provider.get_num_data(rgb_stream_id) > 0:
            # ipynb 패턴으로 이미지 가져오기
            image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
            if image_data[0]:
                image_array = image_data[0].to_numpy_array()
                
                # 이미지 압축 (크기 줄이기)
                pil_image = Image.fromarray(image_array)
                buffer = io.BytesIO()
                pil_image.save(buffer, format='JPEG', quality=50)
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Kafka 메시지 구성
                kafka_data = {
                    'stream_name': 'camera-rgb',
                    'stream_id': str(rgb_stream_id),
                    'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                    'image_shape': list(image_array.shape),
                    'image_data': image_base64,
                    'data_type': 'integration_test',
                    'processing_timestamp': time.time(),
                    'compressed_size_bytes': len(image_base64)
                }
                
                # Kafka로 전송
                future = producer.send('stream-camera-rgb', value=kafka_data, key=b'camera-rgb')
                result = future.get(timeout=10)
                
                print(f"[OK] VRS RGB -> Kafka 성공: {result.topic}:{result.partition}:{result.offset}")
                print(f"원본 이미지: {image_array.shape}, 압축 후: {len(image_base64)} bytes")
        
        # SLAM 이미지 1개 테스트
        slam_stream_id = StreamId("1201-1")  # camera-slam-left
        if provider.get_num_data(slam_stream_id) > 0:
            image_data = provider.get_image_data_by_index(slam_stream_id, 0)
            if image_data[0]:
                image_array = image_data[0].to_numpy_array()
                
                kafka_data = {
                    'stream_name': 'camera-slam-left',
                    'stream_id': str(slam_stream_id),
                    'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                    'image_shape': list(image_array.shape),
                    'data_type': 'slam_test',
                    'processing_timestamp': time.time()
                }
                
                future = producer.send('vrs-frames', value=kafka_data, key=b'slam-left')
                result = future.get(timeout=10)
                
                print(f"[OK] VRS SLAM -> Kafka 성공: {result.topic}:{result.partition}:{result.offset}")
        
        producer.close()
        print("[OK] 통합 테스트 완료")
        
    except Exception as e:
        print(f"[ERROR] 통합 테스트 오류: {e}")


def main():
    """메인 테스트 함수"""
    print("Project Aria VRS + Kafka 연결 테스트")
    print("=" * 50)
    
    # 1. VRS 데이터 접근 테스트
    vrs_success, provider = test_vrs_data_access()
    if not vrs_success:
        return
    
    # 2. Kafka 연결 테스트
    kafka_success = test_kafka_connection()
    if not kafka_success:
        return
    
    # 3. 통합 테스트
    test_vrs_to_kafka_integration(provider)
    
    print("\\n" + "=" * 50)
    print("모든 테스트 완료!")


if __name__ == "__main__":
    main()