"""
통합 스트리밍 API 테스트
"""
from django.core.management.base import BaseCommand
from aria_sessions.models import AriaStreamingSession
from aria_sessions.streaming_service import AriaUnifiedStreaming
import os

class Command(BaseCommand):
    help = '통합 스트리밍 API 테스트'

    def handle(self, *args, **options):
        # 1. 세션 생성
        vrs_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'data', 'sample.vrs'
        )
        
        session = AriaStreamingSession.objects.create(
            vrs_file_path=vrs_file,
            status='READY'
        )
        
        self.stdout.write(f"생성된 세션: {session.session_id}")
        
        # 2. 스트리밍 서비스 테스트
        try:
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = vrs_file
            streaming.create_data_provider()
            
            # 통합 스트리밍 실행 (10개 항목)
            results = streaming.process_unified_stream(
                active_streams=['camera-rgb', 'camera-slam-left', 'camera-slam-right'],
                max_count=10
            )
            
            self.stdout.write(self.style.SUCCESS(f"✅ 통합 스트리밍 성공: {len(results)}개 항목 처리"))
            
            # 3. API 엔드포인트 정보 출력
            self.stdout.write("\n=== API 엔드포인트 ===")
            self.stdout.write(f"세션 목록: GET /api/v1/aria-sessions/api/sessions/")
            self.stdout.write(f"세션 생성: POST /api/v1/aria-sessions/api/sessions/")
            self.stdout.write(f"통합 스트리밍: GET /api/v1/aria-sessions/api/sessions/{session.session_id}/unified_stream/")
            self.stdout.write(f"스트리밍 시작: POST /api/v1/aria-sessions/api/sessions/{session.session_id}/start_streaming/")
            
            # 4. 테스트 예시 명령어
            self.stdout.write("\n=== 테스트 명령어 ===")
            self.stdout.write(f"curl -X GET http://localhost:8000/api/v1/aria-sessions/api/sessions/")
            self.stdout.write(f"curl -X GET http://localhost:8000/api/v1/aria-sessions/api/sessions/{session.session_id}/unified_stream/?streams=camera-rgb,camera-slam-left&count=5")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 오류: {str(e)}"))
            session.status = 'ERROR'
            session.save()