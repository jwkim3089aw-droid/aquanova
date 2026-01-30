# AquaNova

수처리 공정 시뮬레이터. 모듈형 엔진 + CLI + (옵션) FastAPI.

## 빠른 시작
```bash
uv venv && uv pip install -e .[science]
# 또는 
python - m venv .venv && source .venv/bin/activate
pip install -e .[science]

# 단일 RO 계산 예시 (CLI)
aquanova simulate ro examples/ro_minimal.json --pretty

# API 서버 실행
pip install -e. [fastapi]
uvicorn aquanova.api.app:app --reload

─────────────────────────────────────────────────────────────────────────────
8) 실행 순서 (요약)
─────────────────────────────────────────────────────────────────────────────
1) .env 복사: cp .env.example .env
2) DB 디렉토리 생성: mkdir -p ./.data
3) Alembic 초기화/리비전/업그레이드: 위 명령 3~5단계
alembic revision --autogenerate -m "init"
alembic upgrade head
4) 앱 실행: uvicorn app.main:app --reload --port 8003
5) 헬스 체크: GET http://localhost:8003/health
6) 시드: python scripts/smoke_seed.py


## Pytest
# 1. api_simulation_reports.py
pytest -v tests/test_api_simulation_reports.py
