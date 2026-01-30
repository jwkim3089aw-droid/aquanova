# app/reports/templates/cover.py

from __future__ import annotations
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.core.config import settings
from .common import ensure_font, hex_color

def draw_cover(c, scenario_name: str, brand_primary: str | None = None):
    W, H = A4
    font = ensure_font()
    brand = hex_color(brand_primary or getattr(settings, "BRAND_PRIMARY", "#0a7cff"))

    # 타이틀 밴드
    c.setFillColor(brand)
    c.rect(0, H - 40*mm, W, 40*mm, fill=1, stroke=0)

    # 타이틀
    c.setFillColorRGB(1, 1, 1)
    c.setFont(font, 24)
    c.drawString(20*mm, H - 25*mm, "AquaNova RO Simulation Report")

    # 서브타이틀
    c.setFont(font, 12)
    c.drawString(20*mm, H - 35*mm, f"Scenario: {scenario_name}")

    # 날짜/ENV
    c.setFillColorRGB(0, 0, 0)
    c.setFont(font, 10)
    c.drawString(20*mm, 20*mm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.drawString(20*mm, 15*mm, f"Env: {getattr(settings, 'APP_ENV', 'local')}")

    c.showPage()
