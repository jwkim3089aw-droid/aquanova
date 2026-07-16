from app.services.simulation.calibration.wave_scope_residual_fit import (
    apply_v98_residual_model,
    build_scope_residual_fit,
    classify_regime,
)


def row(split, process, metric, raw, wave, name, **extra):
    return {
        "split": split,
        "process_type": process,
        "metric": metric,
        "aquanova_raw_value": raw,
        "wave_value": wave,
        "wave_pdf_name": name,
        "target_recovery_pct_hint": extra.get("recovery", 90),
        "pass_count_hint": extra.get("pass_count", 1),
        "stage_count_hint": extra.get("stage_count", 1),
        "wave_system_product_flow_m3h": extra.get("product", 5.0),
        "is_stress_case": extra.get("stress", False),
    }


def test_classifies_small_aligned_ccro_scope():
    r = row("train", "ccro", "final_concentrate_tds", 4040, 4038, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82)
    assert classify_regime(r) == "ccro_small_1p82_r90_already_aligned"


def test_residual_fit_is_raw_plus_delta_not_absolute_target():
    rows = [row("train", "ccro", "feed_pressure", 10.0, 8.0, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82) for _ in range(3)]
    rows += [row("holdout", "ccro", "feed_pressure", 20.0, 16.0, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82) for _ in range(2)]
    layer = build_scope_residual_fit(rows)
    model = layer["models"][0]
    assert model["runtime_enabled"] is False
    result = apply_v98_residual_model(model, 20.0)
    assert 15.9 <= result["corrected_value"] <= 16.1
    assert result["corrected_value"] < 30.0


def test_already_aligned_quality_is_not_promoted():
    rows = [row("train", "ccro", "product_tds", 9.3, 9.28, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82) for _ in range(3)]
    rows += [row("holdout", "ccro", "product_tds", 9.4, 9.39, "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf", product=1.82) for _ in range(2)]
    layer = build_scope_residual_fit(rows)
    assert not layer["models"]
    decision = layer["decisions"][0]
    assert decision["decision"] == "review_or_skip"
    assert "already_aligned" in decision["flags"] or "upstream_wave_quality_alignment_scope" in decision["flags"]
