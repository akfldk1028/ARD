"""
백그라운드 VRS → Kafka 스트리밍 서비스
VRS 파일을 한 번만 읽어서 모든 데이터를 Kafka에 실시간 스트리밍
"""
import asyncio
import threading
import logging
import time
import json
import math
from typing import Dict, Any, Optional, List
from django.utils import timezone
import sys
import os

# Add ARD directory to path
ard_path = os.path.dirname(os.path.dirname(__file__))
if ard_path not in sys.path:
    sys.path.append(ard_path)

from common.kafka.vrs_kafka_producer import VRSKafkaProducer
from .streaming_service import AriaUnifiedStreaming

logger = logging.getLogger(__name__)

# Global registry for background streaming
BACKGROUND_STREAMING_SERVICES = {}
STREAMING_DATA_CACHE = {}


class BackgroundVRSKafkaStreaming:
    """백그라운드에서 VRS 데이터를 Kafka로 지속적으로 스트리밍"""
    
    def __init__(self, session_id: str, vrs_file_path: str):
        self.session_id = session_id
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        self.streaming_thread = None
        
        # Kafka components
        self.kafka_producer = VRSKafkaProducer()
        self.vrs_service = AriaUnifiedStreaming()
        
        # Streaming stats
        self.stats = {
            'total_streamed': 0,
            'images_streamed': 0,
            'sensors_streamed': 0,
            'start_time': None,
            'last_activity': None,
            'streaming_rate': 0  # items per second
        }
        
        logger.info(f"BackgroundVRSKafkaStreaming initialized for session {session_id}")
    
    def _clean_nan_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """NaN 값들을 null로 변환하여 JSON 직렬화 가능하게 처리"""
        try:
            def clean_value(obj):
                if isinstance(obj, dict):
                    return {k: clean_value(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_value(item) for item in obj]
                elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                    return None
                else:
                    return obj
            
            return clean_value(data)
        except Exception as e:
            logger.warning(f"Error cleaning NaN values: {e}")
            return data
    
    def start_background_streaming(self, loop_duration: int = 300):
        """백그라운드에서 VRS 스트리밍 시작 (5분간 지속)"""
        if self.is_streaming:
            logger.warning(f"Background streaming already active for session {self.session_id}")
            return False
        
        try:
            # VRS provider 초기화
            if not self.vrs_service.create_data_provider():
                raise Exception("Failed to create VRS data provider")
            
            # 백그라운드 스레드로 스트리밍 시작
            self.is_streaming = True
            self.stats['start_time'] = timezone.now().isoformat()
            
            self.streaming_thread = threading.Thread(
                target=self._streaming_loop,
                args=(loop_duration,),
                daemon=True
            )
            self.streaming_thread.start()
            
            # Global registry에 등록
            BACKGROUND_STREAMING_SERVICES[self.session_id] = self
            
            logger.info(f"Started background VRS streaming for session {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start background streaming: {e}")
            self.is_streaming = False
            return False
    
    def _streaming_loop(self, duration: int):
        """실제 스트리밍 루프 (별도 스레드에서 실행)"""
        try:
            end_time = time.time() + duration
            frame_index = 0
            
            logger.info(f"Background streaming loop started for {duration} seconds")
            
            while self.is_streaming and time.time() < end_time:
                try:
                    # 순환적으로 VRS 데이터 스트리밍 (메모리 효율성)
                    batch_size = 20
                    
                    # 이미지 데이터 배치 (4개 카메라)
                    image_data = self.vrs_service.get_balanced_stream_data(
                        max_images=4,  # 4개 카메라
                        max_sensors=0,  # 센서는 별도 처리
                        start_offset=frame_index
                    )
                    
                    # 센서 데이터 배치
                    sensor_data = self.vrs_service.get_balanced_stream_data(
                        max_images=0,  # 이미지는 별도 처리
                        max_sensors=batch_size,
                        start_offset=frame_index
                    )
                    
                    # Kafka로 스트리밍
                    streamed_count = 0
                    
                    # 이미지 스트리밍
                    for data_item in image_data:
                        if not self.is_streaming:
                            break
                        
                        if data_item.get('has_image_data'):
                            # NaN 값들을 null로 변환
                            cleaned_data = self._clean_nan_values(data_item)
                            
                            # 캐시에도 저장 (빠른 조회용)
                            stream_label = cleaned_data.get('stream_label')
                            cache_key = f"{self.session_id}-{stream_label}-{frame_index}"
                            logger.info(f"DEBUG: Storing image cache key: {cache_key} with stream_label: {stream_label}")
                            STREAMING_DATA_CACHE[cache_key] = {
                                'data': cleaned_data,
                                'timestamp': time.time(),
                                'type': 'image'
                            }
                            
                            # Kafka로 전송 (비동기)
                            asyncio.run_coroutine_threadsafe(
                                self.kafka_producer.stream_vrs_image(
                                    data_item.get('stream_label', 'unknown'),
                                    data_item,
                                    self.session_id
                                ),
                                asyncio.new_event_loop()
                            )
                            
                            streamed_count += 1
                            self.stats['images_streamed'] += 1
                    
                    # 센서 스트리밍
                    for data_item in sensor_data:
                        if not self.is_streaming:
                            break
                        
                        if data_item.get('has_sensor_data'):
                            # NaN 값들을 null로 변환
                            cleaned_data = self._clean_nan_values(data_item)
                            
                            # 캐시에도 저장
                            stream_label = cleaned_data.get('stream_label')
                            cache_key = f"{self.session_id}-{stream_label}-{frame_index}"
                            logger.info(f"DEBUG: Storing sensor cache key: {cache_key} with stream_label: {stream_label}")
                            STREAMING_DATA_CACHE[cache_key] = {
                                'data': cleaned_data,
                                'timestamp': time.time(),
                                'type': 'sensor'
                            }
                            
                            # Kafka로 전송
                            asyncio.run_coroutine_threadsafe(
                                self.kafka_producer.stream_vrs_sensor(data_item, self.session_id),
                                asyncio.new_event_loop()
                            )
                            
                            streamed_count += 1
                            self.stats['sensors_streamed'] += 1
                    
                    # 통계 업데이트
                    self.stats['total_streamed'] += streamed_count
                    self.stats['last_activity'] = timezone.now().isoformat()
                    
                    # 다음 배치로 이동
                    frame_index = (frame_index + batch_size) % 1000  # 순환
                    
                    # 스트리밍 속도 조절 (너무 빠르면 시스템 부하)
                    time.sleep(0.1)  # 100ms 간격
                    
                    # 진행 상황 로그 (10배치마다)
                    if (frame_index // batch_size) % 10 == 0:
                        logger.info(f"Background streaming progress: {self.stats['total_streamed']} items streamed")
                
                except Exception as e:
                    logger.error(f"Error in streaming loop: {e}")
                    time.sleep(1)  # 에러시 잠시 대기
            
            logger.info(f"Background streaming completed for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Background streaming loop error: {e}")
        finally:
            self.stop_streaming()
    
    def stop_streaming(self):
        """백그라운드 스트리밍 중지"""
        self.is_streaming = False
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=5)
        
        # Global registry에서 제거
        if self.session_id in BACKGROUND_STREAMING_SERVICES:
            del BACKGROUND_STREAMING_SERVICES[self.session_id]
        
        logger.info(f"Stopped background streaming for session {self.session_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """스트리밍 통계 조회"""
        elapsed = 0
        if self.stats['start_time']:
            start = timezone.datetime.fromisoformat(self.stats['start_time'].replace('Z', '+00:00'))
            elapsed = (timezone.now() - start).total_seconds()
        
        rate = self.stats['total_streamed'] / elapsed if elapsed > 0 else 0
        self.stats['streaming_rate'] = round(rate, 2)
        
        return {
            'session_id': self.session_id,
            'is_streaming': self.is_streaming,
            'stats': self.stats.copy(),
            'elapsed_seconds': round(elapsed, 2),
            'cache_size': len([k for k in STREAMING_DATA_CACHE.keys() if k.startswith(self.session_id)])
        }


class CachedDataService:
    """캐시된 Kafka 데이터를 빠르게 제공하는 서비스"""
    
    @staticmethod
    def get_cached_image_data(session_id: str, stream_label: str, frame_offset: int = 0) -> Optional[Dict[str, Any]]:
        """캐시에서 이미지 데이터 즉시 조회"""
        try:
            # 캐시 키 패턴으로 검색
            matching_keys = [
                k for k in STREAMING_DATA_CACHE.keys() 
                if k.startswith(f"{session_id}-{stream_label}-") and 
                STREAMING_DATA_CACHE[k]['type'] == 'image'
            ]
            
            if matching_keys:
                # 가장 최신 데이터 반환 (frame_offset 적용)
                sorted_keys = sorted(matching_keys, reverse=True)
                if frame_offset < len(sorted_keys):
                    cache_key = sorted_keys[frame_offset]
                    cached_item = STREAMING_DATA_CACHE[cache_key]
                    
                    # 5초 이내 데이터만 유효
                    if time.time() - cached_item['timestamp'] < 5:
                        return cached_item['data']
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached image data: {e}")
            return None
    
    @staticmethod
    def get_cached_sensor_data(session_id: str, sensor_type: str, count: int = 10) -> List[Dict[str, Any]]:
        """캐시에서 센서 데이터 즉시 조회"""
        try:
            # 센서별 캐시 검색
            matching_keys = [
                k for k in STREAMING_DATA_CACHE.keys()
                if k.startswith(f"{session_id}-") and
                STREAMING_DATA_CACHE[k]['type'] == 'sensor' and
                sensor_type in k
            ]
            
            if matching_keys:
                # 최신 데이터들 반환
                sorted_keys = sorted(matching_keys, reverse=True)[:count]
                return [
                    STREAMING_DATA_CACHE[key]['data'] 
                    for key in sorted_keys
                    if time.time() - STREAMING_DATA_CACHE[key]['timestamp'] < 10  # 10초 이내
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting cached sensor data: {e}")
            return []
    
    @staticmethod
    def cleanup_old_cache(max_age: int = 30):
        """오래된 캐시 데이터 정리"""
        try:
            current_time = time.time()
            old_keys = [
                k for k, v in STREAMING_DATA_CACHE.items()
                if current_time - v['timestamp'] > max_age
            ]
            
            for key in old_keys:
                del STREAMING_DATA_CACHE[key]
            
            if old_keys:
                logger.info(f"Cleaned up {len(old_keys)} old cache entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")


def start_background_streaming_for_session(session_id: str, vrs_file_path: str, duration: int = 300) -> bool:
    """세션의 백그라운드 스트리밍 시작"""
    try:
        if session_id in BACKGROUND_STREAMING_SERVICES:
            logger.warning(f"Background streaming already active for session {session_id}")
            return True
        
        streaming_service = BackgroundVRSKafkaStreaming(session_id, vrs_file_path)
        success = streaming_service.start_background_streaming(duration)
        
        if success:
            logger.info(f"Started background streaming for session {session_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to start background streaming: {e}")
        return False


def stop_background_streaming_for_session(session_id: str) -> bool:
    """세션의 백그라운드 스트리밍 중지"""
    try:
        if session_id in BACKGROUND_STREAMING_SERVICES:
            streaming_service = BACKGROUND_STREAMING_SERVICES[session_id]
            streaming_service.stop_streaming()
            logger.info(f"Stopped background streaming for session {session_id}")
            return True
        else:
            logger.warning(f"No background streaming found for session {session_id}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to stop background streaming: {e}")
        return False


def get_all_background_streaming_stats() -> Dict[str, Any]:
    """모든 백그라운드 스트리밍 상태 조회"""
    try:
        stats = {}
        for session_id, service in BACKGROUND_STREAMING_SERVICES.items():
            stats[session_id] = service.get_stats()
        
        return {
            'active_sessions': len(BACKGROUND_STREAMING_SERVICES),
            'total_cache_size': len(STREAMING_DATA_CACHE),
            'session_stats': stats,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting background streaming stats: {e}")
        return {'error': str(e)}


def ensure_streaming_active(session_id: str, vrs_file_path: str) -> bool:
    """세션의 백그라운드 스트리밍이 활성화되어 있는지 확인하고 필요시 시작"""
    try:
        if session_id not in BACKGROUND_STREAMING_SERVICES:
            logger.info(f"Starting background streaming for session {session_id}")
            return start_background_streaming_for_session(session_id, vrs_file_path)
        else:
            service = BACKGROUND_STREAMING_SERVICES[session_id]
            if service.is_streaming:
                return True
            else:
                # 다시 시작
                logger.info(f"Restarting background streaming for session {session_id}")
                return start_background_streaming_for_session(session_id, vrs_file_path)
                
    except Exception as e:
        logger.error(f"Error ensuring streaming active: {e}")
        return False