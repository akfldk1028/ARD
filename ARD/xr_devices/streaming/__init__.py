"""
통합 XR 기기 스트리밍 관리
"""

from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime
import uuid

from ..models import XRDevice, StreamingSession, StreamingData, DataParser
from ..parsers import XRParserFactory, BaseXRParser
from ..adapters import AdapterFactory, BaseStreamingAdapter

logger = logging.getLogger(__name__)


class UniversalXRStreamingManager:
    """
    모든 XR 기기를 지원하는 통합 스트리밍 관리자
    
    새로운 기기가 추가되어도 이 클래스는 수정하지 않고,
    파서와 어댑터만 추가하면 자동으로 지원됩니다.
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, 'XRStreamingSession'] = {}
        self.supported_devices: Dict[str, XRDevice] = {}
        self._initialize_supported_devices()
    
    def _initialize_supported_devices(self):
        """지원되는 기기들 로드"""
        try:
            devices = XRDevice.objects.filter(is_active=True)
            for device in devices:
                self.supported_devices[device.device_type] = device
                logger.info(f"Loaded device: {device.name} ({device.device_type})")
        except Exception as e:
            logger.warning(f"Failed to load devices from database: {e}")
    
    async def create_session(
        self,
        device_type: str,
        session_name: str,
        user_id: str = None,
        streaming_config: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        새로운 스트리밍 세션 생성
        
        Args:
            device_type: 기기 타입 (meta_aria, google_glass, etc.)
            session_name: 세션 이름
            user_id: 사용자 ID
            streaming_config: 스트리밍 설정
            
        Returns:
            session_id 또는 None (실패시)
        """
        try:
            # 지원되는 기기 확인
            if device_type not in self.supported_devices:
                logger.error(f"Unsupported device type: {device_type}")
                return None
            
            device = self.supported_devices[device_type]
            
            # 세션 ID 생성
            session_id = f"{device_type}_{uuid.uuid4().hex[:8]}"
            
            # 스트리밍 세션 객체 생성
            streaming_session = XRStreamingSession(
                manager=self,
                session_id=session_id,
                device=device,
                session_name=session_name,
                user_id=user_id,
                config=streaming_config or {}
            )
            
            # 초기화
            if await streaming_session.initialize():
                self.active_sessions[session_id] = streaming_session
                logger.info(f"Created streaming session: {session_id}")
                return session_id
            else:
                logger.error(f"Failed to initialize streaming session: {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create streaming session: {e}")
            return None
    
    async def start_streaming(self, session_id: str) -> bool:
        """스트리밍 시작"""
        session = self.active_sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
        
        return await session.start_streaming()
    
    async def stop_streaming(self, session_id: str) -> bool:
        """스트리밍 중지"""
        session = self.active_sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
        
        return await session.stop_streaming()
    
    async def process_data(
        self,
        session_id: str,
        raw_data: bytes,
        sensor_type: str,
        timestamp_ns: int = None
    ) -> bool:
        """데이터 처리 및 스트리밍"""
        session = self.active_sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
        
        return await session.process_data(raw_data, sensor_type, timestamp_ns)
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 상태 조회"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return session.get_status()
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """활성 세션 목록"""
        return [session.get_status() for session in self.active_sessions.values()]
    
    def get_supported_devices(self) -> List[Dict[str, Any]]:
        """지원되는 기기 목록"""
        return [
            {
                'device_type': device.device_type,
                'name': device.name,
                'manufacturer': device.manufacturer,
                'supported_formats': device.supported_formats,
                'preferred_protocol': device.preferred_protocol
            }
            for device in self.supported_devices.values()
        ]


