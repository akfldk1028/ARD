"""
Kafka 환경 자동 감지 및 설정 유틸리티

Docker 환경과 로컬 환경을 자동으로 감지하여 
적절한 Kafka 브로커 주소를 반환합니다.
"""

import os
import socket
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def detect_kafka_environment() -> str:
    """
    현재 실행 환경을 감지하여 적절한 Kafka 브로커 주소를 반환
    
    감지 순서:
    1. 환경변수 KAFKA_BOOTSTRAP_SERVERS 확인
    2. Docker 환경 감지 (DOCKER_ENV, /.dockerenv 파일)
    3. Kafka 컨테이너 연결 테스트
    4. 기본값 반환
    
    Returns:
        str: Kafka 브로커 주소 (예: 'localhost:9092', 'ARD_KAFKA:9092')
    """
    
    # 1. 환경변수가 설정되어 있으면 우선 사용
    env_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
    if env_servers:
        logger.info(f"✅ 환경변수에서 Kafka 서버 발견: {env_servers}")
        return env_servers
    
    # 2. Docker 환경 감지
    docker_env = detect_docker_environment()
    if docker_env:
        # Docker 환경에서는 컨테이너 이름 사용
        kafka_server = 'ARD_KAFKA:9092'
        logger.info(f"🐳 Docker 환경 감지됨: {kafka_server}")
        return kafka_server
    
    # 3. 로컬 환경에서 Kafka 연결 테스트
    possible_servers = [
        'localhost:9092',      # 로컬 Kafka
        '127.0.0.1:9092',      # 로컬 IP
        'ARD_KAFKA:9092'       # Docker 컨테이너 (호스트에서 연결 가능한 경우)
    ]
    
    for server in possible_servers:
        if test_kafka_connection(server):
            logger.info(f"✅ Kafka 연결 테스트 성공: {server}")
            return server
    
    # 4. 기본값 (로컬 환경 가정)
    default_server = 'localhost:9092'
    logger.warning(f"⚠️ Kafka 서버 자동 감지 실패, 기본값 사용: {default_server}")
    return default_server

def detect_docker_environment() -> bool:
    """
    Docker 환경인지 감지
    
    Returns:
        bool: Docker 환경이면 True, 아니면 False
    """
    
    # 방법 1: 환경변수 확인
    if os.getenv('DOCKER_ENV') == 'true':
        return True
    
    # 방법 2: /.dockerenv 파일 존재 확인
    if os.path.exists('/.dockerenv'):
        return True
    
    # 방법 3: cgroup 정보 확인 (Linux에서 Docker 컨테이너 감지)
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass
    
    # 방법 4: Docker 컨테이너 목록에서 현재 호스트명 확인
    try:
        hostname = socket.gethostname()
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and hostname in result.stdout:
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    
    return False

def test_kafka_connection(server: str, timeout: int = 3) -> bool:
    """
    Kafka 서버 연결 테스트
    
    Args:
        server: Kafka 서버 주소 (예: 'localhost:9092')
        timeout: 연결 시도 시간 제한 (초)
    
    Returns:
        bool: 연결 가능하면 True, 아니면 False
    """
    try:
        host, port = server.split(':')
        port = int(port)
        
        # 소켓 연결 테스트
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        return result == 0
        
    except (ValueError, socket.error, OSError) as e:
        logger.debug(f"Kafka 연결 테스트 실패 {server}: {e}")
        return False

def get_optimal_kafka_config() -> dict:
    """
    현재 환경에 최적화된 Kafka 설정을 반환
    
    Returns:
        dict: Kafka 설정 딕셔너리
    """
    
    kafka_server = detect_kafka_environment()
    is_docker = detect_docker_environment()
    
    # Docker 환경과 로컬 환경에 따른 최적화 설정
    if is_docker:
        config = {
            'bootstrap_servers': kafka_server,
            'request_timeout_ms': 30000,      # Docker 네트워크 고려
            'connections_max_idle_ms': 300000,
            'reconnect_backoff_ms': 100,
            'batch_size': 16384,              # 컨테이너 환경에서 작은 배치
        }
    else:
        config = {
            'bootstrap_servers': kafka_server,
            'request_timeout_ms': 10000,      # 로컬에서 빠른 응답 기대
            'connections_max_idle_ms': 180000,
            'reconnect_backoff_ms': 50,
            'batch_size': 32768,              # 로컬에서 큰 배치 허용
        }
    
    logger.info(f"🎯 환경 최적화 Kafka 설정: {config}")
    return config

# 전역 캐시 (한 번 감지하면 재사용)
_kafka_server_cache: Optional[str] = None

def get_kafka_server(force_detect: bool = False) -> str:
    """
    캐시된 Kafka 서버 주소 반환 (성능 최적화)
    
    Args:
        force_detect: True면 캐시를 무시하고 재감지
        
    Returns:
        str: Kafka 서버 주소
    """
    global _kafka_server_cache
    
    if _kafka_server_cache is None or force_detect:
        _kafka_server_cache = detect_kafka_environment()
    
    return _kafka_server_cache

# 환경 정보 출력 (디버깅용)
def print_environment_info():
    """현재 환경 정보를 출력 (디버깅용)"""
    
    print("🔍 Kafka 환경 감지 정보:")
    print(f"   Docker 환경: {detect_docker_environment()}")
    print(f"   호스트명: {socket.gethostname()}")
    print(f"   DOCKER_ENV: {os.getenv('DOCKER_ENV')}")
    print(f"   KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS')}")
    print(f"   /.dockerenv 존재: {os.path.exists('/.dockerenv')}")
    print(f"   감지된 Kafka 서버: {get_kafka_server()}")
    
    # 연결 테스트 결과
    servers_to_test = ['localhost:9092', 'ARD_KAFKA:9092', '127.0.0.1:9092']
    print("📡 Kafka 연결 테스트:")
    for server in servers_to_test:
        status = "✅ 연결됨" if test_kafka_connection(server) else "❌ 연결 실패"
        print(f"   {server}: {status}")