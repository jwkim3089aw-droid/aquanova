#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import py_compile

ROOT = Path(__file__).resolve().parents[2]

# Python backend sanity.
for rel in [
    "app/schemas/simulation.py",
    "app/api/v1/endpoints/simulation.py",
    "app/services/simulation/calibration/wave_runtime_correction.py",
]:
    p = ROOT / rel
    if p.exists():
        py_compile.compile(str(p), doraise=True)

component = ROOT / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"
assert component.exists(), component
ct = component.read_text(encoding="utf-8")
assert "data-v121-wave-correction-toggle" in ct
assert "aquanova.waveCorrectionEnabled" in ct

app = ROOT / "ui/src/App.tsx"
assert app.exists(), app
at = app.read_text(encoding="utf-8")
assert "WaveCorrectionToggle" in at
assert "V121_WAVE_CORRECTION_TOGGLE" in at

flow = ROOT / "ui/src/features/simulation/FlowBuilderScreen.tsx"
if flow.exists():
    ft = flow.read_text(encoding="utf-8")
    assert "V121_WAVE_CORRECTION_TOGGLE" not in ft, "FlowBuilderScreen should be restored; toggle belongs in App.tsx"

print("V121A restore/safe-toggle selftest PASS")