class XRStreamingSession:
    """개별 XR 기기 스트리밍 세션"""
    
    def __init__(
        self,
        manager: UniversalXRStreamingManager,
        session_id: str,
        device: XRDevice,
        session_name: str,
        user_id: str = None,
        config: Dict[str, Any] = None
    ):
        self.manager = manager
        self.session_id = session_id
        self.device = device
        self.session_name = session_name
        self.user_id = user_id
        self.config = config or {}
        
        self.parser: Optional[BaseXRParser] = None
        self.adapter: Optional[BaseStreamingAdapter] = None
        self.db_session: Optional[StreamingSession] = None
        
        self.is_streaming = False
        self.frame_count = 0
        self.total_data_size = 0
        self.start_time = None
    
    async def initialize(self) -> bool:
        """세션 초기화"""
        try:
            # 파서 초기화
            self.parser = XRParserFactory.get_parser(
                self.device.device_type,
                self.device.device_config
            )
            
            if not self.parser:
                logger.error(f"No parser available for device type: {self.device.device_type}")
                return False
            
            # 어댑터 초기화
            self.adapter = AdapterFactory.get_adapter(
                self.device.preferred_protocol,
                self.config.get('streaming', {})
            )
            
            if not self.adapter:
                logger.error(f"No adapter available for protocol: {self.device.preferred_protocol}")
                return False
            
            # 어댑터 연결
            if not await self.adapter.connect():
                logger.error("Failed to connect streaming adapter")
                return False
            
            # 데이터베이스 세션 생성
            self.db_session = StreamingSession.objects.create(
                session_id=self.session_id,
                device=self.device,
                user_id=self.user_id,
                session_name=self.session_name,
                streaming_protocol=self.device.preferred_protocol,
                data_format=self.device.supported_formats[0] if self.device.supported_formats else 'unknown',
                active_sensors=[],
                status='preparing'
            )
            
            logger.info(f"Initialized session: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            return False
    
    async def start_streaming(self) -> bool:
        """스트리밍 시작"""
        if self.is_streaming:
            logger.warning(f"Session {self.session_id} is already streaming")
            return True
        
        try:
            self.is_streaming = True
            self.start_time = datetime.now()
            self.frame_count = 0
            
            # 데이터베이스 상태 업데이트
            if self.db_session:
                self.db_session.status = 'streaming'
                self.db_session.save()
            
            logger.info(f"Started streaming for session: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.is_streaming = False
            return False
    
    async def stop_streaming(self) -> bool:
        """스트리밍 중지"""
        if not self.is_streaming:
            return True
        
        try:
            self.is_streaming = False
            
            # 어댑터 연결 종료
            if self.adapter:
                await self.adapter.disconnect()
            
            # 데이터베이스 상태 업데이트
            if self.db_session:
                self.db_session.status = 'completed'
                self.db_session.end_time = datetime.now()
                self.db_session.total_frames_processed = self.frame_count
                self.db_session.total_data_size_mb = self.total_data_size / (1024 * 1024)
                self.db_session.save()
            
            logger.info(f"Stopped streaming for session: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop streaming: {e}")
            return False
    
    async def process_data(
        self,
        raw_data: bytes,
        sensor_type: str,
        timestamp_ns: int = None
    ) -> bool:
        """데이터 처리 및 스트리밍"""
        if not self.is_streaming:
            logger.warning("Session is not streaming")
            return False
        
        try:
            # 타임스탬프 설정
            if timestamp_ns is None:
                timestamp_ns = int(datetime.now().timestamp() * 1e9)
            
            # 데이터 파싱
            parsed_data = self.parser.parse_frame(raw_data, sensor_type, timestamp_ns)
            
            if not self.parser.validate_data(parsed_data):
                logger.warning("Invalid data format")
                return False
            
            # 스트리밍 어댑터로 전송
            success = await self.adapter.send_data(parsed_data)
            
            if success:
                # 데이터베이스에 저장 (선택사항)
                await self._save_to_database(parsed_data, raw_data, sensor_type, timestamp_ns)
                
                # 통계 업데이트
                self.frame_count += 1
                self.total_data_size += len(raw_data)
                
                return True
            else:
                logger.error("Failed to send data via streaming adapter")
                return False
                
        except Exception as e:
            logger.error(f"Failed to process data: {e}")
            return False
    
    async def _save_to_database(
        self,
        parsed_data: Dict[str, Any],
        raw_data: bytes,
        sensor_type: str,
        timestamp_ns: int
    ):
        """데이터베이스에 데이터 저장 (비동기)"""
        try:
            # 너무 큰 데이터는 저장하지 않음
            if len(raw_data) > 10 * 1024 * 1024:  # 10MB 제한
                raw_data = None
            
            streaming_data = StreamingData.objects.create(
                session=self.db_session,
                sensor_type=sensor_type,
                frame_number=self.frame_count,
                timestamp_ns=timestamp_ns,
                raw_data=raw_data,
                structured_data=parsed_data,
                data_format=self.device.supported_formats[0] if self.device.supported_formats else 'unknown',
                data_size_bytes=len(raw_data) if raw_data else 0
            )
            
        except Exception as e:
            # 데이터베이스 저장 실패는 스트리밍을 중단하지 않음
            logger.warning(f"Failed to save data to database: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """세션 상태 반환"""
        return {
            'session_id': self.session_id,
            'device_type': self.device.device_type,
            'device_name': self.device.name,
            'session_name': self.session_name,
            'user_id': self.user_id,
            'is_streaming': self.is_streaming,
            'frame_count': self.frame_count,
            'total_data_size_mb': round(self.total_data_size / (1024 * 1024), 2),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'streaming_protocol': self.device.preferred_protocol,
            'supported_sensors': self.parser.supported_sensors if self.parser else []
        }


# 전역 관리자 인스턴스
streaming_manager = UniversalXRStreamingManager()