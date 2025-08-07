"""
XR 기기별 데이터 파서 모듈

각 기기별로 다른 데이터 포맷을 통합된 인터페이스로 처리하기 위한 파서들
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
import json
import numpy as np
from datetime import datetime


class BaseXRParser(ABC):
    """모든 XR 기기 파서의 기본 클래스"""
    
    def __init__(self, device_type: str, config: Dict[str, Any] = None):
        self.device_type = device_type
        self.config = config or {}
        self.supported_sensors = []
    
    @abstractmethod
    def parse_frame(self, raw_data: bytes, sensor_type: str, timestamp_ns: int) -> Dict[str, Any]:
        """
        원시 데이터를 파싱하여 구조화된 데이터로 변환
        
        Args:
            raw_data: 원시 바이너리 데이터
            sensor_type: 센서 타입 (SensorType enum 값)
            timestamp_ns: 나노초 단위 타임스탬프
            
        Returns:
            Dict: 구조화된 데이터
        """
        pass
    
    @abstractmethod
    def parse_sensor_data(self, data: Any, sensor_type: str) -> Dict[str, Any]:
        """센서별 특화 데이터 파싱"""
        pass
    
    @abstractmethod
    def get_frame_metadata(self, frame_data: Any) -> Dict[str, Any]:
        """프레임 메타데이터 추출"""
        pass
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        required_fields = ['timestamp_ns', 'sensor_type', 'device_type']
        return all(field in data for field in required_fields)
    
    def normalize_timestamp(self, timestamp: Any) -> int:
        """타임스탬프를 나노초 단위로 정규화"""
        if isinstance(timestamp, (int, float)):
            return int(timestamp)
        elif isinstance(timestamp, datetime):
            return int(timestamp.timestamp() * 1e9)
        else:
            return int(datetime.now().timestamp() * 1e9)
    
    def safe_float(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        """NaN/Infinity를 안전하게 처리하는 float 변환"""
        try:
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return default
            return float_val
        except (ValueError, TypeError, OverflowError):
            return default


class StreamingAdapter(ABC):
    """스트리밍 프로토콜별 어댑터"""
    
    def __init__(self, protocol_type: str, config: Dict[str, Any]):
        self.protocol_type = protocol_type
        self.config = config
    
    @abstractmethod
    async def send_data(self, data: Dict[str, Any], topic: str = None) -> bool:
        """데이터 전송"""
        pass
    
    @abstractmethod
    async def receive_data(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        """데이터 수신"""
        pass
    
    @abstractmethod
    def connect(self) -> bool:
        """연결 설정"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """연결 종료"""
        pass


class DataProcessor:
    """데이터 처리 유틸리티"""
    
    @staticmethod
    def extract_image_data(raw_data: bytes, format: str = 'jpeg') -> Optional[np.ndarray]:
        """이미지 데이터 추출"""
        try:
            import cv2
            nparr = np.frombuffer(raw_data, np.uint8)
            if format.lower() in ['jpg', 'jpeg']:
                return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            elif format.lower() == 'png':
                return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                return None
        except ImportError:
            return None
        except Exception:
            return None
    
    @staticmethod
    def compress_image(image: np.ndarray, quality: int = 75, format: str = 'jpeg') -> bytes:
        """이미지 압축"""
        try:
            import cv2
            if format.lower() in ['jpg', 'jpeg']:
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                _, buffer = cv2.imencode('.jpg', image, encode_param)
            elif format.lower() == 'png':
                encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 9]
                _, buffer = cv2.imencode('.png', image, encode_param)
            else:
                _, buffer = cv2.imencode('.jpg', image)
            
            return buffer.tobytes()
        except Exception:
            return b''
    
    @staticmethod
    def serialize_sensor_data(data: Dict[str, Any]) -> str:
        """센서 데이터 직렬화"""
        def custom_serializer(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(data, default=custom_serializer, ensure_ascii=False)
    
    @staticmethod
    def deserialize_sensor_data(json_str: str) -> Dict[str, Any]:
        """센서 데이터 역직렬화"""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}


# 파서 팩토리
class XRParserFactory:
    """XR 기기별 파서 팩토리"""
    
    _parsers = {}
    
    @classmethod
    def register_parser(cls, device_type: str, parser_class: type):
        """파서 등록"""
        cls._parsers[device_type] = parser_class
    
    @classmethod
    def get_parser(cls, device_type: str, config: Dict[str, Any] = None) -> Optional[BaseXRParser]:
        """파서 인스턴스 반환"""
        parser_class = cls._parsers.get(device_type)
        if parser_class:
            return parser_class(device_type, config)
        return None
    
    @classmethod
    def list_supported_devices(cls) -> List[str]:
        """지원되는 기기 목록"""
        return list(cls._parsers.keys())


# 스트리밍 어댑터 팩토리
class StreamingAdapterFactory:
    """스트리밍 어댑터 팩토리"""
    
    _adapters = {}
    
    @classmethod
    def register_adapter(cls, protocol_type: str, adapter_class: type):
        """어댑터 등록"""
        cls._adapters[protocol_type] = adapter_class
    
    @classmethod
    def get_adapter(cls, protocol_type: str, config: Dict[str, Any]) -> Optional[StreamingAdapter]:
        """어댑터 인스턴스 반환"""
        adapter_class = cls._adapters.get(protocol_type)
        if adapter_class:
            return adapter_class(protocol_type, config)
        return None