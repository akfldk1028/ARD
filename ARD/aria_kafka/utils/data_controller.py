"""
데이터 플로우 컨트롤러 - 너무 많은 데이터로 인한 터짐 방지
"""
import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class StreamMetrics:
    """스트림 메트릭스"""
    message_count: int = 0
    byte_count: int = 0
    error_count: int = 0
    last_message_time: float = 0.0
    messages_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
class DataFlowController:
    """
    데이터 플로우 제어기 - 처리량 조절 및 백프레셔 관리
    """
    
    def __init__(self, max_messages_per_second: int = 100, max_bytes_per_second: int = 10485760):
        """
        초기화
        
        Args:
            max_messages_per_second: 초당 최대 메시지 수
            max_bytes_per_second: 초당 최대 바이트 수 (기본 10MB)
        """
        self.max_messages_per_second = max_messages_per_second
        self.max_bytes_per_second = max_bytes_per_second
        
        # 레이트 리미터
        self.message_tokens = max_messages_per_second
        self.byte_tokens = max_bytes_per_second
        self.last_refill_time = time.time()
        
        # 메트릭스 수집
        self.metrics: Dict[str, StreamMetrics] = defaultdict(StreamMetrics)
        self.recent_messages: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 백프레셔 제어
        self.is_backpressure_active = False
        self.backpressure_threshold = 0.8  # 80% 사용률에서 활성화
        
        # 스레드 안전성
        self.lock = threading.RLock()
        
        # 자동 메트릭스 업데이트
        self.metrics_thread = threading.Thread(target=self._update_metrics_loop, daemon=True)
        self.metrics_thread.start()
        
        logger.info(f"DataFlowController 초기화: {max_messages_per_second} msg/s, {max_bytes_per_second/1024/1024:.1f} MB/s")
    
    def can_send_message(self, stream_name: str, message_size: int) -> bool:
        """
        메시지 전송 가능 여부 확인 (레이트 리미팅)
        
        Args:
            stream_name: 스트림 이름
            message_size: 메시지 크기 (바이트)
            
        Returns:
            전송 가능 여부
        """
        with self.lock:
            # 토큰 리필
            self._refill_tokens()
            
            # 백프레셔 확인
            if self.is_backpressure_active:
                return False
            
            # 토큰 확인
            if self.message_tokens >= 1 and self.byte_tokens >= message_size:
                # 토큰 소비
                self.message_tokens -= 1
                self.byte_tokens -= message_size
                return True
            
            return False
    
    def record_message_sent(self, stream_name: str, message_size: int, success: bool = True):
        """
        메시지 전송 기록
        
        Args:
            stream_name: 스트림 이름
            message_size: 메시지 크기
            success: 성공 여부
        """
        with self.lock:
            current_time = time.time()
            metric = self.metrics[stream_name]
            
            if success:
                metric.message_count += 1
                metric.byte_count += message_size
            else:
                metric.error_count += 1
            
            metric.last_message_time = current_time
            
            # 최근 메시지 기록 (성능 계산용)
            self.recent_messages[stream_name].append({
                'time': current_time,
                'size': message_size,
                'success': success
            })
    
    def wait_if_needed(self, stream_name: str, message_size: int) -> float:
        """
        필요시 대기 (백프레셔 처리)
        
        Args:
            stream_name: 스트림 이름
            message_size: 메시지 크기
            
        Returns:
            대기 시간 (초)
        """
        wait_time = 0.0
        
        # 레이트 리미트 대기
        while not self.can_send_message(stream_name, message_size):
            sleep_time = 0.01  # 10ms 대기
            time.sleep(sleep_time)
            wait_time += sleep_time
            
            # 너무 오래 대기하면 포기
            if wait_time > 1.0:  # 1초 이상 대기
                logger.warning(f"스트림 {stream_name} 대기 시간 초과: {wait_time:.2f}s")
                break
        
        return wait_time
    
    def get_stream_metrics(self, stream_name: str) -> StreamMetrics:
        """스트림 메트릭스 조회"""
        with self.lock:
            return self.metrics[stream_name]
    
    def get_all_metrics(self) -> Dict[str, StreamMetrics]:
        """모든 스트림 메트릭스 조회"""
        with self.lock:
            return dict(self.metrics)
    
    def reset_metrics(self, stream_name: Optional[str] = None):
        """메트릭스 리셋"""
        with self.lock:
            if stream_name:
                self.metrics[stream_name] = StreamMetrics()
                self.recent_messages[stream_name].clear()
            else:
                self.metrics.clear()
                self.recent_messages.clear()
    
    def set_rate_limits(self, max_messages_per_second: int, max_bytes_per_second: int):
        """레이트 리미트 변경"""
        with self.lock:
            self.max_messages_per_second = max_messages_per_second
            self.max_bytes_per_second = max_bytes_per_second
            logger.info(f"레이트 리미트 변경: {max_messages_per_second} msg/s, {max_bytes_per_second/1024/1024:.1f} MB/s")
    
    def enable_backpressure(self, enabled: bool = True):
        """백프레셔 활성화/비활성화"""
        with self.lock:
            self.is_backpressure_active = enabled
            logger.info(f"백프레셔 {'활성화' if enabled else '비활성화'}")
    
    def _refill_tokens(self):
        """토큰 리필 (레이트 리미터)"""
        current_time = time.time()
        time_elapsed = current_time - self.last_refill_time
        
        # 초당 토큰 리필
        self.message_tokens = min(
            self.max_messages_per_second, 
            self.message_tokens + (self.max_messages_per_second * time_elapsed)
        )
        self.byte_tokens = min(
            self.max_bytes_per_second,
            self.byte_tokens + (self.max_bytes_per_second * time_elapsed)
        )
        
        self.last_refill_time = current_time
    
    def _update_metrics_loop(self):
        """메트릭스 업데이트 루프 (별도 스레드)"""
        while True:
            try:
                self._calculate_performance_metrics()
                self._check_backpressure()
                time.sleep(1.0)  # 1초마다 업데이트
            except Exception as e:
                logger.error(f"메트릭스 업데이트 오류: {e}")
                time.sleep(5.0)
    
    def _calculate_performance_metrics(self):
        """성능 메트릭스 계산"""
        current_time = time.time()
        window_size = 10.0  # 10초 윈도우
        
        with self.lock:
            for stream_name, messages in self.recent_messages.items():
                if not messages:
                    continue
                
                # 최근 10초 메시지 필터링
                recent = [msg for msg in messages if current_time - msg['time'] <= window_size]
                
                if recent:
                    # 성능 계산
                    message_count = len(recent)
                    total_bytes = sum(msg['size'] for msg in recent)
                    
                    self.metrics[stream_name].messages_per_second = message_count / window_size
                    self.metrics[stream_name].bytes_per_second = total_bytes / window_size
    
    def _check_backpressure(self):
        """백프레셔 확인"""
        with self.lock:
            # 토큰 사용률 계산
            message_usage = 1.0 - (self.message_tokens / self.max_messages_per_second)
            byte_usage = 1.0 - (self.byte_tokens / self.max_bytes_per_second)
            
            max_usage = max(message_usage, byte_usage)
            
            # 백프레셔 활성화/비활성화 결정
            if max_usage > self.backpressure_threshold and not self.is_backpressure_active:
                self.is_backpressure_active = True
                logger.warning(f"백프레셔 활성화: 사용률 {max_usage:.1%}")
            elif max_usage < (self.backpressure_threshold * 0.7) and self.is_backpressure_active:
                self.is_backpressure_active = False
                logger.info(f"백프레셔 비활성화: 사용률 {max_usage:.1%}")

