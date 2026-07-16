#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile
import re

ROOT = Path(__file__).resolve().parents[2]

schema = ROOT / "app/schemas/simulation.py"
endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
types = ROOT / "ui/src/api/types.ts"

for p in [schema, endpoint]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)

st = schema.read_text(encoding="utf-8")
assert "precision_report" in st
assert "wave_correction_report:" not in st

et = endpoint.read_text(encoding="utf-8")
assert "_v123a_public_precision_report" in et
assert "_v123a_sanitize_simulation_response_public" in et
assert "aquanova.precision_report.v123" in et

if types.exists():
    tt = types.read_text(encoding="utf-8")
    assert "precision_report" in tt
    assert "wave_correction_report" not in tt

# Extract the two V123A helper functions robustly.
start = et.index("def _v123a_public_precision_report")
end = et.index("\n\n\ndef ", et.index("def _v123a_sanitize_simulation_response_public")) if "\n\n\ndef " in et[et.index("def _v123a_sanitize_simulation_response_public"):] else None
if end is None:
    # Fall back: cut before the next router decorator or endpoint definition.
    tail_start = et.index("def _v123a_sanitize_simulation_response_public")
    candidates = []
    for marker in ["\n@router.", "\nasync def run_", "\ndef run_"]:
        idx = et.find(marker, tail_start + 20)
        if idx != -1:
            candidates.append(idx)
    end = min(candidates) if candidates else len(et)

helper_text = et[start:end]
ns: dict[str, object] = {}
exec(helper_text, ns)

raw = {
    "schema_version": "aquanova.wave_runtime_correction.v118",
    "runtime_bridge": "v95_opt_in_simulation_engine",
    "enabled": True,
    "options": {"wave_correction_enabled": False},
    "applied_count": 0,
    "skipped_count": 4,
    "process_type": "ccro",
    "regime": "ccro_other",
    "status": "guarded_no_runtime_corrections_applied",
    "corrections": [
        {
            "metric": "feed_pressure",
            "model_id": "abc",
            "path": "stage_metrics.0.p_in_bar",
            "status": "no_model",
            "raw_value": 30.41,
            "corrected_value": 30.41,
        }
    ],
}
clean = ns["_v123a_public_precision_report"](raw)

assert clean["schema_version"] == "aquanova.precision_report.v123"
assert clean["scope"] == "ccro_other"
assert clean["enabled"] is True
assert clean["applied_count"] == 0
assert "runtime_bridge" not in clean
assert "options" not in clean
assert "model_id" not in clean["corrections"][0]
assert "path" not in clean["corrections"][0]

public_text = str(clean)
assert "wave_runtime" not in public_text
assert "wave_correction" not in public_text
assert "runtime_bridge" not in public_text

print("V123B public precision report sanitizer selftest PASS")
