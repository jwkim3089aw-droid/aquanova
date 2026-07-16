#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wave_records" / "wave_v113_prepare_calibration_dataset.py"

rows = [
    {
        "pdf_name": "V102_LG_BW440_3E_R90_FR150_SOAR5000i.pdf",
        "pdf_path": "x",
        "process": "ccro",
        "report_family": "x",
        "extraction_provider": "PyMuPDF",
        "parse_warnings": "",
        "design_warnings": "Design Warning | Concentrate Flow Rate < Minimum Limit | (m³/h)",
        "pass.feed_pressure_bar": "9.4",
        "system.product_tds_mgL": "5.6",
        "pass.final_concentrate_tds_mgL": "4500",
        "system.specific_energy_kwh_m3": "0.34",
        "ccro.pf_feed_ratio_pct": "150",
    },
    {
        "pdf_name": "V102_LG_BW440_3E_R90_FR300_SOAR5000i.pdf",
        "pdf_path": "x",
        "process": "ccro",
        "report_family": "x",
        "extraction_provider": "PyMuPDF",
        "parse_warnings": "",
        "design_warnings": "PF Feed Ratio > Maximum Value | Limit = 150.00",
        "pass.feed_pressure_bar": "9.1",
        "system.product_tds_mgL": "5.6",
        "pass.final_concentrate_tds_mgL": "4500",
        "system.specific_energy_kwh_m3": "0.34",
        "ccro.pf_feed_ratio_pct": "300",
    },
    {
        "pdf_name": "V102_LG_BW440_3E_TDS2000_R90_SOAR5000i.pdf",
        "pdf_path": "x",
        "process": "ccro",
        "report_family": "x",
        "extraction_provider": "PyMuPDF",
        "parse_warnings": "",
        "design_warnings": "",
        "pass.feed_pressure_bar": "9.1",
        "system.product_tds_mgL": "5.6",
        "pass.final_concentrate_tds_mgL": "4500",
        "system.specific_energy_kwh_m3": "0.34",
        "ccro.pf_feed_ratio_pct": "120",
    },
]

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    csv_path = td / "wave_report_corpus_test.csv"
    fields = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    out_dir = td / "out"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus-csv", str(csv_path), "--out-dir", str(out_dir), "--print-summary"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    manifests = list(out_dir.glob("*_manifest.json"))
    assert manifests, proc.stdout + proc.stderr
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["by_use_class"].get("holdout") == 1, manifest
    assert manifest["by_use_class"].get("stress") == 1, manifest
    assert manifest["by_use_class"].get("exclude") == 1, manifest

print("V113 calibration dataset preparation selftest PASS")
