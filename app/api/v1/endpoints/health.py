# ./app/api/v1/health.py
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
import redis
from rq import Queue
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])

class HealthOut(BaseModel):
    status: str
    env: str
    redis_ping: bool | None = None
    reports_queue_len: int | None = None

@router.get("", response_model=dict)
def health_simple():
    # 기존 settings.ENV → settings.APP_ENV 로 수정
    return {"status": "ok", "env": getattr(settings, "APP_ENV", "local")}

@router.get("/extended", response_model=HealthOut)
def health_extended():
    try:
        r = redis.from_url(settings.REDIS_URL)
        ping = r.ping()
        q = Queue("reports", connection=r)
        # rq 버전별 호환
        try:
            qlen = q.count  # RQ>=1.10은 property
            if callable(qlen):  # 혹시 함수면 호출
                qlen = q.count()
        except Exception:
            try:
                qlen = q.count()
            except Exception:
                try:
                    qlen = len(q.job_ids)
                except Exception:
                    qlen = None
        return HealthOut(status="ok", env=getattr(settings, "APP_ENV", "local"),
                         redis_ping=ping, reports_queue_len=qlen)
    except Exception:
        return HealthOut(status="degraded", env=getattr(settings, "APP_ENV", "local"),
                         redis_ping=False, reports_queue_len=None)
