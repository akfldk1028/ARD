"""
공식 Observer 패턴을 따른 VRS -> Kafka 연속 스트리밍
ipynb deliver_queued_sensor_data를 Observer 스타일로 구현
"""
import os
import time
import json
import base64
import asyncio
from typing import Optional, Dict, Any
from PIL import Image
import io

from kafka import KafkaProducer
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId


class AriaStreamingObserver:
    """
    공식 Observer 패턴을 모방한 VRS 스트리밍 Observer
    실제 StreamingClientObserver와 동일한 인터페이스
    """
    
    def __init__(self, kafka_producer: KafkaProducer):
        self.kafka_producer = kafka_producer
        self.message_count = 0
        self.is_streaming = False
        
        # 스트림별 통계
        self.stream_stats = {}
    
    def on_image_received(self, image_array, stream_label: str, stream_id: str, timestamp_ns: int):
        """
        공식 Observer 패턴: on_image_received 콜백
        실제 디바이스처럼 연속적으로 호출됨
        """
        if not self.is_streaming:
            return
        
        try:
            # 이미지 압축 (스트리밍 효율성)
            pil_image = Image.fromarray(image_array)
            
            # RGB는 더 고화질, SLAM은 압축률 높임
            if 'rgb' in stream_label:
                pil_image = pil_image.resize((400, 400))
                quality = 60
            else:
                pil_image = pil_image.resize((200, 200))  
                quality = 40
            
            buffer = io.BytesIO()
            pil_image.save(buffer, format='JPEG', quality=quality)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Kafka 메시지 구성 (공식 패턴 유지)
            message_data = {
                'stream_name': stream_label,
                'stream_id': stream_id,
                'capture_timestamp_ns': timestamp_ns,
                'device_timestamp_ns': timestamp_ns,
                'original_shape': list(image_array.shape),
                'compressed_shape': list(pil_image.size),
                'image_data': image_base64,
                'data_size_bytes': len(image_base64),
                'data_type': 'streaming_image',
                'processing_timestamp': time.time(),
                'message_sequence': self.message_count
            }
            
            # 토픽 선택
            if 'rgb' in stream_label:
                topic = 'stream-camera-rgb'
            elif 'slam' in stream_label:
                topic = 'vrs-frames'
            else:
                topic = 'image-metadata'
            
            # Kafka로 전송 (논블로킹)
            self.kafka_producer.send(topic, value=message_data, key=stream_label.encode())
            
            # 통계 업데이트
            if stream_label not in self.stream_stats:
                self.stream_stats[stream_label] = 0
            self.stream_stats[stream_label] += 1
            self.message_count += 1
            
            # 주기적 로그 (스트리밍다운 느낌)
            if self.message_count % 10 == 0:
                print(f"[STREAMING] {self.message_count}개 전송 - 최신: {stream_label}")
            
        except Exception as e:
            print(f"[ERROR] on_image_received 오류: {e}")
    
    def on_sensor_data_received(self, sensor_data, stream_label: str, stream_id: str):
        """센서 데이터 수신 콜백"""
        if not self.is_streaming:
            return
        
        try:
            device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
            host_timestamp = sensor_data.get_time_ns(TimeDomain.HOST_TIME)
            
            message_data = {
                'stream_name': stream_label,
                'stream_id': stream_id,
                'device_timestamp_ns': device_timestamp,
                'host_timestamp_ns': host_timestamp,
                'sensor_type': str(sensor_data.sensor_data_type()),
                'data_type': 'streaming_sensor',
                'processing_timestamp': time.time(),
                'message_sequence': self.message_count
            }
            
            # 센서 타입별 토픽 분류
            if 'imu' in stream_label:
                topic = 'stream-imu-right' if 'right' in stream_label else 'sensor-data'
            else:
                topic = 'sensor-data'
            
            self.kafka_producer.send(topic, value=message_data, key=stream_label.encode())
            
            if stream_label not in self.stream_stats:
                self.stream_stats[stream_label] = 0
            self.stream_stats[stream_label] += 1
            self.message_count += 1
            
        except Exception as e:
            print(f"[ERROR] on_sensor_data_received 오류: {e}")
    
    def start_streaming(self):
        """스트리밍 시작"""
        self.is_streaming = True
        self.message_count = 0
        self.stream_stats = {}
        print("[OK] Observer 스트리밍 시작")
    
    def stop_streaming(self):
        """스트리밍 중지"""
        self.is_streaming = False
        print(f"[OK] Observer 스트리밍 중지 - 총 {self.message_count}개 전송")
        print("스트림별 통계:")
        for stream, count in self.stream_stats.items():
            print(f"  {stream}: {count}개")


