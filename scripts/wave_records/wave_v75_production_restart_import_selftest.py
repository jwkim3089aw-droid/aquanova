#!/usr/bin/env python3
"""V75 guard for V73/V74 split production restart imports.

This catches the exact regression where wave_production_restart referenced
_production_family after the V73 module split but did not import it.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace


def main() -> int:
    restart = importlib.import_module("wave_production_restart")
    plan = importlib.import_module("wave_production_plan")

    fn = getattr(restart, "_production_family", None)
    assert fn is plan._production_family, "wave_production_restart must import plan._production_family"
    assert fn(SimpleNamespace(kind="ro_excel")) == "ro_nf"
    assert fn(SimpleNamespace(kind="uf_video")) == "uf"
    assert fn(SimpleNamespace(kind="ccro_video")) == "ccro"

    # Also import the public runner so circular-import mistakes surface early.
    importlib.import_module("wave_production")

    print("V75 production restart import selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
