#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

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
assert "response_model_exclude_none=True" in et or "response_model" not in et

if types.exists():
    tt = types.read_text(encoding="utf-8")
    assert "precision_report" in tt
    assert "wave_correction_report" not in tt

ns = {}
helper_start = et.index("# --- V123A public precision report sanitizer ---")
helper_text = et[helper_start:]
cut_candidates = []
for marker in ["\n@router.", "\nasync def ", "\ndef "]:
    idx = helper_text.find(marker, 10)
    if idx != -1:
        cut_candidates.append(idx)
helper_text = helper_text[: min(cut_candidates)] if cut_candidates else helper_text
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
        {"metric": "feed_pressure", "model_id": "abc", "path": "stage_metrics.0.p_in_bar", "status": "no_model", "raw_value": 30.41, "corrected_value": 30.41}
    ],
}
clean = ns["_v123a_public_precision_report"](raw)
assert clean["schema_version"] == "aquanova.precision_report.v123"
assert clean["scope"] == "ccro_other"
assert "runtime_bridge" not in clean
assert "options" not in clean
assert "model_id" not in clean["corrections"][0]
assert "path" not in clean["corrections"][0]

print("V123A public precision report sanitizer selftest PASS")
