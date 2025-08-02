import cv2
import json
import base64
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from common.kafka.base_producer import BaseKafkaProducer
from common.kafka.topic_manager import TopicManager

logger = logging.getLogger(__name__)


class WebcamKafkaProducer(BaseKafkaProducer):
    """Webcam Kafka producer for video streaming and analysis"""
    
    def __init__(self, bootstrap_servers: str = 'kafka-all:9092'):
        super().__init__('webcam', bootstrap_servers)
        self.topics = TopicManager.get_topics_for_service('webcam')
        
    def send_video_frame(self, session_id: str, frame: np.ndarray, frame_id: str, 
                        width: int, height: int, fps: float = 30.0):
        """Send webcam video frame"""
        
        # Encode frame to base64 for JSON serialization
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'frame_id': frame_id,
            'width': width,
            'height': height,
            'fps': fps,
            'format': 'RGB',
            'frame_data': frame_base64,  # Base64 encoded frame
            'frame_size': len(buffer),
            'metadata': {
                'compression': 'JPEG',
                'quality': 90
            }
        }
        
        return self.send_message('video_frame', message, key=session_id)
    
    def send_motion_detection(self, session_id: str, frame_id: str, 
                            motion_detected: bool, confidence: float,
                            motion_areas: list = None):
        """Send motion detection results"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'frame_id': frame_id,
            'analysis_type': 'motion',
            'motion_detected': motion_detected,
            'confidence': confidence,
            'results': {
                'motion_areas': motion_areas or [],
                'total_motion_pixels': sum(area.get('pixels', 0) for area in (motion_areas or [])),
            },
            'metadata': {
                'detection_algorithm': 'background_subtraction',
                'threshold': 0.5
            }
        }
        
        return self.send_message('motion_detection', message, key=session_id)
    
    def send_face_detection(self, session_id: str, frame_id: str,
                          faces_detected: list, confidence: float):
        """Send face detection results"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'frame_id': frame_id,
            'analysis_type': 'face',
            'faces_count': len(faces_detected),
            'confidence': confidence,
            'results': {
                'faces': faces_detected,  # List of face bounding boxes and features
            },
            'metadata': {
                'detection_model': 'opencv_haarcascade',
                'min_face_size': (30, 30)
            }
        }
        
        return self.send_message('face_detection', message, key=session_id)
    
    def send_activity_recognition(self, session_id: str, activity_type: str,
                                confidence: float, duration: float = None):
        """Send activity recognition results"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'analysis_type': 'activity',
            'activity_type': activity_type,  # sitting, standing, walking, etc.
            'confidence': confidence,
            'duration': duration,
            'results': {
                'recognized_activity': activity_type,
                'alternative_activities': []  # Other possible activities with lower confidence
            },
            'metadata': {
                'recognition_model': 'pose_estimation',
                'frame_window': 30  # frames used for recognition
            }
        }
        
        return self.send_message('activity_recognition', message, key=session_id)
    
    def send_test_message(self, session_id: str = 'test-session'):
        """Send test message for debugging"""
        
        # Create dummy frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(dummy_frame, 'Test Frame', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        success = self.send_video_frame(
            session_id=session_id,
            frame=dummy_frame,
            frame_id=f'test-frame-{datetime.now().strftime("%H%M%S")}',
            width=640,
            height=480,
            fps=30.0
        )
        
        if success:
            logger.info(f"Test webcam message sent successfully for session: {session_id}")
        else:
            logger.error(f"Failed to send test webcam message")
            
        return success