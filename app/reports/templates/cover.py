# app/reports/templates/cover.py

from __future__ import annotations
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

from app.core.config import settings
from .common import ensure_font, hex_color

COLOR_PRIMARY = HexColor("#0F4C81")
COLOR_TEXT = HexColor("#333333")
COLOR_MUTED = HexColor("#757575")


def draw_cover(c, scenario_name: str, brand_primary: str | None = None):
    W, H = A4
    font = ensure_font()

    # 브랜드 컬러 파싱 (없으면 기본 명품 딥 블루 사용)
    brand_hex = brand_primary or getattr(settings, "BRAND_PRIMARY", None)
    brand = hex_color(brand_hex) if brand_hex else COLOR_PRIMARY

    # 1. 타이틀 밴드 (WAVE 스타일의 모던한 상단 헤더 밴드)
    band_h = 50 * mm
    c.setFillColor(brand)
    c.rect(0, H - band_h, W, band_h, fill=1, stroke=0)

    # 2. 메인 타이틀
    c.setFillColorRGB(1, 1, 1)
    c.setFont(font, 26)
    c.drawString(20 * mm, H - 25 * mm, "AquaNova RO Simulation Report")

    # 3. 서브타이틀 (시나리오 명)
    c.setFont(font, 14)
    c.drawString(20 * mm, H - 38 * mm, f"Scenario: {scenario_name}")

    # 4. 하단 메타데이터 (날짜 및 환경)
    c.setFillColor(COLOR_TEXT)
    c.setFont(font, 10)
    c.drawString(
        20 * mm, 25 * mm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    c.setFillColor(COLOR_MUTED)
    c.setFont(font, 9)
    env_str = str(getattr(settings, "APP_ENV", "local")).upper()
    c.drawString(20 * mm, 18 * mm, f"Environment: {env_str}")

    c.showPage()
