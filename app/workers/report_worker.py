# ./app/workers/report_worker.py

import os  # [ADDED] os.name 사용
import redis
from rq import Worker, Queue
from rq.worker import SimpleWorker
from loguru import logger

from app.core.config import settings
from app.core.fs import ensure_dirs

LISTEN_QUEUES = ["reports"]

def main():
    ensure_dirs()
    logger.info(f"Worker boot: queues={LISTEN_QUEUES}")
    logger.info(f"[worker] REDIS_URL={settings.REDIS_URL}")

    redis_conn = redis.from_url(settings.REDIS_URL)

    # 연결점검 ping
    try:
        logger.info(f"[worker] Redis ping: {redis_conn.ping()}")
    except Exception as e:
        logger.error(f"[worker] Redis ping failed: {e}")
        raise
    
    queues = [Queue(q, connection=redis_conn) for q in LISTEN_QUEUES]
    WorkerClass = SimpleWorker if os.name == "nt" else Worker
    worker = WorkerClass(queues, connection=redis_conn)
    worker.work(with_scheduler=True)

if __name__ == "__main__":
    main()
