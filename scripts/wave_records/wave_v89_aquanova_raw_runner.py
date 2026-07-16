#!/usr/bin/env python3
"""Run AquaNova raw simulations for a V88 calibration pair table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_aquanova_raw_runner import (  # noqa: E402
    RAW_FIELDS,
    fill_pair_rows_with_raw,
    read_pair_rows,
    run_raw_rows,
    summarize_v89,
    write_csv_rows,
    write_pair_json,
    write_pair_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate V89 AquaNova raw rows and filled calibration pairs.")
    parser.add_argument("--pairs", required=True, help="V88 pair table CSV or JSON")
    parser.add_argument("--raw-output", default=None, help="Optional AquaNova raw CSV output path")
    parser.add_argument("--filled-output", default=None, help="Optional filled pair CSV output path")
    parser.add_argument("--json-output", default=None, help="Optional filled pair JSON output path")
    parser.add_argument("--markdown-output", default=None, help="Optional filled pair Markdown output path")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    pairs_path = Path(args.pairs).resolve()
    pair_rows = read_pair_rows(pairs_path)
    raw_rows = run_raw_rows(pair_rows)
    filled_rows = fill_pair_rows_with_raw(pair_rows, raw_rows)

    raw_output = Path(args.raw_output).resolve() if args.raw_output else pairs_path.with_name(pairs_path.stem + "_v89_aquanova_raw.csv")
    filled_output = Path(args.filled_output).resolve() if args.filled_output else pairs_path.with_name(pairs_path.stem + "_v89_filled_pairs.csv")
    json_output = Path(args.json_output).resolve() if args.json_output else filled_output.with_suffix(".json")
    md_output = Path(args.markdown_output).resolve() if args.markdown_output else filled_output.with_suffix(".md")

    write_csv_rows(raw_rows, raw_output, fieldnames=RAW_FIELDS)
    write_csv_rows(filled_rows, filled_output)
    write_pair_json(filled_rows, json_output, source_pairs=str(pairs_path))
    write_pair_markdown(filled_rows, md_output)

    print(f"V89 AquaNova raw table written: {raw_output}")
    print(f"filled pairs: {filled_output}")
    print(f"json: {json_output}")
    print(f"markdown: {md_output}")
    if args.print_summary:
        summary = summarize_v89(pair_rows=filled_rows, raw_rows=raw_rows)
        print("summary=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
