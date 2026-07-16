#!/usr/bin/env python3
"""Fit V91 nonlinear calibration candidates from V90 metric errors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_nonlinear_fit import (  # noqa: E402
    build_v91_fit,
    read_metric_rows,
    write_v91_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit V91 nonlinear WAVE calibration candidate models.")
    parser.add_argument("--metric-errors", required=True, help="V90 metric error CSV/JSON, normally *_v90_metric_errors.csv")
    parser.add_argument("--output-base", default=None, help="Optional output base path")
    parser.add_argument("--strict-clean-only", action="store_true", help="Exclude V90 severe rows from fitting")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    metric_path = Path(args.metric_errors).resolve()
    rows = read_metric_rows(metric_path)
    payload = build_v91_fit(rows, include_severe=not args.strict_clean_only)
    base = Path(args.output_base).resolve() if args.output_base else metric_path
    outputs = write_v91_outputs(payload, base)

    print(f"V91 nonlinear fit written from: {metric_path}")
    for key, value in outputs.items():
        print(f"{key}: {value}")
    if args.print_summary:
        print("summary=" + json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
