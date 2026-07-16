#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[2]

component = ROOT / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"
if not component.exists():
    raise SystemExit(f"missing component: {component}")
txt = component.read_text(encoding="utf-8")
assert "aquanova.waveCorrectionEnabled" in txt
assert "WAVE 보정 모드" in txt
assert "data-v121-wave-correction-toggle" in txt

runner = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
if not runner.exists():
    raise SystemExit(f"missing useFlowRunner: {runner}")
runner_txt = runner.read_text(encoding="utf-8")
assert "wave_correction_enabled" in runner_txt
assert "calibration_mode" in runner_txt

found_render = False
for p in (ROOT / "ui/src").rglob("*.tsx"):
    if any(x in str(p) for x in ["node_modules", "dist", "build"]):
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if "V121_WAVE_CORRECTION_TOGGLE" in t and "WaveCorrectionToggle" in t:
        found_render = True
        break
assert found_render, "No TSX render target contains WaveCorrectionToggle"

# Backend sanity still compiles.
for rel in [
    "app/schemas/simulation.py",
    "app/api/v1/endpoints/simulation.py",
    "app/services/simulation/calibration/wave_runtime_correction.py",
]:
    path = ROOT / rel
    if path.exists():
        py_compile.compile(str(path), doraise=True)

print("V121 WAVE correction toggle selftest PASS")
