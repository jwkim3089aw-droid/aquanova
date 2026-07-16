#!/usr/bin/env python3
r"""Summarize V102 LG BW440 WAVE PDFs from the latest report corpus CSV.

Run from code\scripts after exporting corpus:
    python .\wave_lg_bw440_pilot_analyze.py --print-summary

It looks for rows whose case/pdf names contain V102_LG_BW440.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _latest_corpus_csv(scripts_dir: Path) -> Path | None:
    root = scripts_dir / "wave_records" / "results" / "_report_corpus"
    if not root.exists():
        return None
    files = sorted(root.glob("wave_report_corpus_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _row_name(row: dict[str, str]) -> str:
    return " ".join(str(row.get(k, "")) for k in ["case_id", "id", "pdf_name", "source_pdf", "filename", "name"])


def _select_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if "V102_LG_BW440" in _row_name(row)]


def _pick(row: dict[str, str], candidates: list[str]) -> str:
    for key in candidates:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize V102 LG BW440 rows from WAVE report corpus.")
    parser.add_argument("--corpus-csv", default=None)
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    corpus = Path(args.corpus_csv).resolve() if args.corpus_csv else _latest_corpus_csv(scripts_dir)
    if corpus is None or not corpus.exists():
        raise SystemExit("No corpus CSV found. Run wave_v81_report_corpus_export.py first.")

    rows = _select_rows(corpus)
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        out_rows.append({
            "case": _pick(row, ["case_id", "id", "pdf_name", "source_pdf", "filename"]),
            "process": _pick(row, ["process", "process_type"]),
            "pf_feed_ratio_pct": _pick(row, ["ccro.pf_feed_ratio_pct", "pf_feed_ratio_pct"]),
            "feed_pressure_bar": _pick(row, ["pass.feed_pressure_bar", "feed_pressure_bar"]),
            "average_flux_lmh": _pick(row, ["pass.average_flux_lmh", "average_flux_lmh"]),
            "specific_energy_kwh_m3": _pick(row, ["system.specific_energy_kwh_m3", "specific_energy_kwh_m3"]),
            "product_tds_mgL": _pick(row, ["system.product_tds_mgL", "product_tds_mgL"]),
            "final_concentrate_tds_mgL": _pick(row, ["pass.final_concentrate_tds_mgL", "final_concentrate_tds_mgL"]),
            "warnings": _pick(row, ["warnings", "design_warnings", "warning_text"]),
        })

    if args.print_summary:
        print("summary=" + json.dumps({"corpus": str(corpus), "v102_lg_bw440_row_count": len(out_rows)}, ensure_ascii=False))
        for r in out_rows:
            print(json.dumps(r, ensure_ascii=False))

    if args.write:
        out_dir = scripts_dir / "wave_records" / "results" / "_meeting_260709_lg_bw440"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / "wave_lg_bw440_pilot_analysis.csv"
        if out_rows:
            with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
                writer.writeheader()
                writer.writerows(out_rows)
        else:
            out_csv.write_text("no V102_LG_BW440 rows found\n", encoding="utf-8")
        print(f"analysis_csv: {out_csv}")

    if not args.print_summary and not args.write:
        parser.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
