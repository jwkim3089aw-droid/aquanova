# app/reports/templates/summary.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, red, darkblue
from reportlab.pdfgen import canvas

from .common import ensure_font, fmt_num, draw_table, draw_hline

# --- robust helpers ----------------------------------------------------------
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
    if hasattr(m, "model_dump"):  # Pydantic V2
        try:
            return m.model_dump()
        except:
            pass
    if hasattr(m, "dict"):  # Pydantic V1
        try:
            return m.dict()
        except:
            pass
    try:
        return dict(m)
    except:
        return {}


def _get_first(d: Dict[str, Any], keys: Tuple[str, ...], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except:
        return None


def _dp(pin: Any, pout: Any) -> float | None:
    a, b = _num(pin), _num(pout)
    if a is None or b is None:
        return None
    return a - b


def _rows_from_stage_metrics(stage_metrics: List[Any] | None) -> List[List[str]]:
    if not stage_metrics:
        return []
    rows = []
    for m0 in stage_metrics:
        m = _as_dict(m0)
        stg = _get_first(m, _STAGE_KEYS, None)
        mtype = _get_first(m, _TYPE_KEYS, None)
        pin = _get_first(m, _PIN_KEYS, None)
        pout = _get_first(m, _POUT_KEYS, None)
        jw = _get_first(m, _JW_KEYS, None)
        sec = _get_first(m, _SEC_KEYS, None)
        dp = _get_first(m, ("dp_bar", "delta_p_bar", "deltaP_bar"), None)
        dp = dp if dp is not None else _dp(pin, pout)

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

    try:
        rows.sort(key=lambda x: (9999 if x[0] is None else float(x[0])))
    except:
        pass
    return [r for _, r in rows]


def _check_page_break(
    c: canvas.Canvas, y: float, H: float, required_space: float = 30 * mm
) -> float:
    if y < required_space:
        c.showPage()
        return H - 25 * mm
    return y


# --- public ------------------------------------------------------------------
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

    # ==========================================
    # 1. System Summary (WAVE Style Overview)
    # ==========================================
    c.setFont(font, 16)
    c.setFillColor(darkblue)
    c.drawString(x0, y, "System Summary")
    c.setFillColor(black)
    y -= 8
    draw_hline(c, x0, x1, y)
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
        val = _get_first(kpi_dict, keys, None)
        c.drawString(x0, y, f"- {label}: {fmt_num(val, 3)}")
        y -= 14
        y = _check_page_break(c, y, H)

    # ==========================================
    # 2. Mass & Salt Balance (WAVE Parity)
    # ==========================================
    mb = kpi_dict.get("mass_balance")
    if mb:
        y -= 10
        c.setFont(font, 12)
        c.setFillColor(darkblue)
        c.drawString(x0, y, "Mass & Salt Balance (Closure Check)")
        c.setFillColor(black)
        y -= 6
        draw_hline(c, x0, x1, y)
        y -= 14

        c.setFont(font, 10)
        c.drawString(
            x0,
            y,
            f"- Flow Closure Error: {fmt_num(mb.get('flow_error_pct'), 2)} % ({fmt_num(mb.get('flow_error_m3h'), 4)} m³/h)",
        )
        y -= 14
        c.drawString(
            x0,
            y,
            f"- Salt Closure Error: {fmt_num(mb.get('salt_error_pct'), 2)} % ({fmt_num(mb.get('salt_error_kgh'), 2)} kg/h)",
        )
        y -= 14
        c.drawString(
            x0, y, f"- System Rejection: {fmt_num(mb.get('system_rejection_pct'), 2)} %"
        )
        y -= 14
        y = _check_page_break(c, y, H)

    # ==========================================
    # 3. System Warnings
    # ==========================================
    if warnings:
        y -= 10
        c.setFont(font, 12)
        c.setFillColor(red)
        c.drawString(x0, y, f"System Warnings ({len(warnings)})")
        c.setFillColor(black)
        y -= 6
        draw_hline(c, x0, x1, y)
        y -= 14

        c.setFont(font, 9)
        for w in warnings:
            w_dict = _as_dict(w)
            msg = w_dict.get("message", "Unknown Warning")
            stg = w_dict.get("stage", "Global")
            c.drawString(x0, y, f"[{stg}] {msg}")
            y -= 12
            y = _check_page_break(c, y, H)

    # ==========================================
    # 4. Brine Scaling & Solubility (Chemistry)
    # ==========================================
    if chemistry and chemistry.get("final_brine"):
        brine = chemistry.get("final_brine")
        y -= 10
        c.setFont(font, 12)
        c.setFillColor(darkblue)
        c.drawString(x0, y, "Brine Scaling & Solubility (Saturation %)")
        c.setFillColor(black)
        y -= 6
        draw_hline(c, x0, x1, y)
        y -= 14

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
                c.drawString(x0, y, f"- {lbl}: {fmt_num(val, 2)} {unit}")
                y -= 14
                y = _check_page_break(c, y, H)

    # ==========================================
    # 5. Per-Stage Metrics Table
    # ==========================================
    y -= 10
    c.setFont(font, 12)
    c.setFillColor(darkblue)
    c.drawString(x0, y, "Per-Stage Metrics")
    c.setFillColor(black)
    y -= 6
    draw_hline(c, x0, x1, y)
    y -= 14

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
