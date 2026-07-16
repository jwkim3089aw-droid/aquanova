# app/api/v1/endpoints/logs.py
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Any, Optional
from app.core.logging import logger

router = APIRouter()

# UI 로그 전용 로거 (handlers.py의 필터와 매칭되는 태그 부착)
ui_logger = logger.bind(log_type="ui")


class UILogCreate(BaseModel):
    level: str
    message: str
    data: Optional[Any] = None
    url: Optional[str] = None


@router.post("/ui", status_code=204)
async def receive_ui_log(log_data: UILogCreate, request: Request):
    """프론트엔드에서 발생하는 로그(에러, 경고 등)를 수집합니다."""
    # 클라이언트 IP 추출 (리버스 프록시 환경 고려)
    client_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else "unknown"
    )

    log_msg = f"[IP: {client_ip}] [URL: {log_data.url}] {log_data.message}"

    # 딕셔너리나 객체 데이터가 넘어왔을 경우 문자열로 변환
    data_str = f" | DATA: {log_data.data}" if log_data.data else ""
    final_msg = log_msg + data_str

    if log_data.level.upper() == "ERROR":
        ui_logger.error(final_msg)
    elif log_data.level.upper() == "WARN":
        ui_logger.warning(final_msg)
    else:
        ui_logger.info(final_msg)
