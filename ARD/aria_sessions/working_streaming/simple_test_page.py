"""
간단한 테스트 페이지 - 오류 없이 빠르게 테스트
"""

from django.http import HttpResponse
from django.views import View

class SimpleTestPageView(View):
    """
    간단한 테스트 페이지
    """
    
    def get(self, request):
        """간단한 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>서버 동작 테스트</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            font-family: 'Arial', sans-serif;
            color: white;
            text-align: center;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 50px 20px;
        }
        
        .title {
            font-size: 3rem;
            color: #00ff00;
            margin-bottom: 30px;
            text-shadow: 0 0 20px #00ff00;
        }
        
        .status {
            font-size: 1.5rem;
            margin: 20px 0;
            padding: 20px;
            background: rgba(0,255,0,0.1);
            border: 2px solid #00ff00;
            border-radius: 10px;
        }
        
        .test-btn {
            padding: 15px 30px;
            margin: 10px;
            border: none;
            border-radius: 25px;
            font-size: 1.2rem;
            cursor: pointer;
            background: #00ff00;
            color: #000;
            font-weight: bold;
        }
        
        .test-btn:hover {
            background: #00cc00;
            transform: translateY(-2px);
        }
        
        .result-box {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            min-height: 200px;
            font-family: monospace;
            text-align: left;
        }
        
        .success { color: #00ff00; }
        .error { color: #ff6666; }
        .info { color: #00ccff; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="title">서버 동작 확인</h1>
        
        <div class="status">
            Django 서버 정상 작동 중!
        </div>
        
        <div>
            <button class="test-btn" onclick="testBasicAPI()">기본 API 테스트</button>
            <button class="test-btn" onclick="testMultiClient()">다중 클라이언트 테스트</button>
            <button class="test-btn" onclick="testKafkaStatus()">Kafka 상태 테스트</button>
        </div>
        
        <div class="result-box" id="result">
            여기에 테스트 결과가 표시됩니다...
            <br><br>
            <div class="info">현재 시간: <span id="current-time"></span></div>
        </div>
    </div>
    
    <script>
        function updateTime() {
            document.getElementById('current-time').textContent = new Date().toLocaleString();
        }
        
        setInterval(updateTime, 1000);
        updateTime();
        
        function addResult(message, type = 'info') {
            const resultBox = document.getElementById('result');
            const timestamp = new Date().toLocaleTimeString();
            const className = type === 'success' ? 'success' : (type === 'error' ? 'error' : 'info');
            
            const newLine = `<div class="${className}">[${timestamp}] ${message}</div>`;
            resultBox.innerHTML = newLine + '<br>' + resultBox.innerHTML;
        }
        
        async function testBasicAPI() {
            addResult('기본 API 테스트 시작...', 'info');
            
            try {
                const response = await fetch('/api/v1/aria-sessions/test/');
                const data = await response.text();
                
                if (response.ok) {
                    addResult('기본 API 테스트 성공!', 'success');
                    addResult('응답: ' + data.substring(0, 100) + '...', 'info');
                } else {
                    addResult('기본 API 테스트 실패: HTTP ' + response.status, 'error');
                }
            } catch (error) {
                addResult('기본 API 오류: ' + error.message, 'error');
            }
        }
        
        async function testMultiClient() {
            addResult('다중 클라이언트 테스트 시작...', 'info');
            
            // 간단한 다중 요청 시뮬레이션
            const promises = [];
            for (let i = 1; i <= 3; i++) {
                promises.push(
                    fetch('/api/v1/aria-sessions/test/')
                        .then(response => {
                            addResult(`클라이언트 ${i} 응답: HTTP ${response.status}`, 'success');
                            return response.status;
                        })
                        .catch(error => {
                            addResult(`클라이언트 ${i} 오류: ${error.message}`, 'error');
                            return 'error';
                        })
                );
            }
            
            try {
                const results = await Promise.all(promises);
                const successCount = results.filter(r => r === 200).length;
                addResult(`다중 클라이언트 테스트 완료: ${successCount}/3 성공`, 'success');
            } catch (error) {
                addResult('다중 클라이언트 테스트 실패: ' + error.message, 'error');
            }
        }
        
        async function testKafkaStatus() {
            addResult('Kafka 상태 테스트 시작...', 'info');
            
            try {
                const response = await fetch('/api/v1/aria-sessions/kafka-status/');
                
                if (response.ok) {
                    const data = await response.json();
                    addResult('Kafka 상태 테스트 성공!', 'success');
                    addResult('Kafka 활성화: ' + data.kafka_enabled, 'info');
                    addResult('토픽 수: ' + (data.topics ? Object.keys(data.topics).length : 0), 'info');
                } else {
                    addResult('Kafka 상태 테스트 실패: HTTP ' + response.status, 'error');
                }
            } catch (error) {
                addResult('Kafka 상태 오류: ' + error.message, 'error');
            }
        }
        
        // 페이지 로드시 자동 테스트
        setTimeout(() => {
            addResult('페이지 로드 완료 - 서버 연결 정상!', 'success');
        }, 1000);
    </script>
</body>
</html>'''
        
        return HttpResponse(html_template)