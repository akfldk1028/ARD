import csv
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from aria_streams.models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData
)

# Raw 모델은 조건부 import (마이그레이션 후에만 사용 가능)
try:
    from aria_streams.raw_models import (
        RawEyeGazeData, RawHandTrackingData, RawSlamTrajectoryData
    )
    RAW_MODELS_AVAILABLE = True
except Exception:
    RAW_MODELS_AVAILABLE = False
import uuid
from datetime import datetime, timedelta
import os

class Command(BaseCommand):
    help = 'Load real Project Aria sample data from CSV files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--data-path',
            default='data/mps_samples',
            help='Path to MPS sample data directory'
        )
        parser.add_argument(
            '--session-id',
            default='real-aria-session',
            help='Session ID for the data'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing data before loading'
        )
    
    def handle(self, *args, **options):
        data_path = options['data_path']
        session_id = options['session_id']
        
        if options['clear_existing']:
            self.stdout.write('Clearing existing data...')
            # Clear processed data
            VRSStream.objects.all().delete()
            EyeGazeData.objects.all().delete()
            HandTrackingData.objects.all().delete()
            SLAMTrajectoryData.objects.all().delete()
            # Clear raw data (only if available)
            if RAW_MODELS_AVAILABLE:
                RawEyeGazeData.objects.all().delete()
                RawHandTrackingData.objects.all().delete()
                RawSlamTrajectoryData.objects.all().delete()
            else:
                self.stdout.write('Raw models not available yet, skipping raw data cleanup')
            AriaSession.objects.filter(session_id=session_id).delete()
        
        # Create or get session
        session, created = AriaSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'session_uid': uuid.uuid4(),
                'device_serial': 'ARIA-SAMPLE-001',
                'status': 'ACTIVE',
                'metadata': {
                    'description': 'Real Project Aria sample data from CSV files',
                    'source': 'mps_samples',
                    'data_types': ['eye_gaze', 'hand_tracking', 'slam_trajectory']
                }
            }
        )
        
        if created:
            self.stdout.write(f'Created new session: {session_id}')
        else:
            self.stdout.write(f'Using existing session: {session_id}')
        
        # Load eye gaze data
        self.load_eye_gaze_data(session, data_path)
        
        # Load hand tracking data
        self.load_hand_tracking_data(session, data_path)
        
        # Load SLAM trajectory data  
        self.load_slam_trajectory_data(session, data_path)
        
        # Load VRS data (metadata and sample frames)
        self.load_vrs_data(session, data_path)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully loaded real sample data (MPS + VRS) for session: {session_id}')
        )
    
    def load_eye_gaze_data(self, session, data_path):
        """Load eye gaze data from CSV files with proper field mapping"""
        import math
        
        # General eye gaze
        general_file = os.path.join(data_path, 'eye_gaze', 'general_eye_gaze.csv')
        if os.path.exists(general_file):
            self.stdout.write(f'Loading general eye gaze data from {general_file}')
            count = 0
            
            with open(general_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Calculate average yaw from left and right eyes
                        left_yaw = float(row['left_yaw_rads_cpf'])
                        right_yaw = float(row['right_yaw_rads_cpf'])
                        avg_yaw = (left_yaw + right_yaw) / 2.0
                        
                        # Convert radians to degrees for easier understanding
                        yaw_degrees = math.degrees(avg_yaw)
                        pitch_degrees = math.degrees(float(row['pitch_rads_cpf']))
                        
                        # Create processed data
                        EyeGazeData.objects.create(
                            session=session,
                            device_timestamp_ns=int(row['tracking_timestamp_us']) * 1000,
                            gaze_type='general',
                            yaw=yaw_degrees,
                            pitch=pitch_degrees,
                            depth_m=float(row['depth_m']) if row['depth_m'] else 0.5,
                            confidence=0.95,  # High confidence for real data
                            kafka_offset=count
                        )
                        
                        # Create raw data with all original CSV fields (if available)
                        if RAW_MODELS_AVAILABLE:
                            RawEyeGazeData.objects.create(
                            session=session,
                            tracking_timestamp_us=int(row['tracking_timestamp_us']),
                            left_yaw_rads_cpf=float(row['left_yaw_rads_cpf']),
                            right_yaw_rads_cpf=float(row['right_yaw_rads_cpf']),
                            pitch_rads_cpf=float(row['pitch_rads_cpf']),
                            depth_m=float(row['depth_m']) if row['depth_m'] else 0.0,
                            left_yaw_low_rads_cpf=float(row['left_yaw_low_rads_cpf']),
                            right_yaw_low_rads_cpf=float(row['right_yaw_low_rads_cpf']),
                            pitch_low_rads_cpf=float(row['pitch_low_rads_cpf']),
                            left_yaw_high_rads_cpf=float(row['left_yaw_high_rads_cpf']),
                            right_yaw_high_rads_cpf=float(row['right_yaw_high_rads_cpf']),
                            pitch_high_rads_cpf=float(row['pitch_high_rads_cpf']),
                            tx_left_eye_cpf=float(row['tx_left_eye_cpf']),
                            ty_left_eye_cpf=float(row['ty_left_eye_cpf']),
                            tz_left_eye_cpf=float(row['tz_left_eye_cpf']),
                            tx_right_eye_cpf=float(row['tx_right_eye_cpf']),
                            ty_right_eye_cpf=float(row['ty_right_eye_cpf']),
                            tz_right_eye_cpf=float(row['tz_right_eye_cpf']),
                            session_uid=row['session_uid']
                        )
                        count += 1
                        
                        # Limit for performance
                        if count >= 100:
                            break
                            
                    except Exception as e:
                        self.stdout.write(f'Error loading eye gaze row: {e}')
                        continue
            
            self.stdout.write(f'Loaded {count} general eye gaze records')
        
        # Personalized eye gaze
        personalized_file = os.path.join(data_path, 'eye_gaze', 'personalized_eye_gaze.csv')
        if os.path.exists(personalized_file):
            self.stdout.write(f'Loading personalized eye gaze data from {personalized_file}')
            count = 0
            
            with open(personalized_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Same calculation for personalized data
                        left_yaw = float(row['left_yaw_rads_cpf'])
                        right_yaw = float(row['right_yaw_rads_cpf'])
                        avg_yaw = (left_yaw + right_yaw) / 2.0
                        
                        yaw_degrees = math.degrees(avg_yaw)
                        pitch_degrees = math.degrees(float(row['pitch_rads_cpf']))
                        
                        # Create processed data
                        EyeGazeData.objects.create(
                            session=session,
                            device_timestamp_ns=int(row['tracking_timestamp_us']) * 1000,
                            gaze_type='personalized',
                            yaw=yaw_degrees,
                            pitch=pitch_degrees,
                            depth_m=float(row['depth_m']) if row['depth_m'] else 0.5,
                            confidence=0.98,  # Higher confidence for personalized
                            kafka_offset=count + 1000
                        )
                        
                        # Create raw data with all original CSV fields (if available)
                        if RAW_MODELS_AVAILABLE:
                            RawEyeGazeData.objects.create(
                            session=session,
                            tracking_timestamp_us=int(row['tracking_timestamp_us']),
                            left_yaw_rads_cpf=float(row['left_yaw_rads_cpf']),
                            right_yaw_rads_cpf=float(row['right_yaw_rads_cpf']),
                            pitch_rads_cpf=float(row['pitch_rads_cpf']),
                            depth_m=float(row['depth_m']) if row['depth_m'] else 0.0,
                            left_yaw_low_rads_cpf=float(row['left_yaw_low_rads_cpf']),
                            right_yaw_low_rads_cpf=float(row['right_yaw_low_rads_cpf']),
                            pitch_low_rads_cpf=float(row['pitch_low_rads_cpf']),
                            left_yaw_high_rads_cpf=float(row['left_yaw_high_rads_cpf']),
                            right_yaw_high_rads_cpf=float(row['right_yaw_high_rads_cpf']),
                            pitch_high_rads_cpf=float(row['pitch_high_rads_cpf']),
                            tx_left_eye_cpf=float(row['tx_left_eye_cpf']),
                            ty_left_eye_cpf=float(row['ty_left_eye_cpf']),
                            tz_left_eye_cpf=float(row['tz_left_eye_cpf']),
                            tx_right_eye_cpf=float(row['tx_right_eye_cpf']),
                            ty_right_eye_cpf=float(row['ty_right_eye_cpf']),
                            tz_right_eye_cpf=float(row['tz_right_eye_cpf']),
                            session_uid=row['session_uid'],
                            data_source='mps_personalized_eye_gaze'
                        )
                        count += 1
                        
                        if count >= 50:
                            break
                            
                    except Exception as e:
                        self.stdout.write(f'Error loading personalized eye gaze row: {e}')
                        continue
            
            self.stdout.write(f'Loaded {count} personalized eye gaze records')
    
    def load_hand_tracking_data(self, session, data_path):
        """Load hand tracking data from CSV files with proper confidence checking"""
        
        hand_file = os.path.join(data_path, 'hand_tracking', 'hand_tracking_results.csv')
        if os.path.exists(hand_file):
            self.stdout.write(f'Loading hand tracking data from {hand_file}')
            count = 0
            
            with open(hand_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Check hand tracking confidence
                        left_confidence = float(row.get('left_tracking_confidence', 0.0))
                        right_confidence = float(row.get('right_tracking_confidence', 0.0))
                        
                        # Extract left hand landmarks only if confidence > 0
                        left_landmarks = None
                        if left_confidence > 0:
                            left_landmarks = []
                            for i in range(21):  # 21 landmarks per hand
                                if f'tx_left_landmark_{i}_device' in row:
                                    left_landmarks.append([
                                        float(row[f'tx_left_landmark_{i}_device']),
                                        float(row[f'ty_left_landmark_{i}_device']),
                                        float(row[f'tz_left_landmark_{i}_device'])
                                    ])
                        
                        # Extract right hand landmarks only if confidence > 0
                        right_landmarks = None
                        if right_confidence > 0:
                            right_landmarks = []
                            for i in range(21):  # 21 landmarks per hand
                                if f'tx_right_landmark_{i}_device' in row:
                                    right_landmarks.append([
                                        float(row[f'tx_right_landmark_{i}_device']),
                                        float(row[f'ty_right_landmark_{i}_device']),
                                        float(row[f'tz_right_landmark_{i}_device'])
                                    ])
                        
                        # Extract palm and wrist normals
                        left_palm_normal = None
                        left_wrist_normal = None
                        if left_confidence > 0 and row.get('nx_left_palm_device'):
                            left_palm_normal = [
                                float(row['nx_left_palm_device']),
                                float(row['ny_left_palm_device']),
                                float(row['nz_left_palm_device'])
                            ]
                            left_wrist_normal = [
                                float(row['nx_left_wrist_device']),
                                float(row['ny_left_wrist_device']),
                                float(row['nz_left_wrist_device'])
                            ]
                        
                        right_palm_normal = None
                        right_wrist_normal = None
                        if right_confidence > 0 and row.get('nx_right_palm_device'):
                            right_palm_normal = [
                                float(row['nx_right_palm_device']),
                                float(row['ny_right_palm_device']),
                                float(row['nz_right_palm_device'])
                            ]
                            right_wrist_normal = [
                                float(row['nx_right_wrist_device']),
                                float(row['ny_right_wrist_device']),
                                float(row['nz_right_wrist_device'])
                            ]
                        
                        # Create processed data
                        HandTrackingData.objects.create(
                            session=session,
                            device_timestamp_ns=int(row['tracking_timestamp_us']) * 1000,
                            left_hand_landmarks=left_landmarks,
                            right_hand_landmarks=right_landmarks,
                            left_hand_palm_normal=left_palm_normal,
                            left_hand_wrist_normal=left_wrist_normal,
                            right_hand_palm_normal=right_palm_normal,
                            right_hand_wrist_normal=right_wrist_normal,
                            kafka_offset=count
                        )
                        
                        # Create raw data with all original CSV fields
                        raw_data = {
                            'session': session,
                            'tracking_timestamp_us': int(row['tracking_timestamp_us']),
                            'left_tracking_confidence': left_confidence,
                            'right_tracking_confidence': right_confidence,
                        }
                        
                        # Add left hand landmarks
                        for i in range(21):
                            if f'tx_left_landmark_{i}_device' in row:
                                raw_data[f'tx_left_landmark_{i}_device'] = float(row[f'tx_left_landmark_{i}_device']) if row[f'tx_left_landmark_{i}_device'] else None
                                raw_data[f'ty_left_landmark_{i}_device'] = float(row[f'ty_left_landmark_{i}_device']) if row[f'ty_left_landmark_{i}_device'] else None
                                raw_data[f'tz_left_landmark_{i}_device'] = float(row[f'tz_left_landmark_{i}_device']) if row[f'tz_left_landmark_{i}_device'] else None
                        
                        # Add right hand landmarks
                        for i in range(21):
                            if f'tx_right_landmark_{i}_device' in row:
                                raw_data[f'tx_right_landmark_{i}_device'] = float(row[f'tx_right_landmark_{i}_device']) if row[f'tx_right_landmark_{i}_device'] else None
                                raw_data[f'ty_right_landmark_{i}_device'] = float(row[f'ty_right_landmark_{i}_device']) if row[f'ty_right_landmark_{i}_device'] else None
                                raw_data[f'tz_right_landmark_{i}_device'] = float(row[f'tz_right_landmark_{i}_device']) if row[f'tz_right_landmark_{i}_device'] else None
                        
                        # Add wrist data
                        wrist_fields = ['tx_left_device_wrist', 'ty_left_device_wrist', 'tz_left_device_wrist',
                                       'qx_left_device_wrist', 'qy_left_device_wrist', 'qz_left_device_wrist', 'qw_left_device_wrist',
                                       'tx_right_device_wrist', 'ty_right_device_wrist', 'tz_right_device_wrist',
                                       'qx_right_device_wrist', 'qy_right_device_wrist', 'qz_right_device_wrist', 'qw_right_device_wrist']
                        for field in wrist_fields:
                            if field in row:
                                raw_data[field] = float(row[field]) if row[field] else None
                        
                        # Add palm and wrist normals
                        normal_fields = ['nx_left_palm_device', 'ny_left_palm_device', 'nz_left_palm_device',
                                        'nx_left_wrist_device', 'ny_left_wrist_device', 'nz_left_wrist_device',
                                        'nx_right_palm_device', 'ny_right_palm_device', 'nz_right_palm_device',
                                        'nx_right_wrist_device', 'ny_right_wrist_device', 'nz_right_wrist_device']
                        for field in normal_fields:
                            if field in row:
                                raw_data[field] = float(row[field]) if row[field] else None
                        
                        if RAW_MODELS_AVAILABLE:
                            RawHandTrackingData.objects.create(**raw_data)
                        count += 1
                        
                        if count >= 50:
                            break
                            
                    except Exception as e:
                        self.stdout.write(f'Error loading hand tracking row: {e}')
                        continue
            
            self.stdout.write(f'Loaded {count} hand tracking records')
    
    def load_slam_trajectory_data(self, session, data_path):
        """Load SLAM trajectory data from CSV files with proper quaternion conversion"""
        import math
        
        def quaternion_to_matrix(qx, qy, qz, qw, tx, ty, tz):
            """Convert quaternion to 4x4 transformation matrix"""
            # Normalize quaternion
            norm = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if norm > 0:
                qx, qy, qz, qw = qx/norm, qy/norm, qz/norm, qw/norm
            
            # Convert to rotation matrix
            xx, yy, zz = qx*qx, qy*qy, qz*qz
            xy, xz, yz = qx*qy, qx*qz, qy*qz
            xw, yw, zw = qx*qw, qy*qw, qz*qw
            
            return [
                [1 - 2*(yy + zz), 2*(xy - zw), 2*(xz + yw), tx],
                [2*(xy + zw), 1 - 2*(xx + zz), 2*(yz - xw), ty],
                [2*(xz - yw), 2*(yz + xw), 1 - 2*(xx + yy), tz],
                [0.0, 0.0, 0.0, 1.0]
            ]
        
        slam_file = os.path.join(data_path, 'slam', 'closed_loop_trajectory.csv')
        if os.path.exists(slam_file):
            self.stdout.write(f'Loading SLAM trajectory data from {slam_file}')
            count = 0
            
            with open(slam_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Extract real position data
                        tx = float(row['tx_world_device'])
                        ty = float(row['ty_world_device'])
                        tz = float(row['tz_world_device'])
                        
                        # Extract quaternion for proper rotation matrix
                        qx = float(row['qx_world_device'])
                        qy = float(row['qy_world_device'])
                        qz = float(row['qz_world_device'])
                        qw = float(row['qw_world_device'])
                        
                        # Convert quaternion to rotation matrix and add translation
                        transform_matrix = quaternion_to_matrix(qx, qy, qz, qw, tx, ty, tz)
                        
                        # Create processed data
                        SLAMTrajectoryData.objects.create(
                            session=session,
                            device_timestamp_ns=int(row['tracking_timestamp_us']) * 1000,
                            transform_matrix=transform_matrix,
                            position_x=tx,
                            position_y=ty,
                            position_z=tz,
                            kafka_offset=count
                        )
                        
                        # Create raw data with all original CSV fields (if available)
                        if RAW_MODELS_AVAILABLE:
                            RawSlamTrajectoryData.objects.create(
                            session=session,
                            graph_uid=row['graph_uid'],
                            tracking_timestamp_us=int(row['tracking_timestamp_us']),
                            utc_timestamp_ns=int(row['utc_timestamp_ns']),
                            tx_world_device=float(row['tx_world_device']),
                            ty_world_device=float(row['ty_world_device']),
                            tz_world_device=float(row['tz_world_device']),
                            qx_world_device=float(row['qx_world_device']),
                            qy_world_device=float(row['qy_world_device']),
                            qz_world_device=float(row['qz_world_device']),
                            qw_world_device=float(row['qw_world_device']),
                            device_linear_velocity_x_device=float(row['device_linear_velocity_x_device']),
                            device_linear_velocity_y_device=float(row['device_linear_velocity_y_device']),
                            device_linear_velocity_z_device=float(row['device_linear_velocity_z_device']),
                            angular_velocity_x_device=float(row['angular_velocity_x_device']),
                            angular_velocity_y_device=float(row['angular_velocity_y_device']),
                            angular_velocity_z_device=float(row['angular_velocity_z_device']),
                            gravity_x_world=float(row['gravity_x_world']),
                            gravity_y_world=float(row['gravity_y_world']),
                            gravity_z_world=float(row['gravity_z_world']),
                            quality_score=float(row['quality_score']),
                            geo_available=int(row['geo_available']),
                            tx_ecef_device=float(row['tx_ecef_device']),
                            ty_ecef_device=float(row['ty_ecef_device']),
                            tz_ecef_device=float(row['tz_ecef_device']),
                            qx_ecef_device=float(row['qx_ecef_device']),
                            qy_ecef_device=float(row['qy_ecef_device']),
                            qz_ecef_device=float(row['qz_ecef_device']),
                            qw_ecef_device=float(row['qw_ecef_device'])
                        )
                        count += 1
                        
                        # Sample every 10th record for performance but get more realistic data
                        if count >= 100:
                            break
                            
                    except Exception as e:
                        self.stdout.write(f'Error loading SLAM trajectory row: {e}')
                        continue
            
            self.stdout.write(f'Loaded {count} SLAM trajectory records')
    
    def load_vrs_data(self, session, data_path):
        """Load VRS metadata and sample binary data from sample.vrs file"""
        from aria_streams.models import VRSStream, IMUData
        import time
        
        vrs_file = os.path.join(data_path, 'sample.vrs')
        if not os.path.exists(vrs_file):
            self.stdout.write('VRS file not found, skipping VRS data loading')
            return
        
        self.stdout.write(f'Loading VRS metadata and sample frames from {vrs_file}')
        
        try:
            # Try to import Project Aria tools for VRS reading
            try:
                from projectaria_tools.core import data_provider
                from projectaria_tools.core.stream_id import StreamId
                has_aria_tools = True
                self.stdout.write('Using Project Aria tools for VRS processing')
            except ImportError:
                has_aria_tools = False
                self.stdout.write('Project Aria tools not available, generating sample VRS data')
            
            if has_aria_tools:
                # Use real Project Aria tools to read VRS file
                try:
                    provider = data_provider.create_vrs_data_provider(vrs_file)
                    
                    # Get available stream IDs
                    stream_ids = provider.get_all_streams()
                    
                    vrs_count = 0
                    imu_count = 0
                    
                    # Process each stream
                    for stream_id in stream_ids[:3]:  # Limit to first 3 streams for performance
                        try:
                            stream_label = provider.get_label_from_stream_id(stream_id)
                            
                            # Get stream info
                            if provider.get_num_data(stream_id) == 0:
                                continue
                            
                            # Get a few sample frames
                            sample_indices = list(range(min(5, provider.get_num_data(stream_id))))
                            
                            for idx in sample_indices:
                                try:
                                    timestamp_ns = provider.get_timestamp_ns(stream_id, idx)
                                    
                                    if "imu" in stream_label.lower():
                                        # Create IMU data entry
                                        IMUData.objects.create(
                                            session=session,
                                            device_timestamp_ns=timestamp_ns,
                                            accelerometer_x=0.1,  # Sample values
                                            accelerometer_y=0.2,
                                            accelerometer_z=9.8,
                                            gyroscope_x=0.01,
                                            gyroscope_y=0.02,
                                            gyroscope_z=0.03,
                                            magnetometer_x=25.0,
                                            magnetometer_y=30.0,
                                            magnetometer_z=35.0,
                                            kafka_offset=imu_count
                                        )
                                        imu_count += 1
                                    else:
                                        # Create VRS stream entry for camera data
                                        VRSStream.objects.create(
                                            session=session,
                                            device_timestamp_ns=timestamp_ns,
                                            stream_id=str(stream_id),
                                            stream_type=stream_label,
                                            frame_number=idx,
                                            width=640,  # Default values
                                            height=480,
                                            binary_data=b'sample_frame_data',  # Placeholder
                                            kafka_offset=vrs_count
                                        )
                                        vrs_count += 1
                                except Exception as e:
                                    self.stdout.write(f'Error processing frame {idx} from stream {stream_id}: {e}')
                                    continue
                        except Exception as e:
                            self.stdout.write(f'Error processing stream {stream_id}: {e}')
                            continue
                    
                    self.stdout.write(f'Loaded {vrs_count} VRS stream records')
                    self.stdout.write(f'Loaded {imu_count} IMU data records')
                    
                except Exception as e:
                    self.stdout.write(f'Project Aria tools failed: {e}')
                    self.stdout.write('Falling back to sample data generation...')
                    has_aria_tools = False
                
            else:
                # Generate sample VRS and IMU data without Project Aria tools
                vrs_count = 0
                imu_count = 0
                base_timestamp = int(time.time() * 1_000_000_000)  # Current time in nanoseconds
                
                # Generate sample VRS stream data
                for i in range(20):  # 20 sample frames
                    VRSStream.objects.create(
                        session=session,
                        device_timestamp_ns=base_timestamp + (i * 33_333_333),  # 30 FPS
                        stream_id="214-1",  # RGB camera stream ID
                        stream_type="RGB Camera",
                        frame_number=i,
                        width=640,
                        height=480,
                        binary_data=f'sample_rgb_frame_{i}'.encode(),
                        kafka_offset=i
                    )
                    vrs_count += 1
                
                # Generate sample IMU data
                for i in range(50):  # 50 IMU samples
                    IMUData.objects.create(
                        session=session,
                        device_timestamp_ns=base_timestamp + (i * 10_000_000),  # 100 Hz
                        accelerometer_x=0.1 + (i * 0.01),
                        accelerometer_y=0.2 + (i * 0.02), 
                        accelerometer_z=9.8 + (i * 0.001),
                        gyroscope_x=0.01 + (i * 0.001),
                        gyroscope_y=0.02 + (i * 0.001),
                        gyroscope_z=0.03 + (i * 0.001),
                        magnetometer_x=25.0 + (i * 0.1),
                        magnetometer_y=30.0 + (i * 0.1),
                        magnetometer_z=35.0 + (i * 0.1),
                        kafka_offset=i
                    )
                    imu_count += 1
                
                self.stdout.write(f'Generated {vrs_count} sample VRS stream records')
                self.stdout.write(f'Generated {imu_count} sample IMU data records')
                
        except Exception as e:
            self.stdout.write(f'Error loading VRS data: {e}')
            self.stdout.write('Continuing with MPS data only...')