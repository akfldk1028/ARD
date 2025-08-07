"""
다양한 스트리밍 프로토콜을 위한 어댑터들
"""

from typing import Dict, Any, List
import json
import asyncio
from abc import ABC, abstractmethod


class BaseStreamingAdapter(ABC):
    """기본 스트리밍 어댑터"""
    
    def __init__(self, protocol_type: str, config: Dict[str, Any]):
        self.protocol_type = protocol_type
        self.config = config
        self.connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """연결 설정"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """연결 종료"""
        pass
    
    @abstractmethod
    async def send_data(self, data: Dict[str, Any], topic: str = None) -> bool:
        """데이터 전송"""
        pass
    
    @abstractmethod
    async def receive_data(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        """데이터 수신"""
        pass
    
    def serialize_data(self, data: Dict[str, Any]) -> bytes:
        """데이터 직렬화"""
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    def deserialize_data(self, raw_data: bytes) -> Dict[str, Any]:
        """데이터 역직렬화"""
        try:
            return json.loads(raw_data.decode('utf-8'))
        except json.JSONDecodeError:
            return {}


# 어댑터 팩토리
class AdapterFactory:
    """스트리밍 어댑터 팩토리"""
    
    _adapters = {}
    
    @classmethod
    def register_adapter(cls, protocol_type: str, adapter_class: type):
        """어댑터 등록"""
        cls._adapters[protocol_type] = adapter_class
    
    @classmethod
    def get_adapter(cls, protocol_type: str, config: Dict[str, Any]):
        """어댑터 인스턴스 반환"""
        adapter_class = cls._adapters.get(protocol_type)
        if adapter_class:
            return adapter_class(protocol_type, config)
        return None
    
    @classmethod
    def list_supported_protocols(cls) -> List[str]:
        """지원되는 프로토콜 목록"""
        return list(cls._adapters.keys())