# app/reports/templates/stage_metrics.py
from __future__ import annotations
from typing import List, Dict, Any, Iterable, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

from .common import ensure_font, fmt_num, draw_table, draw_hline


def _u(units: Dict[str, str] | None, key: str, default: str) -> str:
    if not isinstance(units, dict):
        return default
    v = units.get(key)
    return v if isinstance(v, str) and v.strip() else default


def _as_dict(m: Any) -> Dict[str, Any]:
    """
    stage_metrics가 dict로 오든, pydantic model로 오든, dataclass로 오든 안전하게 dict로 변환.
    """
    if isinstance(m, dict):
        return m
    if hasattr(m, "model_dump"):  # Pydantic V2
        try:
            return m.model_dump()
        except Exception:
            pass
    if hasattr(m, "dict"):  # Pydantic V1
        try:
            return m.dict()
        except Exception:
            pass
    try:
        return dict(m)  # Key access / Dataclass conversion
    except Exception:
        return {}


def _get_val(m: Dict[str, Any], keys: List[str]) -> Any | None:
    """여러 키 후보 중 값이 있는 첫 번째를 반환 (우선순위 처리)"""
    for k in keys:
        if k in m and m[k] is not None:
            return m[k]
    return None


def _rows_from_stage_metrics(stage_metrics: List[Any] | None) -> List[List[str]]:
    if not stage_metrics:
        return []

    rows: list[tuple[float | int | None, list[str]]] = []

    for m0 in stage_metrics:
        m = _as_dict(m0)

        # 1. Stage Index (Schema: stage, Model: stage_index)
        stg = _get_val(m, ["stage", "stage_index", "idx"])

        # 2. Flux (Schema: flux_lmh, Model: avg_flux_lmh, Legacy: jw_avg_lmh)
        jw = _get_val(m, ["flux_lmh", "avg_flux_lmh", "jw_avg_lmh"])

        # 3. Pressure In (Schema: p_in_bar, Model: pressure_in, Legacy: pin, pin_bar)
        pin = _get_val(m, ["p_in_bar", "pressure_in", "pin", "pin_bar"])

        # 4. Pressure Out (Schema: p_out_bar, Model: pressure_out, Legacy: pout, pout_bar)
        pout = _get_val(m, ["p_out_bar", "pressure_out", "pout", "pout_bar"])

        # 5. SEC (Schema/Model: sec_kwhm3, Legacy: sec_kwh_m3)
        sec = _get_val(m, ["sec_kwhm3", "sec_kwh_m3"])

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
                    fmt_num(jw, 1),
                    fmt_num(pin, 2),
                    fmt_num(pout, 2),
                    fmt_num(sec, 3),
                ],
            )
        )

    # Stage 순서대로 정렬
    try:
        rows.sort(key=lambda x: (9999 if x[0] is None else float(x[0])))
    except Exception:
        pass

    return [r for _, r in rows]


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
    series: List[Tuple[List[float | None], str]],  # [(ys, label)]
    y_unit: str,
    title: str,
):
    font = ensure_font()
    c.setLineWidth(0.8)
    c.setStrokeColor(colors.black)
    c.rect(x, y, w, h, stroke=1, fill=0)

    c.setFont(font, 10)
    c.drawString(x, y + h + 2 * mm, title)
    c.setFont(font, 8)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawRightString(x + w, y - 3, f"[{y_unit}]")
    c.setFillColorRGB(0, 0, 0)

    n = len(xs)
    all_vals = []
    for ys, _ in series:
        all_vals.extend([v for v in ys if isinstance(v, (int, float))])

    if not all_vals:
        c.setFont(font, 8)
        c.drawString(x + 3, y + h / 2, "No data")
        return

    y_min, y_max = _series_bounds(all_vals)

    def y_to_py(v: float) -> float:
        if y_max == y_min:
            return y + h / 2
        return y + ((v - y_min) / (y_max - y_min)) * h

    # Grid Lines
    c.setLineWidth(0.3)
    c.setStrokeColor(colors.lightgrey)
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        gy = y + frac * h
        c.line(x, gy, x + w, gy)
        c.setFont(font, 7)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.drawRightString(x - 2, gy - 2, fmt_num(y_min + frac * (y_max - y_min), 2))

    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)

    # Plot Lines
    dash_styles = [None, [2, 2], None, [1, 2]]
    colors_list = [colors.black, colors.darkgrey, colors.blue, colors.red]

    if n >= 2:
        x_coords = [x + (i / (n - 1)) * w for i in range(n)]
        for idx, (ys, label) in enumerate(series):
            pts = []
            for i, v in enumerate(ys):
                pts.append(None if v is None else (x_coords[i], y_to_py(float(v))))

            c.setLineWidth(1.0 if idx == 0 else 0.8)
            col = colors_list[idx % len(colors_list)]
            c.setStrokeColor(col)
            dash = dash_styles[idx % len(dash_styles)]
            c.setDash(dash or [])

            last = None
            for p in pts:
                if p is None:
                    last = None
                    continue
                if last is not None:
                    c.line(last[0], last[1], p[0], p[1])
                last = p

            # Legend
            c.setFont(font, 7)
            c.setFillColor(col)
            c.drawString(x + 4 + idx * (w * 0.25), y + h + 1.5 * mm, label)
            c.setFillColor(colors.black)

        # X Axis Labels
        c.setFont(font, 7)
        for i in range(n):
            c.drawCentredString(
                x_coords[i],
                y - 10,
                str(int(xs[i])) if isinstance(xs[i], (int, float)) else str(xs[i]),
            )
    else:
        # Point Plot (Single Stage)
        px = x + w / 2
        for idx, (ys, label) in enumerate(series):
            v = next((float(v) for v in ys if isinstance(v, (int, float))), None)
            if v is None:
                continue
            py = y_to_py(v)
            col = colors_list[idx % len(colors_list)]
            c.setFillColor(col)
            c.setStrokeColor(col)
            r = 2.5
            c.circle(px, py, r, stroke=1, fill=1)

            c.setFont(font, 7)
            c.setFillColor(col)
            c.drawString(
                x + 4 + idx * (w * 0.25), y + h + 1.5 * mm, f"{label} • {fmt_num(v, 2)}"
            )
            c.setFillColor(colors.black)

        c.setFont(font, 7)
        c.drawCentredString(
            px,
            y - 10,
            str(int(xs[0])) if isinstance(xs[0], (int, float)) else str(xs[0]),
        )


