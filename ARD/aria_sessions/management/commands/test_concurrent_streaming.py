"""
동시 스트리밍 테스트 - ipynb와 ticsync 패턴 확인
"""
from django.core.management.base import BaseCommand
from aria_sessions.image_streaming_service import AriaImageStreaming
from aria_sessions.streaming_service import AriaUnifiedStreaming

class Command(BaseCommand):
    help = '동시 스트리밍 테스트'

    def handle(self, *args, **options):
        self.stdout.write("=== 동시 이미지 스트리밍 테스트 ===")
        
        image_streaming = AriaImageStreaming()
        
        # 1. 모든 스트림 정보 조회
        stream_info = image_streaming.get_stream_info()
        self.stdout.write("Available streams:")
        for name, info in stream_info.items():
            if 'error' not in info:
                self.stdout.write(f"  {name}: {info['num_frames']} frames, {info['image_width']}x{info['image_height']}")
        
        # 2. 동일 인덱스로 모든 스트림 동시 조회 (ipynb 패턴)
        self.stdout.write("\n=== Frame 5에서 모든 스트림 동시 조회 ===")
        all_images_idx = image_streaming.get_all_streams_by_index(5)
        for name, data in all_images_idx.items():
            if 'error' not in data:
                self.stdout.write(f"  {name}: {data['image_shape']} @ {data['capture_timestamp_ns']}ns")
        
        # 3. 동일 시간으로 모든 스트림 동시 조회 (ticsync 개념)
        self.stdout.write("\n=== 특정 시간에서 모든 스트림 동시 조회 ===")
        target_time = stream_info['camera-rgb']['start_time_ns'] + 1000000000  # 1초 후
        all_images_time = image_streaming.get_all_streams_by_time(target_time)
        for name, data in all_images_time.items():
            if 'error' not in data:
                self.stdout.write(f"  {name}: {data['image_shape']} @ actual: {data['capture_timestamp_ns']}ns")
        
        # 4. 통합 센서 데이터 스트리밍 (deliver_queued_sensor_data)
        self.stdout.write("\n=== 통합 센서 데이터 스트리밍 ===")
        unified_streaming = AriaUnifiedStreaming()
        unified_streaming.vrsfile = image_streaming.vrsfile
        
        # 모든 카메라 스트림 활성화
        active_streams = ["camera-rgb", "camera-slam-left", "camera-slam-right", "camera-eyetracking"]
        results = unified_streaming.process_unified_stream(
            active_streams=active_streams,
            max_count=10,
            include_images=True
        )
        
        self.stdout.write(f"통합 스트리밍 결과: {len(results)}개 항목")
        for i, item in enumerate(results[:5]):  # 처음 5개만 출력
            has_image = item.get('has_image_data', False)
            self.stdout.write(f"  [{i+1}] {item['stream_label']} @ {item['device_timestamp_ns']}ns - Image: {has_image}")
        
        self.stdout.write(self.style.SUCCESS("\n동시 스트리밍 테스트 완료!"))