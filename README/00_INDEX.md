# ARD (Aria Real-time Data) System 문서 가이드

ARD 시스템의 완전한 이해와 사용을 위한 순차적 문서 가이드입니다.

## 📚 문서 읽기 순서

### 🏗️ **Phase 1: 시스템 이해 및 설치**

**[01_ARD_SYSTEM_ARCHITECTURE.md](01_ARD_SYSTEM_ARCHITECTURE.md)**
- ARD 시스템의 전체 아키텍처 이해
- 컴포넌트 간 관계 및 데이터 플로우
- **읽는 시점**: 가장 먼저 읽어야 할 문서

**[02_DOCKER_SETUP_GUIDE.md](02_DOCKER_SETUP_GUIDE.md)**
- Docker 환경 설정 및 실행 가이드
- 컨테이너 구성 및 네트워크 설정
- **읽는 시점**: 시스템 설치 전

### 🔧 **Phase 2: API 이해 및 활용**

**[03_API_STRUCTURE_REFERENCE.md](03_API_STRUCTURE_REFERENCE.md)**
- Django REST API 전체 구조
- 엔드포인트 설명 및 사용법
- **읽는 시점**: API 사용 전 필수

**[04_BINARY_STREAMING_GUIDE.md](04_BINARY_STREAMING_GUIDE.md)**
- 바이너리 스트리밍 아키텍처 이해
- 3-토픽 구조 및 압축 시스템
- **읽는 시점**: 실시간 데이터 처리 개발 시

**[05_REAL_IMAGE_STREAMING_API.md](05_REAL_IMAGE_STREAMING_API.md)**
- 실제 이미지 스트리밍 구현 세부사항
- 성능 최적화 및 압축 알고리즘
- **읽는 시점**: 이미지 처리 기능 개발 시

### 📊 **Phase 3: 데이터 구조 이해**

**[06_PROJECT_ARIA_DATA_OVERVIEW.md](06_PROJECT_ARIA_DATA_OVERVIEW.md)**
- Project Aria 데이터 개요
- VRS 파일 구조 및 MPS 데이터
- **읽는 시점**: Aria 데이터 처리 전

**[07_PROJECT_ARIA_DATA_FIELDS.md](07_PROJECT_ARIA_DATA_FIELDS.md)**
- 상세한 데이터 필드 레퍼런스
- 각 센서별 데이터 구조
- **읽는 시점**: 데이터 파싱 및 분석 시

### 🎮 **Phase 4: Unity 클라이언트 연동**

**[08_UNITY_INTEGRATION_GUIDE.md](08_UNITY_INTEGRATION_GUIDE.md)**
- Unity에서 ARD 시스템 연동 방법
- WebSocket 통신 및 실시간 데이터 수신
- **읽는 시점**: Unity 앱 개발 시

**[09_DOCKER_UNITY_SETUP.md](09_DOCKER_UNITY_SETUP.md)**
- Docker 환경에서 Unity 연동 설정
- 네트워크 구성 및 포트 매핑
- **읽는 시점**: Unity 개발 환경 구성 시

### 🛠️ **Phase 5: 개발 참고 자료**

**[10_DEVELOPMENT_NOTES.md](10_DEVELOPMENT_NOTES.md)**
- 개발 과정 중 주요 리팩토링 내용
- 클래스 기반 아키텍처로의 전환 과정
- **읽는 시점**: 코드 구조 이해 시

**[11_ARDUnityClient.cs](11_ARDUnityClient.cs)**
- Unity 클라이언트 C# 코드 예제
- 실제 구현 가능한 완전한 코드
- **읽는 시점**: Unity 개발 구현 시

---

## 🎯 **사용자별 추천 읽기 경로**

### 👨‍💻 **백엔드 개발자**
```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 10
```

### 🎮 **Unity 개발자**
```
01 → 02 → 03 → 06 → 08 → 09 → 11
```

### 📊 **데이터 분석가**
```
01 → 06 → 07 → 03 → 04 → 05
```

### 🏗️ **시스템 관리자**
```
01 → 02 → 09 → 10
```

### 🚀 **프로젝트 매니저**
```
01 → 02 → 03 → 08 → 10
```

---

## 📋 **문서별 주요 내용 요약**

| 번호 | 문서명 | 주요 내용 | 난이도 | 예상 시간 |
|-----|--------|-----------|--------|----------|
| 01 | 시스템 아키텍처 | 전체 구조, 컴포넌트 관계 | ⭐⭐ | 15분 |
| 02 | Docker 설치 | 환경 구성, 컨테이너 실행 | ⭐⭐ | 10분 |
| 03 | API 구조 | REST API, 엔드포인트 | ⭐⭐⭐ | 20분 |
| 04 | 바이너리 스트리밍 | 실시간 데이터 처리 | ⭐⭐⭐⭐ | 25분 |
| 05 | 이미지 스트리밍 | 이미지 압축, 최적화 | ⭐⭐⭐⭐ | 20분 |
| 06 | Aria 데이터 개요 | VRS, MPS 데이터 구조 | ⭐⭐⭐ | 15분 |
| 07 | 데이터 필드 | 상세 필드 레퍼런스 | ⭐⭐⭐⭐⭐ | 30분 |
| 08 | Unity 연동 | Unity 클라이언트 개발 | ⭐⭐⭐⭐ | 25분 |
| 09 | Docker Unity | Docker 환경 Unity 설정 | ⭐⭐⭐ | 15분 |
| 10 | 개발 노트 | 리팩토링, 아키텍처 변화 | ⭐⭐ | 10분 |
| 11 | Unity 코드 | C# 구현 예제 | ⭐⭐⭐ | 실습 |

---

## 🔗 **추가 리소스**

### 외부 문서
- [Project Aria 공식 문서](https://facebookresearch.github.io/projectaria_tools/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Apache Kafka 문서](https://kafka.apache.org/documentation/)
- [Unity WebSocket](https://docs.unity3d.com/Manual/webgl-networking.html)

### 메인 문서
- **[../README.md](../README.md)**: 빠른 시작 가이드 및 설치 방법
- **[../CLAUDE.md](../CLAUDE.md)**: 개발 환경 및 명령어 레퍼런스

---

## 📞 **지원 및 문의**

- **Issues**: GitHub Issues를 통한 버그 리포트
- **개발 가이드**: CLAUDE.md 참조
- **API 테스트**: `bash test-api.sh` 실행
- **실시간 로그**: `docker logs ARD-BACKEND -f`

---

**📌 팁**: 각 문서는 독립적으로 읽을 수 있지만, 순서대로 읽으면 전체적인 이해도가 크게 향상됩니다.

**⚡ 빠른 시작**: 바로 시작하고 싶다면 `01 → 02 → bash quick-start.sh` 순서로 진행하세요!