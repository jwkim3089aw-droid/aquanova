#!/usr/bin/env python3
"""Offline structural checks for the V52 refactor (does not launch WAVE)."""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

MODULES = (
    "wave_common", "wave_runtime", "wave_windows", "wave_diagnostics",
    "wave_interaction", "wave_uia", "wave_dialogs", "wave_feed",
    "wave_ro_ui", "wave_recorded", "wave_pdf", "wave_ro_engine",
    "wave_batch", "wave_ro_schema", "wave_ro_excel", "wave_ro_catalog", "wave_cli", "wave_video_demo",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--sheet")
    args = parser.parse_args()
    loaded = {name: importlib.import_module(name) for name in MODULES}
    assert callable(loaded["wave_cli"].main)
    assert callable(loaded["wave_uia"].uia_select_combo_exact)
    assert callable(loaded["wave_ro_engine"]._repair_missing_element_type_dialog)
    assert callable(loaded["wave_ro_engine"]._restore_stage_topologies_after_flow_commit)
    assert callable(loaded["wave_ro_engine"]._stabilize_after_flow_commit)
    assert callable(loaded["wave_ro_engine"]._apply_chemical_adjustment)
    assert callable(loaded["wave_ro_engine"]._apply_special_features)
    assert callable(loaded["wave_uia"].uia_configure_chemical_adjustment)
    assert callable(loaded["wave_uia"].uia_configure_special_feature_dialog)
    uia_source = Path(loaded["wave_uia"].__file__).read_text(encoding="utf-8")
    engine_source = Path(loaded["wave_ro_engine"].__file__).read_text(encoding="utf-8")
    assert "CatalogKeyboardIndexProvisional" in uia_source
    assert "SelectionItemPattern" in uia_source
    runner_source = __import__("inspect").getsource(loaded["wave_uia"]._run_powershell_json)
    assert "tempfile.mkstemp" in runner_source
    assert '"-File"' in runner_source
    assert "-EncodedCommand" not in runner_source
    assert "membrane_readback_deferred_v32" in engine_source
    assert "antiscalant_enabled" in uia_source
    assert "dechlorinator_enabled" in uia_source
    assert "chemical_temperature_mode" in uia_source
    assert "chemical_recovery_mode" in uia_source
    assert "table_after" in uia_source
    assert len(Path(__file__).with_name("wave_video_demo.py").read_text(encoding="utf-8").splitlines()) < 30
    if args.xlsx:
        from wave_ro_excel import load_ro_cases
        cases = load_ro_cases(args.xlsx, args.sheet)
        assert cases, "No RO cases loaded"
    print(f"V52 refactor self-test OK: modules={len(MODULES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
