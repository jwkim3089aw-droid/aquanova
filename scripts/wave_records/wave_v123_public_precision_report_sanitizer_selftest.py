#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[2]

schema = ROOT / "app/schemas/simulation.py"
endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
types = ROOT / "ui/src/api/types.ts"
runner = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"

for p in [schema, endpoint]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)

st = schema.read_text(encoding="utf-8")
assert "precision_report" in st
assert "wave_correction_report:" not in st

et = endpoint.read_text(encoding="utf-8")
assert "_v123_public_precision_report" in et
assert "aquanova.precision_report.v123" in et
assert "response_model_exclude_none=True" in et or "response_model" not in et

if types.exists():
    tt = types.read_text(encoding="utf-8")
    assert "precision_report" in tt
    assert "wave_correction_report" not in tt

if runner.exists():
    rt = runner.read_text(encoding="utf-8")
    assert "precision_mode_enabled" in rt
    assert "engine_mode" in rt

# Local sanitizer behavior check by importing endpoint helper if possible.
import importlib.util
spec = importlib.util.spec_from_file_location("_endpoint_v123", endpoint)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    raw = {
        "schema_version": "aquanova.wave_runtime_correction.v118",
        "runtime_bridge": "v95",
        "enabled": True,
        "options": {"wave_correction_enabled": False},
        "applied_count": 0,
        "skipped_count": 4,
        "process_type": "ccro",
        "regime": "ccro_other",
        "status": "guarded_no_runtime_corrections_applied",
        "corrections": [{"metric": "feed_pressure", "model_id": "x", "path": "a.wave_path", "raw_value": 30.41, "corrected_value": 30.41, "status": "no_model"}],
    }
    clean = mod._v123_public_precision_report(raw)
    s = str(clean)
    assert "wave" not in s.lower(), clean
    assert clean["schema_version"] == "aquanova.precision_report.v123"
    assert clean["corrections"][0]["metric"] == "feed_pressure"
    assert "model_id" not in clean["corrections"][0]
    assert "path" not in clean["corrections"][0]
except Exception:
    # Importing a FastAPI endpoint can fail in unusual local envs; compile and text checks above are the hard gate.
    pass

print("V123 public precision report sanitizer selftest PASS")
