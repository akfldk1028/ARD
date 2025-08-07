"""
XR 기기 초기 설정 및 데이터 생성 명령어
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from xr_devices.models import (
    XRDevice, DeviceSensorCapability, DataParser, SensorType, XRDeviceType, 
    DataFormat, StreamingProtocol
)


class Command(BaseCommand):
    help = 'Setup XR devices initial data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all XR device data',
        )
    
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting XR device data...')
            with transaction.atomic():
                XRDevice.objects.all().delete()
                DeviceSensorCapability.objects.all().delete()
                DataParser.objects.all().delete()
        
        self.stdout.write('Setting up XR devices...')
        
        with transaction.atomic():
            self.setup_devices()
            self.setup_parsers()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup XR devices!')
        )
    
    def setup_devices(self):
        """XR 기기 설정"""
        
        # Meta Aria
        aria_device, created = XRDevice.objects.get_or_create(
            name='Meta Aria Development Kit',
            defaults={
                'device_type': XRDeviceType.META_ARIA,
                'manufacturer': 'Meta',
                'model_version': 'Rev A',
                'supported_formats': [DataFormat.VRS.value, DataFormat.JSON_STREAM.value],
                'preferred_protocol': StreamingProtocol.KAFKA.value,
                'device_config': {
                    'vrs_sampling_rate': 30,
                    'max_concurrent_streams': 4,
                    'default_image_quality': 75,
                    'supported_stream_ids': ['214-1', '1201-1', '1201-2', '211-1']
                }
            }
        )
        if created:
            self.stdout.write(f'Created device: {aria_device.name}')
            
            # Aria 센서 능력 설정
            sensors = [
                (SensorType.CAMERA_RGB, '2880x2880', 30.0, 'RGB Camera'),
                (SensorType.CAMERA_FISHEYE, '640x480', 20.0, 'SLAM Cameras'),
                (SensorType.EYE_TRACKING, '320x240', 200.0, 'Eye Tracking'),
                (SensorType.IMU, None, 1000.0, 'IMU Sensor'),
                (SensorType.MAGNETOMETER, None, 100.0, 'Magnetometer'),
                (SensorType.BAROMETER, None, 50.0, 'Barometer'),
                (SensorType.GPS, None, 1.0, 'GPS'),
            ]
            
            for sensor_type, resolution, frequency, description in sensors:
                DeviceSensorCapability.objects.get_or_create(
                    device=aria_device,
                    sensor_type=sensor_type,
                    defaults={
                        'resolution': resolution,
                        'frequency_hz': frequency,
                        'sensor_config': {'description': description}
                    }
                )
        
        # Google AR Glass (미래 기기)
        glass_device, created = XRDevice.objects.get_or_create(
            name='Google AR Glass',
            defaults={
                'device_type': XRDeviceType.GOOGLE_GLASS,
                'manufacturer': 'Google',
                'model_version': 'Enterprise Edition',
                'supported_formats': [DataFormat.JSON_STREAM.value, DataFormat.PROTOBUF.value],
                'preferred_protocol': StreamingProtocol.WEBSOCKET.value,
                'device_config': {
                    'android_version': '14',
                    'assistant_integration': True,
                    'voice_commands': True
                }
            }
        )
        if created:
            self.stdout.write(f'Created device: {glass_device.name}')
            
            # Google Glass 센서 설정
            glass_sensors = [
                (SensorType.CAMERA_RGB, '1920x1080', 30.0, 'Front Camera'),
                (SensorType.IMU, None, 100.0, 'Motion Sensor'),
                (SensorType.GPS, None, 1.0, 'Location'),
                (SensorType.MICROPHONE, None, 48000.0, 'Voice Input'),
                (SensorType.VOICE_RECOGNITION, None, None, 'Speech Recognition'),
            ]
            
            for sensor_type, resolution, frequency, description in glass_sensors:
                DeviceSensorCapability.objects.get_or_create(
                    device=glass_device,
                    sensor_type=sensor_type,
                    defaults={
                        'resolution': resolution,
                        'frequency_hz': frequency,
                        'sensor_config': {'description': description}
                    }
                )
        
        # Apple Vision Pro (미래 기기)
        vision_device, created = XRDevice.objects.get_or_create(
            name='Apple Vision Pro',
            defaults={
                'device_type': XRDeviceType.APPLE_VISION,
                'manufacturer': 'Apple',
                'model_version': '1st Generation',
                'supported_formats': [DataFormat.GLTF.value, DataFormat.JSON_STREAM.value],
                'preferred_protocol': StreamingProtocol.GRPC.value,
                'device_config': {
                    'vision_os_version': '1.0',
                    'spatial_computing': True,
                    'siri_integration': True,
                    'continuity_support': True
                }
            }
        )
        if created:
            self.stdout.write(f'Created device: {vision_device.name}')
            
            # Apple Vision Pro 센서 설정
            vision_sensors = [
                (SensorType.CAMERA_RGB, '4K', 60.0, 'External Cameras'),
                (SensorType.CAMERA_DEPTH, '4K', 60.0, 'Depth Cameras'),
                (SensorType.EYE_TRACKING, '1024x1024', 120.0, 'Eye Tracking'),
                (SensorType.HAND_TRACKING, None, 60.0, 'Hand Tracking'),
                (SensorType.LIDAR, None, 30.0, 'LiDAR Scanner'),
                (SensorType.IMU, None, 1000.0, 'Motion Sensors'),
            ]
            
            for sensor_type, resolution, frequency, description in vision_sensors:
                DeviceSensorCapability.objects.get_or_create(
                    device=vision_device,
                    sensor_type=sensor_type,
                    defaults={
                        'resolution': resolution,
                        'frequency_hz': frequency,
                        'sensor_config': {'description': description}
                    }
                )
        
        # Microsoft HoloLens (미래 기기)
        hololens_device, created = XRDevice.objects.get_or_create(
            name='Microsoft HoloLens',
            defaults={
                'device_type': XRDeviceType.HOLOLENS,
                'manufacturer': 'Microsoft',
                'model_version': 'HoloLens 3',
                'supported_formats': [DataFormat.GLTF.value, DataFormat.JSON_STREAM.value],
                'preferred_protocol': StreamingProtocol.REST_API.value,
                'device_config': {
                    'windows_holographic_version': '21H1',
                    'mixed_reality': True,
                    'cortana_integration': True
                }
            }
        )
        if created:
            self.stdout.write(f'Created device: {hololens_device.name}')
    
    def setup_parsers(self):
        """데이터 파서 설정"""
        
        parsers = [
            # Meta Aria 파서
            {
                'device_type': XRDeviceType.META_ARIA,
                'data_format': DataFormat.VRS,
                'parser_class': 'xr_devices.parsers.meta.AriaVRSParser',
                'parser_version': '1.0.0',
                'supported_sensors': [
                    SensorType.CAMERA_RGB.value,
                    SensorType.CAMERA_FISHEYE.value,
                    SensorType.EYE_TRACKING.value,
                    SensorType.IMU.value,
                    SensorType.MAGNETOMETER.value,
                    SensorType.BAROMETER.value,
                    SensorType.GPS.value,
                ]
            },
            # Google Glass 파서
            {
                'device_type': XRDeviceType.GOOGLE_GLASS,
                'data_format': DataFormat.JSON_STREAM,
                'parser_class': 'xr_devices.parsers.meta.GoogleGlassParser',
                'parser_version': '1.0.0',
                'supported_sensors': [
                    SensorType.CAMERA_RGB.value,
                    SensorType.IMU.value,
                    SensorType.GPS.value,
                    SensorType.VOICE_RECOGNITION.value,
                ]
            },
            # Apple Vision Pro 파서
            {
                'device_type': XRDeviceType.APPLE_VISION,
                'data_format': DataFormat.GLTF,
                'parser_class': 'xr_devices.parsers.meta.AppleVisionParser',
                'parser_version': '1.0.0',
                'supported_sensors': [
                    SensorType.CAMERA_RGB.value,
                    SensorType.CAMERA_DEPTH.value,
                    SensorType.EYE_TRACKING.value,
                    SensorType.HAND_TRACKING.value,
                    SensorType.LIDAR.value,
                ]
            },
        ]
        
        for parser_data in parsers:
            parser, created = DataParser.objects.get_or_create(
                device_type=parser_data['device_type'],
                data_format=parser_data['data_format'],
                defaults={
                    'parser_class': parser_data['parser_class'],
                    'parser_version': parser_data['parser_version'],
                    'supported_sensors': parser_data['supported_sensors']
                }
            )
            if created:
                self.stdout.write(f'Created parser: {parser.device_type} - {parser.data_format}')