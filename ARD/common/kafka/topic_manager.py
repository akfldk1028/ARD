"""
Kafka Topic Management
Central topic registry and naming conventions
"""

class TopicManager:
    """Centralized topic management and naming conventions"""
    
    # Topic naming convention: {service}.{category}.{type}
    TOPICS = {
        'aria': {
            'vrs_frame': 'aria.vrs.frame',
            'imu_data': 'aria.sensor.imu',
            'eye_gaze_general': 'aria.mps.eye_gaze.general',
            'eye_gaze_personalized': 'aria.mps.eye_gaze.personalized',
            'hand_tracking': 'aria.mps.hand_tracking',
            'slam_trajectory': 'aria.mps.slam.trajectory',
            'slam_points': 'aria.mps.slam.points',
            'slam_calibration': 'aria.mps.slam.calibration',
            'analytics': 'aria.analytics.realtime'
        },
        'webcam': {
            'video_frame': 'webcam.video.frame',
            'motion_detection': 'webcam.analysis.motion',
            'face_detection': 'webcam.analysis.face',
            'object_detection': 'webcam.analysis.object',
            'activity_recognition': 'webcam.analysis.activity'
        },
        'smartwatch': {
            'heart_rate': 'smartwatch.sensor.heart_rate',
            'accelerometer': 'smartwatch.sensor.accelerometer',
            'gyroscope': 'smartwatch.sensor.gyroscope',
            'gps': 'smartwatch.sensor.gps',
            'step_counter': 'smartwatch.sensor.steps',
            'sleep_tracking': 'smartwatch.health.sleep',
            'activity_recognition': 'smartwatch.health.activity',
            'health_metrics': 'smartwatch.health.metrics'
        }
    }
    
    @classmethod
    def get_topics_for_service(cls, service_name: str) -> dict:
        """Get all topics for a specific service"""
        return cls.TOPICS.get(service_name, {})
    
    @classmethod
    def get_topic(cls, service_name: str, topic_key: str) -> str:
        """Get specific topic name"""
        service_topics = cls.get_topics_for_service(service_name)
        return service_topics.get(topic_key)
    
    @classmethod
    def get_all_topics(cls) -> list:
        """Get all topic names across all services"""
        all_topics = []
        for service_topics in cls.TOPICS.values():
            all_topics.extend(service_topics.values())
        return all_topics
    
    @classmethod
    def get_topics_by_category(cls, category: str) -> list:
        """Get topics by category (sensor, mps, analysis, etc.)"""
        matching_topics = []
        for service_topics in cls.TOPICS.values():
            for topic in service_topics.values():
                if f'.{category}.' in topic:
                    matching_topics.append(topic)
        return matching_topics
    
    @classmethod
    def validate_topic(cls, service_name: str, topic_key: str) -> bool:
        """Validate if topic exists for service"""
        return topic_key in cls.get_topics_for_service(service_name)


# Topic configurations for different environments
TOPIC_CONFIGS = {
    'development': {
        'num_partitions': 1,
        'replication_factor': 1,
        'retention_ms': 86400000,  # 1 day
    },
    'production': {
        'num_partitions': 3,
        'replication_factor': 2,
        'retention_ms': 604800000,  # 7 days
    }
}