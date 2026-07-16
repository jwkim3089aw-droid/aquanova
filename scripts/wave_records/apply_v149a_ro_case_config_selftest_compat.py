#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT_REL = Path("scripts") / "wave_records"
TARGETS = [
    (
        ROOT_REL / "wave_v142_ro_case_config_capture_state_selftest.py",
        "# V149A_CAPTURE_STATE_SELFTEST_COMPAT_APPLIED",
        '#!/usr/bin/env python3\n# V149A_CAPTURE_STATE_SELFTEST_COMPAT_APPLIED\nfrom __future__ import annotations\n\nfrom pathlib import Path\nimport ast\nimport importlib\nimport json\nimport py_compile\nimport sys\n\nROOT = Path(__file__).resolve().parents[2]\nwr = ROOT / "scripts" / "wave_records"\nlegacy = wr / "wave_ro_engine_legacy.py"\nwrapper = wr / "wave_ro_engine.py"\ncase_config = wr / "ro" / "case_config.py"\nmanifest = wr / "ro" / "v142_ro_case_config_capture_state_manifest.json"\n\nfor p in [legacy, wrapper, case_config]:\n    assert p.exists(), p\n    py_compile.compile(str(p), doraise=True)\n    ast.parse(p.read_text(encoding="utf-8"))\n\nassert manifest.exists(), manifest\ndata = json.loads(manifest.read_text(encoding="utf-8"))\nmoved = data["moved_functions"]\nassert moved == ["_capture_case_ro_state"], moved\n\nlt = legacy.read_text(encoding="utf-8")\nct = case_config.read_text(encoding="utf-8")\n\ncompatible_import_markers = [\n    "# V142_RO_CASE_CONFIG_IMPORT_START",\n    "# V143_RO_CASE_CONFIG_IMPORT_START",\n    "# V143A_RO_CASE_CONFIG_IMPORT_START",\n    "# V149_RO_CASE_CONFIG_IMPORT_START",\n]\nassert any(marker in lt for marker in compatible_import_markers), compatible_import_markers\nassert "_capture_case_ro_state" in lt, "_capture_case_ro_state must still be imported/re-exported by legacy"\nassert "# V142_RO_CASE_CONFIG_CAPTURE_STATE_APPLIED" in ct\nassert "def _capture_case_ro_state(" not in lt\nassert "def _capture_case_ro_state(" in ct\n\nif "_ro_diagnostic_points" in data.get("known_ro_dependencies", []):\n    assert "from ro.membrane import _ro_diagnostic_points" in ct or "from .membrane import _ro_diagnostic_points" in ct\nif "capture_ro_state" in data.get("explicit_import_dependencies", []):\n    assert "capture_ro_state" in ct\n\nsys.path.insert(0, str(wr))\nimport wave_ro_engine  # type: ignore\nassert hasattr(wave_ro_engine, "_capture_case_ro_state")\nassert hasattr(wave_ro_engine, "configure_schema_ro_case")\n\nmod = importlib.import_module("ro.case_config")\nassert hasattr(mod, "_capture_case_ro_state")\n\nprint("V149A/V142-compatible RO case_config capture-state selftest PASS")\nprint("moved_count=1")\nprint("known_ro_dependencies=" + ",".join(data.get("known_ro_dependencies", [])))\nprint("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))\n',
    ),
    (
        ROOT_REL / "wave_v143a_ro_case_config_verify_inputs_selftest.py",
        "# V149A_VERIFY_INPUTS_SELFTEST_COMPAT_APPLIED",
        '#!/usr/bin/env python3\n# V149A_VERIFY_INPUTS_SELFTEST_COMPAT_APPLIED\nfrom __future__ import annotations\n\nfrom pathlib import Path\nimport ast\nimport importlib\nimport json\nimport py_compile\nimport sys\n\nROOT = Path(__file__).resolve().parents[2]\nwr = ROOT / "scripts" / "wave_records"\nlegacy = wr / "wave_ro_engine_legacy.py"\nwrapper = wr / "wave_ro_engine.py"\ncase_config = wr / "ro" / "case_config.py"\nmanifest = wr / "ro" / "v143a_ro_case_config_verify_inputs_manifest.json"\n\nfor p in [legacy, wrapper, case_config]:\n    assert p.exists(), p\n    py_compile.compile(str(p), doraise=True)\n    ast.parse(p.read_text(encoding="utf-8"))\n\nassert manifest.exists(), manifest\ndata = json.loads(manifest.read_text(encoding="utf-8"))\nmoved = data["moved_functions"]\nassert moved == ["_verify_case_operating_inputs"], moved\n\nlt = legacy.read_text(encoding="utf-8")\nct = case_config.read_text(encoding="utf-8")\n\ncompatible_import_markers = [\n    "# V143A_RO_CASE_CONFIG_IMPORT_START",\n    "# V149_RO_CASE_CONFIG_IMPORT_START",\n]\nassert any(marker in lt for marker in compatible_import_markers), compatible_import_markers\nassert "_verify_case_operating_inputs" in lt, "_verify_case_operating_inputs must still be imported/re-exported by legacy"\nassert "# V143A_RO_CASE_CONFIG_VERIFY_INPUTS_APPLIED" in ct\nassert "def _verify_case_operating_inputs(" not in lt\nassert "def _verify_case_operating_inputs(" in ct\n\nfor ref in data.get("bridged_legacy_refs", []):\n    assert f"def {ref}(" in ct, f"legacy bridge missing for {ref}"\n\nfor dep in data.get("explicit_import_dependencies", []):\n    assert dep in ct, f"explicit import dependency missing: {dep}"\n\nsys.path.insert(0, str(wr))\nimport wave_ro_engine  # type: ignore\nassert hasattr(wave_ro_engine, "_verify_case_operating_inputs")\nassert hasattr(wave_ro_engine, "configure_schema_ro_case")\n\nmod = importlib.import_module("ro.case_config")\nassert hasattr(mod, "_verify_case_operating_inputs")\n\nprint("V149A/V143A-compatible RO case_config verify-inputs selftest PASS")\nprint("moved_count=1")\nprint("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))\nprint("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))\n',
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

        backup = path.with_suffix(path.suffix + ".v149a_compat.bak")
        if not backup.exists():
            backup.write_text(current, encoding="utf-8")

        path.write_text(content, encoding="utf-8")
        py_compile.compile(str(path), doraise=True)
        updated.append(str(path))

    print("V149A RO case_config selftest compatibility hotfix applied")
    for path in updated:
        print(f"updated={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
