#!/usr/bin/env python3
"""
Stream Connection Test Script
Test Kafka producer/consumer connections for all stream types
"""

import os
import sys
import time
import json
from datetime import datetime

# Add ARD directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ARD'))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')

import django
django.setup()

from common.kafka.stream_manager import stream_manager
from aria_streams.producers import AriaKafkaProducer
from webcam_streams.producers import WebcamKafkaProducer
from smartwatch_streams.producers import SmartwatchKafkaProducer


def test_kafka_connection():
    """Test basic Kafka connection"""
    print("🔍 Testing Kafka Connection...")
    
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'host.docker.internal:9092')
    print(f"   Bootstrap servers: {bootstrap_servers}")
    
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 10, 1),
            request_timeout_ms=5000
        )
        
        # Try to get metadata
        metadata = producer.bootstrap_connected()
        producer.close()
        
        if metadata:
            print("   ✅ Kafka connection successful")
            return True
        else:
            print("   ❌ Kafka connection failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Kafka connection error: {e}")
        return False


def test_aria_producer():
    """Test Aria producer"""
    print("\n🎯 Testing Aria Producer...")
    
    try:
        producer = AriaKafkaProducer()
        
        # Test sending VRS frame
        success = producer.send_test_message()
        
        if success:
            print("   ✅ Aria producer test successful")
        else:
            print("   ❌ Aria producer test failed")
            
        producer.close()
        return success
        
    except Exception as e:
        print(f"   ❌ Aria producer error: {e}")
        return False


def test_webcam_producer():
    """Test Webcam producer"""
    print("\n📷 Testing Webcam Producer...")
    
    try:
        producer = WebcamKafkaProducer()
        
        # Test sending webcam frame
        success = producer.send_test_message()
        
        if success:
            print("   ✅ Webcam producer test successful")
        else:
            print("   ❌ Webcam producer test failed")
            
        producer.close()
        return success
        
    except Exception as e:
        print(f"   ❌ Webcam producer error: {e}")
        return False


def test_smartwatch_producer():
    """Test Smartwatch producer"""
    print("\n⌚ Testing Smartwatch Producer...")
    
    try:
        producer = SmartwatchKafkaProducer()
        
        # Test sending sensor data
        success = producer.send_test_sensor_data()
        
        if success:
            print("   ✅ Smartwatch producer test successful")
        else:
            print("   ❌ Smartwatch producer test failed")
            
        producer.close()
        return success
        
    except Exception as e:
        print(f"   ❌ Smartwatch producer error: {e}")
        return False


def test_stream_manager():
    """Test Stream Manager"""
    print("\n🎛️  Testing Stream Manager...")
    
    try:
        # Get active streams
        active_streams = stream_manager.get_active_services()
        print(f"   Active streams: {active_streams}")
        
        # Get service status
        status = stream_manager.get_service_status()
        
        for service, service_status in status.items():
            print(f"   {service}:")
            print(f"     Registered: {service_status['registered']}")
            print(f"     Topics: {len(service_status['topics'])}")
        
        print("   ✅ Stream Manager test successful")
        return True
        
    except Exception as e:
        print(f"   ❌ Stream Manager error: {e}")
        return False


def main():
    """Run all connection tests"""
    print("🚀 ARD Stream Connection Test")
    print("=" * 50)
    
    # Test results
    results = {}
    
    # Test Kafka connection
    results['kafka'] = test_kafka_connection()
    
    # Test producers
    results['aria'] = test_aria_producer()
    results['webcam'] = test_webcam_producer()
    results['smartwatch'] = test_smartwatch_producer()
    
    # Test stream manager
    results['stream_manager'] = test_stream_manager()
    
    # Summary
    print("\n📊 Test Summary")
    print("-" * 30)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Stream connections are working.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)