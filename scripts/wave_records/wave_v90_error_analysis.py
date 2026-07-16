#!/usr/bin/env python3
"""Analyze V89 filled calibration pairs and prepare V91 fitting views."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_error_analysis import (  # noqa: E402
    build_v90_analysis,
    read_pair_rows,
    write_v90_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate V90 WAVE-vs-AquaNova error analysis outputs.")
    parser.add_argument("--filled-pairs", required=True, help="V89 filled pairs CSV or JSON")
    parser.add_argument("--output-base", default=None, help="Optional base path used for V90 output filenames")
    parser.add_argument("--top-n", type=int, default=15, help="Top absolute percent errors to include in JSON/Markdown")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.filled_pairs).resolve()
    rows = read_pair_rows(input_path)
    analysis = build_v90_analysis(rows, top_n=max(1, args.top_n))
    base = Path(args.output_base).resolve() if args.output_base else input_path
    outputs = write_v90_outputs(analysis, base)

    print(f"V90 error analysis written from: {input_path}")
    for key, value in outputs.items():
        print(f"{key}: {value}")
    if args.print_summary:
        print("summary=" + json.dumps(analysis["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
