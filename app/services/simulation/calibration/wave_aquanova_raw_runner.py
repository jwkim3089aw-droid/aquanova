"""AquaNova raw-result runner for WAVE calibration pairs (V89).

V88 creates a target-first pair table where every WAVE PDF row is waiting for
an AquaNova raw result.  V89 is the next bridge:

    V88 pair row -> reconstructed AquaNova request -> raw result -> filled pair row

The runner is deliberately defensive.  It tries to use the current AquaNova
``SimulationEngine`` so that the calibration table captures the real uncorrected
engine behavior.  If a row cannot be simulated, the output row remains explicit
(``Status=ENGINE_ERROR``) instead of silently inventing a value.
"""
from __future__ import annotations

import csv
import json
import math
import re
import traceback
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

Number = int | float

RAW_FIELDS: tuple[str, ...] = (
    "Case_ID",
    "Source_WAVE_PDF",
    "Process",
    "Membrane_Model",
    "Feed_TDS_mgL",
    "Temp_C",
    "Target_Recovery_%",
    "Result_Recovery_%",
    "Feed_Pressure_bar",
    "Permeate_Flow_m3h",
    "Permeate_TDS_mgL",
    "Brine_TDS_mgL",
    "SEC_kwhm3",
    "Warnings",
    "Status",
    "Status_Detail",
)

# Canonical AquaNova columns used by V88 pair tables.
AQUA_PAIR_COLUMNS: Mapping[str, str] = {
    "aquanova_case_id": "Case_ID",
    "aquanova_process": "Process",
    "aquanova_membrane_model": "Membrane_Model",
    "aquanova_feed_tds_mgL": "Feed_TDS_mgL",
    "aquanova_temperature_c": "Temp_C",
    "aquanova_target_recovery_pct": "Target_Recovery_%",
    "aquanova_result_recovery_pct": "Result_Recovery_%",
    "aquanova_feed_pressure_bar": "Feed_Pressure_bar",
    "aquanova_permeate_flow_m3h": "Permeate_Flow_m3h",
    "aquanova_permeate_tds_mgL": "Permeate_TDS_mgL",
    "aquanova_brine_tds_mgL": "Brine_TDS_mgL",
    "aquanova_sec_kwh_m3": "SEC_kwhm3",
    "aquanova_warnings": "Warnings",
    "aquanova_status": "Status",
}

ERROR_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("feed_pressure", "wave_pass_feed_pressure_bar", "aquanova_feed_pressure_bar"),
    ("product_tds", "wave_system_product_tds_mgL", "aquanova_permeate_tds_mgL"),
    ("final_concentrate_tds", "wave_pass_final_concentrate_tds_mgL", "aquanova_brine_tds_mgL"),
    ("specific_energy", "wave_system_specific_energy_kwh_m3", "aquanova_sec_kwh_m3"),
    ("recovery", "wave_system_recovery_pct", "aquanova_result_recovery_pct"),
)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace(",", "")
    for token in (
        "m3/h", "m³/h", "mg/L", "mg/l", "bar", "%", "LMH", "kWh/m3", "kWh/m³",
        "cycles", "min",
    ):
        text = text.replace(token, "")
    try:
        out = float(text.strip())
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def _r(value: Any, digits: int = 6) -> float | None:
    f = _to_float(value)
    if f is None:
        return None
    return round(f, digits)


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _s(value).lower()).strip("_")


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_pair_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return read_csv_rows(p)
    if p.suffix.lower() == ".json":
        payload = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return [dict(x) for x in payload["records"] if isinstance(x, Mapping)]
        if isinstance(payload, list):
            return [dict(x) for x in payload if isinstance(x, Mapping)]
    raise ValueError(f"Unsupported pair input: {p}")


