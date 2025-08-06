"""
기존 common/kafka 모듈을 활용한 테스트
공식 패턴 + 기존 코드 결합
"""
import os
import sys
import time
import asyncio

# 기존 common/kafka 모듈 사용
from common.kafka.binary_producer import BinaryKafkaProducer
from common.kafka.base_producer import BaseKafkaProducer

# Project Aria tools (ipynb 패턴)
from projectaria_tools.core import data_provider
from projectaria_tools.core.stream_id import StreamId


class AriaCommonKafkaProducer(BaseKafkaProducer):
    """기존 BaseKafkaProducer를 Aria용으로 확장"""
    
    def __init__(self):
        super().__init__(service_name='aria_streaming', bootstrap_servers='localhost:9092')
        
        # Aria 스트림용 토픽 매핑
        self.topics = {
            'rgb': 'stream-camera-rgb',
            'slam': 'vrs-frames', 
            'sensor': 'sensor-data',
            'imu': 'stream-imu-right',
            'metadata': 'image-metadata'
        }


async def test_existing_kafka_simple():
    """기존 Kafka 모듈 간단 테스트"""
    print("=== 기존 common/kafka 모듈 테스트 ===")
    
    # 1. 기존 BaseKafkaProducer 테스트
    print("\\n1. BaseKafkaProducer 테스트...")
    aria_producer = AriaCommonKafkaProducer()
    
    try:
        for i in range(3):
            test_message = {
                'test_id': i,
                'message': f'기존 모듈 테스트 {i}',
                'timestamp': time.time(),
                'stream_type': 'test'
            }
            
            success = aria_producer.send_message('rgb', test_message, key=f'test-{i}')
            if success:
                print(f"  [OK] 메시지 {i} 전송 성공")
            else:
                print(f"  [ERROR] 메시지 {i} 전송 실패")
            
            await asyncio.sleep(0.5)
        
        aria_producer.close()
        print("[OK] BaseKafkaProducer 테스트 완료")
        
    except Exception as e:
        print(f"[ERROR] BaseKafkaProducer 오류: {e}")
    
    # 2. BinaryKafkaProducer 테스트
    print("\\n2. BinaryKafkaProducer 테스트...")
    binary_producer = BinaryKafkaProducer(bootstrap_servers='localhost:9092')
    
    try:
        # 테스트 바이너리 프레임 전송
        result = binary_producer.send_test_binary_frame(session_id='test-binary-session')
        
        if result.get('success'):
            print(f"  [OK] 바이너리 프레임 전송 성공")
            print(f"    Frame ID: {result['frame_id']}")
            print(f"    압축 크기: {result['binary_size']} bytes")
            print(f"    압축률: {result['compression']['compression_ratio']:.3f}")
        else:
            print(f"  [ERROR] 바이너리 프레임 전송 실패: {result.get('error')}")
        
        binary_producer.close()
        print("[OK] BinaryKafkaProducer 테스트 완료")
        
    except Exception as e:
        print(f"[ERROR] BinaryKafkaProducer 오류: {e}")


async def test_vrs_with_existing_kafka():
    """VRS 데이터와 기존 Kafka 모듈 연결"""
    print("\\n=== VRS + 기존 Kafka 모듈 연결 테스트 ===")
    
    # VRS 데이터 로드
    vrs_file = "data/mps_samples/sample.vrs"
    
    if not os.path.exists(vrs_file):
        print(f"[ERROR] VRS 파일 없음: {vrs_file}")
        return
    
    try:
        # ipynb 패턴
        print(f"Creating data provider from {vrs_file}")
        provider = data_provider.create_vrs_data_provider(vrs_file)
        
        if not provider:
            print("Invalid vrs data provider")
            return
        
        # 기존 Binary Producer 사용
        binary_producer = BinaryKafkaProducer(bootstrap_servers='localhost:9092')
        
        # RGB 이미지 몇 개 연속 전송
        rgb_stream_id = StreamId("214-1")
        num_frames = provider.get_num_data(rgb_stream_id)
        
        print(f"RGB 스트림: {num_frames}개 프레임")
        
        if num_frames > 0:
            for frame_idx in range(min(3, num_frames)):  # 처음 3개만
                image_data = provider.get_image_data_by_index(rgb_stream_id, frame_idx)
                if image_data and image_data[0]:
                    image_array = image_data[0].to_numpy_array()
                    
                    # 기존 binary_producer 사용
                    result = binary_producer.send_vrs_frame_binary(
                        session_id='vrs-test-session',
                        stream_id=str(rgb_stream_id),
                        numpy_image=image_array,
                        frame_index=frame_idx,
                        capture_timestamp_ns=image_data[1].capture_timestamp_ns,
                        format='jpeg',
                        quality=70
                    )
                    
                    if result.get('success'):
                        compression = result['compression']
                        print(f"  [OK] RGB 프레임 {frame_idx}: {compression['compressed_size']} bytes (압축률: {compression['compression_ratio']:.3f})")
                    else:
                        print(f"  [ERROR] RGB 프레임 {frame_idx} 실패: {result.get('error')}")
                    
                    await asyncio.sleep(0.3)  # 300ms 간격
        
        binary_producer.close()
        print("[SUCCESS] VRS + 기존 Kafka 연결 완료!")
        
    except Exception as e:
        print(f"[ERROR] VRS + Kafka 연결 오류: {e}")


async def main():
    """메인 테스트"""
    print("기존 common/kafka 모듈 활용 테스트")
    print("=" * 50)
    
    # 1. 기존 모듈 단독 테스트
    await test_existing_kafka_simple()
    
    # 2. VRS 연결 테스트
    await test_vrs_with_existing_kafka()
    
    print("\\n" + "=" * 50)
    print("[COMPLETE] 모든 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())