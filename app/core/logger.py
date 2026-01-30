# app/core/logger.py
import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings

# 로그 저장 경로: 실행 위치 기준 .logs/aquanova_server.log
# settings.BASE_DIR이 없다면 현재 작업 디렉토리(cwd)를 기준으로 합니다.
BASE_DIR = getattr(settings, "BASE_DIR", Path.cwd())
LOG_DIR = BASE_DIR / ".logs"
LOG_FILE = LOG_DIR / "aquanova_server.log"

def setup_logging() -> str:
    """
    Loguru를 사용하여 로그 설정을 초기화합니다.
    - Console: INFO 레벨 이상 (Launcher의 api.log에 기록됨)
    - File: DEBUG 레벨 이상 (aquanova_server.log에 통합 기록)
    """
    # 디렉토리 생성 보장
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 기존 핸들러 제거 (중복 방지)
    logger.remove()

    # 2. 콘솔 출력 설정 (표준 에러 스트림 사용)
    # 런처 스크립트가 이 출력을 잡아 api.log / worker.log에 기록합니다.
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )

    # 3. 파일 출력 설정 (핵심 통합 로그)
    # - 매일 자정(00:00)에 파일 회전
    # - 10일치 보관
    # - zip 압축 저장
    # - 비동기 안전(enqueue=True)
    logger.add(
        str(LOG_FILE),
        rotation="00:00",
        retention="10 days",
        compression="zip",
        level="DEBUG",
        enqueue=True,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} - {message}"
    )

    return str(LOG_FILE)