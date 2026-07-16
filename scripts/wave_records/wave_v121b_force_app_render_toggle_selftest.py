#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[2]

app = ROOT / "ui/src/App.tsx"
component = ROOT / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"

assert app.exists(), app
assert component.exists(), component

at = app.read_text(encoding="utf-8")
ct = component.read_text(encoding="utf-8")

assert "import WaveCorrectionToggle" in at, "App.tsx imports toggle"
assert "<WaveCorrectionToggle" in at, "App.tsx renders toggle"
assert "V121_WAVE_CORRECTION_TOGGLE" in at, "render marker exists"
assert "data-v121-wave-correction-toggle" in ct, "component DOM marker exists"

for rel in [
    "app/schemas/simulation.py",
    "app/api/v1/endpoints/simulation.py",
    "app/services/simulation/calibration/wave_runtime_correction.py",
]:
    p = ROOT / rel
    if p.exists():
        py_compile.compile(str(p), doraise=True)

print("V121B force App render toggle selftest PASS")
