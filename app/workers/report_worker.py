# app/workers/report_worker.py
from __future__ import annotations

import os
import sys

import redis
from loguru import logger
from rq import Queue, Worker
from rq.worker import SimpleWorker

from app.core.config import settings
from app.core.fs import ensure_dirs

DEFAULT_QUEUES = ["reports"]


def _parse_queues() -> list[str]:
    """
    AQUANOVA_WORKER_QUEUES="reports,high,low" 형태 지원.
    """
    raw = os.getenv("AQUANOVA_WORKER_QUEUES", "").strip()
    if not raw:
        return DEFAULT_QUEUES
    qs = [q.strip() for q in raw.split(",") if q.strip()]
    return qs or DEFAULT_QUEUES


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "y", "on")


def main() -> int:
    ensure_dirs()

    queues = _parse_queues()
    burst = _bool_env("AQUANOVA_WORKER_BURST", "0")
    with_scheduler = _bool_env("AQUANOVA_RQ_WITH_SCHEDULER", "1")

    logger.info(f"[worker] boot queues={queues}")
    logger.info(f"[worker] REDIS_URL={settings.REDIS_URL}")
    logger.info(f"[worker] burst={burst} with_scheduler={with_scheduler}")
    logger.info(f"[worker] platform={os.name} python={sys.version.split()[0]}")
    logger.info(f"[worker] cwd={os.getcwd()}")

    redis_conn = redis.from_url(settings.REDIS_URL)

    # 연결 점검
    try:
        ok = redis_conn.ping()
        logger.info(f"[worker] Redis ping: {ok}")
        if not ok:
            raise RuntimeError("Redis ping returned False")
    except Exception as e:
        logger.error(f"[worker] Redis ping failed: {e}")
        raise

    q_objs = [Queue(q, connection=redis_conn) for q in queues]

    # Windows(nt)는 SimpleWorker가 더 안정적인 케이스가 많음
    WorkerClass = SimpleWorker if os.name == "nt" else Worker

    worker = WorkerClass(q_objs, connection=redis_conn)
    worker.work(with_scheduler=with_scheduler, burst=burst)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
