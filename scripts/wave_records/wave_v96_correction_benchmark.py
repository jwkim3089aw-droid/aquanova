#!/usr/bin/env python3
"""Run V96 raw-vs-corrected benchmark comparison for the built-in HRRO WAVE PDF case."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.simulation import ScenarioInput  # noqa: E402
from app.services.simulation.engine import SimulationEngine  # noqa: E402
from app.services.simulation.wave_benchmark import (  # noqa: E402
    compare_output_to_wave_specs,
    wave_1p82_hrro_r90_payload,
)
from app.services.simulation.wave_corrected_engine import maybe_apply_wave_correction  # noqa: E402
from app.services.simulation.calibration.wave_runtime_benchmark import (  # noqa: E402
    compare_raw_vs_corrected_reports,
    format_runtime_benchmark_markdown,
    write_json,
)
from app.services.simulation.calibration.wave_runtime_correction import DEFAULT_LAYER_PATH  # noqa: E402


def _run_once(layer_path: str | Path | None = None) -> tuple[dict, str]:
    payload = wave_1p82_hrro_r90_payload()
    raw_output = SimulationEngine().run(ScenarioInput(**payload))
    raw_report = compare_output_to_wave_specs(raw_output, scenario_payload=payload)
    corrected_output, correction_report = maybe_apply_wave_correction(
        raw_output,
        options={"enable_wave_correction": True},
        layer_path=layer_path or DEFAULT_LAYER_PATH,
        config={"enabled": False, "force_apply_promoted_shadow_models": True},
    )
    corrected_report = compare_output_to_wave_specs(corrected_output, scenario_payload=payload)
    summary = compare_raw_vs_corrected_reports(raw_report, corrected_report, correction_report=correction_report)
    return {
        "summary": summary,
        "raw_report": raw_report.model_dump(),
        "corrected_report": corrected_report.model_dump(),
        "correction_report": correction_report,
    }, str(payload.get("scenario_name") or "wave_1p82_hrro_r90")


def main() -> int:
    parser = argparse.ArgumentParser(description="V96 raw-vs-corrected WAVE benchmark gate")
    parser.add_argument("--correction-layer", default=DEFAULT_LAYER_PATH)
    parser.add_argument("--out-dir", default="results/wave_benchmarks")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--print-markdown", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true", help="Return non-zero if the V96 gate detects regression.")
    args = parser.parse_args()

    result, scenario_name = _run_once(args.correction_layer)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"wave_v96_runtime_correction_benchmark_{stamp}.json"
    md_path = out_dir / f"wave_v96_runtime_correction_benchmark_{stamp}.md"
    write_json(result, json_path)
    md = format_runtime_benchmark_markdown(result["summary"], title=f"V96 WAVE Runtime Correction Benchmark - {scenario_name}")
    md_path.write_text(md, encoding="utf-8")
    print("V96 runtime correction benchmark written:")
    print(json_path)
    print(md_path)
    if args.print_summary:
        print("summary=" + json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    if args.print_markdown:
        print()
        print(md)
    if args.fail_on_regression and str(result["summary"].get("gate_status")) == "review_regression":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
