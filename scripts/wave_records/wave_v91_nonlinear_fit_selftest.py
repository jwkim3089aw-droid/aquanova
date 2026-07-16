#!/usr/bin/env python3
"""Small smoke test for V91 nonlinear fitting."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_nonlinear_fit import build_v91_fit  # noqa: E402


def main() -> int:
    rows = []
    for idx, rec in enumerate([75, 80, 85, 90, 95, 88, 82, 78, 92, 86, 84, 89]):
        raw = 10.0 + idx
        wave = 2.0 + 1.15 * raw + 0.02 * raw * (rec / 100.0)
        rows.append({
            "pair_id": f"p{idx}",
            "split": "holdout" if idx in {2, 8} else "train",
            "process_type": "ccro",
            "metric": "feed_pressure",
            "wave_pdf_name": f"case_{idx}.pdf",
            "wave_value": wave,
            "aquanova_raw_value": raw,
            "target_recovery_pct_hint": rec,
            "wave_pass_average_flux_lmh": 16.0,
            "v90_error_class": "clean",
        })
    payload = build_v91_fit(rows)
    assert payload["summary"]["fitted_group_count"] == 1
    assert payload["summary"]["candidate_count"] >= 2
    model = payload["recommended_models"][0]
    assert model["process_type"] == "ccro"
    assert model["metric"] == "feed_pressure"
    print("V91 nonlinear fit selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
