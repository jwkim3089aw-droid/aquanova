#!/usr/bin/env python3
"""Compatibility facade for wave_batch.

V128 moved the previous implementation to ``wave_batch_legacy.py`` so the
public import path remains stable while batch logic can be split safely in
later refactors.

Do not add new logic here. New batch code should go under
``scripts/wave_records/batch/`` and be re-exported deliberately.
"""
from __future__ import annotations

import importlib
import runpy
from pathlib import Path
from types import ModuleType


def _import_legacy() -> ModuleType:
    try:
        return importlib.import_module("wave_batch_legacy")
    except ImportError:
        if __package__:
            return importlib.import_module(f"{__package__}.wave_batch_legacy")
        raise


def _export_public(mod: ModuleType) -> list[str]:
    exported: list[str] = []
    for name in dir(mod):
        if name.startswith("__") and name.endswith("__"):
            continue
        globals()[name] = getattr(mod, name)
        exported.append(name)
    return sorted(exported)


if __name__ == "__main__":
    # Preserve old behavior when somebody directly runs wave_batch.py.
    runpy.run_path(str(Path(__file__).with_name("wave_batch_legacy.py")), run_name="__main__")
else:
    _legacy = _import_legacy()
    __all__ = _export_public(_legacy)
