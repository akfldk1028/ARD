@echo off
REM Kafka 로컬 설치 스크립트 (Windows용)

echo === Apache Kafka 로컬 설치 (Windows) ===

REM 설치 디렉토리
set KAFKA_VERSION=3.6.0
set SCALA_VERSION=2.13
set KAFKA_ARCHIVE=kafka_%SCALA_VERSION%-%KAFKA_VERSION%.tgz
set KAFKA_URL=https://downloads.apache.org/kafka/%KAFKA_VERSION%/%KAFKA_ARCHIVE%
set KAFKA_DIR=%USERPROFILE%\kafka
set KAFKA_HOME=%KAFKA_DIR%\kafka_%SCALA_VERSION%-%KAFKA_VERSION%

REM 1. Java 확인
echo 1. Java 버전 확인...
java -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Java가 설치되어 있지 않습니다.
    echo Java 17+ 설치: https://adoptium.net/
    pause
    exit /b 1
)

java -version 2>&1 | findstr /i "version"
echo [OK] Java 확인됨

REM 2. 디렉토리 생성
echo.
echo 2. 디렉토리 생성...
if not exist "%KAFKA_DIR%" mkdir "%KAFKA_DIR%"
cd /d "%KAFKA_DIR%"

REM 3. Kafka 다운로드
echo.
echo 3. Kafka 다운로드...
if not exist "%KAFKA_ARCHIVE%" (
    echo 다운로드 중: %KAFKA_URL%
    echo 브라우저에서 다운로드 후 %KAFKA_DIR%에 저장하세요
    echo URL: %KAFKA_URL%
    pause
)

REM 4. 압축 해제
echo.
echo 4. 압축 해제...
echo tar 명령 사용 (Windows 10 이상)
tar -xzf "%KAFKA_ARCHIVE%"
echo [OK] 설치 위치: %KAFKA_HOME%

REM 5. 설정 파일 생성
echo.
echo 5. Windows용 설정 파일 생성...
cd /d "%KAFKA_HOME%"

REM server.properties 생성
(
echo # Kafka Server Properties for Windows
echo broker.id=0
echo listeners=PLAINTEXT://localhost:9092
echo advertised.listeners=PLAINTEXT://localhost:9092
echo log.dirs=%KAFKA_HOME%\logs
echo.
echo # KRaft 모드 설정
echo process.roles=broker,controller
echo node.id=1
echo controller.quorum.voters=1@localhost:9093
echo listeners=PLAINTEXT://localhost:9092,CONTROLLER://localhost:9093
echo inter.broker.listener.name=PLAINTEXT
echo controller.listener.names=CONTROLLER
echo.
echo # 로그 설정
echo log.retention.hours=24
echo log.segment.bytes=1073741824
echo.
echo # 성능 설정
echo num.network.threads=8
echo num.io.threads=8
echo socket.send.buffer.bytes=102400
echo socket.receive.buffer.bytes=102400
echo.
echo # 개발 설정
echo auto.create.topics.enable=true
echo delete.topic.enable=true
) > config\server-windows.properties

echo [OK] 설정 파일 생성됨

REM 6. 시작 스크립트 생성
echo.
echo 6. Windows 시작 스크립트 생성...

REM start-kafka-windows.bat
(
echo @echo off
echo echo === Kafka 시작 (Windows) ===
echo.
echo REM 클러스터 ID 생성
echo if not exist "%KAFKA_HOME%\.cluster_id" (
echo     echo 클러스터 ID 생성...
echo     for /f %%i in ('bin\windows\kafka-storage.bat random-uuid'^) do set KAFKA_CLUSTER_ID=%%i
echo     echo %%KAFKA_CLUSTER_ID%% ^> "%KAFKA_HOME%\.cluster_id"
echo     bin\windows\kafka-storage.bat format -t %%KAFKA_CLUSTER_ID%% -c config\server-windows.properties
echo ^)
echo.
echo echo Kafka 서버 시작...
echo bin\windows\kafka-server-start.bat config\server-windows.properties
) > start-kafka-windows.bat

REM stop-kafka-windows.bat
(
echo @echo off
echo echo Kafka 종료...
echo bin\windows\kafka-server-stop.bat
echo echo 완료
) > stop-kafka-windows.bat

REM create-topics-windows.bat
(
echo @echo off
echo echo === Project Aria 토픽 생성 ===
echo.
echo set BOOTSTRAP=localhost:9092
echo.
echo echo 메인 토픽 생성...
echo bin\windows\kafka-topics.bat --create --topic vrs-frames --bootstrap-server %%BOOTSTRAP%% --partitions 3 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic sensor-data --bootstrap-server %%BOOTSTRAP%% --partitions 3 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic image-metadata --bootstrap-server %%BOOTSTRAP%% --partitions 3 --replication-factor 1 --if-not-exists
echo.
echo echo 스트림 토픽 생성...
echo bin\windows\kafka-topics.bat --create --topic stream-camera-rgb --bootstrap-server %%BOOTSTRAP%% --partitions 2 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-camera-slam-left --bootstrap-server %%BOOTSTRAP%% --partitions 2 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-camera-slam-right --bootstrap-server %%BOOTSTRAP%% --partitions 2 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-camera-eyetracking --bootstrap-server %%BOOTSTRAP%% --partitions 2 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-imu-right --bootstrap-server %%BOOTSTRAP%% --partitions 1 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-imu-left --bootstrap-server %%BOOTSTRAP%% --partitions 1 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-magnetometer --bootstrap-server %%BOOTSTRAP%% --partitions 1 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-barometer --bootstrap-server %%BOOTSTRAP%% --partitions 1 --replication-factor 1 --if-not-exists
echo bin\windows\kafka-topics.bat --create --topic stream-microphone --bootstrap-server %%BOOTSTRAP%% --partitions 1 --replication-factor 1 --if-not-exists
echo.
echo echo 토픽 목록:
echo bin\windows\kafka-topics.bat --list --bootstrap-server %%BOOTSTRAP%%
) > create-topics-windows.bat

echo [OK] 스크립트 생성 완료

REM 7. 완료 메시지
echo.
echo === 설치 완료 ===
echo Kafka 홈: %KAFKA_HOME%
echo.
echo 사용법:
echo   1. cd %KAFKA_HOME%
echo   2. start-kafka-windows.bat     # Kafka 시작
echo   3. create-topics-windows.bat   # 토픽 생성 (새 창에서)
echo   4. stop-kafka-windows.bat      # Kafka 종료
echo.
echo Python kafka-python 설치:
echo   pip install kafka-python
echo.
pause