from django.core.management.base import BaseCommand
from aria_sessions.models import AriaStreamingSession

class Command(BaseCommand):
    help = 'Generate WebSocket test URLs'

    def handle(self, *args, **options):
        sessions = AriaStreamingSession.objects.all()
        
        if not sessions:
            self.stdout.write('No sessions found')
            return
        
        self.stdout.write("=== WebSocket Streaming Test URLs ===")
        
        for session in sessions:
            session_id = str(session.session_id)
            
            self.stdout.write(f"\nSession: {session_id}")
            self.stdout.write(f"Real-time Streaming Test Page:")
            self.stdout.write(f"http://127.0.0.1:8000/api/v1/aria-sessions/simple/{session_id}/streaming_test/")
            
            self.stdout.write(f"WebSocket URL:")
            self.stdout.write(f"ws://127.0.0.1:8000/ws/aria-sessions/{session_id}/stream/")
        
        self.stdout.write(f"\n=== Instructions ===")
        self.stdout.write("1. Click on the streaming test page URL")  
        self.stdout.write("2. Click 'Connect' button")
        self.stdout.write("3. Click 'Start Streaming' for real-time data")
        self.stdout.write("4. Click 'Get Single Frame' for image with Base64")