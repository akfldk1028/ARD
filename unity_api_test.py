#!/usr/bin/env python3
"""
Unity 연동을 위한 ARD API 테스트 스크립트
Unity에서 이 API들을 호출하여 실시간 AR 데이터를 받을 수 있습니다.
"""

import requests
import json
import time
import sys
from datetime import datetime

class ARDAPITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/streams/api"
        
    def test_connection(self):
        """API 연결 테스트"""
        try:
            response = requests.get(f"{self.api_base}/sessions/", timeout=5)
            if response.status_code == 200:
                print("✅ API 연결 성공!")
                return True
            else:
                print(f"❌ API 연결 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 연결 오류: {e}")
            return False
    
    def start_streaming(self, duration=30, stream_type="all"):
        """VRS/MPS 스트리밍 시작 (Unity에서 호출할 함수)"""
        print(f"\n🚀 스트리밍 시작: {stream_type} ({duration}초)")
        
        data = {
            "duration": duration,
            "stream_type": stream_type
        }
        
        try:
            response = requests.post(
                f"{self.api_base}/streaming/",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 스트리밍 시작 성공: {result['message']}")
                return True
            else:
                print(f"❌ 스트리밍 시작 실패: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 스트리밍 오류: {e}")
            return False
    
    def get_streaming_status(self):
        """스트리밍 상태 확인 (Unity에서 주기적으로 호출)"""
        try:
            response = requests.get(f"{self.api_base}/streaming/")
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"❌ 상태 확인 오류: {e}")
            return None
    
    def get_realtime_data(self, data_type="eye-gaze", limit=10):
        """실시간 데이터 가져오기 (Unity에서 지속적으로 호출)"""
        endpoints = {
            "eye-gaze": f"{self.api_base}/eye-gaze/",
            "hand-tracking": f"{self.api_base}/hand-tracking/",
            "slam-trajectory": f"{self.api_base}/slam-trajectory/",
            "vrs-streams": f"{self.api_base}/vrs-streams/"
        }
        
        if data_type not in endpoints:
            print(f"❌ 지원되지 않는 데이터 타입: {data_type}")
            return None
        
        try:
            params = {
                "ordering": "-timestamp",
                "page_size": limit
            }
            
            response = requests.get(endpoints[data_type], params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                print(f"❌ 데이터 가져오기 실패: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 데이터 요청 오류: {e}")
            return None
    
    def get_session_statistics(self, session_id):
        """세션 통계 가져오기 (Unity 대시보드용)"""
        try:
            response = requests.get(f"{self.api_base}/sessions/{session_id}/statistics/")
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"❌ 통계 요청 오류: {e}")
            return None
    
    def get_gaze_heatmap(self, session_id=None, gaze_type="general"):
        """시선 히트맵 데이터 (Unity 시각화용)"""
        try:
            params = {"gaze_type": gaze_type}
            if session_id:
                params["session"] = session_id
                
            response = requests.get(f"{self.api_base}/eye-gaze/gaze_heatmap/", params=params)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"❌ 히트맵 요청 오류: {e}")
            return None
    
    def get_slam_trajectory(self, session_id=None, limit=100):
        """SLAM 궤적 데이터 (Unity 3D 시각화용)"""
        try:
            params = {"limit": limit}
            if session_id:
                params["session"] = session_id
                
            response = requests.get(f"{self.api_base}/slam-trajectory/trajectory_path/", params=params)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"❌ 궤적 요청 오류: {e}")
            return None
    
    def run_unity_simulation(self, duration=30):
        """Unity 연동 시뮬레이션 (전체 워크플로우 테스트)"""
        print("🎮 Unity 연동 시뮬레이션 시작")
        print("=" * 50)
        
        # 1. 연결 테스트
        if not self.test_connection():
            return False
        
        # 2. 스트리밍 시작
        if not self.start_streaming(duration=duration):
            return False
        
        # 3. 실시간 데이터 모니터링
        print(f"\n📊 {duration}초 동안 실시간 데이터 모니터링...")
        
        start_time = time.time()
        data_counts = {
            "eye-gaze": 0,
            "hand-tracking": 0,
            "slam-trajectory": 0,
            "vrs-streams": 0
        }
        
        while time.time() - start_time < duration:
            # 스트리밍 상태 확인
            status = self.get_streaming_status()
            if status and status.get('data', {}).get('is_streaming'):
                print(f"⏰ 스트리밍 진행 중... ({int(time.time() - start_time)}s)")
            
            # 각 데이터 타입별로 최신 데이터 확인
            for data_type in data_counts.keys():
                data = self.get_realtime_data(data_type, limit=5)
                if data:
                    data_counts[data_type] += len(data)
                    if data:  # 최신 데이터가 있으면 샘플 출력
                        latest = data[0]
                        print(f"📈 {data_type}: {len(data)}개 새 데이터 (최신: {latest.get('timestamp', 'N/A')})")
            
            time.sleep(5)  # 5초마다 체크
        
        # 4. 결과 요약
        print("\n📋 Unity 연동 테스트 결과:")
        print("-" * 30)
        total_data = sum(data_counts.values())
        print(f"전체 수신 데이터: {total_data}개")
        for data_type, count in data_counts.items():
            print(f"  - {data_type}: {count}개")
        
        # 5. 시각화용 데이터 테스트
        print("\n🎨 Unity 시각화용 데이터 테스트:")
        
        # 시선 히트맵
        heatmap = self.get_gaze_heatmap()
        if heatmap:
            print(f"  ✅ 시선 히트맵: {heatmap.get('total_samples', 0)}개 샘플")
        
        # SLAM 궤적
        trajectory = self.get_slam_trajectory()
        if trajectory:
            print(f"  ✅ SLAM 궤적: {trajectory.get('total_points', 0)}개 포인트")
        
        print("\n🎉 Unity 연동 시뮬레이션 완료!")
        return True

def main():
    """메인 실행 함수"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"
    
    print(f"🔗 ARD API 서버: {base_url}")
    
    tester = ARDAPITester(base_url)
    
    # Unity 시뮬레이션 실행
    success = tester.run_unity_simulation(duration=20)
    
    if success:
        print("\n✅ Unity 연동 준비 완료!")
        print("\n🎯 Unity에서 사용할 주요 API 엔드포인트:")
        print(f"  - 스트리밍 제어: {base_url}/api/streams/api/streaming/")
        print(f"  - 실시간 시선 데이터: {base_url}/api/streams/api/eye-gaze/")
        print(f"  - 실시간 손 추적: {base_url}/api/streams/api/hand-tracking/")
        print(f"  - SLAM 궤적: {base_url}/api/streams/api/slam-trajectory/")
        print(f"  - 시선 히트맵: {base_url}/api/streams/api/eye-gaze/gaze_heatmap/")
        print(f"  - DRF 브라우저: {base_url}/api/streams/api/")
    else:
        print("\n❌ Unity 연동 테스트 실패")
        sys.exit(1)

if __name__ == "__main__":
    main()