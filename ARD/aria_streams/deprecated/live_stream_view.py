"""
실시간 VRS 이미지 스트리밍 뷰어
모든 VRS 이미지를 실시간으로 연속 표시
"""

from django.http import HttpResponse, StreamingHttpResponse
from django.views import View
from django.template import Template, Context
import json
import base64
import time

class LiveStreamView(View):
    """실시간 VRS 스트리밍 뷰어 - 연속 이미지 표시"""
    
    def get(self, request):
        """실시간 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎥 실시간 VRS 이미지 스트리밍</title>
    <meta charset="utf-8">
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: #000;
            color: #fff;
            font-family: 'Courier New', monospace;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        .stream-container {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        .stream-image {
            max-width: 800px;
            max-height: 600px;
            border: 2px solid #00ff00;
            border-radius: 10px;
            background: #111;
        }
        .controls {
            text-align: center;
            margin: 20px 0;
        }
        .btn {
            background: #00ff00;
            color: #000;
            border: none;
            padding: 10px 20px;
            margin: 0 10px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        .btn:hover {
            background: #00cc00;
        }
        .status {
            text-align: center;
            margin: 10px 0;
            font-size: 14px;
        }
        .frame-info {
            text-align: center;
            margin: 10px 0;
            color: #00ff00;
            font-size: 12px;
        }
        .loading {
            text-align: center;
            color: #ff6600;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 실시간 VRS 이미지 스트리밍</h1>
            <p>Project Aria sample.vrs 실시간 연속 스트리밍</p>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="startStreaming()">🚀 스트리밍 시작</button>
            <button class="btn" onclick="stopStreaming()">🛑 스트리밍 중지</button>
            <button class="btn" onclick="captureFrame()">📸 프레임 캡처</button>
            <button class="btn" onclick="toggleReplay()" id="replayBtn">🔄 리플레이 OFF</button>
        </div>
        
        <div class="controls">
            <label style="color: #00ff00; margin-right: 10px;">스트리밍 속도:</label>
            <button class="btn" onclick="changeSpeed(0.5)">0.5x</button>
            <button class="btn" onclick="changeSpeed(1)" id="speed1x" style="background: #ff6600;">1x</button>
            <button class="btn" onclick="changeSpeed(2)">2x</button>
            <button class="btn" onclick="changeSpeed(5)">5x</button>
        </div>
        
        <div class="status" id="status">준비됨 - 스트리밍 시작 버튼을 누르세요</div>
        <div class="frame-info" id="frameInfo"></div>
        
        <div class="stream-container">
            <img id="streamImage" class="stream-image" src="" alt="VRS 스트리밍 이미지" 
                 style="display: none;" onload="onImageLoad()" onerror="onImageError()">
            <div id="loadingMessage" class="loading">이미지 로딩 중...</div>
        </div>
    </div>

    <script>
        let streamingActive = false;
        let streamingInterval = null;
        let frameCount = 0;
        let startTime = null;
        let replayEnabled = false;
        let streamingSpeed = 1.0;  // 1x speed
        let vrsEndDetected = false;
        let replayCount = 0;
        
        const statusEl = document.getElementById('status');
        const frameInfoEl = document.getElementById('frameInfo');
        const imageEl = document.getElementById('streamImage');
        const loadingEl = document.getElementById('loadingMessage');
        
        function startStreaming() {
            if (streamingActive) return;
            
            streamingActive = true;
            frameCount = 0;
            startTime = Date.now();
            
            statusEl.textContent = '🚀 스트리밍 활성화 - VRS 이미지 로딩 중...';
            statusEl.style.color = '#00ff00';
            
            // 먼저 스트리밍 시작 요청
            fetch('/api/v1/aria/streaming/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: 'start',
                    config: {
                        vrs_file: 'data/mps_samples/sample.vrs',
                        stream_type: 'rgb',
                        fps: Math.max(1, 3 * streamingSpeed),
                        duration: 120,
                        replay: replayEnabled,
                        adaptive_quality: true
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('스트리밍 시작:', data);
                
                // 이미지 새로고침 시작 (속도에 따라)
                const intervalMs = Math.max(100, 1000 / streamingSpeed);
                streamingInterval = setInterval(loadNewFrame, intervalMs);
                loadNewFrame(); // 즉시 첫 프레임 로드
            })
            .catch(error => {
                console.error('스트리밍 시작 실패:', error);
                statusEl.textContent = '❌ 스트리밍 시작 실패';
                statusEl.style.color = '#ff0000';
                streamingActive = false;
            });
        }
        
        function stopStreaming() {
            streamingActive = false;
            
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
            
            statusEl.textContent = '🛑 스트리밍 중지됨';
            statusEl.style.color = '#ff6600';
            frameInfoEl.textContent = '';
            
            // 스트리밍 중지 요청
            fetch('/api/v1/aria/streaming/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({action: 'stop'})
            });
        }
        
        function loadNewFrame() {
            if (!streamingActive) return;
            
            // 캐시 방지를 위한 타임스탬프 추가
            const timestamp = Date.now();
            const imageUrl = `/image/?t=${timestamp}`;
            
            loadingEl.style.display = 'block';
            imageEl.style.display = 'none';
            
            // 새 이미지 로드
            imageEl.src = imageUrl;
        }
        
        function onImageLoad() {
            frameCount++;
            const elapsed = (Date.now() - startTime) / 1000;
            const fps = frameCount / elapsed;
            
            loadingEl.style.display = 'none';
            imageEl.style.display = 'block';
            
            statusEl.textContent = `🎥 스트리밍 활성화 - 실시간 VRS 이미지`;
            statusEl.style.color = '#00ff00';
            
            frameInfoEl.textContent = `프레임 ${frameCount} | ${fps.toFixed(1)} FPS | 경과 시간: ${elapsed.toFixed(1)}s`;
        }
        
        function onImageError() {
            console.log('이미지 로드 실패, 다시 시도...');
            loadingEl.textContent = '이미지 로딩 중... (재시도)';
            vrsEndDetected = true;
            
            if (streamingActive) {
                if (replayEnabled) {
                    // VRS 리플레이 시작
                    replayCount++;
                    statusEl.textContent = `🔄 VRS 리플레이 시작 (${replayCount}회차)`;
                    statusEl.style.color = '#ff6600';
                    
                    // 새로운 스트리밍 세션 시작
                    setTimeout(restartVRSStreaming, 2000);
                } else {
                    // 리플레이 비활성화시 재시도만
                    setTimeout(loadNewFrame, 2000);
                }
            }
        }
        
        function restartVRSStreaming() {
            console.log('VRS 리플레이 시작...');
            vrsEndDetected = false;
            frameCount = 0;  // 프레임 카운트 리셋하지 않고 계속 누적
            
            // 새로운 스트리밍 세션 시작
            fetch('/api/v1/aria/streaming/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: 'start',
                    config: {
                        vrs_file: 'data/mps_samples/sample.vrs',
                        stream_type: 'rgb',
                        fps: Math.max(1, 3 * streamingSpeed),
                        duration: 120,
                        replay: true,
                        adaptive_quality: true
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('VRS 리플레이 시작됨:', data);
                statusEl.textContent = `🔄 VRS 리플레이 활성화 (${replayCount}회차)`;
                statusEl.style.color = '#00ff00';
                loadNewFrame();
            })
            .catch(error => {
                console.error('VRS 리플레이 실패:', error);
            });
        }
        
        function toggleReplay() {
            replayEnabled = !replayEnabled;
            const replayBtn = document.getElementById('replayBtn');
            
            if (replayEnabled) {
                replayBtn.textContent = '🔄 리플레이 ON';
                replayBtn.style.background = '#00ff00';
                replayBtn.style.color = '#000';
                statusEl.textContent += ' | 🔄 리플레이 활성화됨';
            } else {
                replayBtn.textContent = '🔄 리플레이 OFF';
                replayBtn.style.background = '#666';
                replayBtn.style.color = '#fff';
                statusEl.textContent = statusEl.textContent.replace(' | 🔄 리플레이 활성화됨', '');
            }
        }
        
        function changeSpeed(newSpeed) {
            streamingSpeed = newSpeed;
            
            // 모든 속도 버튼 리셋
            document.querySelectorAll('.controls .btn').forEach(btn => {
                if (btn.textContent.includes('x')) {
                    btn.style.background = '#00ff00';
                }
            });
            
            // 현재 속도 버튼 강조
            event.target.style.background = '#ff6600';
            
            // 스트리밍 중이면 간격 업데이트
            if (streamingActive && streamingInterval) {
                clearInterval(streamingInterval);
                const intervalMs = Math.max(100, 1000 / streamingSpeed);
                streamingInterval = setInterval(loadNewFrame, intervalMs);
            }
            
            statusEl.textContent = statusEl.textContent.replace(/\d+\.?\d*x 속도/, '') + ` | ${streamingSpeed}x 속도`;
        }
        
        function captureFrame() {
            const link = document.createElement('a');
            link.download = `vrs_frame_${frameCount}_${Date.now()}.jpg`;
            link.href = imageEl.src;
            link.click();
        }
        
        // 페이지 언로드 시 스트리밍 중지
        window.addEventListener('beforeunload', function() {
            if (streamingActive) {
                stopStreaming();
            }
        });
        
        // 초기 로드
        console.log('🎥 VRS 실시간 스트리밍 뷰어 준비 완료');
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template, content_type='text/html')


class VRSFrameStreamView(View):
    """VRS 프레임 연속 스트리밍 API"""
    
    def get(self, request):
        """연속적인 VRS 프레임을 JSON으로 반환"""
        
        def generate_frames():
            """VRS 프레임을 연속으로 생성"""
            frame_count = 0
            
            while True:
                try:
                    # 새로운 VRS 이미지 생성
                    import requests
                    response = requests.post('http://localhost:8000/api/v1/aria/simple-image/generate/')
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            frame_count += 1
                            
                            # 이미지 데이터 가져오기
                            image_response = requests.get('http://localhost:8000/api/v1/aria/simple-image/?format=base64')
                            
                            if image_response.status_code == 200:
                                image_data = image_response.json()
                                
                                frame_data = {
                                    'frame_number': frame_count,
                                    'timestamp': time.time(),
                                    'frame_id': data.get('frame_id'),
                                    'image_base64': image_data.get('image_base64'),
                                    'metadata': data.get('metadata', {})
                                }
                                
                                yield f"data: {json.dumps(frame_data)}\\n\\n"
                    
                    time.sleep(1)  # 1초 간격
                    
                except Exception as e:
                    error_data = {
                        'error': str(e),
                        'timestamp': time.time()
                    }
                    yield f"data: {json.dumps(error_data)}\\n\\n"
                    time.sleep(2)
        
        response = StreamingHttpResponse(
            generate_frames(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['Access-Control-Allow-Origin'] = '*'
        
        return response