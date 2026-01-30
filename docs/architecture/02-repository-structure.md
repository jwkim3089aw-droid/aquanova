# 02. Repository Structure

AquaNova 프로젝트는 **FastAPI 정석 아키텍처**와 **로컬 배포 환경**을 기반으로 한 모노레포 구조를 채택합니다.

```bash
📦 aquanova/
├── app/                        # FastAPI 애플리케이션 모듈
│   ├── api/                    # 라우터 (도메인별 분리)
│   │   ├── v1/
│   │   │   ├── simulation.py   # 시뮬레이터 API
│   │   │   ├── reports.py      # PDF 리포트 API
│   │   │   └── auth.py         # 인증 API (JWT Cookie)
│   ├── core/                   # 핵심 설정 및 보안
│   │   ├── config.py           # pydantic-settings 환경설정
│   │   ├── security.py         # JWT, 쿠키 처리
│   │   └── dependencies.py     # Depends DI 정의
│   ├── db/                     # SQLAlchemy 2.0 ORM
│   │   ├── base.py             # Declarative Base
│   │   ├── session.py          # 세션/엔진 관리
│   │   └── models/             # 도메인별 모델
│   ├── services/               # 비즈니스 로직 계층
│   │   ├── simulation.py
│   │   ├── reporting.py
│   │   └── auth_service.py
│   ├── workers/                # Redis RQ 기반 워커
│   │   └── report_worker.py
│   ├── utils/                  # 공통 유틸리티
│   └── main.py                 # FastAPI 엔트리포인트
│
├── reports/                    # PDF 템플릿 및 출력물
│   ├── templates/              # ReportLab 기반 템플릿 (로고/브랜딩 포함)
│   │   ├── cover.py            # 표지
│   │   ├── summary.py          # 시스템 요약 표
│   │   ├── streams.py          # 스트림별 표
│   │   ├── kpi.py              # KPI 요약 및 그래프
│   │   └── diagram.py          # 다이어그램 축소본
│   └── outputs/                # 생성된 PDF 파일 저장 위치
│
├── tests/                      # Pytest 기반 테스트
│   ├── api/
│   ├── services/
│   └── e2e/
│
├── scripts/                    # 유틸리티 스크립트 (DB 마이그레이션, 초기화 등)
│
├── docker/                     # 로컬 배포용 Dockerfile/Compose
│   ├── docker-compose.yml
│   └── Dockerfile
│
├── docs/                       # 문서화 (요구사항/설계서 포함)
│   ├── 01-requirements.md
│   ├── 02-repository-structure.md   # (현재 파일)
│   └── 03-architecture.md
│
├── .env.example                # 환경변수 예시
├── pyproject.toml              # Poetry 설정
├── README.md
└── Makefile                    # 빌드/테스트/배포 단축 명령
```

---

## 주요 특징

- **FastAPI 정석 구조**: 모듈형 라우터와 Depends 기반 DI로 유지보수성과 확장성 강화
- **DB 계층**: SQLAlchemy 2.0 Typed ORM 및 Alembic 마이그레이션 지원
- **비동기 워크플로우**: Redis RQ 워커를 통한 PDF 보고서 비동기 처리
- **문서화**: `docs/` 폴더에 요구사항 및 설계 문서 포함
- **PDF 보고서**: `reports/templates`에서 브랜딩, 폰트, 레이아웃 일원 관리

---

이 구조는 개발, 테스트, 배포, 문서화, 보고서 생성 등 AquaNova의 모든 핵심 워크플로우를 일관되게 지원합니다.