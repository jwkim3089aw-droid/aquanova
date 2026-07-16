# app/core/logging/handlers.py
import sys
from loguru import logger

from app.core.logging.config import (
    LOG_DIR,
    LOG_FILE,
    CONSOLE_LOG_LEVEL,
    FILE_LOG_LEVEL,
    LOG_ROTATION,
    LOG_RETENTION,
    LOG_COMPRESSION,
)
from app.core.logging.formatters import CONSOLE_FORMAT, FILE_FORMAT


def setup_logging() -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()

    # 1. 콘솔 출력 핸들러
    logger.add(sys.stderr, level=CONSOLE_LOG_LEVEL, format=CONSOLE_FORMAT)

    # 2. 메인 서버 로그 파일 핸들러 (UI 로그 제외)
    logger.add(
        str(LOG_FILE),
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        level=FILE_LOG_LEVEL,
        enqueue=True,
        encoding="utf-8",
        format=FILE_FORMAT,
        delay=True,  # 💡 정석 패치: 실제 로그 기록 순간까지 파일 오픈(Lock) 지연
        filter=lambda record: record["extra"].get("log_type") != "ui",
    )

    # 3. 프론트엔드(UI) 전용 로그 파일 핸들러 (ui.log에 따로 저장)
    logger.add(
        str(LOG_DIR / "ui.log"),
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        level="INFO",
        enqueue=True,
        encoding="utf-8",
        format=FILE_FORMAT,
        delay=True,  # 💡 정석 패치: 멀티 프로세스 환경 파일 잠금 충돌 원천 차단
        filter=lambda record: record["extra"].get("log_type") == "ui",
    )

    return str(LOG_FILE)
