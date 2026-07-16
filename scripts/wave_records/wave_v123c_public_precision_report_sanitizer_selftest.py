#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile
import re

ROOT = Path(__file__).resolve().parents[2]

schema = ROOT / "app/schemas/simulation.py"
endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
types = ROOT / "ui/src/api/types.ts"
runner = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
toggle = ROOT / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"

for p in [schema, endpoint]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)

schema_text = schema.read_text(encoding="utf-8")
endpoint_text = endpoint.read_text(encoding="utf-8")
types_text = types.read_text(encoding="utf-8") if types.exists() else ""
runner_text = runner.read_text(encoding="utf-8") if runner.exists() else ""
toggle_text = toggle.read_text(encoding="utf-8") if toggle.exists() else ""

# Public schema surface
assert "precision_report" in schema_text
assert "wave_correction_report:" not in schema_text

# Public endpoint sanitizer installation
assert "_v123a_public_precision_report" in endpoint_text
assert "_v123a_sanitize_simulation_response_public" in endpoint_text
assert '"schema_version": "aquanova.precision_report.v123"' in endpoint_text
assert "return _v123a_sanitize_simulation_response_public(" in endpoint_text

# Public frontend names
if types.exists():
    assert "precision_report" in types_text
    assert "wave_correction_report" not in types_text

if runner.exists():
    assert "precision_mode_enabled" in runner_text
    assert "engine_mode" in runner_text

if toggle.exists():
    assert "AquaNova 정밀 모드" in toggle_text
    assert "data-aquanova-precision-toggle" in toggle_text
    assert "WAVE 보정 모드" not in toggle_text

# Sanitizer source should strip internal fields from the public precision_report.
helper_region_start = endpoint_text.find("def _v123a_public_precision_report")
assert helper_region_start >= 0
helper_region = endpoint_text[helper_region_start: endpoint_text.find("def _v123a_sanitize_simulation_response_public", helper_region_start)]
assert "runtime_bridge" not in helper_region
assert "options" not in helper_region
assert "model_id" not in helper_region
assert "path" not in helper_region

print("V123C public precision report sanitizer selftest PASS")
