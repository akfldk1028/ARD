"""
Universal XR Devices 사용 예시

이 파일은 새로운 XR 기기 시스템을 사용하는 방법을 보여줍니다.
"""

import asyncio
import json
from datetime import datetime

# Django 설정이 필요한 경우
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')

import django
django.setup()

from xr_devices.streaming import streaming_manager
from xr_devices.parsers import XRParserFactory
from xr_devices.adapters import AdapterFactory
from xr_devices.models import XRDevice


async def demo_meta_aria_streaming():
    """Meta Aria 기기 스트리밍 데모"""
    print("🥽 Meta Aria 스트리밍 데모 시작...")
    
    try:
        # 1. 세션 생성
        session_id = await streaming_manager.create_session(
            device_type='meta_aria',
            session_name='demo_aria_session',
            user_id='demo_user',
            streaming_config={
                'streaming': {
                    'bootstrap_servers': 'localhost:9092'
                }
            }
        )
        
        if not session_id:
            print("❌ 세션 생성 실패 - Kafka가 실행 중인지 확인하세요")
            return
            
        print(f"✅ 세션 생성됨: {session_id}")
        
        # 2. 스트리밍 시작
        success = await streaming_manager.start_streaming(session_id)
        if success:
            print("🚀 스트리밍 시작됨")
        else:
            print("❌ 스트리밍 시작 실패")
            return
        
        # 3. 시뮬레이션 데이터 처리
        print("📊 데이터 처리 시뮬레이션...")
        
        # RGB 카메라 데이터
        rgb_data = b'fake_rgb_camera_data_' + str(datetime.now().timestamp()).encode()
        await streaming_manager.process_data(
            session_id=session_id,
            raw_data=rgb_data,
            sensor_type='camera_rgb'
        )
        print("📷 RGB 카메라 데이터 처리됨")
        
        # IMU 센서 데이터
        imu_data = b'fake_imu_sensor_data_' + str(datetime.now().timestamp()).encode()
        await streaming_manager.process_data(
            session_id=session_id,
            raw_data=imu_data,
            sensor_type='imu'
        )
        print("🧭 IMU 센서 데이터 처리됨")
        
        # 시선 추적 데이터
        eye_data = b'fake_eye_tracking_data_' + str(datetime.now().timestamp()).encode()
        await streaming_manager.process_data(
            session_id=session_id,
            raw_data=eye_data,
            sensor_type='eye_tracking'
        )
        print("👁️ 시선 추적 데이터 처리됨")
        
        # 4. 세션 상태 확인
        status = streaming_manager.get_session_status(session_id)
        if status:
            print(f"📈 세션 상태: {status['frame_count']}프레임, {status['total_data_size_mb']}MB 처리됨")
        
        # 5. 스트리밍 중지
        await asyncio.sleep(1)  # 잠시 대기
        await streaming_manager.stop_streaming(session_id)
        print("⏹️ 스트리밍 중지됨")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def demo_future_devices():
    """미래 기기들 준비 상태 데모"""
    print("\n🔮 미래 XR 기기 지원 현황...")
    
    # 지원되는 기기 목록
    devices = streaming_manager.get_supported_devices()
    print(f"📱 지원 기기: {len(devices)}개")
    
    for device in devices:
        status = "✅ 준비됨" if device['device_type'] == 'meta_aria' else "🚧 개발 예정"
        print(f"  - {device['name']}: {status}")
    
    # 지원되는 파서 목록
    parsers = XRParserFactory.list_supported_devices()
    print(f"🔧 지원 파서: {len(parsers)}개")
    for parser in parsers:
        print(f"  - {parser} Parser")
    
    # 지원되는 프로토콜 목록
    protocols = AdapterFactory.list_supported_protocols()
    print(f"📡 지원 프로토콜: {len(protocols)}개")
    for protocol in protocols:
        print(f"  - {protocol.upper()}")


def demo_parser_usage():
    """파서 직접 사용 데모"""
    print("\n🔧 파서 직접 사용 데모...")
    
    # Meta Aria 파서 테스트
    aria_parser = XRParserFactory.get_parser('meta_aria')
    if aria_parser:
        print("✅ Meta Aria 파서 로드됨")
        
        # 테스트 데이터 파싱
        test_data = b'test_sensor_data'
        result = aria_parser.parse_frame(
            raw_data=test_data,
            sensor_type='imu',
            timestamp_ns=int(datetime.now().timestamp() * 1e9)
        )
        
        print("📊 파싱 결과:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Google Glass 파서 테스트 (미래 기기)
    glass_parser = XRParserFactory.get_parser('google_glass')
    if glass_parser:
        print("🥽 Google Glass 파서도 준비됨!")


async def demo_multi_device_session():
    """다중 기기 세션 데모"""
    print("\n🌐 다중 기기 세션 데모...")
    
    active_sessions = []
    
    try:
        # 각 지원 기기별로 세션 생성 시도
        devices = ['meta_aria']  # 현재는 Aria만 완전 구현
        
        for device_type in devices:
            session_id = await streaming_manager.create_session(
                device_type=device_type,
                session_name=f'multi_device_{device_type}',
                user_id='multi_user'
            )
            
            if session_id:
                active_sessions.append((device_type, session_id))
                print(f"✅ {device_type} 세션 생성: {session_id[:12]}...")
        
        # 활성 세션 목록 출력
        all_sessions = streaming_manager.list_active_sessions()
        print(f"📊 총 활성 세션: {len(all_sessions)}개")
        
        # 정리
        for device_type, session_id in active_sessions:
            await streaming_manager.stop_streaming(session_id)
            print(f"🗑️ {device_type} 세션 정리됨")
    
    except Exception as e:
        print(f"❌ 다중 기기 데모 오류: {e}")


def print_system_info():
    """시스템 정보 출력"""
    print("🚀 Universal XR Devices Management System")
    print("=" * 50)
    print("📅 미래 XR 기기 지원을 위한 확장 가능한 아키텍처")
    print("🎯 목표: Meta, Google, Apple, Microsoft 등 모든 XR 기기 통합 지원")
    print("🔧 핵심: 파서와 어댑터만 추가하면 새 기기 자동 지원")
    print("=" * 50)


async def main():
    """메인 데모 실행"""
    print_system_info()
    
    # 1. Meta Aria 스트리밍 데모
    await demo_meta_aria_streaming()
    
    # 2. 미래 기기 준비 현황
    await demo_future_devices()
    
    # 3. 파서 직접 사용
    demo_parser_usage()
    
    # 4. 다중 기기 세션 (현재는 Aria만)
    await demo_multi_device_session()
    
    print("\n🎉 모든 데모 완료!")
    print("💡 팁: 새로운 XR 기기 출시시 파서만 추가하면 바로 지원됩니다!")


if __name__ == '__main__':
    # 비동기 함수 실행
    asyncio.run(main())