"""
메인 대시보드 - 모든 스트리밍 기능 통합 페이지
"""

from django.http import HttpResponse
from django.views import View

class MainDashboardView(View):
    """메인 대시보드 - 카메라 + 센서 통합"""
    
    def get(self, request):
        """메인 대시보드 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Project Aria 통합 스트리밍 대시보드</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .title {
            font-size: 3rem;
            margin: 0;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.4);
            background: linear-gradient(45deg, #ff6b6b, #ffeaa7, #74b9ff, #a29bfe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            font-size: 1.3rem;
            opacity: 0.9;
            margin: 15px 0;
        }
        
        .features-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }
        
        .feature-card {
            background: rgba(255,255,255,0.15);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(15px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
        }
        
        .feature-icon {
            font-size: 3rem;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .feature-title {
            font-size: 1.5rem;
            font-weight: bold;
            text-align: center;
            margin-bottom: 15px;
            color: #ff6b6b;
        }
        
        .feature-description {
            text-align: center;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        
        .feature-specs {
            background: rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9rem;
        }
        
        .feature-btn {
            display: block;
            width: 100%;
            padding: 15px;
            background: linear-gradient(45deg, #ff6b6b, #ee5a52);
            border: none;
            border-radius: 25px;
            color: white;
            font-size: 1.1rem;
            font-weight: bold;
            text-decoration: none;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .feature-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255,107,107,0.4);
        }
        
        .sensor-btn {
            background: linear-gradient(45deg, #74b9ff, #0984e3);
        }
        
        .sensor-btn:hover {
            box-shadow: 0 8px 25px rgba(116,185,255,0.4);
        }
        
        .stats-section {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            margin-top: 30px;
        }
        
        .stats-title {
            text-align: center;
            font-size: 1.3rem;
            margin-bottom: 20px;
            color: #ffeaa7;
        }
        
        .tech-specs {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }
        
        .tech-item {
            background: rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .tech-label {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        
        .tech-value {
            font-size: 1.1rem;
            font-weight: bold;
            color: #a29bfe;
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 Project Aria</h1>
            <p class="subtitle">통합 스트리밍 대시보드</p>
            <p>공식 Observer 패턴 + deliver_queued_sensor_data 기반</p>
        </div>
        
        <div class="features-grid">
            <!-- 4카메라 스트리밍 카드 -->
            <div class="feature-card">
                <div class="feature-icon">📷🎥👁️</div>
                <div class="feature-title">동시 4카메라 스트리밍</div>
                <div class="feature-description">
                    RGB, SLAM Left/Right, Eye Tracking 카메라를<br>
                    동시에 실시간 스트리밍합니다.
                </div>
                <div class="feature-specs">
                    <div>✅ 4개 카메라 동시 처리</div>
                    <div>🔄 자동 순환 재생</div>
                    <div>🚀 10-100배 성능 향상</div>
                    <div>📊 실시간 FPS/통계</div>
                    <div>🧵 멀티스레드 최적화</div>
                </div>
                <a href="/api/v1/aria-sessions/concurrent-streaming-page/" class="feature-btn">
                    🎥 4카메라 스트리밍 시작
                </a>
            </div>
            
            <!-- 센서 스트리밍 카드 -->
            <div class="feature-card">
                <div class="feature-icon">🧭🧲🌡️</div>
                <div class="feature-title">동시 센서 스트리밍</div>
                <div class="feature-description">
                    IMU, 자력계, 기압계, 오디오 센서를<br>
                    동시에 실시간으로 모니터링합니다.
                </div>
                <div class="feature-specs">
                    <div>🧭 IMU 센서 (가속도+자이로)</div>
                    <div>🧲 자력계 (지자기장)</div>
                    <div>🌡️ 기압계 (압력+온도)</div>
                    <div>🎵 오디오 (7채널 48kHz)</div>
                    <div>🔄 무한 순환 재생</div>
                </div>
                <a href="/api/v1/aria-sessions/concurrent-sensor-page/" class="feature-btn sensor-btn">
                    🧭 센서 스트리밍 시작
                </a>
            </div>
        </div>
 
    </div>

    <script>
        // 페이지 로드시 환영 메시지
        console.log('🔥 Project Aria 통합 대시보드 로드됨');
        console.log('📷 4카메라 스트리밍: /api/v1/aria-sessions/concurrent-streaming-page/');
        console.log('🧭 센서 스트리밍: /api/v1/aria-sessions/concurrent-sensor-page/');
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)