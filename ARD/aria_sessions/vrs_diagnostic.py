#!/usr/bin/env python3
"""
VRS 파일 진단 도구 - 모든 센서 데이터 확인
ipynb 패턴을 정확히 따라 VRS 파일의 모든 스트림과 센서 타입 분석
"""
import os
import sys
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId

def diagnose_vrs_file(vrs_file_path):
    """VRS 파일의 모든 센서 데이터 진단"""
    print(f"=== VRS 파일 진단: {vrs_file_path} ===")
    
    # 1. 데이터 프로바이더 생성
    print("\n1. 데이터 프로바이더 생성 중...")
    provider = data_provider.create_vrs_data_provider(vrs_file_path)
    if not provider:
        print("ERROR: 유효하지 않은 VRS 데이터 프로바이더")
        return
    
    print("OK 데이터 프로바이더 생성 성공")
    
    # 2. 모든 스트림 조회 (ipynb 패턴)
    print("\n2. 모든 스트림 조회...")
    try:
        all_streams = provider.get_all_streams()
        print(f"OK 총 {len(all_streams)}개 스트림 발견")
        
        stream_summary = {}
        for stream_id in all_streams:
            try:
                label = provider.get_label_from_stream_id(stream_id)
                data_count = provider.get_num_data(stream_id)
                
                # 시간 범위 확인
                if data_count > 0:
                    try:
                        start_time = provider.get_first_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                        end_time = provider.get_last_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                        duration_sec = (end_time - start_time) / 1e9
                    except:
                        start_time = end_time = duration_sec = 0
                else:
                    start_time = end_time = duration_sec = 0
                
                stream_summary[label] = {
                    'stream_id': str(stream_id),
                    'data_count': data_count,
                    'duration_sec': duration_sec,
                    'available': data_count > 0
                }
                
                status = "✅" if data_count > 0 else "❌"
                print(f"  {status} {label:<25} ({stream_id}) - {data_count:>6} 데이터, {duration_sec:.1f}초")
                
            except Exception as e:
                print(f"  ❌ 스트림 {stream_id} 처리 오류: {e}")
    
    except Exception as e:
        print(f"❌ 스트림 조회 실패: {e}")
        return
    
    # 3. RecordableTypeId별 센서 검색 (ipynb 패턴)
    print("\n3. 센서 타입별 상세 분석...")
    
    sensor_types = [
        (RecordableTypeId.SLAM_CAMERA_DATA, "SLAM 카메라"),
        (RecordableTypeId.RGB_CAMERA_DATA, "RGB 카메라"), 
        (RecordableTypeId.EYE_CAMERA_DATA, "아이트래킹 카메라"),
        (RecordableTypeId.SLAM_IMU_DATA, "SLAM IMU"),
        (RecordableTypeId.MOTION_IMU_DATA, "Motion IMU"),
        (RecordableTypeId.BAROMETER_DATA, "기압계"),
        (RecordableTypeId.MAGNETOMETER_DATA, "자력계"),
        (RecordableTypeId.AUDIO_DATA, "오디오"),
        (RecordableTypeId.GPS_DATA, "GPS"),
    ]
    
    found_sensors = {}
    for sensor_type, sensor_name in sensor_types:
        try:
            sensor_stream_ids = provider.get_stream_ids(sensor_type)
            if sensor_stream_ids:
                found_sensors[sensor_name] = []
                print(f"  ✅ {sensor_name}: {len(sensor_stream_ids)}개 스트림")
                for stream_id in sensor_stream_ids:
                    label = provider.get_label_from_stream_id(stream_id)
                    data_count = provider.get_num_data(stream_id)
                    found_sensors[sensor_name].append({
                        'label': label,
                        'stream_id': str(stream_id),
                        'data_count': data_count
                    })
                    print(f"    - {label} ({stream_id}): {data_count} 데이터")
            else:
                print(f"  ❌ {sensor_name}: 스트림 없음")
                
        except Exception as e:
            print(f"  ⚠️  {sensor_name}: 조회 오류 - {e}")
    
    # 4. 실제 센서 데이터 샘플링 테스트
    print("\n4. 센서 데이터 샘플링 테스트...")
    
    # deliver_queued_sensor_data로 실제 데이터 확인
    try:
        options = provider.get_default_deliver_queued_options()
        options.set_truncate_first_device_time_ns(int(1e8))  # 0.1초 후부터
        options.set_truncate_last_device_time_ns(int(1e9))   # 1초 전까지
        
        # 모든 센서 활성화
        options.deactivate_stream_all()
        
        # 사용 가능한 모든 스트림 활성화
        activated_count = 0
        for stream_id in all_streams:
            try:
                data_count = provider.get_num_data(stream_id)
                if data_count > 0:
                    options.activate_stream(stream_id)
                    options.set_subsample_rate(stream_id, 10)  # 10개 중 1개만 샘플링
                    activated_count += 1
            except:
                pass
        
        print(f"  활성화된 스트림: {activated_count}개")
        
        # 실제 데이터 이터레이션
        iterator = provider.deliver_queued_sensor_data(options)
        sensor_data_types = {}
        sample_count = 0
        
        for sensor_data in iterator:
            if sample_count >= 50:  # 50개 샘플만 테스트
                break
                
            try:
                label = provider.get_label_from_stream_id(sensor_data.stream_id())
                sensor_type = str(sensor_data.sensor_data_type())
                device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                
                if sensor_type not in sensor_data_types:
                    sensor_data_types[sensor_type] = []
                
                sensor_data_types[sensor_type].append({
                    'label': label,
                    'timestamp': device_timestamp,
                    'stream_id': str(sensor_data.stream_id())
                })
                
                sample_count += 1
                
            except Exception as e:
                print(f"    샘플 {sample_count} 처리 오류: {e}")
        
        print(f"  총 {sample_count}개 데이터 샘플 수집")
        print("\n  발견된 센서 데이터 타입:")
        for sensor_type, samples in sensor_data_types.items():
            unique_labels = set(sample['label'] for sample in samples)
            print(f"    ✅ {sensor_type}: {len(samples)}개 샘플, {len(unique_labels)}개 센서")
            for label in sorted(unique_labels):
                count = sum(1 for s in samples if s['label'] == label)
                print(f"      - {label}: {count}개")
        
    except Exception as e:
        print(f"  ❌ 센서 데이터 샘플링 실패: {e}")
    
    # 5. 요약 리포트
    print("\n" + "="*60)
    print("📊 VRS 파일 진단 요약")
    print("="*60)
    
    available_streams = [name for name, info in stream_summary.items() if info['available']]
    unavailable_streams = [name for name, info in stream_summary.items() if not info['available']]
    
    print(f"✅ 사용 가능한 스트림 ({len(available_streams)}개):")
    for stream in available_streams:
        info = stream_summary[stream]
        print(f"   - {stream}: {info['data_count']} 데이터, {info['duration_sec']:.1f}초")
    
    if unavailable_streams:
        print(f"\n❌ 사용 불가능한 스트림 ({len(unavailable_streams)}개):")
        for stream in unavailable_streams:
            print(f"   - {stream}")
    
    print(f"\n🔍 발견된 센서 타입:")
    for sensor_name, streams in found_sensors.items():
        if streams:
            total_data = sum(s['data_count'] for s in streams)
            print(f"   ✅ {sensor_name}: {len(streams)}개 스트림, {total_data} 총 데이터")
    
    return stream_summary, found_sensors

def main():
    """메인 함수"""
    # 기본 VRS 파일 경로 (aria_sessions/data/sample.vrs)
    current_dir = os.path.dirname(__file__)
    default_vrs_path = os.path.join(current_dir, 'data', 'sample.vrs')
    
    # 명령행 인자로 VRS 파일 경로 지정 가능
    if len(sys.argv) > 1:
        vrs_file_path = sys.argv[1]
    else:
        vrs_file_path = default_vrs_path
    
    if not os.path.exists(vrs_file_path):
        print(f"❌ VRS 파일을 찾을 수 없습니다: {vrs_file_path}")
        print(f"사용법: python {sys.argv[0]} [VRS_파일_경로]")
        return
    
    try:
        stream_summary, found_sensors = diagnose_vrs_file(vrs_file_path)
        print(f"\n✅ 진단 완료: {vrs_file_path}")
        
    except Exception as e:
        print(f"❌ 진단 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()