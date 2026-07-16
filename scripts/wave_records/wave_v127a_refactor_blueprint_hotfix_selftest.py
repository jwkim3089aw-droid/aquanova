#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile
import importlib.util
import tempfile

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "scripts" / "wave_records" / "aquanova_refactor_blueprint.py"

assert path.exists(), path
py_compile.compile(str(path), doraise=True)

spec = importlib.util.spec_from_file_location("_v127_blueprint", path)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "x.py"
    p.write_text("def hello():\n    return 1\n", encoding="utf-8")
    tree, err = mod.parse_ast(p)
    assert tree is not None
    assert err is None

    p2 = Path(td) / "bad.py"
    p2.write_text("def bad(:\n", encoding="utf-8")
    tree2, err2 = mod.parse_ast(p2)
    assert tree2 is None
    assert err2

print("V127A refactor blueprint hotfix selftest PASS")
