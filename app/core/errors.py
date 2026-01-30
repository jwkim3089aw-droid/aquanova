# ./app/core/errors.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

__all__ = ["register_exception_handlers"]


def _build_problem_response(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: Any | None = None,
) -> JSONResponse:
    """애플리케이션 공통 에러 응답 포맷 생성."""
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if detail is not None:
        payload["detail"] = detail

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={
            "Content-Type": "application/problem+json",
        },
    )


def _convert_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """FastAPI RequestValidationError → 단순화된 에러 리스트로 변환."""
    return [
        {
            "loc": e.get("loc"),
            "msg": e.get("msg"),
            "type": e.get("type"),
        }
        for e in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    """
    FastAPI 앱 전역 예외 핸들러 등록.

    - RequestValidationError: 입력 검증 실패(422)
    - HTTPException / StarletteHTTPException: 일반 HTTP 에러(404 등)
    - Exception: 그 외 모든 예외(500)
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # type: ignore[unused-ignore]
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """요청 바디/쿼리/패스 파라미터 검증 실패 핸들러."""
        errors = _convert_validation_errors(exc)

        logger.info(
            "Request validation failed: %s %s (%d errors)",
            request.method,
            request.url.path,
            len(errors),
        )

        return _build_problem_response(
            status_code=422,
            code="INVALID_INPUT",
            message="입력 검증 실패",
            detail=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """
        FastAPI / Starlette HTTPException 공통 핸들러.

        예: 404 Not Found, 401 Unauthorized 등
        """
        logger.warning(
            "HTTPException: %s %s -> %d (%s)",
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail,
        )

        # 필요하면 status_code별 code를 세분화해도 됨 (e.g. NOT_FOUND, UNAUTHORIZED 등)
        return _build_problem_response(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=str(exc.detail) if exc.detail else "HTTP error",
            detail=None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        최상위 핸들러: 예상치 못한 모든 예외를 500으로 포장.
        """
        logger.exception(
            "Unhandled exception: %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )

        return _build_problem_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="알 수 없는 오류가 발생했습니다.",
            detail=None,
        )
