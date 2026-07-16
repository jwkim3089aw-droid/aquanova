#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

SELFTEST_REL = Path("scripts") / "wave_records" / "wave_v140_ro_stages_stage_grid_points_selftest.py"
MARKER = "# V140A_STAGE_GRID_POINTS_SELFTEST_COMPAT_APPLIED"

NEW_SELFTEST = '#!/usr/bin/env python3\n# V140A_STAGE_GRID_POINTS_SELFTEST_COMPAT_APPLIED\nfrom __future__ import annotations\n\nfrom pathlib import Path\nimport ast\nimport importlib\nimport json\nimport py_compile\nimport sys\n\nROOT = Path(__file__).resolve().parents[2]\nwr = ROOT / "scripts" / "wave_records"\nlegacy = wr / "wave_ro_engine_legacy.py"\nwrapper = wr / "wave_ro_engine.py"\nstages = wr / "ro" / "stages.py"\nmanifest = wr / "ro" / "v140_ro_stages_stage_grid_points_manifest.json"\n\nfor p in [legacy, wrapper, stages]:\n    assert p.exists(), p\n    py_compile.compile(str(p), doraise=True)\n    ast.parse(p.read_text(encoding="utf-8"))\n\nassert manifest.exists(), manifest\ndata = json.loads(manifest.read_text(encoding="utf-8"))\nmoved = data["moved_functions"]\nassert moved == ["_stage_grid_points"], moved\n\nlt = legacy.read_text(encoding="utf-8")\nst = stages.read_text(encoding="utf-8")\n\ncompatible_import_markers = [\n    "# V140_RO_STAGES_IMPORT_START",\n    "# V145_RO_STAGES_IMPORT_START",\n    "# V145A_RO_STAGES_IMPORT_START",\n]\nassert any(marker in lt for marker in compatible_import_markers), compatible_import_markers\nassert "_stage_grid_points" in lt, "_stage_grid_points must still be imported/re-exported by legacy"\nassert "# V140_RO_STAGES_STAGE_GRID_POINTS_APPLIED" in st\nassert "def _stage_grid_points(" not in lt\nassert "def _stage_grid_points(" in st\n\nfor ref in data.get("bridged_legacy_refs", []):\n    assert f"def {ref}(" in st, f"bridge missing for {ref}"\n\nsys.path.insert(0, str(wr))\nimport wave_ro_engine  # type: ignore\nassert hasattr(wave_ro_engine, "_stage_grid_points")\nassert hasattr(wave_ro_engine, "configure_schema_ro_case")\n\nmod = importlib.import_module("ro.stages")\nassert hasattr(mod, "_stage_grid_points")\n\nprint("V140A/V140-compatible RO stages stage-grid-points selftest PASS")\nprint("moved_count=1")\nprint("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))\n'


def main() -> int:
    root = Path.cwd().resolve()
    selftest = root / SELFTEST_REL
    if not selftest.exists():
        raise SystemExit(f"selftest not found: {selftest}")

    current = selftest.read_text(encoding="utf-8", errors="ignore")
    if MARKER in current and "V140A/V140-compatible" in current:
        print("V140A selftest compatibility hotfix already applied")
        return 0

    backup = selftest.with_suffix(selftest.suffix + ".v140a_compat.bak")
    if not backup.exists():
        backup.write_text(current, encoding="utf-8")

    selftest.write_text(NEW_SELFTEST, encoding="utf-8")
    py_compile.compile(str(selftest), doraise=True)

    print("V140A stage-grid-points selftest compatibility hotfix applied")
    print(f"updated={selftest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
