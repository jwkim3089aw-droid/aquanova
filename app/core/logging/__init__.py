# app/core/logging/__init__.py
from loguru import logger
from app.core.logging.handlers import setup_logging

__all__ = ["logger", "setup_logging"]