class SmartSampler:
    """
    스마트 샘플링 - 중요한 데이터는 유지하고 중복 제거
    """
    
    def __init__(self, sample_rate: float = 0.1):
        """
        초기화
        
        Args:
            sample_rate: 기본 샘플링 비율 (0.1 = 10%)
        """
        self.sample_rate = sample_rate
        self.last_samples: Dict[str, Any] = {}
        self.sample_counters: Dict[str, int] = defaultdict(int)
        
    def should_sample(self, stream_name: str, data: Any, force_important: bool = False) -> bool:
        """
        샘플링 여부 결정
        
        Args:
            stream_name: 스트림 이름
            data: 데이터
            force_important: 중요한 데이터 강제 전송
            
        Returns:
            샘플링 여부
        """
        if force_important:
            return True
        
        counter = self.sample_counters[stream_name]
        self.sample_counters[stream_name] += 1
        
        # 중복 데이터 체크
        if self._is_duplicate(stream_name, data):
            return False
        
        # 샘플링 비율 적용
        return (counter % int(1.0 / self.sample_rate)) == 0
    
    def _is_duplicate(self, stream_name: str, data: Any) -> bool:
        """중복 데이터 확인 (간단한 버전)"""
        try:
            # 데이터를 문자열로 변환해서 비교
            data_str = str(data)
            last_data_str = str(self.last_samples.get(stream_name, ''))
            
            is_duplicate = data_str == last_data_str
            
            if not is_duplicate:
                self.last_samples[stream_name] = data
            
            return is_duplicate
            
        except Exception:
            return False

# 전역 인스턴스들
DEFAULT_CONTROLLER = DataFlowController(
    max_messages_per_second=100,    # 초당 100개 메시지
    max_bytes_per_second=10485760   # 초당 10MB
)

HIGH_THROUGHPUT_CONTROLLER = DataFlowController(
    max_messages_per_second=500,    # 초당 500개 메시지
    max_bytes_per_second=52428800   # 초당 50MB
)

LOW_LATENCY_CONTROLLER = DataFlowController(
    max_messages_per_second=50,     # 초당 50개 메시지
    max_bytes_per_second=5242880    # 초당 5MB
)