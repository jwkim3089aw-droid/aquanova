#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_METRICS = [
    "pass.feed_pressure_bar",
    "pass.average_flux_lmh",
    "pass.final_concentrate_tds_mgL",
    "system.product_tds_mgL",
    "system.specific_energy_kwh_m3",
    "system.product_flow_m3h",
    "system.recovery_pct",
    "ccro.pf_feed_ratio_pct",
    "ccro.pf_feed_flow_m3h_per_pv",
]


def _project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records" / "results").exists():
        return cwd
    here = Path(__file__).resolve()
    # .../code/scripts/wave_records/script.py
    try:
        root = here.parents[2]
        if (root / "scripts" / "wave_records").exists():
            return root
    except Exception:
        pass
    return cwd


def _is_number(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return False
    try:
        return math.isfinite(float(s))
    except Exception:
        return False


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _latest_corpus_csv(results_dir: Path) -> Path:
    corpus_dir = results_dir / "_report_corpus"
    files = sorted(corpus_dir.glob("wave_report_corpus_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No corpus CSV found under {corpus_dir}")
    return files[0]


def _reason(row: dict[str, str]) -> tuple[str, str]:
    name = row.get("pdf_name", "") or ""
    proc = (row.get("process", "") or "").lower()
    warnings = (row.get("design_warnings", "") or "")
    parse_warn = (row.get("parse_warnings", "") or "")

    # Hard exclusions: not useful as WAVE numeric targets for AquaNova calibration.
    if proc in {"unknown", ""}:
        return "exclude", "unknown_process"
    if parse_warn and parse_warn.lower() not in {"nan", "none"}:
        return "exclude", "parse_warning_present"

    # Old V104 trial PDFs before SOAR tag naming are stale duplicates.
    if name.startswith("V102_LG_BW440") and ("SOAR4000i" not in name and "SOAR5000i" not in name):
        return "exclude", "stale_lg_bw440_pdf_without_soar_tag"

    # The TDS sweep naming was generated, but the WAVE feed water composition was not actually changed.
    if re.search(r"TDS(?:0450|1000|1500|2000)", name):
        return "exclude", "feed_tds_sweep_input_not_verified"

    # Explicit WAVE limit/stress cases should not train the normal WAVE-like correction layer.
    if "PF Feed Ratio > Maximum Value" in warnings:
        return "stress", "pf_feed_ratio_above_wave_limit"
    if re.search(r"_FR(?:270|300)(?:_|\.pdf)", name):
        return "stress", "fr_above_normal_training_range"
    if "FLUX_P3p0" in name:
        return "stress", "high_product_flow_stress"

    # UF report has different target structure; keep as reference unless later UF-specific calibration is run.
    if proc == "uf":
        return "reference", "uf_reference_not_core_ro_nf_ccro_training"

    # Need at least one major target.
    target_cols = [
        "pass.feed_pressure_bar",
        "system.product_tds_mgL",
        "pass.final_concentrate_tds_mgL",
        "system.specific_energy_kwh_m3",
    ]
    if not any(_is_number(row.get(c)) for c in target_cols):
        return "exclude", "no_core_numeric_targets"

    # Mild WAVE warnings are still useful as holdout/reference, but not first-pass clean training.
    if warnings and warnings.lower() not in {"nan", "none"}:
        if "Concentrate Flow Rate < Minimum Limit" in warnings:
            return "holdout", "wave_warning_concentrate_flow_minimum"
        return "holdout", "wave_design_warning_present"

    return "train_candidate", "clean_numeric_wave_anchor"


def _metric_count(row: dict[str, str]) -> int:
    return sum(1 for k, v in row.items() if k not in {"pdf_name", "pdf_path", "process", "report_family", "extraction_provider", "parse_warnings", "design_warnings"} and _is_number(v))


def main() -> int:
    ap = argparse.ArgumentParser(description="V113 prepare WAVE corpus rows for AquaNova calibration refresh.")
    ap.add_argument("--results-dir", default=None, help="WAVE results directory. Defaults to scripts/wave_records/results.")
    ap.add_argument("--corpus-csv", default=None, help="Specific wave_report_corpus_*.csv file.")
    ap.add_argument("--out-dir", default=None, help="Output directory. Defaults to results/_calibration_v113.")
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = _project_root()
    results_dir = Path(args.results_dir).resolve() if args.results_dir else root / "scripts" / "wave_records" / "results"
    corpus_csv = Path(args.corpus_csv).resolve() if args.corpus_csv else _latest_corpus_csv(results_dir)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else results_dir / "_calibration_v113"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_csv(corpus_csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    corpus_base = corpus_csv.stem

    prepared: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        use_class, reason = _reason(row)
        out = dict(row)
        out["v113_row_index"] = idx
        out["v113_use_class"] = use_class
        out["v113_reason"] = reason
        out["v113_metric_count"] = _metric_count(row)
        prepared.append(out)

    fields = list(prepared[0].keys()) if prepared else []
    summary = {
        "schema_version": "aquanova.wave_calibration_dataset.v113",
        "generated_at": timestamp,
        "input_corpus_csv": str(corpus_csv),
        "row_count": len(prepared),
        "by_use_class": dict(Counter(r["v113_use_class"] for r in prepared)),
        "by_reason": dict(Counter(r["v113_reason"] for r in prepared)),
        "by_process": dict(Counter((r.get("process") or "unknown") for r in prepared)),
    }

    selected = [r for r in prepared if r["v113_use_class"] in {"train_candidate", "holdout"}]
    stress = [r for r in prepared if r["v113_use_class"] == "stress"]
    reference = [r for r in prepared if r["v113_use_class"] == "reference"]
    excluded = [r for r in prepared if r["v113_use_class"] == "exclude"]

    prefix = f"wave_v113_{corpus_base}_{timestamp}"
    prepared_csv = out_dir / f"{prefix}_all_classified.csv"
    selected_csv = out_dir / f"{prefix}_selected_for_pairing.csv"
    stress_csv = out_dir / f"{prefix}_stress_reference.csv"
    excluded_csv = out_dir / f"{prefix}_excluded.csv"
    manifest_json = out_dir / f"{prefix}_manifest.json"
    summary_md = out_dir / f"{prefix}_summary.md"

    _write_csv(prepared_csv, prepared, fields)
    _write_csv(selected_csv, selected, fields)
    _write_csv(stress_csv, stress + reference, fields)
    _write_csv(excluded_csv, excluded, fields)
    manifest_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# V113 AquaNova calibration dataset preparation\n")
    md.append(f"- Input corpus: `{corpus_csv.name}`")
    md.append(f"- Total rows: {len(prepared)}")
    md.append("\n## Use class counts\n")
    for k, v in summary["by_use_class"].items():
        md.append(f"- {k}: {v}")
    md.append("\n## Important handling\n")
    md.append("- `train_candidate` / `holdout`: use for next WAVE target ↔ AquaNova raw pairing.")
    md.append("- `stress`: keep for warning/stress validation, not first-pass normal correction training.")
    md.append("- `reference`: keep for separate UF/reference workflows.")
    md.append("- `exclude`: do not use for calibration pairing.")
    md.append("\n## Known exclusions\n")
    md.append("- LG BW440/SOAR stale PDFs without SOAR tags are excluded.")
    md.append("- TDS0450/1000/1500/2000 runs are excluded because feed-water composition was not verified as changed in WAVE.")
    md.append("- FR270/FR300 and PF-ratio-limit warnings are stress/reference rows, not normal training rows.")
    summary_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"all_classified: {prepared_csv}")
        print(f"selected_for_pairing: {selected_csv}")
        print(f"stress_reference: {stress_csv}")
        print(f"excluded: {excluded_csv}")
        print(f"manifest: {manifest_json}")
        print(f"summary_md: {summary_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
