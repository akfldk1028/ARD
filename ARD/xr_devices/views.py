"""
XR Devices 통합 관리 뷰
"""

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
import asyncio
import json
import logging
from typing import Dict, Any

from .models import XRDevice, StreamingSession, StreamingData, DataParser
from .streaming import streaming_manager
from .parsers import XRParserFactory
from .adapters import AdapterFactory

logger = logging.getLogger(__name__)


class XRDeviceViewSet(viewsets.ModelViewSet):
    """XR 기기 관리 ViewSet"""
    
    queryset = XRDevice.objects.all()
    
    @action(detail=False, methods=['get'])
    def supported_devices(self, request):
        """지원되는 기기 목록"""
        devices = streaming_manager.get_supported_devices()
        return Response({
            'status': 'success',
            'supported_devices': devices,
            'total_count': len(devices)
        })
    
    @action(detail=False, methods=['get'])
    def supported_parsers(self, request):
        """지원되는 파서 목록"""
        parsers = XRParserFactory.list_supported_devices()
        return Response({
            'status': 'success',
            'supported_parsers': parsers
        })
    
    @action(detail=False, methods=['get'])
    def supported_protocols(self, request):
        """지원되는 스트리밍 프로토콜"""
        protocols = AdapterFactory.list_supported_protocols()
        return Response({
            'status': 'success',
            'supported_protocols': protocols
        })


