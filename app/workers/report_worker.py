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
    raw = os.getenv("AQUANOVA_WORKER_QUEUES", "").strip()
    return [q.strip() for q in raw.split(",") if q.strip()] or DEFAULT_QUEUES


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    ensure_dirs()

    queues = _parse_queues()
    burst = _bool_env("AQUANOVA_WORKER_BURST", "0")
    with_scheduler = _bool_env("AQUANOVA_RQ_WITH_SCHEDULER", "1")

    logger.info(
        f"[worker] Booting... queues={queues}, burst={burst}, scheduler={with_scheduler}"
    )
    logger.info(
        f"[worker] Env: platform={os.name}, python={sys.version.split()[0]}, cwd={os.getcwd()}"
    )

    # Redis Connection & Health Check
    try:
        redis_conn = redis.from_url(settings.REDIS_URL)
        if not redis_conn.ping():
            raise RuntimeError("Redis ping returned False")
        logger.info("[worker] Redis connection established successfully.")
    except Exception as e:
        logger.error(f"[worker] Redis connection failed: {e}")
        return 1  # 예외를 날리기보다 안전하게 종료 코드를 반환하여 오케스트레이터(Docker 등)가 재시작을 관리하도록 위임

    q_objs = [Queue(q, connection=redis_conn) for q in queues]

    # Windows(nt) 환경에서는 멀티프로세싱 포크 이슈로 인해 SimpleWorker 사용
    worker_class = SimpleWorker if os.name == "nt" else Worker
    worker = worker_class(q_objs, connection=redis_conn)

    worker.work(with_scheduler=with_scheduler, burst=burst)

    return 0


if __name__ == "__main__":
    sys.exit(main())
