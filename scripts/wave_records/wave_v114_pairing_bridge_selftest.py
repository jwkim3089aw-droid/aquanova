#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wave_records" / "wave_v114_pairing_bridge.py"

rows = [
    {
        "pdf_name": "RO_T001.pdf",
        "process": "ro",
        "v113_use_class": "holdout",
        "v113_reason": "wave_warning_concentrate_flow_minimum",
        "pass.feed_pressure_bar": "12.3",
        "system.product_tds_mgL": "20",
        "pass.final_concentrate_tds_mgL": "",
        "system.specific_energy_kwh_m3": "0.5",
    },
    {
        "pdf_name": "UF_X.pdf",
        "process": "uf",
        "v113_use_class": "reference",
        "v113_reason": "uf_reference",
        "pass.feed_pressure_bar": "",
        "system.product_tds_mgL": "",
        "pass.final_concentrate_tds_mgL": "",
        "system.specific_energy_kwh_m3": "",
    },
]

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    inp = td / "selected.csv"
    fields = sorted({k for r in rows for k in r.keys()})
    with inp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    out = td / "out"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--selected-csv", str(inp), "--out-dir", str(out), "--print-summary"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    manifest = json.loads(next(out.glob("*_manifest.json")).read_text(encoding="utf-8"))
    assert manifest["ready_rows"] == 1, manifest
    assert manifest["skipped_rows"] == 1, manifest

print("V114 pairing bridge selftest PASS")
