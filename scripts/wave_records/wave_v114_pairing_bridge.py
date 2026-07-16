#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


CORE_TARGETS = [
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
    root = here.parents[2]
    if (root / "scripts" / "wave_records").exists():
        return root
    return cwd


def _latest_selected_csv(results_dir: Path) -> Path:
    d = results_dir / "_calibration_v113"
    files = sorted(d.glob("*_selected_for_pairing.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No V113 selected_for_pairing CSV found under {d}")
    return files[0]


def _is_num(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip()
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


def _classify_pair_readiness(row: dict[str, str]) -> tuple[str, str]:
    proc = (row.get("process") or "").lower()
    if proc not in {"ro", "nf", "ccro"}:
        return "skip", f"unsupported_process_{proc or 'blank'}"

    # For the next raw-runner step, a row is ready if it has at least one core numeric target.
    numeric_targets = [c for c in CORE_TARGETS if _is_num(row.get(c))]
    if not numeric_targets:
        return "skip", "no_numeric_core_targets"

    name = row.get("pdf_name", "") or ""
    # LG/SOAR FR150 and baseline rows are useful as holdout/reference; FR270/300 should have been stress, not selected.
    if re.search(r"_FR(?:270|300)(?:_|\.pdf)", name):
        return "skip", "fr270_300_should_be_stress_not_pair_training"

    return "ready", "ready_for_aquanova_raw_pairing"


def main() -> int:
    ap = argparse.ArgumentParser(description="V114 bridge: prepare AquaNova raw pairing manifest from V113 selected rows.")
    ap.add_argument("--results-dir", default=None)
    ap.add_argument("--selected-csv", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = _project_root()
    results_dir = Path(args.results_dir).resolve() if args.results_dir else root / "scripts" / "wave_records" / "results"
    selected_csv = Path(args.selected_csv).resolve() if args.selected_csv else _latest_selected_csv(results_dir)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else results_dir / "_calibration_v114"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_csv(selected_csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_rows = []
    for i, row in enumerate(rows, start=1):
        status, reason = _classify_pair_readiness(row)
        numeric_targets = [c for c in CORE_TARGETS if _is_num(row.get(c))]
        out = dict(row)
        out["v114_pair_row_index"] = i
        out["v114_pair_status"] = status
        out["v114_pair_reason"] = reason
        out["v114_numeric_target_count"] = len(numeric_targets)
        out["v114_numeric_targets"] = ";".join(numeric_targets)

        # Keep placeholders for the next actual AquaNova raw runner.
        out["aquanova_raw_status"] = "pending" if status == "ready" else "not_applicable"
        out["aquanova_raw_error"] = ""
        out_rows.append(out)

    ready = [r for r in out_rows if r["v114_pair_status"] == "ready"]
    skipped = [r for r in out_rows if r["v114_pair_status"] != "ready"]

    prefix = f"wave_v114_pairing_bridge_{timestamp}"
    all_csv = out_dir / f"{prefix}_all_rows.csv"
    ready_csv = out_dir / f"{prefix}_ready_for_raw_runner.csv"
    skipped_csv = out_dir / f"{prefix}_skipped.csv"
    manifest_json = out_dir / f"{prefix}_manifest.json"
    summary_md = out_dir / f"{prefix}_summary.md"

    fields = list(out_rows[0].keys()) if out_rows else []
    _write_csv(all_csv, out_rows, fields)
    _write_csv(ready_csv, ready, fields)
    _write_csv(skipped_csv, skipped, fields)

    summary = {
        "schema_version": "aquanova.wave_calibration_pairing_bridge.v114",
        "generated_at": timestamp,
        "input_selected_csv": str(selected_csv),
        "input_rows": len(rows),
        "ready_rows": len(ready),
        "skipped_rows": len(skipped),
        "by_process_ready": dict(Counter(r.get("process") or "unknown" for r in ready)),
        "by_pair_status": dict(Counter(r["v114_pair_status"] for r in out_rows)),
        "by_pair_reason": dict(Counter(r["v114_pair_reason"] for r in out_rows)),
        "next_step": "Run AquaNova raw simulation for ready_for_raw_runner rows, then compare WAVE targets vs AquaNova raw outputs.",
    }
    manifest_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# V114 pairing bridge summary",
        f"- Input selected CSV: `{selected_csv.name}`",
        f"- Input rows: {len(rows)}",
        f"- Ready rows: {len(ready)}",
        f"- Skipped rows: {len(skipped)}",
        "",
        "## Ready rows by process",
    ]
    for k, v in summary["by_process_ready"].items():
        md.append(f"- {k}: {v}")
    md += [
        "",
        "## Next",
        "Use `_ready_for_raw_runner.csv` as the input list for AquaNova raw simulation.",
        "This step does not mutate the engine and does not apply correction; it only prepares the pairing manifest.",
    ]
    summary_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"ready_for_raw_runner: {ready_csv}")
        print(f"manifest: {manifest_json}")
        print(f"summary_md: {summary_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
