#!/usr/bin/env python3
"""Offline regression checks for V52 persistent RO temperature commits."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
engine = (ROOT / "wave_ro_engine.py").read_text(encoding="utf-8")
ui = (ROOT / "wave_ro_ui.py").read_text(encoding="utf-8")

ast.parse(engine)
ast.parse(ui)

assert "def _reassert_global_temperature_after_flow_commit(" in engine
assert "ro_temperature_persistent_reassert_v44" in engine
assert 'context="post_recovery_v44"' in engine
assert "summary_flow_calculator_attempt_{attempt}_v44" in engine
assert "for pass_index, pass_config in enumerate(case.passes, start=1):" in engine
assert "temperature_after_tab_roundtrip" in engine
assert 'commit="enter_then_tab_then_pass_roundtrip"' in engine

assert "force_mode_selection: bool = False" in ui
assert "force_mode_selection=force_mode_selection" in ui
assert 'pyautogui.press("enter")' in ui
assert 'value_commit"] = "enter_then_tab_then_neutral_click"' in ui
assert "underlying pass model still keeps" in ui

# The final recovery commit must be followed by persistent temperature restore
# before sticky operating-input verification.
flow = engine.index("Stage 토폴로지 확정 후 Recovery 재확정")
stabilize = engine.index("_stabilize_after_flow_commit(", flow)
helper = engine.index("def _stabilize_after_flow_commit(")
helper_end = engine.index("def configure_schema_ro_case(", helper)
helper_body = engine[helper:helper_end]
assert "_reassert_global_temperature_after_flow_commit(" in helper_body
assert "_verify_case_operating_inputs(" in helper_body
assert flow < stabilize

print("V52 persistent temperature commit self-test OK")
