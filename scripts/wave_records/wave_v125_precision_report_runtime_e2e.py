from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def fail(message: str) -> None:
    print(f"\nFAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    probe = ROOT / "scripts/wave_records/wave_v95_runtime_probe.py"

    print("=" * 80)
    print("V125 precision report runtime E2E")
    print("=" * 80)

    completed = subprocess.run(
        [PYTHON, str(probe), "--enable", "--print-json"],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    output = completed.stdout or ""
    print(output)

    if completed.returncode != 0:
        fail(f"V95 probe failed: returncode={completed.returncode}")

    json_start = output.find("{")
    if json_start < 0:
        fail("V95 probe JSON output not found")

    try:
        payload = json.loads(output[json_start:])
    except json.JSONDecodeError as exc:
        fail(f"V95 probe JSON parse failed: {exc}")

    raw_report = payload.get("report")
    if not isinstance(raw_report, dict):
        fail("runtime report is missing")

    from app.api.v1.endpoints.simulation import (
        _v123a_public_precision_report,
        _v123a_sanitize_simulation_response_public,
    )

    public_report = _v123a_public_precision_report(raw_report)

    expected_keys = {
        "schema_version",
        "enabled",
        "mode",
        "status",
        "applied_count",
        "skipped_count",
        "process_type",
        "scope",
        "corrections",
    }

    if set(public_report) != expected_keys:
        fail(
            "public report keys mismatch\n"
            f"expected={sorted(expected_keys)}\n"
            f"actual={sorted(public_report)}"
        )

    if public_report["schema_version"] != "aquanova.precision_report.v123":
        fail("public schema version mismatch")

    if public_report["enabled"] is not True:
        fail("precision report should be enabled")

    if public_report["mode"] != "precision":
        fail("precision report mode should be precision")

    if public_report["status"] != "corrected":
        fail(f"unexpected precision status: {public_report['status']}")

    if public_report["applied_count"] != 2:
        fail(
            "expected two applied corrections, "
            f"actual={public_report['applied_count']}"
        )

    corrections = public_report.get("corrections")
    if not isinstance(corrections, list) or not corrections:
        fail("public corrections are missing")

    allowed_correction_keys = {
        "metric",
        "status",
        "raw_value",
        "corrected_value",
    }

    for index, correction in enumerate(corrections):
        if set(correction) != allowed_correction_keys:
            fail(
                f"correction[{index}] has unexpected keys: "
                f"{sorted(correction)}"
            )

    public_text = json.dumps(
        public_report,
        ensure_ascii=False,
        sort_keys=True,
    )

    forbidden_terms = [
        "model_id",
        "runtime_bridge",
        "options",
        "guard_reason",
        "blocked_corrected_value",
        "stage_index",
        "engine_integration_schema_version",
        "wave_runtime_correction",
        "wave_corrected_engine",
    ]

    leaked = [term for term in forbidden_terms if term in public_text]
    if leaked:
        fail(f"internal fields leaked into public report: {leaked}")

    response = {
        "scenario_id": "v125-test",
        "precision_report": raw_report,
    }

    sanitized = _v123a_sanitize_simulation_response_public(response)

    if "precision_report" not in sanitized:
        fail("sanitizer removed precision_report")

    if sanitized["precision_report"] != public_report:
        fail("response sanitizer result does not match public report")

    corrected_metrics = [
        item["metric"]
        for item in public_report["corrections"]
        if item["status"] == "corrected"
    ]

    print("\n" + "#" * 80)
    print("V125 FINAL SUMMARY")
    print("#" * 80)
    print(f"status={public_report['status']}")
    print(f"applied_count={public_report['applied_count']}")
    print(f"skipped_count={public_report['skipped_count']}")
    print(f"corrected_metrics={corrected_metrics}")
    print("internal_field_leak=0")
    print("precision_report_retained=True")
    print("\nV125 precision report runtime E2E PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
