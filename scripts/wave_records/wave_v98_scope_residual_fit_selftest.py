from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_scope_residual_fit import (
    apply_v98_residual_model,
    build_scope_residual_fit,
    classify_regime,
)


def _row(split: str, process: str, metric: str, raw: float, wave: float, pdf: str, **extra):
    row = {
        "split": split,
        "process_type": process,
        "metric": metric,
        "aquanova_raw_value": raw,
        "wave_value": wave,
        "wave_pdf_name": pdf,
        "target_recovery_pct_hint": extra.get("recovery", 90),
        "pass_count_hint": extra.get("pass_count", 1),
        "stage_count_hint": extra.get("stage_count", 1),
        "wave_system_product_flow_m3h": extra.get("product", 5.0),
        "is_stress_case": extra.get("stress", False),
    }
    return row


def main() -> int:
    small = _row("train", "ccro", "product_tds", 9.3, 9.28, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82)
    assert classify_regime(small) == "ccro_small_1p82_r90_already_aligned"

    rows = []
    for split in ("train", "train", "holdout", "holdout"):
        rows.append(_row(split, "ccro", "feed_pressure", 10.0, 8.0, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82))
    rows.append(small)
    layer = build_scope_residual_fit(rows)
    decisions = layer["decisions"]
    pressure = [d for d in decisions if d["metric"] == "feed_pressure"][0]
    assert pressure["decision"] == "promote_candidate", pressure
    quality = [d for d in decisions if d["metric"] == "product_tds"][0]
    assert "already_aligned" in quality["flags"] or "upstream_wave_quality_alignment_scope" in quality["flags"]
    result = apply_v98_residual_model(pressure, 10.0)
    assert 7.9 <= result["corrected_value"] <= 8.1, result
    assert layer["runtime_enabled_by_default"] is False
    print("V98 scope residual selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
