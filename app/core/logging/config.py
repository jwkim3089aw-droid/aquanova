# app/core/logging/config.py
from pathlib import Path
from app.core.config import settings

BASE_DIR = getattr(settings, "BASE_DIR", Path.cwd())
LOG_DIR = BASE_DIR / ".logs"
LOG_FILE = LOG_DIR / "aquanova_server.log"

CONSOLE_LOG_LEVEL = "INFO"
FILE_LOG_LEVEL = "DEBUG"

LOG_ROTATION = "00:00"
LOG_RETENTION = "10 days"
LOG_COMPRESSION = "zip"
