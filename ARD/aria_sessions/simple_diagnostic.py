#!/usr/bin/env python3
"""
Simple VRS diagnostic without Unicode symbols
"""
import os
import sys
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId

def diagnose_vrs_simple(vrs_file_path):
    """VRS 파일의 모든 센서 데이터 간단 진단"""
    print(f"=== VRS File Diagnostic: {vrs_file_path} ===")
    
    # 1. Create data provider
    print("\n1. Creating data provider...")
    provider = data_provider.create_vrs_data_provider(vrs_file_path)
    if not provider:
        print("ERROR: Invalid VRS data provider")
        return
    
    print("OK: Data provider created successfully")
    
    # 2. Get all streams
    print("\n2. Getting all streams...")
    try:
        all_streams = provider.get_all_streams()
        print(f"OK: Found {len(all_streams)} total streams")
        
        stream_summary = {}
        for stream_id in all_streams:
            try:
                label = provider.get_label_from_stream_id(stream_id)
                data_count = provider.get_num_data(stream_id)
                
                stream_summary[label] = {
                    'stream_id': str(stream_id),
                    'data_count': data_count,
                    'available': data_count > 0
                }
                
                status = "OK" if data_count > 0 else "EMPTY"
                print(f"  {status:5} {label:<25} ({stream_id}) - {data_count:>6} data points")
                
            except Exception as e:
                print(f"  ERROR processing stream {stream_id}: {e}")
    
    except Exception as e:
        print(f"ERROR: Failed to get streams: {e}")
        return
    
    # 3. Check specific sensor types
    print("\n3. Checking sensor types...")
    
    sensor_types = [
        (RecordableTypeId.SLAM_CAMERA_DATA, "SLAM Camera"),
        (RecordableTypeId.RGB_CAMERA_DATA, "RGB Camera"), 
        (RecordableTypeId.EYE_CAMERA_DATA, "Eye Tracking Camera"),
        (RecordableTypeId.SLAM_IMU_DATA, "SLAM IMU"),
        (RecordableTypeId.MOTION_IMU_DATA, "Motion IMU"),
        (RecordableTypeId.BAROMETER_DATA, "Barometer"),
        (RecordableTypeId.MAGNETOMETER_DATA, "Magnetometer"),
        (RecordableTypeId.AUDIO_DATA, "Audio"),
        (RecordableTypeId.GPS_DATA, "GPS"),
    ]
    
    found_sensors = {}
    for sensor_type, sensor_name in sensor_types:
        try:
            sensor_stream_ids = provider.get_stream_ids(sensor_type)
            if sensor_stream_ids:
                found_sensors[sensor_name] = []
                print(f"  OK    {sensor_name}: {len(sensor_stream_ids)} streams")
                for stream_id in sensor_stream_ids:
                    label = provider.get_label_from_stream_id(stream_id)
                    data_count = provider.get_num_data(stream_id)
                    found_sensors[sensor_name].append({
                        'label': label,
                        'stream_id': str(stream_id),
                        'data_count': data_count
                    })
                    print(f"    - {label} ({stream_id}): {data_count} data points")
            else:
                print(f"  EMPTY {sensor_name}: No streams")
                
        except Exception as e:
            print(f"  ERROR {sensor_name}: {e}")
    
    # 4. Test actual sensor data sampling
    print("\n4. Testing sensor data sampling...")
    
    try:
        options = provider.get_default_deliver_queued_options()
        options.set_truncate_first_device_time_ns(int(1e8))  # 0.1 sec after start
        options.set_truncate_last_device_time_ns(int(1e9))   # 1 sec before end
        
        # Activate all streams
        options.deactivate_stream_all()
        
        activated_count = 0
        for stream_id in all_streams:
            try:
                data_count = provider.get_num_data(stream_id)
                if data_count > 0:
                    options.activate_stream(stream_id)
                    options.set_subsample_rate(stream_id, 20)  # Sample every 20th data
                    activated_count += 1
            except:
                pass
        
        print(f"  Activated streams: {activated_count}")
        
        # Iterate through actual data
        iterator = provider.deliver_queued_sensor_data(options)
        sensor_data_types = {}
        sample_count = 0
        
        for sensor_data in iterator:
            if sample_count >= 100:  # Test 100 samples
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
                print(f"    Sample {sample_count} error: {e}")
        
        print(f"  Collected {sample_count} data samples total")
        print("\n  Found sensor data types:")
        for sensor_type, samples in sensor_data_types.items():
            unique_labels = set(sample['label'] for sample in samples)
            print(f"    OK {sensor_type}: {len(samples)} samples from {len(unique_labels)} sensors")
            for label in sorted(unique_labels):
                count = sum(1 for s in samples if s['label'] == label)
                print(f"      - {label}: {count} samples")
        
    except Exception as e:
        print(f"  ERROR: Sensor data sampling failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Summary report
    print("\n" + "="*60)
    print("SUMMARY: VRS File Diagnostic Results")
    print("="*60)
    
    available_streams = [name for name, info in stream_summary.items() if info['available']]
    unavailable_streams = [name for name, info in stream_summary.items() if not info['available']]
    
    print(f"Available streams ({len(available_streams)}):")
    for stream in available_streams:
        info = stream_summary[stream]
        print(f"   - {stream}: {info['data_count']} data points")
    
    if unavailable_streams:
        print(f"\nUnavailable streams ({len(unavailable_streams)}):")
        for stream in unavailable_streams:
            print(f"   - {stream}")
    
    print(f"\nFound sensor types:")
    for sensor_name, streams in found_sensors.items():
        if streams:
            total_data = sum(s['data_count'] for s in streams)
            print(f"   OK {sensor_name}: {len(streams)} streams, {total_data} total data")
    
    return stream_summary, found_sensors

def main():
    current_dir = os.path.dirname(__file__)
    default_vrs_path = os.path.join(current_dir, 'data', 'sample.vrs')
    
    if len(sys.argv) > 1:
        vrs_file_path = sys.argv[1]
    else:
        vrs_file_path = default_vrs_path
    
    if not os.path.exists(vrs_file_path):
        print(f"ERROR: VRS file not found: {vrs_file_path}")
        print(f"Usage: python {sys.argv[0]} [VRS_file_path]")
        return
    
    try:
        stream_summary, found_sensors = diagnose_vrs_simple(vrs_file_path)
        print(f"\nDiagnostic completed: {vrs_file_path}")
        
    except Exception as e:
        print(f"ERROR: Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()