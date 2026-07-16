# app/reports/templates/summary.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from .common import ensure_font, fmt_num, draw_table, draw_hline

COLOR_PRIMARY = HexColor("#0F4C81")
COLOR_WARNING = HexColor("#D32F2F")
COLOR_TEXT = HexColor("#333333")
COLOR_LINE = HexColor("#CFD8DC")

_STAGE_KEYS = ("stage", "stage_no", "stage_index", "stage_id", "idx")
_TYPE_KEYS = ("module_type", "type", "module", "unit_op")
_PIN_KEYS = ("p_in_bar", "pin", "pin_bar", "inlet_pressure_bar", "inlet_bar", "p_in")
_POUT_KEYS = (
    "p_out_bar",
    "pout",
    "pout_bar",
    "outlet_pressure_bar",
    "outlet_bar",
    "p_out",
)
_JW_KEYS = ("flux_lmh", "jw_avg_lmh", "avg_flux_lmh", "Flux_LMH")
_SEC_KEYS = ("sec_kwhm3", "sec_kwh_m3", "SEC_kWh_m3", "SEC_total")


def _as_dict(m: Any) -> Dict[str, Any]:
    if isinstance(m, dict):
        return m
    for method in ("model_dump", "dict"):
        if hasattr(m, method):
            try:
                return getattr(m, method)()
            except Exception:
                pass
    try:
        return dict(m)
    except Exception:
        return {}


def _get_first(d: Dict[str, Any], keys: Tuple[str, ...], default: Any = None) -> Any:
    return next((d[k] for k in keys if d.get(k) is not None), default)


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _dp(pin: Any, pout: Any) -> float | None:
    a, b = _num(pin), _num(pout)
    return a - b if a is not None and b is not None else None


def _rows_from_stage_metrics(stage_metrics: List[Any] | None) -> List[List[Any]]:
    if not stage_metrics:
        return []

    rows = []
    for m0 in stage_metrics:
        m = _as_dict(m0)
        stg = _get_first(m, _STAGE_KEYS)
        mtype = _get_first(m, _TYPE_KEYS)
        pin = _get_first(m, _PIN_KEYS)
        pout = _get_first(m, _POUT_KEYS)
        jw = _get_first(m, _JW_KEYS)
        sec = _get_first(m, _SEC_KEYS)
        dp = _get_first(m, ("dp_bar", "delta_p_bar", "deltaP_bar"), _dp(pin, pout))

        stage_lbl = (
            str(int(stg))
            if isinstance(stg, (int, float))
            else (str(stg) if stg else "—")
        )
        type_lbl = (
            str(mtype).upper()
            if isinstance(mtype, str)
            else (str(mtype) if mtype else "—")
        )

        rows.append(
            (
                stg,
                [
                    stage_lbl,
                    type_lbl,
                    fmt_num(pin, 2),
                    fmt_num(pout, 2),
                    fmt_num(dp, 2),
                    fmt_num(jw, 1),
                    fmt_num(sec, 3),
                ],
            )
        )

    rows.sort(key=lambda x: (9999 if x[0] is None else _num(x[0]) or 9999))
    return [r for _, r in rows]


def _check_page_break(
    c: canvas.Canvas, y: float, H: float, required_space: float = 30 * mm
) -> float:
    if y < required_space:
        c.showPage()
        return H - 25 * mm
    return y


def _draw_section_header(
    c: canvas.Canvas,
    title: str,
    x0: float,
    x1: float,
    y: float,
    font: str,
    color: HexColor = COLOR_PRIMARY,
) -> float:
    y -= 10
    c.setFont(font, 12)
    c.setFillColor(color)
    c.drawString(x0, y, title)
    y -= 6
    c.setStrokeColor(COLOR_LINE)
    draw_hline(c, x0, x1, y)
    c.setFillColor(COLOR_TEXT)
    return y - 14


