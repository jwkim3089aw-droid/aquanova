"""WAVE PDF benchmark comparison helpers.

V79 adds the missing bridge between AquaNova's WAVE-style diagnostic layer and
actual WAVE report numbers.  The goal is not to force the solver to match WAVE
silently; it is to produce a transparent diff table that shows which values
already align and which missing physics/tuning topics still need work.

The built-in benchmark is the 1.82 m3/h HRRO/CCRO R90 WAVE report used during
AquaNova development.  The reference values are intentionally kept as plain data
so the same comparison engine can later load additional parsed PDF targets.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
import json

from app.schemas.simulation import ScenarioInput, ScenarioOutput
from app.services.simulation.engine import SimulationEngine


Number = float | int


@dataclass(frozen=True)
class BenchmarkSpec:
    """Single benchmark target value from a WAVE report."""

    key: str
    label: str
    target: float
    unit: str = ""
    tolerance_pct: Optional[float] = None
    tolerance_abs: Optional[float] = None
    group: str = "system"
    source: str = "WAVE PDF"
    note: str = ""


@dataclass(frozen=True)
class BenchmarkRow:
    """One AquaNova-vs-WAVE comparison row."""

    key: str
    label: str
    target: float
    actual: Optional[float]
    unit: str
    abs_error: Optional[float]
    pct_error: Optional[float]
    tolerance_pct: Optional[float]
    tolerance_abs: Optional[float]
    status: str
    group: str
    source: str
    note: str = ""


@dataclass(frozen=True)
class BenchmarkReport:
    """Serializable benchmark report."""

    benchmark_id: str
    title: str
    schema: str
    rows: List[BenchmarkRow]
    summary: Dict[str, Any]
    scenario_payload: Dict[str, Any]

    def model_dump(self) -> Dict[str, Any]:
        data = asdict(self)
        data["rows"] = [asdict(row) for row in self.rows]
        return data

    def to_json(self, **kwargs: Any) -> str:
        opts = {"ensure_ascii": False, "indent": 2}
        opts.update(kwargs)
        return json.dumps(self.model_dump(), **opts)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"- Benchmark ID: `{self.benchmark_id}`",
            f"- Schema: `{self.schema}`",
            f"- Compared rows: {self.summary.get('row_count', len(self.rows))}",
            f"- PASS/WARN/FAIL/MISSING: {self.summary.get('status_counts', {})}",
            "",
            "| Group | Key | WAVE target | AquaNova | Error | Status |",
            "|---|---|---:|---:|---:|---|",
        ]
        for row in self.rows:
            target = _format_num(row.target, row.unit)
            actual = "—" if row.actual is None else _format_num(row.actual, row.unit)
            err = "—" if row.pct_error is None else f"{row.pct_error:.2f}%"
            lines.append(
                f"| {row.group} | `{row.key}` | {target} | {actual} | {err} | {row.status} |"
            )
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        lines.append(
            "This report is a diagnostic diff. A FAIL does not mean the scenario crashed; "
            "it marks a WAVE-to-AquaNova mismatch that should be investigated or tuned."
        )
        return "\n".join(lines)


def _format_num(value: float, unit: str = "") -> str:
    txt = f"{float(value):.4g}"
    return f"{txt} {unit}".strip()


def _get_path(data: Any, path: str) -> Optional[float]:
    cur = data
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    try:
        if cur is None:
            return None
        return float(cur)
    except (TypeError, ValueError):
        return None


def _status_for(spec: BenchmarkSpec, actual: Optional[float]) -> Tuple[str, Optional[float], Optional[float]]:
    if actual is None:
        return "MISSING", None, None
    abs_error = abs(float(actual) - float(spec.target))
    pct_error = None if abs(spec.target) < 1e-12 else abs_error / abs(float(spec.target)) * 100.0
    pass_abs = spec.tolerance_abs is not None and abs_error <= float(spec.tolerance_abs)
    pass_pct = spec.tolerance_pct is not None and pct_error is not None and pct_error <= float(spec.tolerance_pct)
    if pass_abs or pass_pct:
        return "PASS", abs_error, pct_error
    # If there is no tolerance, keep it informational.
    if spec.tolerance_abs is None and spec.tolerance_pct is None:
        return "INFO", abs_error, pct_error
    # Use WARN for moderately outside tolerance, FAIL for large misses.
    if pct_error is not None and spec.tolerance_pct is not None:
        return ("WARN" if pct_error <= spec.tolerance_pct * 2.0 else "FAIL"), abs_error, pct_error
    if spec.tolerance_abs is not None:
        return ("WARN" if abs_error <= spec.tolerance_abs * 2.0 else "FAIL"), abs_error, pct_error
    return "FAIL", abs_error, pct_error


def _stage0(output: ScenarioOutput) -> Dict[str, Any]:
    if not output.stage_metrics:
        return {}
    sm = output.stage_metrics[0]
    return sm.model_dump() if hasattr(sm, "model_dump") else dict(sm)


def _actual_value_map(output: ScenarioOutput) -> Dict[str, float]:
    """Flatten key AquaNova outputs into WAVE-comparable names."""
    kpi = output.kpi.model_dump() if output.kpi is not None else {}
    stage = _stage0(output)
    chemistry = stage.get("chemistry") or {}
    streams = chemistry.get("streams") or {}
    cycle = chemistry.get("ccro_cycle") or {}

    actual: Dict[str, Optional[float]] = {
        "system.feed_flow_m3h": kpi.get("feed_m3h", stage.get("Qf")),
        "system.product_flow_m3h": kpi.get("permeate_m3h", stage.get("Qp")),
        "system.concentrate_flow_m3h": stage.get("Qc"),
        "system.recovery_pct": kpi.get("recovery_pct", stage.get("recovery_pct")),
        "system.product_tds_mgL": kpi.get("prod_tds", stage.get("Cp")),
        "system.specific_energy_kwh_m3": kpi.get("sec_kwhm3", stage.get("sec_kwhm3")),
        "pass.average_flux_lmh": kpi.get("flux_lmh", stage.get("flux_lmh")),
        "pass.ndp_bar": kpi.get("ndp_bar", stage.get("ndp_bar")),
        "pass.feed_pressure_bar": stage.get("p_in_bar"),
        "pass.final_concentrate_tds_mgL": stage.get("Cc") or _get_path(streams, "concentrate.tds_mgL"),
        "ccro.cc_recovery_pct": cycle.get("cc_recovery_pct"),
        "ccro.pf_recovery_pct": cycle.get("pf_recovery_pct"),
        "ccro.pf_feed_ratio_pct": cycle.get("pf_feed_ratio_pct"),
        "ccro.cc_concentrate_flow_m3h_per_pv": cycle.get("cc_concentrate_flow_m3h_per_pv"),
        "ccro.pf_concentrate_flow_m3h_per_pv": cycle.get("pf_concentrate_flow_m3h_per_pv"),
        "ccro.cc_net_feed_flow_m3h_per_pv": cycle.get("cc_net_feed_flow_m3h_per_pv"),
        "ccro.pf_feed_flow_m3h_per_pv": cycle.get("pf_feed_flow_m3h_per_pv"),
        "ccro.total_cycles": cycle.get("total_cycles"),
        "ccro.pf_sequence_duration_min": cycle.get("pf_sequence_duration_min"),
        "ccro.cc_sequence_duration_min": cycle.get("cc_sequence_duration_min"),
        "ccro.complete_cycle_duration_min": cycle.get("complete_sequence_duration_min"),
        "ccro.cc_system_volume_m3": cycle.get("cc_system_volume_m3"),
    }
    return {k: float(v) for k, v in actual.items() if v is not None}


WAVE_1P82_HRRO_R90_SPECS: Tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec("system.feed_flow_m3h", "Raw/Net feed to RO system", 2.02, "m3/h", tolerance_pct=3.0, group="system"),
    BenchmarkSpec("system.product_flow_m3h", "Net product from RO system", 1.82, "m3/h", tolerance_pct=3.0, group="system"),
    BenchmarkSpec("system.concentrate_flow_m3h", "Total concentrate from pass 1", 0.20, "m3/h", tolerance_abs=0.05, group="system"),
    BenchmarkSpec("system.recovery_pct", "Net RO system recovery", 90.0, "%", tolerance_abs=1.0, group="system"),
    BenchmarkSpec("system.product_tds_mgL", "Net product TDS", 9.28, "mg/L", tolerance_pct=20.0, group="water_quality"),
    BenchmarkSpec("system.specific_energy_kwh_m3", "Specific energy", 0.30, "kWh/m3", tolerance_pct=25.0, group="energy"),
    BenchmarkSpec("pass.average_flux_lmh", "Pass average flux", 16.3, "LMH", tolerance_pct=5.0, group="pass"),
    BenchmarkSpec("pass.ndp_bar", "Average NDP", 6.0, "bar", tolerance_pct=35.0, group="pass"),
    BenchmarkSpec("pass.feed_pressure_bar", "Max feed pressure", 8.2, "bar", tolerance_pct=20.0, group="pass"),
    BenchmarkSpec("pass.final_concentrate_tds_mgL", "Pass final concentrate TDS", 4038.0, "mg/L", tolerance_pct=20.0, group="water_quality"),
    BenchmarkSpec("ccro.cc_recovery_pct", "CC recovery", 29.26, "%", tolerance_pct=5.0, group="ccro"),
    BenchmarkSpec("ccro.pf_recovery_pct", "PF recovery", 10.0, "%", tolerance_abs=0.25, group="ccro"),
    BenchmarkSpec("ccro.pf_feed_ratio_pct", "PF feed ratio", 270.0, "%", tolerance_abs=1.0, group="ccro"),
    BenchmarkSpec("ccro.cc_concentrate_flow_m3h_per_pv", "CC concentrate flow", 4.54, "m3/h/PV", tolerance_pct=3.0, group="ccro"),
    BenchmarkSpec("ccro.pf_concentrate_flow_m3h_per_pv", "PF concentrate flow", 4.56, "m3/h/PV", tolerance_pct=5.0, group="ccro"),
    BenchmarkSpec("ccro.cc_net_feed_flow_m3h_per_pv", "CC net feed flow", 6.42, "m3/h/PV", tolerance_pct=3.0, group="ccro"),
    BenchmarkSpec("ccro.pf_feed_flow_m3h_per_pv", "PF feed flow", 5.07, "m3/h/PV", tolerance_pct=5.0, group="ccro"),
    BenchmarkSpec("ccro.total_cycles", "Total cycles", 22.50, "cycles", tolerance_pct=3.0, group="ccro"),
    BenchmarkSpec("ccro.pf_sequence_duration_min", "PF sequence duration", 1.24, "min", tolerance_pct=8.0, group="ccro"),
    BenchmarkSpec("ccro.cc_sequence_duration_min", "CC sequence duration", 26.87, "min", tolerance_pct=5.0, group="ccro"),
    BenchmarkSpec("ccro.complete_cycle_duration_min", "Complete cycle duration", 28.11, "min", tolerance_pct=5.0, group="ccro"),
    BenchmarkSpec("ccro.cc_system_volume_m3", "CC system volume", 0.09, "m3", tolerance_abs=0.005, group="ccro"),
)


def wave_1p82_hrro_r90_payload() -> Dict[str, Any]:
    """Return the AquaNova scenario used to compare against the 1.82 m3/h WAVE PDF."""
    return {
        "project_id": "wave_pdf_benchmark_v79",
        "scenario_name": "V79 WAVE 1.82 m3/h HRRO R90 benchmark",
        "feed": {
            "flow_m3h": 2.02,
            "tds_mgL": 412.4,
            "temperature_C": 25.0,
            "pressure_bar": 0.0,
            "ph": 6.5,
        },
        "stages": [
            {
                "stage_id": "hrro_wave_1p82_r90",
                "module_type": "HRRO",
                "recovery_target_pct": 90.0,
                "vessel_count": 1,
                "elements_per_vessel": 3,
                "elements": 3,
                "element_inch": 8,
                "membrane_model": "FilmTec SOAR 5000i",
                "membrane_area_m2": 37.16,
                "membrane_area_m2_per_element": 37.16,
                "membrane_A_lmh_bar": 5.50,
                "membrane_B_lmh": 0.060,
                "membrane_salt_rejection_pct": 99.5,
                "flow_factor": 0.70,
                "fouling_factor": 1.0,
                "pump_efficiency": 0.80,
                "loop_volume_m3": 0.09,
                "cc_recycle_m3h_per_pv": 4.54,
                "pf_feed_ratio_pct": 270.0,
                "pf_recovery_pct": 10.0,
                "dp_per_elem_bar": 0.0333,
                "max_minutes": 60.0,
                "hrro_engine": "physics",
                "hrro_pressure_limit_bar": 12.0,
                "max_tmp_bar": 12.0,
                "cp_tuning_factor": 1.0,
            }
        ],
        "options": {},
    }


def compare_output_to_wave_specs(
    output: ScenarioOutput,
    specs: Iterable[BenchmarkSpec] = WAVE_1P82_HRRO_R90_SPECS,
    *,
    benchmark_id: str = "wave_1p82_hrro_r90",
    title: str = "AquaNova vs WAVE 1.82 m3/h HRRO R90 Benchmark",
    scenario_payload: Optional[Dict[str, Any]] = None,
) -> BenchmarkReport:
    actual_map = _actual_value_map(output)
    rows: List[BenchmarkRow] = []
    for spec in specs:
        actual = actual_map.get(spec.key)
        status, abs_error, pct_error = _status_for(spec, actual)
        rows.append(
            BenchmarkRow(
                key=spec.key,
                label=spec.label,
                target=float(spec.target),
                actual=actual,
                unit=spec.unit,
                abs_error=abs_error,
                pct_error=pct_error,
                tolerance_pct=spec.tolerance_pct,
                tolerance_abs=spec.tolerance_abs,
                status=status,
                group=spec.group,
                source=spec.source,
                note=spec.note,
            )
        )
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    max_pct_error = max((row.pct_error or 0.0 for row in rows), default=0.0)
    summary = {
        "row_count": len(rows),
        "status_counts": counts,
        "max_pct_error": max_pct_error,
        "failed_keys": [row.key for row in rows if row.status == "FAIL"],
        "warn_keys": [row.key for row in rows if row.status == "WARN"],
        "missing_keys": [row.key for row in rows if row.status == "MISSING"],
    }
    return BenchmarkReport(
        benchmark_id=benchmark_id,
        title=title,
        schema="aquanova.wave_benchmark.v79",
        rows=rows,
        summary=summary,
        scenario_payload=scenario_payload or {},
    )


def run_wave_1p82_hrro_r90_benchmark() -> BenchmarkReport:
    payload = wave_1p82_hrro_r90_payload()
    output = SimulationEngine().run(ScenarioInput(**payload))
    return compare_output_to_wave_specs(output, scenario_payload=payload)


__all__ = [
    "BenchmarkSpec",
    "BenchmarkRow",
    "BenchmarkReport",
    "WAVE_1P82_HRRO_R90_SPECS",
    "wave_1p82_hrro_r90_payload",
    "compare_output_to_wave_specs",
    "run_wave_1p82_hrro_r90_benchmark",
]
