# ./app/reports/templates/common.py

from __future__ import annotations
from typing import Iterable, Sequence, Any
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, lightgrey, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.core.config import settings

def ensure_font(name: str = "NotoSans", path: str | None = None) -> str:
    path = path or getattr(settings, "FONT_PATH", "./assets/fonts/NotoSans-Regular.ttf")
    try:
        if name not in pdfmetrics.getRegisteredFontNames() and Path(path).exists():
            pdfmetrics.registerFont(TTFont(name, path))
        return name if name in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    except Exception:
        return "Helvetica"
    
def hex_color(code: str, default: Color = black) -> Color:
    try:
        return HexColor(code)
    except Exception:
        return default
    
def fmt_num(v: Any, nd: int = 2, none: str = "—") -> str:
    try:
        x = float(v)
        if abs(x) >= 1000:
            return f"{x:,.{nd}f}"
        s = f"{x:.{nd}f}"

        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        return none
    
def draw_hline(c, x1: float, x2: float, y: float, w: float = 0.6):
    c.setLineWidth(w)
    c.line(x1, y, x2, y)

def draw_table(
        c,
        x: float,
        y: float,
        col_headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        col_widths: Sequence[float],
        row_h: float = 16,
        header_fill: Color = lightgrey,
        text_font: str = "Helvetica",
        text_size: int = 9,
) -> float:
    c.setFont(text_font, text_size)
    c.setFillColor(header_fill)
    c.rect(x, y - row_h, sum(col_widths), row_h, stroke=0, fill=1)
    c.setFillColor(black)

    cx = x
    for i, h in enumerate(col_headers):
        c.drawString(cx + 3, y - row_h + 3, str(h))
        cx += col_widths[i]

    ty = y - row_h
    for r in rows:
        ty -= row_h
        cx = x
        for i, cell in enumerate(r):
            c.drawString(cx + 3, ty + 3, str(cell))
            cx += col_widths[i]

        draw_hline(c, x, x + sum(col_widths), ty, w=0.4)

    return ty
