# app\core\config.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, List, Union

from pydantic import Field, AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 환경 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,  # 환경변수 대소문자 구분을 위해 True 권장
    )

    # =========================================================
    # 1. 프로젝트 기본 정보 (Main.py에서 사용하는 필수 값)
    # =========================================================
    PROJECT_NAME: str = Field(
        default="AquaNova API", description="Swagger UI 등에 표시될 프로젝트 이름"
    )
    API_V1_STR: str = Field(default="/api/v1", description="API 버전 Prefix")

    APP_ENV: Literal["local", "dev", "test", "prod"] = Field(
        default="local",
        description="애플리케이션 실행 환경 (local/dev/test/prod)",
    )

    # =========================================================
    # 2. 보안 / CORS (프론트엔드 연동 필수)
    # =========================================================
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = Field(
        default=[], description="CORS 허용 도메인 목록 (예: http://localhost:3000)"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """문자열로 들어온 CORS 설정을 리스트로 변환"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # =========================================================
    # 3. 데이터베이스 / 인프라
    # =========================================================
    DB_URL: str = Field(
        default="sqlite:///./.data/aquanova.db",
        description="SQLAlchemy DB URL",
    )

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis / RQ 연결 URL",
    )

    # =========================================================
    # 4. 리포트 및 에셋 경로
    # =========================================================
    REPORT_DIR: str = Field(
        default="reports/outputs",
        description="PDF 등 리포트 출력 디렉터리 (상대/절대 경로 모두 허용)",
    )

    BRAND_PRIMARY: str = Field(
        default="#0a7cff",
        description="UI 및 리포트 기본 포인트 컬러 (hex)",
    )

    FONT_PATH: str = Field(
        default="./assets/fonts/NotoSans-Regular.ttf",
        description="리포트 렌더링에 사용할 TTF 폰트 경로",
    )

    # =========================================================
    # 5. Path 편의 프로퍼티 (Helper Properties)
    # =========================================================

    @property
    def REPORT_DIR_ABS(self) -> str:
        """리포트 출력 디렉터리 절대 경로 (str)."""
        return str(Path(self.REPORT_DIR).resolve())

    @property
    def report_dir_path(self) -> Path:
        """리포트 출력 디렉터리 절대 경로 (Path 객체)."""
        return Path(self.REPORT_DIR).resolve()

    @property
    def FONT_PATH_ABS(self) -> str:
        """폰트 파일 절대 경로 (str)."""
        return str(Path(self.FONT_PATH).resolve())

    @property
    def font_path(self) -> Path:
        """폰트 파일 절대 경로 (Path 객체)."""
        return Path(self.FONT_PATH).resolve()


@lru_cache
def get_settings() -> Settings:
    """FastAPI Depends용 싱글톤 Settings 인스턴스."""
    return Settings()


# 전역 설정 객체
settings = get_settings()