class UniversalStreamingControlView(View):
    """통합 스트리밍 제어 뷰"""
    
    def post(self, request, action):
        """스트리밍 제어 액션"""
        try:
            if action == 'create_session':
                return asyncio.run(self._create_session(request))
            elif action == 'start':
                return asyncio.run(self._start_streaming(request))
            elif action == 'stop':
                return asyncio.run(self._stop_streaming(request))
            elif action == 'process_data':
                return asyncio.run(self._process_data(request))
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Streaming control error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    def get(self, request, action):
        """스트리밍 상태 조회"""
        try:
            if action == 'status':
                session_id = request.GET.get('session_id')
                if session_id:
                    status = streaming_manager.get_session_status(session_id)
                    if status:
                        return JsonResponse({
                            'status': 'success',
                            'session_status': status
                        })
                    else:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Session not found'
                        }, status=404)
                else:
                    # 모든 활성 세션 조회
                    sessions = streaming_manager.list_active_sessions()
                    return JsonResponse({
                        'status': 'success',
                        'active_sessions': sessions,
                        'total_count': len(sessions)
                    })
            
            elif action == 'devices':
                devices = streaming_manager.get_supported_devices()
                return JsonResponse({
                    'status': 'success',
                    'supported_devices': devices
                })
            
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Streaming status error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    async def _create_session(self, request):
        """스트리밍 세션 생성"""
        try:
            data = json.loads(request.body) if request.body else {}
            
            device_type = data.get('device_type', 'meta_aria')  # 기본값
            session_name = data.get('session_name', f'Session_{device_type}')
            user_id = data.get('user_id', 'anonymous')
            streaming_config = data.get('streaming_config', {
                'streaming': {
                    'bootstrap_servers': 'localhost:9092'
                }
            })
            
            session_id = await streaming_manager.create_session(
                device_type=device_type,
                session_name=session_name,
                user_id=user_id,
                streaming_config=streaming_config
            )
            
            if session_id:
                return JsonResponse({
                    'status': 'success',
                    'session_id': session_id,
                    'device_type': device_type,
                    'message': f'Session created for {device_type}'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to create session'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    async def _start_streaming(self, request):
        """스트리밍 시작"""
        try:
            data = json.loads(request.body) if request.body else {}
            session_id = data.get('session_id')
            
            if not session_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'session_id is required'
                }, status=400)
            
            success = await streaming_manager.start_streaming(session_id)
            
            if success:
                return JsonResponse({
                    'status': 'success',
                    'session_id': session_id,
                    'message': 'Streaming started successfully'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to start streaming'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    async def _stop_streaming(self, request):
        """스트리밍 중지"""
        try:
            data = json.loads(request.body) if request.body else {}
            session_id = data.get('session_id')
            
            if not session_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'session_id is required'
                }, status=400)
            
            success = await streaming_manager.stop_streaming(session_id)
            
            if success:
                return JsonResponse({
                    'status': 'success',
                    'session_id': session_id,
                    'message': 'Streaming stopped successfully'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to stop streaming'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    async def _process_data(self, request):
        """데이터 처리"""
        try:
            data = json.loads(request.body) if request.body else {}
            
            session_id = data.get('session_id')
            sensor_type = data.get('sensor_type', 'camera_rgb')
            raw_data = data.get('raw_data', b'')
            timestamp_ns = data.get('timestamp_ns')
            
            if not session_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'session_id is required'
                }, status=400)
            
            # raw_data가 문자열이면 바이트로 변환
            if isinstance(raw_data, str):
                raw_data = raw_data.encode('utf-8')
            
            success = await streaming_manager.process_data(
                session_id=session_id,
                raw_data=raw_data,
                sensor_type=sensor_type,
                timestamp_ns=timestamp_ns
            )
            
            if success:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Data processed successfully'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to process data'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class XRDeviceManagementDashboard(View):
    """XR 기기 관리 대시보드"""
    
    def get(self, request):
        """XR 기기 관리 HTML 대시보드"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Universal XR Device Management</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 50%, #9b59b6 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .title {
            text-align: center;
            font-size: 2.5rem;
            margin: 20px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            color: #ecf0f1;
        }
        
        .subtitle {
            text-align: center;
            font-size: 1.2rem;
            margin: 10px 0 40px 0;
            color: #bdc3c7;
        }
        
        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin: 30px 0;
        }
        
        .device-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
        }
        
        .device-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            border-color: rgba(255,255,255,0.4);
        }
        
        .device-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .device-icon {
            font-size: 2.5rem;
            margin-right: 15px;
        }
        
        .device-title {
            font-size: 1.4rem;
            font-weight: bold;
            color: #ecf0f1;
        }
        
        .device-subtitle {
            font-size: 0.9rem;
            color: #bdc3c7;
            margin-top: 5px;
        }
        
        .device-status {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
            font-size: 0.9rem;
        }
        
        .status-item {
            display: flex;
            align-items: center;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-active { background: #2ecc71; }
        .status-inactive { background: #e74c3c; }
        .status-preparing { background: #f39c12; }
        
        .device-controls {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.3s ease;
            flex: 1;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white;
        }
        
        .btn-success {
            background: linear-gradient(45deg, #2ecc71, #27ae60);
            color: white;
        }
        
        .btn-danger {
            background: linear-gradient(45deg, #e74c3c, #c0392b);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .stats-panel {
            background: rgba(0,0,0,0.3);
            border-radius: 15px;
            padding: 25px;
            margin: 30px 0;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .stat-item {
            text-align: center;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #3498db;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #bdc3c7;
        }
        
        .session-log {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
        }
        
        .log-entry {
            margin: 5px 0;
            padding: 5px;
            border-left: 3px solid #3498db;
            padding-left: 10px;
        }
        
        .log-success { border-left-color: #2ecc71; color: #2ecc71; }
        .log-error { border-left-color: #e74c3c; color: #e74c3c; }
        .log-info { border-left-color: #3498db; color: #3498db; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="title">🚀 Universal XR Device Management</h1>
        <div class="subtitle">Meta Aria | Google Glass | Apple Vision | Microsoft HoloLens | Magic Leap</div>
        
        <div class="stats-panel">
            <h3 style="text-align: center; margin-bottom: 20px;">시스템 상태</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number" id="total-devices">0</div>
                    <div class="stat-label">지원 기기</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="active-sessions">0</div>
                    <div class="stat-label">활성 세션</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-parsers">0</div>
                    <div class="stat-label">지원 파서</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-protocols">0</div>
                    <div class="stat-label">스트리밍 프로토콜</div>
                </div>
            </div>
        </div>
        
        <div class="device-grid" id="device-grid">
            <!-- 기기 카드들이 여기에 동적으로 생성됩니다 -->
        </div>
        
        <div class="session-log" id="session-log">
            <h4 style="margin-top: 0; color: #ecf0f1;">세션 로그</h4>
            <div id="log-entries">
                <div class="log-entry log-info">[시작] Universal XR Device Management 시스템 초기화 중...</div>
            </div>
        </div>
    </div>
    
    <script>
        let deviceSessions = {};
        let updateInterval = null;
        
        window.onload = function() {
            addLog('시스템 로드 완료', 'success');
            initializeSystem();
            startPeriodicUpdates();
        };
        
        async function initializeSystem() {
            await loadDevices();
            await loadStats();
        }
        
        async function loadDevices() {
            try {
                const response = await fetch('/api/xr-devices/streaming/devices');
                const data = await response.json();
                
                if (data.status === 'success') {
                    renderDeviceCards(data.supported_devices);
                    document.getElementById('total-devices').textContent = data.supported_devices.length;
                    addLog(`${data.supported_devices.length}개 기기 로드 완료`, 'success');
                }
            } catch (error) {
                addLog(`기기 로드 실패: ${error.message}`, 'error');
            }
        }
        
        async function loadStats() {
            try {
                const [parsersResp, protocolsResp] = await Promise.all([
                    fetch('/api/xr-devices/supported_parsers/'),
                    fetch('/api/xr-devices/supported_protocols/')
                ]);
                
                const parsersData = await parsersResp.json();
                const protocolsData = await protocolsResp.json();
                
                document.getElementById('total-parsers').textContent = parsersData.supported_parsers?.length || 0;
                document.getElementById('total-protocols').textContent = protocolsData.supported_protocols?.length || 0;
                
            } catch (error) {
                addLog(`통계 로드 실패: ${error.message}`, 'error');
            }
        }
        
        function renderDeviceCards(devices) {
            const grid = document.getElementById('device-grid');
            grid.innerHTML = '';
            
            const deviceIcons = {
                'meta_aria': '🥽',
                'google_glass': '👓',
                'apple_vision': '🥽',
                'hololens': '🔬',
                'magic_leap': '✨',
                'nreal': '👁️',
                'vuzix': '📱'
            };
            
            devices.forEach(device => {
                const card = document.createElement('div');
                card.className = 'device-card';
                card.innerHTML = `
                    <div class="device-header">
                        <div class="device-icon">${deviceIcons[device.device_type] || '🔧'}</div>
                        <div>
                            <div class="device-title">${device.name}</div>
                            <div class="device-subtitle">${device.manufacturer} - ${device.device_type}</div>
                        </div>
                    </div>
                    <div class="device-status">
                        <div class="status-item">
                            <div class="status-dot status-inactive" id="status-${device.device_type}"></div>
                            <span id="status-text-${device.device_type}">대기중</span>
                        </div>
                        <div class="status-item">
                            <span id="session-info-${device.device_type}">세션 없음</span>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: #bdc3c7; margin: 10px 0;">
                        <div>프로토콜: ${device.preferred_protocol}</div>
                        <div>포맷: ${device.supported_formats.join(', ')}</div>
                    </div>
                    <div class="device-controls">
                        <button class="btn btn-primary" onclick="createSession('${device.device_type}')">
                            세션 생성
                        </button>
                        <button class="btn btn-success" onclick="startStreaming('${device.device_type}')" disabled>
                            스트리밍 시작
                        </button>
                        <button class="btn btn-danger" onclick="stopStreaming('${device.device_type}')" disabled>
                            중지
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
        }
        
        async function createSession(deviceType) {
            try {
                const response = await fetch('/api/xr-devices/streaming/create_session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        device_type: deviceType,
                        session_name: `${deviceType}_session_${new Date().getTime()}`,
                        user_id: 'dashboard_user',
                        streaming_config: {
                            streaming: {
                                bootstrap_servers: 'localhost:9092'
                            }
                        }
                    })
                });
                
                const data = await response.json();
                if (data.status === 'success') {
                    deviceSessions[deviceType] = data.session_id;
                    updateDeviceStatus(deviceType, 'preparing', `세션: ${data.session_id.substring(0, 8)}...`);
                    addLog(`${deviceType} 세션 생성 성공: ${data.session_id}`, 'success');
                    
                    // 버튼 상태 업데이트
                    const buttons = document.querySelectorAll(`[onclick*="${deviceType}"]`);
                    buttons[0].disabled = true;  // 세션 생성 버튼 비활성화
                    buttons[1].disabled = false; // 스트리밍 시작 버튼 활성화
                } else {
                    addLog(`${deviceType} 세션 생성 실패: ${data.message}`, 'error');
                }
            } catch (error) {
                addLog(`세션 생성 오류: ${error.message}`, 'error');
            }
        }
        
        async function startStreaming(deviceType) {
            const sessionId = deviceSessions[deviceType];
            if (!sessionId) {
                addLog(`${deviceType}: 세션이 없습니다`, 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/xr-devices/streaming/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
                
                const data = await response.json();
                if (data.status === 'success') {
                    updateDeviceStatus(deviceType, 'active', '스트리밍 중');
                    addLog(`${deviceType} 스트리밍 시작됨`, 'success');
                    
                    // 버튼 상태 업데이트
                    const buttons = document.querySelectorAll(`[onclick*="${deviceType}"]`);
                    buttons[1].disabled = true;  // 스트리밍 시작 버튼 비활성화
                    buttons[2].disabled = false; // 중지 버튼 활성화
                } else {
                    addLog(`${deviceType} 스트리밍 시작 실패: ${data.message}`, 'error');
                }
            } catch (error) {
                addLog(`스트리밍 시작 오류: ${error.message}`, 'error');
            }
        }
        
        async function stopStreaming(deviceType) {
            const sessionId = deviceSessions[deviceType];
            if (!sessionId) return;
            
            try {
                const response = await fetch('/api/xr-devices/streaming/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
                
                const data = await response.json();
                if (data.status === 'success') {
                    updateDeviceStatus(deviceType, 'inactive', '중지됨');
                    addLog(`${deviceType} 스트리밍 중지됨`, 'info');
                    
                    // 세션 정리 및 버튼 상태 초기화
                    delete deviceSessions[deviceType];
                    const buttons = document.querySelectorAll(`[onclick*="${deviceType}"]`);
                    buttons[0].disabled = false; // 세션 생성 버튼 활성화
                    buttons[1].disabled = true;  // 스트리밍 시작 버튼 비활성화
                    buttons[2].disabled = true;  // 중지 버튼 비활성화
                } else {
                    addLog(`${deviceType} 스트리밍 중지 실패: ${data.message}`, 'error');
                }
            } catch (error) {
                addLog(`스트리밍 중지 오류: ${error.message}`, 'error');
            }
        }
        
        function updateDeviceStatus(deviceType, status, text) {
            const statusDot = document.getElementById(`status-${deviceType}`);
            const statusText = document.getElementById(`status-text-${deviceType}`);
            const sessionInfo = document.getElementById(`session-info-${deviceType}`);
            
            if (statusDot && statusText) {
                statusDot.className = `status-dot status-${status}`;
                statusText.textContent = text;
            }
            
            if (sessionInfo && deviceSessions[deviceType]) {
                sessionInfo.textContent = `세션: ${deviceSessions[deviceType].substring(0, 8)}...`;
            }
        }
        
        function startPeriodicUpdates() {
            updateInterval = setInterval(async () => {
                await updateActiveSessions();
            }, 3000); // 3초마다 업데이트
        }
        
        async function updateActiveSessions() {
            try {
                const response = await fetch('/api/xr-devices/streaming/status');
                const data = await response.json();
                
                if (data.status === 'success') {
                    document.getElementById('active-sessions').textContent = data.active_sessions.length;
                }
            } catch (error) {
                // 오류는 로그에 남기지 않음 (너무 빈번함)
            }
        }
        
        function addLog(message, type = 'info') {
            const logEntries = document.getElementById('log-entries');
            const timestamp = new Date().toLocaleTimeString();
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry log-${type}`;
            logEntry.textContent = `[${timestamp}] ${message}`;
            
            logEntries.insertBefore(logEntry, logEntries.firstChild);
            
            // 로그 개수 제한
            const entries = logEntries.children;
            if (entries.length > 50) {
                logEntries.removeChild(entries[entries.length - 1]);
            }
        }
        
        // 페이지 종료 시 정리
        window.addEventListener('beforeunload', function() {
            if (updateInterval) clearInterval(updateInterval);
        });
    </script>
</body>
</html>'''
        
        return HttpResponse(html_template)