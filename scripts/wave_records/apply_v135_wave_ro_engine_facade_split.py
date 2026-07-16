#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WRAPPER = '#!/usr/bin/env python3\n"""Compatibility facade for wave_ro_engine.\n\nV135 moved the previous implementation to ``wave_ro_engine_legacy.py`` so the\npublic import path remains stable while RO configuration logic can be split\nsafely in later refactors.\n\nDo not add new logic here. New RO automation code should go under\n``scripts/wave_records/ro/`` and be re-exported deliberately.\n"""\nfrom __future__ import annotations\n\nimport importlib\nimport runpy\nfrom pathlib import Path\nfrom types import ModuleType\n\n\ndef _import_legacy() -> ModuleType:\n    try:\n        return importlib.import_module("wave_ro_engine_legacy")\n    except ImportError:\n        if __package__:\n            return importlib.import_module(f"{__package__}.wave_ro_engine_legacy")\n        raise\n\n\ndef _export_public(mod: ModuleType) -> list[str]:\n    exported: list[str] = []\n    for name in dir(mod):\n        if name.startswith("__") and name.endswith("__"):\n            continue\n        globals()[name] = getattr(mod, name)\n        exported.append(name)\n    return sorted(exported)\n\n\nif __name__ == "__main__":\n    runpy.run_path(str(Path(__file__).with_name("wave_ro_engine_legacy.py")), run_name="__main__")\nelse:\n    _legacy = _import_legacy()\n    __all__ = _export_public(_legacy)\n'
RO_INIT = '"""RO automation package.\n\nV135 introduces this package as the future home for RO case configuration,\nfeedwater, membrane, stage/pass, chemical, and report orchestration code.\n\nCurrent state:\n- `wave_ro_engine.py` is a compatibility facade.\n- `wave_ro_engine_legacy.py` contains the previous full implementation.\n- Later patches should move one behavior group at a time from legacy into this package.\n"""\n'
README = '# RO refactor package\n\nV135 created this package as the target for gradually splitting\n`scripts/wave_records/wave_ro_engine_legacy.py`.\n\nPlanned split:\n\n```text\nro/\n  case_config.py      # schema case preparation and validation\n  feedwater.py        # feedwater/composition/temperature mode helpers\n  membrane.py         # membrane family/model selection helpers\n  stages.py           # stage/pass/vessel/element configuration\n  chemicals.py        # chemical adjustment helpers\n  reports.py          # report/export helpers\n  runner.py           # high-level configure/run entrypoints\n```\n\nCurrent state:\n- `wave_ro_engine.py` is a compatibility facade.\n- `wave_ro_engine_legacy.py` contains the previous full implementation.\n- No behavior should change in V135.\n'
STUBS = {'case_config.py': '"""Planned home for RO case config helpers. V135 scaffold only."""\n', 'feedwater.py': '"""Planned home for RO feedwater helpers. V135 scaffold only."""\n', 'membrane.py': '"""Planned home for RO membrane selection helpers. V135 scaffold only."""\n', 'stages.py': '"""Planned home for RO stage/pass configuration helpers. V135 scaffold only."""\n', 'chemicals.py': '"""Planned home for RO chemical adjustment helpers. V135 scaffold only."""\n', 'reports.py': '"""Planned home for RO report/export helpers. V135 scaffold only."""\n', 'runner.py': '"""Planned home for RO high-level runner helpers. V135 scaffold only."""\n'}


def backup(path: Path) -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + ".v134e_before_v135.bak")
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    root = Path.cwd().resolve()
    wave_records = root / "scripts" / "wave_records"
    src = wave_records / "wave_ro_engine.py"
    legacy = wave_records / "wave_ro_engine_legacy.py"
    pkg = wave_records / "ro"

    if not src.exists():
        raise SystemExit(f"not found: {src}")

    text = src.read_text(encoding="utf-8")
    already_facade = "Compatibility facade for wave_ro_engine" in text and legacy.exists()

    if already_facade:
        print("V135 already applied: wave_ro_engine.py is already a facade")
    else:
        backup(src)
        if legacy.exists():
            raise SystemExit(f"Refusing to overwrite existing legacy file: {legacy}")
        legacy.write_text(text, encoding="utf-8")
        src.write_text(WRAPPER, encoding="utf-8")
        print(f"Moved implementation: {src.relative_to(root)} -> {legacy.relative_to(root)}")
        print(f"Installed facade: {src.relative_to(root)}")

    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(RO_INIT, encoding="utf-8")
    (pkg / "README_REFACTOR.md").write_text(README, encoding="utf-8")
    for name, content in STUBS.items():
        p = pkg / name
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    print("V135 wave_ro_engine facade split applied")
    print("Behavior target: no runtime behavior change; public wave_ro_engine import path preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
