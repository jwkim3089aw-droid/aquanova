#!/usr/bin/env python3
"""Selftest for V88 calibration pair-table creation."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_calibration_pairing import (  # noqa: E402
    build_pair_rows,
    load_corpus_records,
    load_feature_splits,
    summarize_pair_rows,
    write_pair_table,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus = root / "corpus.json"
        features = root / "features.csv"
        out = root / "pairs.csv"
        payload = {
            "records": [
                {
                    "pdf_name": "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf",
                    "process": "ccro",
                    "parse_warnings": [],
                    "design_warnings": ["PF Feed Ratio > Maximum Value"],
                    "metrics": {
                        "system.feed_flow_m3h": 2.02,
                        "system.product_flow_m3h": 1.82,
                        "system.recovery_pct": 90.0,
                        "system.product_tds_mgL": 9.28,
                        "system.specific_energy_kwh_m3": 0.30,
                        "system.temperature_c": 25.0,
                        "pass.feed_pressure_bar": 8.2,
                        "pass.final_concentrate_tds_mgL": 4038.0,
                        "ccro.pf_feed_ratio_pct": 270.0,
                    },
                },
                {
                    "pdf_name": "V84_UF_SFP2660_F120.pdf",
                    "process": "uf",
                    "metrics": {"uf.net_product_flow_m3h": 120.0, "uf.recovery_pct": 95.0},
                },
            ]
        }
        corpus.write_text(json.dumps(payload), encoding="utf-8")
        with features.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["trace__pdf_name", "split"])
            writer.writeheader()
            writer.writerow({"trace__pdf_name": "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", "split": "holdout"})
            writer.writerow({"trace__pdf_name": "V84_UF_SFP2660_F120.pdf", "split": "train"})

        rows = build_pair_rows(load_corpus_records(corpus), feature_splits=load_feature_splits(features))
        assert len(rows) == 2
        assert rows[0]["pair_status"] == "needs_aquanova_raw"
        assert rows[0]["split"] == "holdout"
        assert rows[0]["wave_pass_feed_pressure_bar"] == 8.2
        assert rows[0]["wave_system_product_tds_mgL"] == 9.28
        assert rows[0]["target_recovery_pct_hint"] == 90.0
        assert rows[1]["process_type"] == "uf"
        assert rows[1]["wave_uf_recovery_pct"] == 95.0
        summary = summarize_pair_rows(rows)
        assert summary["row_count"] == 2
        assert summary["needs_aquanova_raw_count"] == 2
        write_pair_table(rows, out)
        assert out.exists() and out.read_text(encoding="utf-8-sig").startswith("pair_id,")
    print("V88 calibration pair selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
