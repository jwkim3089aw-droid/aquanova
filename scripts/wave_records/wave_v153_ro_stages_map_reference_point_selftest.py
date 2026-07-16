#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import ast
import importlib
import json
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[2]
wr = ROOT / "scripts" / "wave_records"
legacy = wr / "wave_ro_engine_legacy.py"
wrapper = wr / "wave_ro_engine.py"
stages = wr / "ro" / "stages.py"
manifest = wr / "ro" / "v153_ro_stages_map_reference_point_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_map_reference_point"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V153_RO_STAGES_IMPORT_START",
    "# V152_RO_STAGES_IMPORT_START",
    "# V151_RO_STAGES_IMPORT_START",
    "# V150_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V140_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_map_reference_point" in lt, "_map_reference_point must still be imported/re-exported by legacy"
assert "# V153_RO_STAGES_MAP_REFERENCE_POINT_APPLIED" in st
assert "def _map_reference_point(" not in lt
assert "def _map_reference_point(" in st

strategy = data.get("constant_strategy")
assert strategy in {"assignments", "imports", "lazy_getters"}, data
if strategy == "assignments":
    copied = set(data.get("copied_constants", []))
    assert {"REFERENCE_WIDTH", "REFERENCE_HEIGHT"} <= copied, data
elif strategy == "imports":
    deps = set(data.get("explicit_import_dependencies", []))
    assert {"REFERENCE_WIDTH", "REFERENCE_HEIGHT"} <= deps, data
elif strategy == "lazy_getters":
    refs = set(data.get("lazy_getter_refs", []))
    assert {"REFERENCE_WIDTH", "REFERENCE_HEIGHT"} <= refs, data
    assert "def _legacy_reference_width(" in st
    assert "def _legacy_reference_height(" in st
    assert "_legacy_reference_width()" in st
    assert "_legacy_reference_height()" in st

bridges = set(data.get("bridged_legacy_refs", []))
assert "_get_window_rect" in bridges, data
assert "def _get_window_rect(" in st
assert "getattr(_legacy, '_get_window_rect')" in st

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_map_reference_point")
assert hasattr(wave_ro_engine, "_stage_cell_point")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_map_reference_point")
assert hasattr(mod, "_stage_cell_point")
assert hasattr(mod, "_get_window_rect")

print("V153C RO stages map-reference-point extraction selftest PASS")
print("moved_count=1")
print("constant_strategy=" + str(strategy))
print("copied_constants=" + ",".join(data.get("copied_constants", [])))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("lazy_getter_refs=" + ",".join(data.get("lazy_getter_refs", [])))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