def draw_system_summary(
    c: canvas.Canvas,
    streams: list[dict],
    kpi: dict,
    units: dict | None = None,
    stage_metrics: list[Any] | None = None,
    chemistry: dict | None = None,
    warnings: list[dict] | None = None,
):
    units = units or {"flow": "m3/h", "pressure": "bar", "flux": "LMH"}
    W, H = A4
    font = ensure_font()
    x0, x1 = 20 * mm, W - 20 * mm
    y = H - 25 * mm

    kpi_dict = _as_dict(kpi)

    c.setFont(font, 16)
    c.setFillColor(COLOR_PRIMARY)
    c.drawString(x0, y, "System Summary")
    y -= 8
    c.setStrokeColor(COLOR_LINE)
    draw_hline(c, x0, x1, y)
    c.setFillColor(COLOR_TEXT)
    y -= 14

    c.setFont(font, 10)
    k_map = [
        ("Total Recovery (%)", ("recovery_pct", "total_recovery_pct")),
        (
            f"Permeate Flow ({units.get('flow','m3/h')})",
            ("permeate_m3h", "permeate_flow_m3h"),
        ),
        (f"Feed Flow ({units.get('flow','m3/h')})", ("feed_m3h", "feed_flow_m3h")),
        ("SEC Total (kWh/m³)", ("sec_kwhm3", "sec_kwh_m3")),
        (f"NDP ({units.get('pressure','bar')})", ("ndp_bar", "NDP_bar")),
        (f"Average Flux ({units.get('flux','LMH')})", ("flux_lmh", "jw_avg_lmh")),
    ]
    for label, keys in k_map:
        val = _get_first(kpi_dict, keys)
        c.drawString(x0, y, f"• {label}: {fmt_num(val, 3)}")
        y -= 14
        y = _check_page_break(c, y, H)

    mb = kpi_dict.get("mass_balance")
    if mb:
        y = _draw_section_header(
            c, "Mass & Salt Balance (Closure Check)", x0, x1, y, font
        )
        c.setFont(font, 10)
        c.drawString(
            x0,
            y,
            f"• Flow Closure Error: {fmt_num(mb.get('flow_error_pct'), 2)} % ({fmt_num(mb.get('flow_error_m3h'), 4)} m³/h)",
        )
        y -= 14
        c.drawString(
            x0,
            y,
            f"• Salt Closure Error: {fmt_num(mb.get('salt_error_pct'), 2)} % ({fmt_num(mb.get('salt_error_kgh'), 2)} kg/h)",
        )
        y -= 14
        c.drawString(
            x0, y, f"• System Rejection: {fmt_num(mb.get('system_rejection_pct'), 2)} %"
        )
        y -= 14
        y = _check_page_break(c, y, H)

    if warnings:
        y = _draw_section_header(
            c,
            f"System Warnings ({len(warnings)})",
            x0,
            x1,
            y,
            font,
            color=COLOR_WARNING,
        )
        c.setFont(font, 9)
        for w in warnings:
            w_dict = _as_dict(w)
            msg = w_dict.get("message", "Unknown Warning")
            stg = w_dict.get("stage", "Global")
            c.drawString(x0, y, f"[{stg}] {msg}")
            y -= 12
            y = _check_page_break(c, y, H)

    chem_dict = _as_dict(chemistry)
    if chem_dict and chem_dict.get("final_brine"):
        brine = _as_dict(chem_dict.get("final_brine"))
        y = _draw_section_header(
            c, "Brine Scaling & Solubility (Saturation %)", x0, x1, y, font
        )
        c.setFont(font, 10)
        scale_map = [
            ("LSI", "lsi", ""),
            ("Stiff & Davis (SDSI)", "s_dsi", ""),
            ("CaSO4 Saturation", "caso4_sat_pct", "%"),
            ("BaSO4 Saturation", "baso4_sat_pct", "%"),
            ("Silica (SiO2) Saturation", "sio2_sat_pct", "%"),
        ]
        for lbl, key, unit in scale_map:
            val = brine.get(key)
            if val is not None:
                c.drawString(x0, y, f"• {lbl}: {fmt_num(val, 2)} {unit}")
                y -= 14
                y = _check_page_break(c, y, H)

    y = _draw_section_header(c, "Per-Stage Metrics", x0, x1, y, font)
    headers = [
        "Stage",
        "Type",
        f"Pin ({units.get('pressure','bar')})",
        f"Pout ({units.get('pressure','bar')})",
        f"ΔP ({units.get('pressure','bar')})",
        f"Flux ({units.get('flux','LMH')})",
        "SEC (kWh/m³)",
    ]
    rows = _rows_from_stage_metrics(stage_metrics)
    total_w = x1 - x0
    col_ws = [
        total_w * 0.10,
        total_w * 0.12,
        total_w * 0.15,
        total_w * 0.15,
        total_w * 0.12,
        total_w * 0.16,
        total_w * 0.20,
    ]

    if rows:
        approx_h = (1 + len(rows)) * 16 + 20
        y = _check_page_break(c, y, H, required_space=approx_h)
        y = (
            draw_table(
                c,
                x0,
                y,
                col_headers=headers,
                rows=rows,
                col_widths=col_ws,
                row_h=16,
                text_font=font,
                text_size=9,
            )
            - 10
        )
    else:
        c.setFont(font, 9)
        c.drawString(x0, y, "No per-stage metrics were available.")
        y -= 10
