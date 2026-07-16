#!/usr/bin/env python3
from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for rel in [
    "app/schemas/simulation.py",
    "app/api/v1/endpoints/simulation.py",
    "app/services/simulation/wave_corrected_engine.py",
]:
    path = ROOT / rel
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    py_compile.compile(str(path), doraise=True)

schema = (ROOT / "app/schemas/simulation.py").read_text(encoding="utf-8")
endpoint = (ROOT / "app/api/v1/endpoints/simulation.py").read_text(encoding="utf-8")
assert "wave_correction_enabled" in schema
assert "wave_correction_report" in schema
assert "run_simulation_with_optional_wave_correction" in endpoint
assert "V120: explicit WAVE correction opt-in" in endpoint

runner = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
if runner.exists():
    txt = runner.read_text(encoding="utf-8")
    assert "isWaveCorrectionOptIn" in txt
    assert "wave_correction_enabled" in txt

print("V120 WAVE opt-in patch selftest PASS")
