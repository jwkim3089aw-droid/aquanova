#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WRAPPER = '#!/usr/bin/env python3\n"""Compatibility facade for wave_batch.\n\nV128 moved the previous implementation to ``wave_batch_legacy.py`` so the\npublic import path remains stable while batch logic can be split safely in\nlater refactors.\n\nDo not add new logic here. New batch code should go under\n``scripts/wave_records/batch/`` and be re-exported deliberately.\n"""\nfrom __future__ import annotations\n\nimport importlib\nimport runpy\nfrom pathlib import Path\nfrom types import ModuleType\n\n\ndef _import_legacy() -> ModuleType:\n    try:\n        return importlib.import_module("wave_batch_legacy")\n    except ImportError:\n        if __package__:\n            return importlib.import_module(f"{__package__}.wave_batch_legacy")\n        raise\n\n\ndef _export_public(mod: ModuleType) -> list[str]:\n    exported: list[str] = []\n    for name in dir(mod):\n        if name.startswith("__") and name.endswith("__"):\n            continue\n        globals()[name] = getattr(mod, name)\n        exported.append(name)\n    return sorted(exported)\n\n\nif __name__ == "__main__":\n    # Preserve old behavior when somebody directly runs wave_batch.py.\n    runpy.run_path(str(Path(__file__).with_name("wave_batch_legacy.py")), run_name="__main__")\nelse:\n    _legacy = _import_legacy()\n    __all__ = _export_public(_legacy)\n'
BATCH_INIT = '"""Batch automation package.\n\nV128 introduces this package as the future home for production-plan, resume,\nartifact, retry, and runner code.\n\nThe existing implementation is intentionally preserved in\n``wave_batch_legacy.py`` and re-exported through ``wave_batch.py`` first.\nLater patches should move one behavior group at a time from legacy into this\npackage while keeping tests green.\n"""\n'
README = '# Batch refactor package\n\nV128 created this package as the target for gradually splitting\n`scripts/wave_records/wave_batch_legacy.py`.\n\nPlanned split:\n\n```text\nbatch/\n  plan_schema.py   # production-plan and row schema parsing\n  resume.py        # run-state, resume markers, completed-case checks\n  artifacts.py     # PDF/log/output naming and validation helpers\n  retries.py       # retry policy and failure classification\n  runner.py        # orchestration entrypoints\n```\n\nCurrent state:\n- `wave_batch.py` is a compatibility facade.\n- `wave_batch_legacy.py` contains the previous full implementation.\n- No behavior should change in V128.\n'
STUBS = {'plan_schema.py': '"""Planned home for batch plan schema parsing. V128 scaffold only."""\n', 'resume.py': '"""Planned home for batch resume/checkpoint logic. V128 scaffold only."""\n', 'artifacts.py': '"""Planned home for batch output artifact naming/validation. V128 scaffold only."""\n', 'retries.py': '"""Planned home for batch retry/failure policy. V128 scaffold only."""\n', 'runner.py': '"""Planned home for batch orchestration. V128 scaffold only."""\n'}


def backup(path: Path) -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + ".v127_before_v128.bak")
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    root = Path.cwd().resolve()
    wave_records = root / "scripts" / "wave_records"
    src = wave_records / "wave_batch.py"
    legacy = wave_records / "wave_batch_legacy.py"
    pkg = wave_records / "batch"

    if not src.exists():
        raise SystemExit(f"not found: {src}")

    text = src.read_text(encoding="utf-8")
    already_facade = "Compatibility facade for wave_batch" in text and legacy.exists()

    if already_facade:
        print("V128 already applied: wave_batch.py is already a facade")
    else:
        backup(src)
        if legacy.exists():
            raise SystemExit(f"Refusing to overwrite existing legacy file: {legacy}")
        legacy.write_text(text, encoding="utf-8")
        src.write_text(WRAPPER, encoding="utf-8")
        print(f"Moved implementation: {src.relative_to(root)} -> {legacy.relative_to(root)}")
        print(f"Installed facade: {src.relative_to(root)}")

    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(BATCH_INIT, encoding="utf-8")
    (pkg / "README_REFACTOR.md").write_text(README, encoding="utf-8")
    for name, content in STUBS.items():
        p = pkg / name
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    print("V128 batch facade split applied")
    print("Behavior target: no runtime behavior change; public wave_batch import path preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
