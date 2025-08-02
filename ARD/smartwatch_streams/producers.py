import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
from common.kafka.base_producer import BaseKafkaProducer
from common.kafka.topic_manager import TopicManager

logger = logging.getLogger(__name__)


class SmartwatchKafkaProducer(BaseKafkaProducer):
    """Smartwatch Kafka producer for sensor data and health metrics"""
    
    def __init__(self, bootstrap_servers: str = 'kafka-all:9092'):
        super().__init__('smartwatch', bootstrap_servers)
        self.topics = TopicManager.get_topics_for_service('smartwatch')
        
    def send_heart_rate(self, session_id: str, bpm: int, accuracy: float = 1.0):
        """Send heart rate sensor data"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'sensor_type': 'heart_rate',
            'values': {
                'bpm': bpm,
                'rhythm': 'normal' if 60 <= bpm <= 100 else 'irregular'
            },
            'accuracy': accuracy,
            'metadata': {
                'sensor': 'optical_hr',
                'measurement_duration': 30,  # seconds
                'confidence_level': 'high' if accuracy > 0.8 else 'medium'
            }
        }
        
        return self.send_message('heart_rate', message, key=session_id)
    
    def send_accelerometer(self, session_id: str, x: float, y: float, z: float, 
                          accuracy: float = 1.0):
        """Send accelerometer sensor data"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'sensor_type': 'accelerometer',
            'values': {
                'x': x,  # m/s²
                'y': y,
                'z': z,
                'magnitude': (x**2 + y**2 + z**2)**0.5
            },
            'accuracy': accuracy,
            'metadata': {
                'sensor': '3-axis_accelerometer',
                'sampling_rate': 50,  # Hz
                'range': '±16g'
            }
        }
        
        return self.send_message('accelerometer', message, key=session_id)
    
    def send_gyroscope(self, session_id: str, x: float, y: float, z: float,
                      accuracy: float = 1.0):
        """Send gyroscope sensor data"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'sensor_type': 'gyroscope',
            'values': {
                'x': x,  # rad/s
                'y': y,
                'z': z,
                'angular_velocity': (x**2 + y**2 + z**2)**0.5
            },
            'accuracy': accuracy,
            'metadata': {
                'sensor': '3-axis_gyroscope',
                'sampling_rate': 50,  # Hz
                'range': '±2000dps'
            }
        }
        
        return self.send_message('gyroscope', message, key=session_id)
    
    def send_gps(self, session_id: str, latitude: float, longitude: float,
                altitude: float = None, accuracy: float = 1.0):
        """Send GPS location data"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'sensor_type': 'gps',
            'values': {
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'speed': 0.0,  # m/s
                'bearing': 0.0  # degrees
            },
            'accuracy': accuracy,
            'metadata': {
                'sensor': 'gps_receiver',
                'satellites': random.randint(4, 12),
                'fix_type': '3D' if altitude else '2D'
            }
        }
        
        return self.send_message('gps', message, key=session_id)
    
    def send_step_counter(self, session_id: str, steps: int, cadence: float = None):
        """Send step counter data"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'sensor_type': 'step_counter',
            'values': {
                'steps': steps,
                'cadence': cadence,  # steps per minute
                'step_length': 0.7,  # average step length in meters
                'distance': steps * 0.7  # estimated distance
            },
            'accuracy': 0.95,
            'metadata': {
                'sensor': 'pedometer',
                'detection_algorithm': 'peak_detection',
                'calibrated': True
            }
        }
        
        return self.send_message('step_counter', message, key=session_id)
    
    def send_health_metrics(self, session_id: str, heart_rate: int = None,
                           blood_oxygen: float = None, stress_level: float = None,
                           sleep_stage: str = None):
        """Send comprehensive health metrics"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'heart_rate': heart_rate,
            'blood_oxygen': blood_oxygen,  # SpO2 percentage
            'stress_level': stress_level,  # 0-100
            'sleep_stage': sleep_stage,  # awake, light, deep, rem
            'body_temperature': 36.5 + random.uniform(-0.5, 0.5),  # Celsius
            'metadata': {
                'measurement_window': 300,  # seconds
                'data_quality': 'high',
                'sensors_active': ['hr', 'spo2', 'temperature']
            }
        }
        
        return self.send_message('health_metrics', message, key=session_id)
    
    def send_activity_recognition(self, session_id: str, activity_type: str,
                                confidence: float, duration: int = None):
        """Send activity recognition results"""
        
        message = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'activity_type': activity_type,  # walking, running, sitting, etc.
            'confidence': confidence,
            'duration': duration,  # seconds
            'start_time': (datetime.utcnow() - timedelta(seconds=duration or 60)).isoformat(),
            'calories_burned': self._estimate_calories(activity_type, duration or 60),
            'metadata': {
                'recognition_model': 'ml_classifier',
                'sensor_fusion': ['accelerometer', 'gyroscope', 'heart_rate'],
                'activity_intensity': self._get_intensity(activity_type)
            }
        }
        
        return self.send_message('activity_recognition', message, key=session_id)
    
    def send_test_sensor_data(self, session_id: str = 'test-smartwatch-session'):
        """Send comprehensive test sensor data"""
        
        # Heart rate
        hr_success = self.send_heart_rate(
            session_id=session_id,
            bpm=random.randint(60, 100),
            accuracy=0.95
        )
        
        # Accelerometer 
        acc_success = self.send_accelerometer(
            session_id=session_id,
            x=random.uniform(-2, 2),
            y=random.uniform(-2, 2), 
            z=random.uniform(8, 12),  # gravity + movement
            accuracy=0.98
        )
        
        # GPS
        gps_success = self.send_gps(
            session_id=session_id,
            latitude=37.7749 + random.uniform(-0.01, 0.01),  # SF area
            longitude=-122.4194 + random.uniform(-0.01, 0.01),
            altitude=random.uniform(0, 100),
            accuracy=0.85
        )
        
        # Health metrics
        health_success = self.send_health_metrics(
            session_id=session_id,
            heart_rate=random.randint(65, 95),
            blood_oxygen=random.uniform(95, 100),
            stress_level=random.uniform(10, 40)
        )
        
        success_count = sum([hr_success, acc_success, gps_success, health_success])
        
        if success_count == 4:
            logger.info(f"All test smartwatch messages sent successfully for session: {session_id}")
        else:
            logger.warning(f"Only {success_count}/4 test messages sent successfully")
            
        return success_count == 4
    
    def _estimate_calories(self, activity_type: str, duration_seconds: int) -> float:
        """Estimate calories burned based on activity and duration"""
        # Rough calorie estimates per minute for different activities
        calorie_rates = {
            'walking': 4.0,
            'running': 12.0,
            'cycling': 8.0,
            'sitting': 1.5,
            'standing': 2.0,
            'sleeping': 1.0,
            'workout': 10.0
        }
        
        rate = calorie_rates.get(activity_type, 3.0)
        return rate * (duration_seconds / 60.0)
    
    def _get_intensity(self, activity_type: str) -> str:
        """Get activity intensity level"""
        intensity_map = {
            'sleeping': 'very_low',
            'sitting': 'low', 
            'standing': 'low',
            'walking': 'moderate',
            'cycling': 'moderate',
            'running': 'high',
            'workout': 'high'
        }
        
        return intensity_map.get(activity_type, 'moderate')