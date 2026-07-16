#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[2]

component = ROOT / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"
assert component.exists(), component
ct = component.read_text(encoding="utf-8")
assert "AquaNova 정밀 모드" in ct
assert "data-aquanova-precision-toggle" in ct
assert "WAVE 보정 모드" not in ct
assert "aquanova.precisionModeEnabled" in ct

app = ROOT / "ui/src/App.tsx"
assert app.exists(), app
at = app.read_text(encoding="utf-8")
assert "<WaveCorrectionToggle" in at
assert "V122_AQUANOVA_PRECISION_TOGGLE" in at or "V121_WAVE_CORRECTION_TOGGLE" not in at

flow = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
assert flow.exists(), flow
ft = flow.read_text(encoding="utf-8")
assert "precision_mode_enabled" in ft, "frontend payload should use public precision_mode_enabled"
assert "engine_mode" in ft or "calibration_mode" in ft, "frontend payload should send public mode"
assert "wave_correction_enabled:" not in ft, "frontend should not send public wave_correction_enabled field"

schema = ROOT / "app/schemas/simulation.py"
st = schema.read_text(encoding="utf-8")
assert "precision_mode_enabled" in st
assert "engine_mode" in st
assert "precision_report" in st

endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
et = endpoint.read_text(encoding="utf-8")
assert "precision_mode_enabled" in et or "engine_mode" in et
assert "precision_report" in et
assert "wave_correction_report" not in et

for rel in [
    "app/schemas/simulation.py",
    "app/api/v1/endpoints/simulation.py",
    "app/services/simulation/calibration/wave_runtime_correction.py",
]:
    p = ROOT / rel
    if p.exists():
        py_compile.compile(str(p), doraise=True)

print("V122 AquaNova precision-mode rebrand selftest PASS")
