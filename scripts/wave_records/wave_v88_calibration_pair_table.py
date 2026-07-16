#!/usr/bin/env python3
"""Build a V88 WAVE-target/AquaNova-raw calibration pair table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_calibration_pairing import (  # noqa: E402
    build_pair_rows,
    load_corpus_records,
    load_feature_splits,
    read_csv_rows,
    summarize_pair_rows,
    write_pair_json,
    write_pair_markdown,
    write_pair_table,
)


def _default_feature_path(corpus: Path) -> Path:
    return corpus.with_name(corpus.stem + "_v84_calibration_features.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create V88 calibration pair rows from a V81 WAVE corpus.")
    parser.add_argument("--corpus", required=True, help="Path to wave_report_corpus_*.json or .csv")
    parser.add_argument("--features", default=None, help="Optional V84 feature CSV to preserve train/holdout split")
    parser.add_argument("--aquanova-raw", default=None, help="Optional AquaNova raw result CSV to fuzzy-match into pair rows")
    parser.add_argument("--output", default=None, help="Output CSV path. Defaults beside corpus with _v88_calibration_pairs.csv suffix")
    parser.add_argument("--json-output", default=None, help="Optional JSON output path. Defaults beside CSV")
    parser.add_argument("--markdown-output", default=None, help="Optional Markdown output path. Defaults beside CSV")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    corpus = Path(args.corpus).resolve()
    feature_path = Path(args.features).resolve() if args.features else _default_feature_path(corpus)
    features_for_split = feature_path if feature_path.exists() else None
    raw_rows = read_csv_rows(args.aquanova_raw) if args.aquanova_raw else None

    rows = build_pair_rows(
        load_corpus_records(corpus),
        feature_splits=load_feature_splits(features_for_split),
        aquanova_raw_rows=raw_rows,
    )

    output = Path(args.output).resolve() if args.output else corpus.with_name(corpus.stem + "_v88_calibration_pairs.csv")
    write_pair_table(rows, output)
    json_output = Path(args.json_output).resolve() if args.json_output else output.with_suffix(".json")
    md_output = Path(args.markdown_output).resolve() if args.markdown_output else output.with_suffix(".md")
    write_pair_json(rows, json_output, source_corpus=str(corpus))
    write_pair_markdown(rows, md_output)

    print(f"V88 calibration pair table written: {output}")
    print(f"json: {json_output}")
    print(f"markdown: {md_output}")
    if features_for_split:
        print(f"splits: {features_for_split}")
    else:
        print("splits: stable hash fallback")
    if args.print_summary:
        print("summary=" + json.dumps(summarize_pair_rows(rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
