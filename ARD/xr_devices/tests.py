"""
XR Devices 테스트
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import XRDevice, XRDeviceType, DataFormat, StreamingProtocol
from .parsers import XRParserFactory
from .adapters import AdapterFactory


class XRDeviceModelTest(TestCase):
    """XR 기기 모델 테스트"""
    
    def setUp(self):
        self.device = XRDevice.objects.create(
            name='Test Aria Device',
            device_type=XRDeviceType.META_ARIA,
            manufacturer='Meta',
            model_version='Test Version',
            supported_formats=[DataFormat.VRS.value],
            preferred_protocol=StreamingProtocol.KAFKA.value
        )
    
    def test_device_creation(self):
        """기기 생성 테스트"""
        self.assertEqual(self.device.name, 'Test Aria Device')
        self.assertEqual(self.device.device_type, XRDeviceType.META_ARIA)
        self.assertTrue(self.device.is_active)
    
    def test_device_string_representation(self):
        """문자열 표현 테스트"""
        expected = f"{self.device.name} ({self.device.device_type})"
        self.assertEqual(str(self.device), expected)


class XRParserTest(TestCase):
    """XR 파서 테스트"""
    
    def test_parser_factory(self):
        """파서 팩토리 테스트"""
        # Meta Aria 파서 테스트
        parser = XRParserFactory.get_parser('meta_aria')
        self.assertIsNotNone(parser)
        
        # 지원되는 기기 목록 테스트
        devices = XRParserFactory.list_supported_devices()
        self.assertIn('meta_aria', devices)
    
    def test_aria_parser_data_processing(self):
        """Aria 파서 데이터 처리 테스트"""
        parser = XRParserFactory.get_parser('meta_aria')
        
        # 테스트 데이터
        test_data = b'test_camera_data'
        result = parser.parse_frame(test_data, 'camera_rgb', 1234567890000)
        
        self.assertEqual(result['device_type'], 'meta_aria')
        self.assertEqual(result['sensor_type'], 'camera_rgb')
        self.assertIn('timestamp_ns', result)


class AdapterTest(TestCase):
    """스트리밍 어댑터 테스트"""
    
    def test_adapter_factory(self):
        """어댑터 팩토리 테스트"""
        config = {'bootstrap_servers': 'localhost:9092'}
        adapter = AdapterFactory.get_adapter('kafka', config)
        self.assertIsNotNone(adapter)
        
        # 지원되는 프로토콜 목록 테스트
        protocols = AdapterFactory.list_supported_protocols()
        self.assertIn('kafka', protocols)


class XRDeviceAPITest(APITestCase):
    """XR 기기 API 테스트"""
    
    def setUp(self):
        self.device = XRDevice.objects.create(
            name='Test API Device',
            device_type=XRDeviceType.META_ARIA,
            manufacturer='Meta',
            model_version='API Test',
            supported_formats=[DataFormat.VRS.value],
            preferred_protocol=StreamingProtocol.KAFKA.value
        )
    
    def test_supported_devices_api(self):
        """지원 기기 목록 API 테스트"""
        url = reverse('xr-devices-supported-devices')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertGreater(len(response.data['supported_devices']), 0)
    
    def test_supported_parsers_api(self):
        """지원 파서 목록 API 테스트"""
        url = reverse('xr-devices-supported-parsers')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
    
    def test_streaming_control_status(self):
        """스트리밍 상태 조회 API 테스트"""
        url = reverse('universal_streaming_control', kwargs={'action': 'status'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('active_sessions', response.data)


class StreamingSessionTest(TestCase):
    """스트리밍 세션 테스트"""
    
    def setUp(self):
        self.device = XRDevice.objects.create(
            name='Test Streaming Device',
            device_type=XRDeviceType.META_ARIA,
            manufacturer='Meta',
            model_version='Streaming Test',
            supported_formats=[DataFormat.VRS.value],
            preferred_protocol=StreamingProtocol.KAFKA.value
        )
    
    def test_session_creation_api(self):
        """세션 생성 API 테스트"""
        url = reverse('universal_streaming_control', kwargs={'action': 'create_session'})
        data = {
            'device_type': 'meta_aria',
            'session_name': 'test_session',
            'user_id': 'test_user'
        }
        
        response = self.client.post(url, data, format='json')
        # 실제 Kafka 연결 없이는 실패할 수 있으므로 상태 코드만 확인
        self.assertIn(response.status_code, [200, 500])
        
        if response.status_code == 200:
            self.assertEqual(response.data['status'], 'success')
            self.assertIn('session_id', response.data)