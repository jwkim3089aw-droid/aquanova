# app/reports/templates/summary.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

from .common import ensure_font, fmt_num, draw_table, draw_hline

_STAGE_KEYS = ("stage", "stage_no", "stage_index", "stage_id", "idx")

# ✅ 표준: p_in_bar / p_out_bar, 레거시: pin_bar / pout_bar 등
_PIN_KEYS = (
    "p_in_bar",
    "pin_bar",
    "Pin_bar",
    "P_in_bar",
    "inlet_pressure_bar",
    "inlet_bar",
    "Pin",
    "p_in",
)
_POUT_KEYS = (
    "p_out_bar",
    "pout_bar",
    "Pout_bar",
    "P_out_bar",
    "outlet_pressure_bar",
    "outlet_bar",
    "Pout",
    "p_out",
)

# ✅ 표준: jw_avg_lmh, 레거시: flux_lmh 등
_JW_KEYS = (
    "jw_avg_lmh",
    "Jw_avg_Lmh",
    "Jw_avg_LMH",
    "flux_lmh",
    "Flux_LMH",
    "Jw_LMH",
    "avg_LMH",
    "Jw_avg",
    "jw_avg",
)

# ✅ 표준: sec_kwhm3, 레거시: sec_kwh_m3 등
_SEC_KEYS = (
    "sec_kwhm3",
    "sec_kwh_m3",
    "SEC_kWh_m3",
    "SEC_kWh_per_m3",
    "SEC_total",
    "sec_total",
)


def _get_first(d: Dict[str, Any], keys: Tuple[str, ...], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _rows_from_stage_metrics(
    stage_metrics: List[Dict[str, Any]] | None,
) -> List[List[str]]:
    if not stage_metrics:
        return []
    rows = []
    for m in stage_metrics:
        stg = _get_first(m, _STAGE_KEYS, None)
        pin = _get_first(m, _PIN_KEYS, None)
        pout = _get_first(m, _POUT_KEYS, None)
        jw = _get_first(m, _JW_KEYS, None)
        sec = _get_first(m, _SEC_KEYS, None)

        stage_lbl = (
            str(int(stg))
            if isinstance(stg, (int, float))
            else (str(stg) if stg else "—")
        )
        rows.append(
            (
                stg,
                [
                    stage_lbl,
                    fmt_num(pin, 2),
                    fmt_num(pout, 2),
                    fmt_num(jw, 1),
                    fmt_num(sec, 3),
                ],
            )
        )
    try:
        rows.sort(key=lambda x: (9999 if x[0] is None else float(x[0])))
    except Exception:
        pass
    return [r for _, r in rows]


def _rows_from_streams(streams: List[Dict[str, Any]] | None) -> List[List[str]]:
    if not streams:
        return []
    rows = []
    for s in streams:
        stg = _get_first(s, _STAGE_KEYS, None)
        pin = _get_first(s, _PIN_KEYS, None)
        pout = _get_first(s, _POUT_KEYS, None)
        jw = _get_first(s, _JW_KEYS, None)
        sec = _get_first(s, _SEC_KEYS, None)

        if stg is None and all(v is None for v in (pin, pout, jw, sec)):
            continue

        stage_lbl = (
            str(int(stg))
            if isinstance(stg, (int, float))
            else (str(stg) if stg else "—")
        )
        rows.append(
            (
                stg,
                [
                    stage_lbl,
                    fmt_num(pin, 2),
                    fmt_num(pout, 2),
                    fmt_num(jw, 1),
                    fmt_num(sec, 3),
                ],
            )
        )
    try:
        rows.sort(key=lambda x: (9999 if x[0] is None else float(x[0])))
    except Exception:
        pass
    return [r for _, r in rows]


def draw_system_summary(
    c: canvas.Canvas,
    streams: list[dict],
    kpi: dict,
    units: dict | None = None,
    stage_metrics: list[dict] | None = None,
):
    units = units or {"flow": "m3/h", "pressure": "bar", "flux": "LMH"}
    W, H = A4
    font = ensure_font()
    x0, x1 = 20 * mm, W - 20 * mm
    y = H - 25 * mm

    c.setFont(font, 16)
    c.setFillColor(black)
    c.drawString(x0, y, "System Summary")
    y -= 8
    draw_hline(c, x0, x1, y)
    y -= 10

    c.setFont(font, 10)
    k_map = [
        (
            "Total Recovery (%)",
            ("recovery_pct", "total_recovery_pct", "recovery", "RecoveryPct"),
        ),
        (
            f"Permeate Flow ({units.get('flow','m3/h')})",
            ("permeate_m3h", "permeate_flow_m3h", "Qp_m3h"),
        ),
        (
            f"Feed Flow ({units.get('flow','m3/h')})",
            ("feed_m3h", "feed_flow_m3h", "Qf_m3h"),
        ),
        (
            "SEC Total (kWh/m³)",
            ("sec_kwhm3", "sec_kwh_m3", "SEC_kWh_m3", "SEC_total", "sec_total"),
        ),
        (f"NDP ({units.get('pressure','bar')})", ("ndp_bar", "NDP_bar", "deltaP_bar")),
        (
            f"Flux ({units.get('flux','LMH')})",
            ("flux_lmh", "jw_avg_lmh", "Flux_LMH", "Jw_LMH_avg"),
        ),
    ]
    for label, keys in k_map:
        val = _get_first(kpi or {}, keys, None) if isinstance(kpi, dict) else None
        c.drawString(x0, y, f"- {label}: {fmt_num(val, 3)}")
        y -= 14
        if y < 30 * mm:
            c.showPage()
            y = H - 25 * mm
            c.setFont(font, 10)

    y -= 6

    c.setFont(font, 12)
    c.drawString(x0, y, "Per-Stage Metrics")
    y -= 6
    draw_hline(c, x0, x1, y)
    y -= 10

    headers = [
        "Stage",
        f"Pin ({units.get('pressure','bar')})",
        f"Pout ({units.get('pressure','bar')})",
        f"Jw avg ({units.get('flux','LMH')})",
        "SEC (kWh/m³)",
    ]

    rows = (
        _rows_from_stage_metrics(stage_metrics)
        if stage_metrics
        else _rows_from_streams(streams)
    )

    total_w = x1 - x0
    col_ws = [
        total_w * 0.14,
        total_w * 0.21,
        total_w * 0.21,
        total_w * 0.22,
        total_w * 0.22,
    ]

    if rows:
        approx_h = (1 + len(rows)) * 16 + 20
        if y - approx_h < 15 * mm:
            c.showPage()
            y = H - 25 * mm
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

    if y < 15 * mm:
        c.showPage()
