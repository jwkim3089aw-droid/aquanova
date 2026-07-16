#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT_REL = Path("scripts") / "wave_records"
TARGETS = [
    (
        ROOT_REL / "wave_v140_ro_stages_stage_grid_points_selftest.py",
        "# V148A_STAGE_GRID_POINTS_SELFTEST_COMPAT_APPLIED",
        '#!/usr/bin/env python3\n# V148A_STAGE_GRID_POINTS_SELFTEST_COMPAT_APPLIED\nfrom __future__ import annotations\n\nfrom pathlib import Path\nimport ast\nimport importlib\nimport json\nimport py_compile\nimport sys\n\nROOT = Path(__file__).resolve().parents[2]\nwr = ROOT / "scripts" / "wave_records"\nlegacy = wr / "wave_ro_engine_legacy.py"\nwrapper = wr / "wave_ro_engine.py"\nstages = wr / "ro" / "stages.py"\nmanifest = wr / "ro" / "v140_ro_stages_stage_grid_points_manifest.json"\n\nfor p in [legacy, wrapper, stages]:\n    assert p.exists(), p\n    py_compile.compile(str(p), doraise=True)\n    ast.parse(p.read_text(encoding="utf-8"))\n\nassert manifest.exists(), manifest\ndata = json.loads(manifest.read_text(encoding="utf-8"))\nmoved = data["moved_functions"]\nassert moved == ["_stage_grid_points"], moved\n\nlt = legacy.read_text(encoding="utf-8")\nst = stages.read_text(encoding="utf-8")\n\ncompatible_import_markers = [\n    "# V140_RO_STAGES_IMPORT_START",\n    "# V145_RO_STAGES_IMPORT_START",\n    "# V145A_RO_STAGES_IMPORT_START",\n    "# V148_RO_STAGES_IMPORT_START",\n]\nassert any(marker in lt for marker in compatible_import_markers), compatible_import_markers\nassert "_stage_grid_points" in lt, "_stage_grid_points must still be imported/re-exported by legacy"\nassert "# V140_RO_STAGES_STAGE_GRID_POINTS_APPLIED" in st\nassert "def _stage_grid_points(" not in lt\nassert "def _stage_grid_points(" in st\n\nfor ref in data.get("bridged_legacy_refs", []):\n    assert f"def {ref}(" in st, f"bridge missing for {ref}"\n\nsys.path.insert(0, str(wr))\nimport wave_ro_engine  # type: ignore\nassert hasattr(wave_ro_engine, "_stage_grid_points")\nassert hasattr(wave_ro_engine, "configure_schema_ro_case")\n\nmod = importlib.import_module("ro.stages")\nassert hasattr(mod, "_stage_grid_points")\n\nprint("V148A/V140-compatible RO stages stage-grid-points selftest PASS")\nprint("moved_count=1")\nprint("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))\n',
    ),
    (
        ROOT_REL / "wave_v145a_ro_stages_stabilize_after_flow_commit_selftest.py",
        "# V148A_STABILIZE_SELFTEST_COMPAT_APPLIED",
        '#!/usr/bin/env python3\n# V148A_STABILIZE_SELFTEST_COMPAT_APPLIED\nfrom __future__ import annotations\n\nfrom pathlib import Path\nimport ast\nimport importlib\nimport json\nimport py_compile\nimport sys\n\nROOT = Path(__file__).resolve().parents[2]\nwr = ROOT / "scripts" / "wave_records"\nlegacy = wr / "wave_ro_engine_legacy.py"\nwrapper = wr / "wave_ro_engine.py"\nstages = wr / "ro" / "stages.py"\nmanifest = wr / "ro" / "v145a_ro_stages_stabilize_after_flow_commit_manifest.json"\n\nfor p in [legacy, wrapper, stages]:\n    assert p.exists(), p\n    py_compile.compile(str(p), doraise=True)\n    ast.parse(p.read_text(encoding="utf-8"))\n\nassert manifest.exists(), manifest\ndata = json.loads(manifest.read_text(encoding="utf-8"))\nmoved = data["moved_functions"]\nassert moved == ["_stabilize_after_flow_commit"], moved\n\nlt = legacy.read_text(encoding="utf-8")\nst = stages.read_text(encoding="utf-8")\n\ncompatible_import_markers = [\n    "# V145A_RO_STAGES_IMPORT_START",\n    "# V148_RO_STAGES_IMPORT_START",\n]\nassert any(marker in lt for marker in compatible_import_markers), compatible_import_markers\nassert "_stabilize_after_flow_commit" in lt, "_stabilize_after_flow_commit must still be imported/re-exported by legacy"\nassert "# V145A_RO_STAGES_STABILIZE_AFTER_FLOW_COMMIT_APPLIED" in st\nassert "def _stabilize_after_flow_commit(" not in lt\nassert "def _stabilize_after_flow_commit(" in st\n\nfor ref in data.get("bridged_case_config_refs", []):\n    assert f"def {ref}(" in st, f"case_config bridge missing for {ref}"\nassert "_verify_case_operating_inputs" in data.get("bridged_case_config_refs", []), data\n\nfor ref in data.get("bridged_legacy_refs", []):\n    assert f"def {ref}(" in st, f"legacy bridge missing for {ref}"\n\nsys.path.insert(0, str(wr))\nimport wave_ro_engine  # type: ignore\nassert hasattr(wave_ro_engine, "_stabilize_after_flow_commit")\nassert hasattr(wave_ro_engine, "configure_schema_ro_case")\n\nmod = importlib.import_module("ro.stages")\nassert hasattr(mod, "_stabilize_after_flow_commit")\nassert hasattr(mod, "_verify_case_operating_inputs")\n\nprint("V148A/V145A-compatible RO stages stabilize-after-flow selftest PASS")\nprint("moved_count=1")\nprint("bridged_case_config_refs=" + ",".join(data.get("bridged_case_config_refs", [])))\nprint("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))\n',
    ),
]


def main() -> int:
    root = Path.cwd().resolve()
    updated = []

    for rel, marker, content in TARGETS:
        path = root / rel
        if not path.exists():
            raise SystemExit(f"selftest not found: {path}")

        current = path.read_text(encoding="utf-8", errors="ignore")
        if marker in current:
            print(f"already compatible: {path}")
            continue

        backup = path.with_suffix(path.suffix + ".v148a_compat.bak")
        if not backup.exists():
            backup.write_text(current, encoding="utf-8")

        path.write_text(content, encoding="utf-8")
        py_compile.compile(str(path), doraise=True)
        updated.append(str(path))

    print("V148A RO stages selftest compatibility hotfix applied")
    for path in updated:
        print(f"updated={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
