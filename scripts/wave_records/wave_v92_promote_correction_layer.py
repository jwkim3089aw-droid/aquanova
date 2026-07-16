#!/usr/bin/env python3
"""Promote safe V91 nonlinear candidates into a V92 correction layer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import (  # noqa: E402
    DEFAULT_PROMOTION_THRESHOLDS,
    build_v92_layer,
    read_recommended_models,
    write_v92_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote V91 WAVE calibration models into a conservative V92 correction layer.")
    parser.add_argument("--recommended-models", required=True, help="V91 *_recommended_models.json")
    parser.add_argument("--output-base", default=None, help="Optional output base path")
    parser.add_argument("--enable-runtime", action="store_true", help="Mark promoted models as runtime_enabled=true; default is shadow/off")
    parser.add_argument("--min-train-n", type=int, default=int(DEFAULT_PROMOTION_THRESHOLDS["min_train_n"]))
    parser.add_argument("--min-holdout-n", type=int, default=int(DEFAULT_PROMOTION_THRESHOLDS["min_holdout_n"]))
    parser.add_argument("--min-holdout-improvement-pct", type=float, default=float(DEFAULT_PROMOTION_THRESHOLDS["min_holdout_improvement_pct"]))
    parser.add_argument("--max-holdout-error-pct", type=float, default=float(DEFAULT_PROMOTION_THRESHOLDS["max_holdout_corrected_mean_abs_error_pct"]))
    parser.add_argument("--max-train-error-pct", type=float, default=float(DEFAULT_PROMOTION_THRESHOLDS["max_train_corrected_mean_abs_error_pct"]))
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    rec_path = Path(args.recommended_models).resolve()
    models = read_recommended_models(rec_path)
    thresholds = {
        "min_train_n": args.min_train_n,
        "min_holdout_n": args.min_holdout_n,
        "min_holdout_improvement_pct": args.min_holdout_improvement_pct,
        "max_holdout_corrected_mean_abs_error_pct": args.max_holdout_error_pct,
        "max_train_corrected_mean_abs_error_pct": args.max_train_error_pct,
    }
    layer = build_v92_layer(models, thresholds=thresholds, enable_runtime_by_default=args.enable_runtime)
    base = Path(args.output_base).resolve() if args.output_base else rec_path
    outputs = write_v92_outputs(layer, base)

    print(f"V92 correction layer promotion written from: {rec_path}")
    for key, value in outputs.items():
        print(f"{key}: {value}")
    if args.print_summary:
        print("summary=" + json.dumps(layer["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
