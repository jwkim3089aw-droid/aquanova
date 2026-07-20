from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from app.schemas.simulation import StageConfig
from app.services.simulation.modules.hrro.ccro_cycle import (
    _norm_pf_mode,
)
from app.services.simulation.modules.hrro.engine import (
    HRROSolveState,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v136_backend_unspecified_mode_keeps_wave_compatibility():
    assert (
        StageConfig.model_fields["pf_mode"].default
        == "wave_true_plug_flow"
    )

    defaults = {
        field.name: field.default
        for field in fields(HRROSolveState)
    }

    assert defaults["pf_mode"] == "wave_true_plug_flow"
    assert _norm_pf_mode(None) == "wave_true_plug_flow"
    assert _norm_pf_mode("") == "wave_true_plug_flow"


def test_v136_explicit_smart_mode_remains_supported():
    assert (
        _norm_pf_mode("smart_partial_drain")
        == "smart_partial_drain"
    )
    assert (
        _norm_pf_mode("field_optimized_low_fr")
        == "field_optimized_low_fr"
    )


def test_v136_product_ui_defaults_to_smart_fr150():
    editor = (
        ROOT
        / "ui/src/features/simulation/editors/"
        "UnitForms/HRROEditor.tsx"
    ).read_text(
        encoding="utf-8-sig"
    )

    logic = (
        ROOT
        / "ui/src/features/simulation/model/logic.ts"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "pf_feed_ratio_pct: 150," in editor
    assert "pf_mode: 'smart_partial_drain'," in editor
    assert (
        "cfg.pf_mode ?? 'smart_partial_drain'"
        in editor
    )

    assert "pf_feed_ratio_pct: 150.0," in logic
    assert "pf_mode: 'smart_partial_drain'," in logic
    assert (
        "pf_feed_ratio_pct: "
        "cfg.pf_feed_ratio_pct ?? 150.0"
        in logic
    )
    assert (
        "pf_mode: "
        "cfg.pf_mode ?? 'smart_partial_drain'"
        in logic
    )