class AriaVRSStreamer:
    """
    VRS 파일을 실시간 스트리밍처럼 재생하는 클래스
    공식 StreamingManager 패턴을 모방
    """
    
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.provider = None
        self.observer = None
        self.kafka_producer = None
        
        # 공식 패턴의 스트림 매핑
        self.stream_mappings = {
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"),
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
        }
    
    def setup_streaming(self):
        """스트리밍 설정 (공식 패턴 모방)"""
        try:
            # VRS 프로바이더 생성 (ipynb 패턴)
            print(f"Creating data provider from {self.vrs_file_path}")
            self.provider = data_provider.create_vrs_data_provider(self.vrs_file_path)
            
            if not self.provider:
                print("Invalid vrs data provider")
                return False
            
            # Kafka Producer 생성
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                max_request_size=10485760,
                compression_type='gzip',
                batch_size=16384,
                linger_ms=5  # 약간의 배치 지연
            )
            
            # Observer 생성 (공식 패턴)
            self.observer = AriaStreamingObserver(self.kafka_producer)
            
            print("[OK] 스트리밍 설정 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 스트리밍 설정 실패: {e}")
            return False
    
    async def start_streaming(self, duration_seconds: int = 30):
        """
        연속 스트리밍 시작 (공식 StreamingManager.start_streaming() 모방)
        deliver_queued_sensor_data로 연속적인 데이터 흐름 생성
        """
        if not self.provider or not self.observer:
            print("[ERROR] 스트리밍이 설정되지 않음")
            return
        
        print(f"연속 스트리밍 시작 ({duration_seconds}초) - Observer 패턴")
        
        # Observer 스트리밍 시작
        self.observer.start_streaming()
        
        try:
            # ipynb 패턴: deliver_queued_sensor_data 사용
            options = self.provider.get_default_deliver_queued_options()
            
            # 시간 범위 설정
            rgb_stream_id = StreamId("214-1")
            start_time = self.provider.get_first_time_ns(rgb_stream_id, TimeDomain.DEVICE_TIME)
            end_time = start_time + (duration_seconds * 1_000_000_000)
            
            options.set_truncate_first_device_time_ns(start_time)
            options.set_truncate_last_device_time_ns(end_time)
            
            # 스트림 설정 (데이터 overflow 방지)
            slam_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_CAMERA_DATA)
            imu_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_IMU_DATA)
            rgb_stream_ids = options.get_stream_ids(RecordableTypeId.RGB_CAMERA_DATA)
            
            # 적절한 샘플링 레이트
            for stream_id in slam_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 8)  # 8프레임 중 1개
                
            for stream_id in rgb_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 15)  # 15프레임 중 1개
                
            for stream_id in imu_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 30)  # 30개 중 1개
            
            # 연속 스트리밍 (Observer 패턴으로 처리)
            iterator = self.provider.deliver_queued_sensor_data(options)
            
            for sensor_data in iterator:
                if not self.observer.is_streaming:
                    break
                
                stream_id = sensor_data.stream_id()
                stream_label = self.provider.get_label_from_stream_id(stream_id)
                
                # 이미지 데이터인 경우
                if hasattr(sensor_data, 'image_data_and_record'):
                    try:
                        image_data = self.provider.get_image_data_by_index(stream_id, 0)
                        if image_data and image_data[0]:
                            image_array = image_data[0].to_numpy_array()
                            # Observer 콜백 호출 (공식 패턴)
                            self.observer.on_image_received(
                                image_array, 
                                stream_label, 
                                str(stream_id),
                                sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                            )
                    except:
                        pass  # 이미지가 아닌 경우 무시
                
                # 센서 데이터인 경우
                else:
                    # Observer 콜백 호출
                    self.observer.on_sensor_data_received(sensor_data, stream_label, str(stream_id))
                
                # 스트리밍 속도 조절 (실시간 느낌)
                await asyncio.sleep(0.05)  # 50ms 간격
                
        except Exception as e:
            print(f"[ERROR] 스트리밍 오류: {e}")
        finally:
            self.stop_streaming()
    
    def stop_streaming(self):
        """스트리밍 중지 (공식 패턴)"""
        if self.observer:
            self.observer.stop_streaming()
        
        if self.kafka_producer:
            self.kafka_producer.flush()
            self.kafka_producer.close()
        
        print("[OK] 스트리밍 완전 중지")


async def test_observer_streaming():
    """Observer 패턴 스트리밍 테스트"""
    print("=== 공식 Observer 패턴 스트리밍 테스트 ===")
    
    vrs_file = "data/mps_samples/sample.vrs"
    
    if not os.path.exists(vrs_file):
        print(f"[ERROR] VRS 파일 없음: {vrs_file}")
        return
    
    # VRS Streamer 생성 (공식 패턴)
    streamer = AriaVRSStreamer(vrs_file)
    
    if not streamer.setup_streaming():
        print("[ERROR] 스트리밍 설정 실패")
        return
    
    print("Observer 패턴으로 10초간 연속 스트리밍...")
    await streamer.start_streaming(duration_seconds=10)
    
    print("[SUCCESS] Observer 패턴 스트리밍 완료")


if __name__ == "__main__":
    asyncio.run(test_observer_streaming())