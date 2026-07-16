#!/usr/bin/env python3
"""Run V93 shadow validation for a V92 correction layer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_shadow_validation import (  # noqa: E402
    DEFAULT_SHADOW_THRESHOLDS,
    read_csv_rows,
    read_layer,
    summarize_shadow_rows,
    build_shadow_metric_rows,
    write_v93_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a V92 WAVE correction layer in shadow mode against V89 filled pairs.")
    parser.add_argument("--filled-pairs", required=True, help="V89 *_filled_pairs.csv")
    parser.add_argument("--correction-layer", required=True, help="V92 *_correction_layer.json")
    parser.add_argument("--output-base", default=None, help="Optional output base path")
    parser.add_argument("--include-unmodeled", action="store_true", help="Also emit rows for metrics with no promoted V92 model")
    parser.add_argument("--min-total-n", type=int, default=int(DEFAULT_SHADOW_THRESHOLDS["min_total_n"]))
    parser.add_argument("--min-holdout-n", type=int, default=int(DEFAULT_SHADOW_THRESHOLDS["min_holdout_n"]))
    parser.add_argument("--min-holdout-improvement-pct", type=float, default=float(DEFAULT_SHADOW_THRESHOLDS["min_holdout_improvement_pct"]))
    parser.add_argument("--max-holdout-error-pct", type=float, default=float(DEFAULT_SHADOW_THRESHOLDS["max_holdout_corrected_mean_abs_error_pct"]))
    parser.add_argument("--max-total-error-pct", type=float, default=float(DEFAULT_SHADOW_THRESHOLDS["max_total_corrected_mean_abs_error_pct"]))
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    pair_path = Path(args.filled_pairs).resolve()
    layer_path = Path(args.correction_layer).resolve()
    pair_rows = read_csv_rows(pair_path)
    layer = read_layer(layer_path)
    thresholds = {
        "min_total_n": args.min_total_n,
        "min_holdout_n": args.min_holdout_n,
        "min_holdout_improvement_pct": args.min_holdout_improvement_pct,
        "max_holdout_corrected_mean_abs_error_pct": args.max_holdout_error_pct,
        "max_total_corrected_mean_abs_error_pct": args.max_total_error_pct,
    }
    base = Path(args.output_base).resolve() if args.output_base else pair_path
    outputs = write_v93_outputs(pair_rows, layer, base, include_unmodeled=args.include_unmodeled, thresholds=thresholds)

    print(f"V93 shadow validation written from: {pair_path}")
    print(f"correction_layer: {layer_path}")
    for key, value in outputs.items():
        print(f"{key}: {value}")
    if args.print_summary:
        metric_rows = build_shadow_metric_rows(pair_rows, layer, include_unmodeled=args.include_unmodeled)
        payload = summarize_shadow_rows(metric_rows, thresholds=thresholds)
        print("summary=" + json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
