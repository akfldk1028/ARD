"""
Project Aria Kafka 시스템 v2
데이터 처리량 최적화 및 안정성 개선
"""

__version__ = "2.0.0"
__author__ = "ARD Backend Team"

# 주요 클래스들 import
from .producers.vrs_producer import VRSKafkaProducer
from .consumers.streaming_consumer import StreamingKafkaConsumer
from .managers.stream_manager import AriaStreamManager
from .utils.data_controller import DataFlowController

__all__ = [
    'VRSKafkaProducer',
    'StreamingKafkaConsumer', 
    'AriaStreamManager',
    'DataFlowController'
]