def draw_stage_metrics_page(
    c, stage_metrics: List[Any] | None, units: Dict[str, str] | None = None
) -> None:
    """
    pdfgen.canvas 기반 전용 페이지: Stage Metrics 표 + 3 미니 차트(Avg Flux / Pin·Pout / Stage SEC)
    """
    W, H = A4
    x0, x1 = 20 * mm, W - 20 * mm
    y = H - 25 * mm
    font = ensure_font()

    c.setFont(font, 16)
    c.drawString(x0, y, "Stage Metrics")
    y -= 8
    draw_hline(c, x0, x1, y)
    y -= 14

    if not stage_metrics:
        c.setFont(font, 10)
        c.drawString(x0, y, "No per-stage metrics were available.")
        return

    headers = [
        "Stage",
        f"Jw avg ({_u(units, 'flux', 'LMH')})",
        f"Pin ({_u(units, 'pressure', 'bar')})",
        f"Pout ({_u(units, 'pressure', 'bar')})",
        "SEC (kWh/m³)",
    ]

    # 테이블용 데이터 생성
    rows = _rows_from_stage_metrics(stage_metrics)

    total_w = x1 - x0
    col_ws = [
        total_w * 0.14,
        total_w * 0.24,
        total_w * 0.21,
        total_w * 0.21,
        total_w * 0.20,
    ]

    approx_h = (1 + len(rows)) * 16 + 20
    chart_h = 58 * mm
    gap = 8 * mm
    need_h = approx_h + gap + chart_h

    if y - need_h < 15 * mm:
        c.showPage()
        y = H - 25 * mm
        c.setFont(font, 16)
        c.drawString(x0, y, "Stage Metrics")
        y -= 8
        draw_hline(c, x0, x1, y)
        y -= 14

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

    # 차트용 데이터 추출 (테이블과 동일한 로직 사용)
    xs = []
    flux = []
    pin = []
    pout = []
    sec = []

    # 정렬된 순서를 보장하기 위해 _rows_from_stage_metrics와 동일하게 처리하지 않고
    # 이미 정렬된 rows 데이터를 기반으로 하거나, 다시 정렬 로직을 타야 함.
    # 여기서는 원본 데이터를 다시 순회하되 _rows_from_stage_metrics 내부 정렬 로직을 고려하여
    # stage_index 기준으로 정렬 후 추출합니다.

    metrics_list = []
    for m0 in stage_metrics:
        m = _as_dict(m0)
        stg = _get_val(m, ["stage", "stage_index", "idx"])
        if stg is not None:
            metrics_list.append((stg, m))

    metrics_list.sort(key=lambda x: float(x[0]))

    for stg, m in metrics_list:
        xs.append(stg)
        flux.append(_get_val(m, ["flux_lmh", "avg_flux_lmh", "jw_avg_lmh"]))
        pin.append(_get_val(m, ["p_in_bar", "pressure_in", "pin", "pin_bar"]))
        pout.append(_get_val(m, ["p_out_bar", "pressure_out", "pout", "pout_bar"]))
        sec.append(_get_val(m, ["sec_kwhm3", "sec_kwh_m3"]))

    if y - chart_h < 20 * mm:
        c.showPage()
        y = H - 30 * mm

    w_total = x1 - x0
    gap_x = 6 * mm
    each_w = (w_total - 2 * gap_x) / 3.0
    xA = x0
    xB = xA + each_w + gap_x
    xC = xB + each_w + gap_x

    _plot_lines(
        c,
        xA,
        y - chart_h,
        each_w,
        chart_h,
        xs=xs,
        series=[(flux, "Avg Flux")],
        y_unit=_u(units, "flux", "LMH"),
        title="Avg Flux",
    )

    _plot_lines(
        c,
        xB,
        y - chart_h,
        each_w,
        chart_h,
        xs=xs,
        series=[(pin, "Pin"), (pout, "Pout")],
        y_unit=_u(units, "pressure", "bar"),
        title="Pin / Pout",
    )

    _plot_lines(
        c,
        xC,
        y - chart_h,
        each_w,
        chart_h,
        xs=xs,
        series=[(sec, "SEC")],
        y_unit=_u(units, "sec", "kWh/m³"),
        title="Stage SEC",
    )
