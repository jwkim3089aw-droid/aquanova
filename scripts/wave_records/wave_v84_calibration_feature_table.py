#!/usr/bin/env python3
"""Build a flattened V84 nonlinear-calibration feature table from a V81 corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Allow running this script from scripts/wave_records without installing the app.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_calibration_features import (  # noqa: E402
    build_feature_rows,
    load_wave_corpus_records,
    summarize_feature_rows,
    write_feature_table,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert WAVE report corpus JSON/CSV into a flat calibration feature table.")
    parser.add_argument("--corpus", required=True, help="Path to V81 wave_report_corpus_*.json or .csv")
    parser.add_argument("--output", default=None, help="Output CSV path. Defaults beside corpus with _v84_features suffix.")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    corpus = Path(args.corpus).resolve()
    records = load_wave_corpus_records(corpus)
    rows = build_feature_rows(records)
    if args.output:
        output = Path(args.output).resolve()
    else:
        output = corpus.with_name(corpus.stem + "_v84_calibration_features.csv")
    write_feature_table(rows, output)
    print(f"V84 calibration feature table written: {output}")
    if args.print_summary:
        print("summary=" + json.dumps(summarize_feature_rows(rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
