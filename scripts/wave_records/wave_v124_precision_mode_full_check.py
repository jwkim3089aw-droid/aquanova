from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

checks = []
failed = []


def run_check(name: str, cmd, cwd: Path | None = None, shell: bool = False, must_contain: list[str] | None = None):
    print("\n" + "=" * 80)
    print(f"[CHECK] {name}")
    print("=" * 80)

    p = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        shell=shell,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    out = p.stdout or ""
    print(out)

    ok = p.returncode == 0
    if must_contain:
        ok = ok and all(s in out for s in must_contain)

    checks.append((name, ok))

    if not ok:
        failed.append(name)

    print(f"[RESULT] {name}: {'PASS' if ok else 'FAIL'}")
    return ok, out


def static_check(name: str, path: Path, required: list[str], forbidden: list[str] | None = None):
    print("\n" + "=" * 80)
    print(f"[CHECK] {name}")
    print("=" * 80)

    text = path.read_text(encoding="utf-8")
    missing = [s for s in required if s not in text]
    bad = [s for s in (forbidden or []) if s in text]

    ok = not missing and not bad
    checks.append((name, ok))

    if not ok:
        failed.append(name)

    if missing:
        print("missing:", missing)
    if bad:
        print("forbidden:", bad)

    print(f"[RESULT] {name}: {'PASS' if ok else 'FAIL'}")


def main() -> int:
    endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
    schema = ROOT / "app/schemas/simulation.py"
    runner = ROOT / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"

    run_check(
        "backend py_compile",
        [PY, "-m", "py_compile", str(endpoint)],
    )

    run_check(
        "V122 precision-mode rebrand selftest",
        [PY, str(ROOT / "scripts/wave_records/wave_v122_precision_mode_rebrand_selftest.py")],
        must_contain=["PASS"],
    )

    run_check(
        "V123C public precision report sanitizer selftest",
        [PY, str(ROOT / "scripts/wave_records/wave_v123c_public_precision_report_sanitizer_selftest.py")],
        must_contain=["PASS"],
    )

    run_check(
        "V94/V95/V97 runtime correction pytest",
        [
            PY,
            "-m",
            "pytest",
            "tests/test_wave_runtime_correction_v94.py",
            "tests/test_wave_engine_integration_v95.py",
            "tests/test_wave_runtime_guard_v97.py",
            "-p",
            "no:cacheprovider",
            "-q",
        ],
        must_contain=["100%"],
    )

    run_check(
        "V95 probe OFF should stay disabled",
        [PY, str(ROOT / "scripts/wave_records/wave_v95_runtime_probe.py"), "--print-json"],
        must_contain=["status=disabled", "applied_count=0"],
    )

    run_check(
        "V95 probe ON should apply correction",
        [PY, str(ROOT / "scripts/wave_records/wave_v95_runtime_probe.py"), "--enable", "--print-json"],
        must_contain=["status=corrected", "applied_count=2"],
    )

    static_check(
        "backend endpoint precision opt-in wiring",
        endpoint,
        required=[
            "precision_mode_enabled",
            "options={\"enable_wave_correction\": True}",
            "precision_report",
            "_v123a_public_precision_report",
        ],
        forbidden=[
            'obj.pop("precision_report", None)',
            'setattr(obj, "precision_report", None)',
        ],
    )

    static_check(
        "schema precision fields",
        schema,
        required=[
            "precision_mode_enabled",
            "engine_mode",
            "precision_report",
        ],
        forbidden=[
            "wave_correction_report:",
        ],
    )

    static_check(
        "frontend payload precision fields",
        runner,
        required=[
            "precision_mode_enabled",
            "engine_mode",
            "aquanova.precisionModeEnabled",
        ],
        forbidden=[
            "wave_correction_enabled:",
        ],
    )

    run_check(
        "frontend npm build",
        "npm run build",
        cwd=ROOT / "ui",
        shell=True,
        must_contain=["built in"],
    )

    print("\n" + "#" * 80)
    print("FINAL SUMMARY")
    print("#" * 80)

    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'} - {name}")

    if failed:
        print("\nFAILED CHECKS:")
        for name in failed:
            print(f"- {name}")
        return 1

    print("\nALL PASS")
    print("정밀 모드 / 보정 레이어 / 공개 precision_report / 프론트 빌드까지 통과했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

