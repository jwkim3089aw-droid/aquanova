# app/reports/templates/stage_metrics.py
from __future__ import annotations
from typing import List, Dict, Any, Iterable, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

from .common import ensure_font, fmt_num, draw_table, draw_hline

# --- Corporate Design Palette ---
COLOR_PRIMARY = HexColor("#0F4C81")
COLOR_TEXT = HexColor("#333333")
COLOR_LINE = HexColor("#CFD8DC")

# 차트용 데이터 시리즈 색상 (딥블루, 청록, 다크그레이, 주황)
CHART_COLORS = [
    HexColor("#0F4C81"),
    HexColor("#26A69A"),
    HexColor("#546E7A"),
    HexColor("#F57C00"),
]


def _u(units: Dict[str, str] | None, key: str, default: str) -> str:
    if isinstance(units, dict):
        v = units.get(key)
        return v if isinstance(v, str) and v.strip() else default
    return default


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


def _get_val(m: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    return next((m[k] for k in keys if m.get(k) is not None), default)


def _series_bounds(values: Iterable[float | None]) -> Tuple[float, float]:
    vs = [float(v) for v in values if isinstance(v, (int, float))]
    if not vs:
        return (0.0, 1.0)
    lo, hi = min(vs), max(vs)
    if hi == lo:
        return (lo - abs(lo) * 0.05 - 1e-6, hi + abs(hi) * 0.05 + 1e-6)
    span = hi - lo
    return (lo - 0.05 * span, hi + 0.05 * span)


def _plot_lines(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    xs: List[float],
    series: List[Tuple[List[float | None], str]],
    y_unit: str,
    title: str,
):
    font = ensure_font()

    # 차트 배경 및 외곽선
    c.setLineWidth(0.8)
    c.setStrokeColor(COLOR_LINE)
    c.rect(x, y, w, h, stroke=1, fill=0)

    # 차트 타이틀 및 단위
    c.setFont(font, 10)
    c.setFillColor(COLOR_PRIMARY)
    c.drawString(x, y + h + 2 * mm, title)
    c.setFont(font, 8)
    c.setFillColor(HexColor("#9E9E9E"))
    c.drawRightString(x + w, y - 3, f"[{y_unit}]")

    all_vals = [float(v) for ys, _ in series for v in ys if isinstance(v, (int, float))]
    if not all_vals:
        c.setFont(font, 8)
        c.setFillColor(COLOR_TEXT)
        c.drawString(x + 3, y + h / 2, "No data")
        return

    y_min, y_max = _series_bounds(all_vals)

    def y_to_py(v: float) -> float:
        return y + h / 2 if y_max == y_min else y + ((v - y_min) / (y_max - y_min)) * h

    # Y축 Grid Lines
    c.setLineWidth(0.3)
    c.setStrokeColor(HexColor("#EEEEEE"))
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        gy = y + frac * h
        c.line(x, gy, x + w, gy)
        c.setFont(font, 7)
        c.setFillColor(HexColor("#757575"))
        c.drawRightString(x - 2, gy - 2, fmt_num(y_min + frac * (y_max - y_min), 2))

    n = len(xs)
    dash_styles = [None, [2, 2], None, [1, 2]]

    # 다중 스테이지 Plot
    if n >= 2:
        x_coords = [x + (i / (n - 1)) * w for i in range(n)]
        for idx, (ys, label) in enumerate(series):
            pts = [
                (x_coords[i], y_to_py(float(v))) if v is not None else None
                for i, v in enumerate(ys)
            ]

            col = CHART_COLORS[idx % len(CHART_COLORS)]
            c.setLineWidth(1.2 if idx == 0 else 0.8)
            c.setStrokeColor(col)
            c.setDash(dash_styles[idx % len(dash_styles)] or [])

            last = None
            for p in pts:
                if p is not None and last is not None:
                    c.line(last[0], last[1], p[0], p[1])
                last = p

            # 범례 (Legend)
            c.setFont(font, 7)
            c.setFillColor(col)
            c.drawString(x + 4 + idx * (w * 0.25), y + h + 1.5 * mm, label)

        # X축 Labels
        c.setFont(font, 7)
        c.setFillColor(COLOR_TEXT)
        for i in range(n):
            c.drawCentredString(
                x_coords[i],
                y - 10,
                str(int(xs[i])) if isinstance(xs[i], (int, float)) else str(xs[i]),
            )

    # 단일 스테이지 Plot (Point)
    else:
        px = x + w / 2
        for idx, (ys, label) in enumerate(series):
            v = next((float(v) for v in ys if isinstance(v, (int, float))), None)
            if v is None:
                continue

            py = y_to_py(v)
            col = CHART_COLORS[idx % len(CHART_COLORS)]
            c.setFillColor(col)
            c.setStrokeColor(col)
            c.circle(px, py, 2.5, stroke=1, fill=1)

            c.setFont(font, 7)
            c.drawString(
                x + 4 + idx * (w * 0.25), y + h + 1.5 * mm, f"{label} • {fmt_num(v, 2)}"
            )

        c.setFont(font, 7)
        c.setFillColor(COLOR_TEXT)
        c.drawCentredString(
            px,
            y - 10,
            str(int(xs[0])) if isinstance(xs[0], (int, float)) else str(xs[0]),
        )

    c.setDash([])  # 점선 상태 초기화


def draw_stage_metrics_page(
    c, stage_metrics: List[Any] | None, units: Dict[str, str] | None = None
) -> None:
    W, H = A4
    x0, x1 = 20 * mm, W - 20 * mm
    y = H - 25 * mm
    font = ensure_font()

    c.setFont(font, 16)
    c.setFillColor(COLOR_PRIMARY)
    c.drawString(x0, y, "Stage Metrics")
    y -= 8
    c.setStrokeColor(COLOR_LINE)
    draw_hline(c, x0, x1, y)
    c.setFillColor(COLOR_TEXT)
    y -= 14

    if not stage_metrics:
        c.setFont(font, 10)
        c.drawString(x0, y, "No per-stage metrics were available.")
        return

    # 1. 단일 루프로 데이터를 깔끔하게 파싱 (표와 차트에 동시 사용)
    parsed_data = []
    for m0 in stage_metrics:
        m = _as_dict(m0)
        stg = _get_val(m, ["stage", "stage_index", "idx"])
        if stg is None:
            continue

        pin = _get_val(m, ["p_in_bar", "pressure_in", "pin", "pin_bar"])
        pout = _get_val(m, ["p_out_bar", "pressure_out", "pout", "pout_bar"])
        dp = _get_val(m, ["dp_bar", "delta_p_bar", "deltaP_bar"])
        if (
            dp is None
            and isinstance(pin, (int, float))
            and isinstance(pout, (int, float))
        ):
            dp = float(pin) - float(pout)

        parsed_data.append(
            {
                "stg": (
                    float(stg)
                    if isinstance(stg, (int, float, str))
                    and str(stg).replace(".", "", 1).isdigit()
                    else 9999
                ),
                "lbl": str(int(stg)) if isinstance(stg, (int, float)) else str(stg),
                "type": str(
                    _get_val(m, ["module_type", "type", "module", "unit_op"], "—")
                ).upper(),
                "jw": _get_val(m, ["flux_lmh", "avg_flux_lmh", "jw_avg_lmh"]),
                "pin": pin,
                "pout": pout,
                "dp": dp,
                "sec": _get_val(m, ["sec_kwhm3", "sec_kwh_m3"]),
            }
        )

    parsed_data.sort(key=lambda d: d["stg"])

    # 2. 테이블 렌더링
    headers = [
        "Stage",
        "Type",
        f"Jw/Flux ({_u(units, 'flux', 'LMH')})",
        f"Pin ({_u(units, 'pressure', 'bar')})",
        f"Pout ({_u(units, 'pressure', 'bar')})",
        f"ΔP ({_u(units, 'pressure', 'bar')})",
        "SEC (kWh/m³)",
    ]
    rows = [
        (
            d["stg"],
            [
                d["lbl"],
                d["type"],
                fmt_num(d["jw"], 1),
                fmt_num(d["pin"], 2),
                fmt_num(d["pout"], 2),
                fmt_num(d["dp"], 2),
                fmt_num(d["sec"], 3),
            ],
        )
        for d in parsed_data
    ]

    total_w = x1 - x0
    col_ws = [total_w * w for w in [0.10, 0.12, 0.18, 0.15, 0.15, 0.12, 0.18]]

    approx_h = (1 + len(rows)) * 16 + 20
    chart_h = 58 * mm
    if y - (approx_h + chart_h + 8 * mm) < 15 * mm:
        c.showPage()
        y = H - 25 * mm
        c.setFont(font, 16)
        c.setFillColor(COLOR_PRIMARY)
        c.drawString(x0, y, "Stage Metrics")
        y -= 8
        c.setStrokeColor(COLOR_LINE)
        draw_hline(c, x0, x1, y)
        c.setFillColor(COLOR_TEXT)
        y -= 14

    y = (
        draw_table(
            c,
            x0,
            y,
            col_headers=headers,
            rows=[r for _, r in rows],
            col_widths=col_ws,
            row_h=16,
            text_font=font,
            text_size=8,
        )
        - 10
    )

    # 3. 차트 렌더링
    if y - chart_h < 20 * mm:
        c.showPage()
        y = H - 30 * mm

    xs = [d["stg"] for d in parsed_data]
    each_w = (total_w - 12 * mm) / 3.0

    _plot_lines(
        c,
        x0,
        y - chart_h,
        each_w,
        chart_h,
        xs,
        series=[([d["jw"] for d in parsed_data], "Avg Flux")],
        y_unit=_u(units, "flux", "LMH"),
        title="Avg Flux",
    )

    _plot_lines(
        c,
        x0 + each_w + 6 * mm,
        y - chart_h,
        each_w,
        chart_h,
        xs,
        series=[
            ([d["pin"] for d in parsed_data], "Pin"),
            ([d["pout"] for d in parsed_data], "Pout"),
            ([d["dp"] for d in parsed_data], "ΔP"),
        ],
        y_unit=_u(units, "pressure", "bar"),
        title="Pin / Pout / ΔP",
    )

    _plot_lines(
        c,
        x0 + 2 * (each_w + 6 * mm),
        y - chart_h,
        each_w,
        chart_h,
        xs,
        series=[([d["sec"] for d in parsed_data], "SEC")],
        y_unit="kWh/m³",
        title="Stage SEC",
    )