def write_csv_rows(rows: Sequence[Mapping[str, Any]], path: str | Path, fieldnames: Sequence[str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return out


def infer_feed_tds_from_wave_pair(row: Mapping[str, Any], default: float | None = None) -> float | None:
    """Infer feed TDS from WAVE mass balance when feed TDS was not parsed.

    WAVE PDFs often expose product TDS and final concentrate TDS but not always a
    separate feed TDS field in the corpus.  For RO/NF/CCRO rows we can use:

        Qf * Cf = Qp * Cp + Qc * Cc
    """
    qf = _to_float(row.get("wave_system_feed_flow_m3h") or row.get("wave_pass_feed_flow_m3h"))
    qp = _to_float(row.get("wave_system_product_flow_m3h") or row.get("wave_pass_permeate_flow_m3h"))
    qc = _to_float(row.get("wave_system_concentrate_flow_m3h"))
    cp = _to_float(row.get("wave_system_product_tds_mgL"))
    cc = _to_float(row.get("wave_pass_final_concentrate_tds_mgL"))
    if qf is not None and qf > 0 and qp is not None and qc is not None and cp is not None and cc is not None:
        cf = ((qp * cp) + (qc * cc)) / qf
        if math.isfinite(cf) and cf >= 0:
            return round(cf, 6)
    return default


def _default_feed_tds(row: Mapping[str, Any]) -> float:
    process = _norm(row.get("process_type"))
    water = _norm(row.get("water_profile_hint"))
    if process == "uf":
        return 120.0
    if "low_tds" in water:
        return 180.0
    if "low" in water:
        return 300.0
    if "high" in water:
        return 650.0
    if process == "ccro":
        return 412.4
    return 500.0


def _feed_flow(row: Mapping[str, Any]) -> float:
    for key in (
        "wave_system_feed_flow_m3h",
        "wave_pass_feed_flow_m3h",
        "wave_uf_net_product_flow_m3h",
    ):
        val = _to_float(row.get(key))
        if val is not None and val > 0:
            # For UF net product, recover gross feed using parsed recovery.
            if key == "wave_uf_net_product_flow_m3h":
                rec = _to_float(row.get("wave_uf_recovery_pct") or row.get("target_recovery_pct_hint")) or 90.0
                return max(0.001, val / max(1e-9, rec / 100.0))
            return val
    return 100.0


def _target_recovery(row: Mapping[str, Any]) -> float:
    for key in (
        "wave_system_recovery_pct",
        "wave_uf_recovery_pct",
        "target_recovery_pct_hint",
        "wave_pass_recovery_pct",
    ):
        val = _to_float(row.get(key))
        if val is not None and 0 < val <= 99.9:
            return val
    return 90.0


def _temperature(row: Mapping[str, Any]) -> float:
    for key in ("wave_system_temperature_c", "wave_uf_temperature_c", "temperature_c_hint"):
        val = _to_float(row.get(key))
        if val is not None:
            return val
    return 25.0


def _membrane_model(row: Mapping[str, Any]) -> str:
    raw = _s(row.get("membrane_model_hint"))
    if raw:
        return raw
    process = _norm(row.get("process_type"))
    if process == "uf":
        return "SFP-2660"
    if process == "nf":
        return "NF270"
    if process == "ccro":
        return "SOAR-5000i"
    return "BW30-400"


def _module_type_for_process(process: str) -> str:
    p = _norm(process)
    if p == "ccro":
        return "HRRO"
    if p == "nf":
        return "NF"
    if p == "uf":
        return "UF"
    return "RO"


def build_surrogate_request_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build a minimal SimulationRequest payload from a V88 pair row.

    This returns plain dicts so the function is testable even before importing
    the full application.  ``run_engine_for_pair`` converts it to Pydantic models.
    """
    process = _norm(row.get("process_type"))
    module_type = _module_type_for_process(process)
    feed_flow = _feed_flow(row)
    target_recovery = _target_recovery(row)
    temperature = _temperature(row)
    feed_tds = infer_feed_tds_from_wave_pair(row, default=_default_feed_tds(row)) or _default_feed_tds(row)
    flow_factor_pct = _to_float(row.get("flow_factor_pct_hint"))
    flow_factor = (flow_factor_pct / 100.0) if flow_factor_pct and flow_factor_pct > 0 else 0.85
    membrane = _membrane_model(row)

    stage: dict[str, Any] = {
        "stage_id": _s(row.get("pair_id") or row.get("wave_case_key") or row.get("wave_pdf_name")),
        "stage_idx": 1,
        "pass_idx": 1,
        "module_type": module_type,
        "membrane_model": membrane,
        "feed_flow_m3h": feed_flow,
        "recovery_target_pct": target_recovery,
        "flow_factor": flow_factor,
        "pump_efficiency": 0.80,
        "source_file": _s(row.get("wave_pdf_name")),
        "chemistry": {"wave_pair_source": _s(row.get("wave_pdf_name")), "calibration_raw_mode": "v89"},
    }

    if module_type in {"RO", "NF", "HRRO"}:
        stage.update({
            "element_inch": 8,
            "vessel_count": 1 if feed_flow < 10 else 10,
            "elements_per_vessel": 3 if module_type == "HRRO" else 5,
            "elements": 3 if module_type == "HRRO" else 50,
            "membrane_area_m2_per_element": 37.16,
            "membrane_area_m2": 37.16,
            "design_flux_lmh": _to_float(row.get("wave_pass_average_flux_lmh")) or None,
        })
    if module_type == "HRRO":
        stage.update({
            "hrro_engine": "physics",
            "ccro_recovery_pct": target_recovery,
            "stop_recovery_pct": target_recovery,
            "pf_feed_ratio_pct": _to_float(row.get("wave_ccro_pf_feed_ratio_pct")) or 270.0,
            "pf_recovery_pct": _to_float(row.get("wave_ccro_pf_recovery_pct")) or 10.0,
            "cc_recycle_m3h_per_pv": _to_float(row.get("wave_ccro_cc_concentrate_flow_m3h_per_pv")) or 4.54,
            "loop_volume_m3": _to_float(row.get("wave_ccro_system_volume_m3")) or 0.09,
            "wave_quality_alignment_enabled": False,
            "pf_mode": "wave_true_plug_flow",
        })
    if module_type == "UF":
        stage.update({
            "design_flux_lmh": _to_float(row.get("wave_pass_average_flux_lmh")) or 55.5,
            "filtration_cycle_min": 30.0,
            "backwash_duration_sec": 60.0,
            "membrane_area_m2": 77.0,
            "modules_count": 1,
        })

    return {
        "simulation_id": _s(row.get("pair_id") or row.get("wave_case_key") or "v89_raw"),
        "project_id": "wave_calibration_v89",
        "scenario_name": f"V89 raw {_s(row.get('wave_pdf_name'))}",
        "feed": {
            "water_type": "RO/NF Well Water",
            "flow_m3h": feed_flow,
            "temperature_C": temperature,
            "ph": 7.5,
            "tds_mgL": feed_tds,
            "pressure_bar": 0.0,
        },
        "stages": [stage],
        "options": {"calibration_raw_mode": "v89", "source_wave_pdf": _s(row.get("wave_pdf_name"))},
    }


def _stream_value(result: Any, label: str, attr: str) -> float | None:
    streams = getattr(result, "streams", None) or []
    for stream in streams:
        if _norm(getattr(stream, "label", "")) == _norm(label):
            return _to_float(getattr(stream, attr, None))
    return None


def _warnings_text(result: Any) -> str:
    warnings = getattr(result, "warnings", None) or []
    parts: list[str] = []
    for item in warnings:
        key = getattr(item, "key", None) or "warning"
        msg = getattr(item, "message", None) or ""
        parts.append(f"{key}:{msg}" if msg else str(key))
    return " | ".join(parts)


def _first_stage_metric(result: Any) -> Any | None:
    metrics = getattr(result, "stage_metrics", None) or []
    return metrics[0] if metrics else None


def run_engine_for_pair(row: Mapping[str, Any]) -> dict[str, Any]:
    """Run the current AquaNova engine for one V88 pair row."""
    raw: dict[str, Any] = {key: None for key in RAW_FIELDS}
    raw.update({
        "Case_ID": _s(row.get("pair_id") or row.get("wave_case_key") or row.get("wave_pdf_name")),
        "Source_WAVE_PDF": _s(row.get("wave_pdf_name")),
        "Process": _s(row.get("process_type")),
        "Membrane_Model": _membrane_model(row),
        "Feed_TDS_mgL": _r(infer_feed_tds_from_wave_pair(row, default=_default_feed_tds(row)), 6),
        "Temp_C": _r(_temperature(row), 3),
        "Target_Recovery_%": _r(_target_recovery(row), 3),
    })

    if _norm(row.get("process_type")) == "unknown" or _to_float(row.get("wave_target_value_count")) in (None, 0.0):
        raw["Status"] = "WAVE_INSUFFICIENT"
        raw["Status_Detail"] = "WAVE row has no usable target metrics."
        return raw

    try:
        from app.schemas.simulation import SimulationRequest  # type: ignore
        from app.services.simulation.engine import SimulationEngine  # type: ignore

        payload = build_surrogate_request_payload(row)
        request = SimulationRequest(**payload)
        result = SimulationEngine().run(request)
        kpi = getattr(result, "kpi", None)
        metric = _first_stage_metric(result)

        feed_pressure = (
            _to_float(getattr(metric, "p_in_bar", None))
            or _to_float(getattr(metric, "p_out_bar", None))
            or _to_float(getattr(kpi, "ndp_bar", None))
        )
        brine_tds = _stream_value(result, "Brine", "tds_mgL")
        if brine_tds is None and metric is not None:
            brine_tds = _to_float(getattr(metric, "Cc", None))

        raw.update({
            "Result_Recovery_%": _r(getattr(kpi, "recovery_pct", None), 6) if kpi else None,
            "Feed_Pressure_bar": _r(feed_pressure, 6),
            "Permeate_Flow_m3h": _r(getattr(kpi, "permeate_m3h", None), 6) if kpi else None,
            "Permeate_TDS_mgL": _r(getattr(kpi, "prod_tds", None), 6) if kpi else None,
            "Brine_TDS_mgL": _r(brine_tds, 6),
            "SEC_kwhm3": _r(getattr(kpi, "sec_kwhm3", None), 6) if kpi else None,
            "Warnings": _warnings_text(result),
            "Status": "SUCCESS",
            "Status_Detail": "",
        })
    except Exception as exc:  # pragma: no cover - exercised in user env if engine rejects a row
        raw["Status"] = "ENGINE_ERROR"
        raw["Status_Detail"] = f"{exc.__class__.__name__}: {exc}"
        # Keep a short traceback string for debugging without making CSV unreadable.
        tb = traceback.format_exc(limit=2).replace("\n", " | ")
        if tb:
            raw["Warnings"] = tb[:1000]
    return raw


def run_raw_rows(pair_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [run_engine_for_pair(row) for row in pair_rows]


def _add_error_columns(row: dict[str, Any]) -> None:
    for label, wave_col, aqua_col in ERROR_TARGETS:
        wave = _to_float(row.get(wave_col))
        aqua = _to_float(row.get(aqua_col))
        abs_col = f"error_{label}_abs"
        pct_col = f"error_{label}_pct"
        if wave is None or aqua is None:
            row[abs_col] = None
            row[pct_col] = None
            continue
        diff = aqua - wave
        row[abs_col] = round(diff, 8)
        row[pct_col] = round(diff / wave * 100.0, 8) if abs(wave) > 1e-12 else None


def fill_pair_rows_with_raw(pair_rows: Sequence[Mapping[str, Any]], raw_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    filled: list[dict[str, Any]] = []
    for pair, raw in zip(pair_rows, raw_rows):
        row = dict(pair)
        status = _s(raw.get("Status"))
        target_count = _to_float(row.get("wave_target_value_count")) or 0.0
        for aqua_col, raw_col in AQUA_PAIR_COLUMNS.items():
            row[aqua_col] = raw.get(raw_col)
        row["aquanova_match_score"] = 1.0 if status == "SUCCESS" else 0.0
        if target_count <= 0:
            row["pair_status"] = "wave_insufficient"
        elif status == "SUCCESS":
            row["pair_status"] = "paired"
        else:
            row["pair_status"] = "aquanova_raw_error"
        _add_error_columns(row)
        filled.append(row)
    return filled


def write_pair_json(rows: Sequence[Mapping[str, Any]], path: str | Path, *, source_pairs: str | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "aquanova.wave_calibration_pairs.v89",
        "source_pairs": source_pairs,
        "summary": summarize_v89(pair_rows=rows),
        "records": list(rows),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_pair_markdown(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_v89(pair_rows=rows)
    lines = [
        "# V89 AquaNova Raw Calibration Pairs",
        "",
        f"- Rows: `{summary['row_count']}`",
        f"- Pair status: `{summary['pair_status_counts']}`",
        f"- Process counts: `{summary['process_counts']}`",
        "",
        "| Process | PDF | Status | Pressure error % | Product TDS error % | SEC error % |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows[:100]:
        lines.append(
            f"| {row.get('process_type','')} | `{row.get('wave_pdf_name','')}` | {row.get('pair_status','')} | "
            f"{_s(row.get('error_feed_pressure_pct'))} | {_s(row.get('error_product_tds_pct'))} | "
            f"{_s(row.get('error_specific_energy_pct'))} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def summarize_v89(*, pair_rows: Sequence[Mapping[str, Any]] | None = None, raw_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(pair_rows or [])
    raw = list(raw_rows or [])
    process_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    raw_status_counts: dict[str, int] = {}
    for row in rows:
        process = _s(row.get("process_type") or "unknown")
        status = _s(row.get("pair_status") or "unknown")
        process_counts[process] = process_counts.get(process, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
    for row in raw:
        status = _s(row.get("Status") or "unknown")
        raw_status_counts[status] = raw_status_counts.get(status, 0) + 1
    return {
        "schema_version": "aquanova.wave_calibration_pairs.v89",
        "row_count": len(rows) if rows else len(raw),
        "process_counts": dict(sorted(process_counts.items())),
        "pair_status_counts": dict(sorted(status_counts.items())),
        "raw_status_counts": dict(sorted(raw_status_counts.items())),
        "paired_row_count": status_counts.get("paired", 0),
        "aquanova_raw_error_count": status_counts.get("aquanova_raw_error", 0),
        "wave_insufficient_count": status_counts.get("wave_insufficient", 0),
    }
