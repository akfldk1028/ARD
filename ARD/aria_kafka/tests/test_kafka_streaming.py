"""
Kafka 스트리밍 테스트 - 실제 동작 확인
"""
import os
import time
import requests
import json
from django.conf import settings

# API 기본 URL
BASE_URL = "http://127.0.0.1:8000"

def test_kafka_endpoints():
    """Kafka API 엔드포인트 테스트"""
    print("=== Kafka API 엔드포인트 테스트 ===\n")
    
    # 1. 지원되는 스트림 목록 확인
    print("1. 지원되는 스트림 목록 확인")
    response = requests.get(f"{BASE_URL}/api/v2/kafka-streams/admin/streams/")
    if response.status_code == 200:
        data = response.json()
        print("[OK] 이미지 스트림:", data['supported_streams']['images'])
        print("[OK] 센서 스트림:", data['supported_streams']['sensors'])
    else:
        print(f"[ERROR] 오류: {response.status_code}")
    
    print("\n" + "="*50 + "\n")
    
    # 2. 개별 스트림 시작
    print("2. RGB 카메라 스트림 시작")
    response = requests.post(
        f"{BASE_URL}/api/v2/kafka-streams/control/producer/start/camera-rgb/",
        json={"fps": 10.0, "duration": 30}
    )
    if response.status_code == 200:
        print("[OK] RGB 스트림 시작:", response.json())
    else:
        print(f"[ERROR] 오류: {response.status_code}")
    
    # 잠시 대기
    time.sleep(2)
    
    print("\n" + "="*50 + "\n")
    
    # 3. 스트림 데이터 확인
    print("3. RGB 카메라 최신 데이터 확인")
    response = requests.get(f"{BASE_URL}/api/v2/kafka-streams/images/camera-rgb/latest/")
    if response.status_code == 200:
        data = response.json()
        if data.get('data'):
            print("[OK] 이미지 데이터 수신:")
            print(f"  - 타임스탬프: {data['data'].get('timestamp_ns', 'N/A')}")
            print(f"  - 이미지 크기: {data['data'].get('data', {}).get('shape', 'N/A')}")
        else:
            print("[OK] 아직 데이터 없음 (정상)")
    else:
        print(f"[ERROR] 오류: {response.status_code}")
    
    print("\n" + "="*50 + "\n")
    
    # 4. 시스템 상태 확인
    print("4. 시스템 상태 확인")
    response = requests.get(f"{BASE_URL}/api/v2/kafka-streams/admin/status/")
    if response.status_code == 200:
        data = response.json()
        print("[OK] 시스템 요약:")
        print(f"  - 전체 스트림: {data['summary']['total_streams']}")
        print(f"  - 활성 스트림: {data['summary']['active_streams']}")
    else:
        print(f"[ERROR] 오류: {response.status_code}")
    
    print("\n" + "="*50 + "\n")
    
    # 5. 헬스 체크
    print("5. 헬스 체크")
    response = requests.get(f"{BASE_URL}/api/v2/kafka-streams/admin/health/")
    if response.status_code == 200:
        data = response.json()
        print("[OK] 헬스 상태:", data.get('status', 'unknown'))
        print(f"  - Producer: {'정상' if data.get('producer_healthy') else '오류'}")
        print(f"  - Consumer: {'정상' if data.get('consumer_healthy') else '오류'}")
    else:
        print(f"[ERROR] 오류: {response.status_code}")
    
    print("\n" + "="*50 + "\n")
    
    # 6. 스트림 중지
    print("6. RGB 카메라 스트림 중지")
    response = requests.post(f"{BASE_URL}/api/v2/kafka-streams/control/producer/stop/camera-rgb/")
    if response.status_code == 200:
        print("[OK] RGB 스트림 중지:", response.json())
    else:
        print(f"[ERROR] 오류: {response.status_code}")

def test_without_kafka():
    """Kafka 없이 테스트 (Mock 모드)"""
    print("\n=== Kafka 없이 테스트 (Mock 모드) ===\n")
    
    # 기본 API 동작만 확인
    endpoints = [
        "/api/v2/kafka-streams/admin/streams/",
        "/api/v2/kafka-streams/admin/health/",
        "/api/v2/kafka-streams/images/camera-rgb/latest/",
    ]
    
    for endpoint in endpoints:
        print(f"테스트: {endpoint}")
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            print(f"  상태: {response.status_code}")
            if response.status_code == 200:
                print("  [OK] 정상 응답")
        except Exception as e:
            print(f"  [ERROR] 오류: {e}")
        print()

if __name__ == "__main__":
    print("Kafka 스트리밍 시스템 테스트\n")
    
    # Django 서버 실행 확인
    try:
        response = requests.get(f"{BASE_URL}/admin/")
        print("[OK] Django 서버 실행 중\n")
    except:
        print("[ERROR] Django 서버가 실행되지 않았습니다.")
        print("먼저 실행: python ARD/manage.py runserver\n")
        exit(1)
    
    # Kafka 없이도 동작하는 부분 테스트
    test_without_kafka()
    
    print("\n전체 테스트를 위해서는:")
    print("1. Kafka 서버 시작")
    print("2. python ARD/manage.py start_kafka_streaming")
    print("3. 이 스크립트 다시 실행")