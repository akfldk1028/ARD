"""
ipynb와 공식문서 패턴을 정확히 따른 이미지 스트리밍 서비스
"""
import os
import base64
from io import BytesIO
from PIL import Image
import numpy as np
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions
from projectaria_tools.core.stream_id import StreamId
# from .data_downloader import download_ipynb_sample_data

class AriaImageStreaming:
    """ipynb 패턴을 따른 이미지 스트리밍"""
    
    def __init__(self):
        self.provider = None
        self.vrsfile = None
        self.stream_mappings = {
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"),
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
        }
    
    def setup_provider(self):
        """ipynb 패턴: 데이터 프로바이더 설정"""
        # 샘플 데이터 경로
        self.vrsfile = os.path.join(os.path.dirname(__file__), 'data', 'sample.vrs')
        
        if not os.path.exists(self.vrsfile):
            raise FileNotFoundError(f"VRS file not found: {self.vrsfile}")
        
        print(f"Creating data provider from {self.vrsfile}")
        self.provider = data_provider.create_vrs_data_provider(self.vrsfile)
        if not self.provider:
            raise Exception("Invalid vrs data provider")
    
    def get_image_by_index(self, stream_name, frame_index):
        """ipynb 패턴: 인덱스로 이미지 데이터 조회"""
        if not self.provider:
            self.setup_provider()
            
        if stream_name not in self.stream_mappings:
            raise ValueError(f"Unknown stream: {stream_name}")
        
        stream_id = self.stream_mappings[stream_name]
        
        # ipynb 패턴 그대로
        image_tuple = self.provider.get_image_data_by_index(stream_id, frame_index)
        image_data, record = image_tuple
        image_array = image_data.to_numpy_array()
        
        return {
            'stream_name': stream_name,
            'stream_id': str(stream_id),
            'frame_index': frame_index,
            'image_array': image_array,
            'image_shape': list(image_array.shape),
            'capture_timestamp_ns': record.capture_timestamp_ns,
            'frame_number': getattr(record, 'frame_number', None)
        }
    
    def get_image_by_time(self, stream_name, timestamp_ns, time_domain=TimeDomain.DEVICE_TIME, option=TimeQueryOptions.CLOSEST):
        """ipynb 패턴: 시간으로 이미지 데이터 조회"""
        if not self.provider:
            self.setup_provider()
            
        if stream_name not in self.stream_mappings:
            raise ValueError(f"Unknown stream: {stream_name}")
        
        stream_id = self.stream_mappings[stream_name]
        
        # ipynb 패턴 그대로
        image_tuple = self.provider.get_image_data_by_time_ns(stream_id, timestamp_ns, time_domain, option)
        image_data, record = image_tuple
        image_array = image_data.to_numpy_array()
        
        return {
            'stream_name': stream_name,
            'stream_id': str(stream_id),
            'query_timestamp_ns': timestamp_ns,
            'image_array': image_array,
            'image_shape': list(image_array.shape),
            'capture_timestamp_ns': record.capture_timestamp_ns,
            'frame_number': getattr(record, 'frame_number', None)
        }
    
    def get_all_streams_by_index(self, frame_index):
        """ipynb 패턴: 모든 스트림에서 동일 인덱스 이미지 조회"""
        if not self.provider:
            self.setup_provider()
        
        results = {}
        for stream_name, stream_id in self.stream_mappings.items():
            try:
                # ipynb 패턴 그대로
                image_tuple = self.provider.get_image_data_by_index(stream_id, frame_index)
                image_data, record = image_tuple
                image_array = image_data.to_numpy_array()
                
                results[stream_name] = {
                    'stream_id': str(stream_id),
                    'frame_index': frame_index,
                    'image_shape': list(image_array.shape),
                    'capture_timestamp_ns': record.capture_timestamp_ns,
                    'image_array': image_array
                }
            except Exception as e:
                results[stream_name] = {'error': str(e)}
        
        return results
    
    def get_all_streams_by_time(self, timestamp_ns):
        """ipynb 패턴: 모든 스트림에서 동일 시간 이미지 조회"""
        if not self.provider:
            self.setup_provider()
        
        time_domain = TimeDomain.DEVICE_TIME
        option = TimeQueryOptions.CLOSEST
        
        results = {}
        for stream_name, stream_id in self.stream_mappings.items():
            try:
                # ipynb 패턴 그대로
                image_tuple = self.provider.get_image_data_by_time_ns(stream_id, timestamp_ns, time_domain, option)
                image_data, record = image_tuple
                image_array = image_data.to_numpy_array()
                
                results[stream_name] = {
                    'stream_id': str(stream_id),
                    'query_timestamp_ns': timestamp_ns,
                    'image_shape': list(image_array.shape),
                    'capture_timestamp_ns': record.capture_timestamp_ns,
                    'image_array': image_array
                }
            except Exception as e:
                results[stream_name] = {'error': str(e)}
        
        return results
    
    def convert_to_base64_jpeg(self, image_array, quality=85):
        """이미지 배열을 Base64 JPEG로 변환"""
        pil_image = Image.fromarray(image_array)
        buffer = BytesIO()
        pil_image.save(buffer, format='JPEG', quality=quality)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def get_stream_info(self):
        """스트림 정보 조회"""
        if not self.provider:
            self.setup_provider()
        
        stream_info = {}
        for stream_name, stream_id in self.stream_mappings.items():
            try:
                num_data = self.provider.get_num_data(stream_id)
                start_time = self.provider.get_first_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                end_time = self.provider.get_last_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                
                # 이미지 설정 정보
                image_config = self.provider.get_image_configuration(stream_id)
                
                stream_info[stream_name] = {
                    'stream_id': str(stream_id),
                    'num_frames': num_data,
                    'start_time_ns': start_time,
                    'end_time_ns': end_time,
                    'image_width': image_config.image_width,
                    'image_height': image_config.image_height,
                    'pixel_format': str(image_config.pixel_format),
                    'nominal_rate_hz': image_config.nominal_rate_hz
                }
            except Exception as e:
                stream_info[stream_name] = {'error': str(e)}
        
        return stream_info

def test_image_streaming():
    """이미지 스트리밍 테스트"""
    streaming = AriaImageStreaming()
    
    print("=== Stream Info ===")
    stream_info = streaming.get_stream_info()
    for name, info in stream_info.items():
        if 'error' not in info:
            print(f"{name}: {info['num_frames']} frames, {info['image_width']}x{info['image_height']}")
    
    print("\n=== Single Image Test ===")
    # RGB 카메라에서 첫 번째 프레임
    rgb_image = streaming.get_image_by_index("camera-rgb", 0)
    print(f"RGB Image: {rgb_image['image_shape']} @ {rgb_image['capture_timestamp_ns']}ns")
    
    print("\n=== All Streams Same Index ===")
    all_images = streaming.get_all_streams_by_index(1)
    for name, data in all_images.items():
        if 'error' not in data:
            print(f"{name}: {data['image_shape']} @ {data['capture_timestamp_ns']}ns")
    
    print("\n=== Time-based Query ===")
    # RGB 스트림의 시작 시간 사용
    start_time = stream_info['camera-rgb']['start_time_ns']
    time_images = streaming.get_all_streams_by_time(start_time)
    for name, data in time_images.items():
        if 'error' not in data:
            print(f"{name}: {data['image_shape']} @ actual: {data['capture_timestamp_ns']}ns")

if __name__ == "__main__":
    test_image_streaming()