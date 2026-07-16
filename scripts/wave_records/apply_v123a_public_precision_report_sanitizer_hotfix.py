#!/usr/bin/env python3
from __future__ import annotations

import re
import py_compile
from pathlib import Path

HELPER_MARK = "# --- V123A public precision report sanitizer ---"

HELPER_CODE = '''
# --- V123A public precision report sanitizer ---
def _v123a_public_precision_report(report):
    if not isinstance(report, dict):
        return report

    corrections = []
    for item in report.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        corrections.append({
            "metric": item.get("metric"),
            "status": item.get("status"),
            "raw_value": item.get("raw_value"),
            "corrected_value": item.get("corrected_value"),
        })

    return {
        "schema_version": "aquanova.precision_report.v123",
        "enabled": bool(report.get("enabled", False)),
        "mode": "precision" if report.get("enabled", False) else "raw",
        "status": report.get("status"),
        "applied_count": int(report.get("applied_count") or 0),
        "skipped_count": int(report.get("skipped_count") or 0),
        "process_type": report.get("process_type"),
        "scope": report.get("regime") or report.get("scope"),
        "corrections": corrections,
    }


def _v123a_sanitize_simulation_response_public(obj):
    if obj is None:
        return obj

    if isinstance(obj, dict):
        if "precision_report" in obj:
            obj["precision_report"] = _v123a_public_precision_report(obj.get("precision_report"))
        obj.pop("wave_correction_report", None)
        return obj

    try:
        if hasattr(obj, "precision_report"):
            obj.precision_report = _v123a_public_precision_report(getattr(obj, "precision_report", None))
    except Exception:
        pass

    try:
        if hasattr(obj, "wave_correction_report"):
            setattr(obj, "wave_correction_report", None)
    except Exception:
        pass

    return obj
'''


def backup(path: Path) -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + ".v123_before_v123a.bak")
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def remove_broken_v123_script(root: Path) -> str:
    path = root / "scripts/wave_records/apply_v123_public_precision_report_sanitizer.py"
    if path.exists():
        backup(path)
        return "OK old broken V123 script backed up/superseded"
    return "OK no old V123 script"


def patch_schema(root: Path) -> str:
    path = root / "app/schemas/simulation.py"
    if not path.exists():
        return "SKIP schema missing"
    backup(path)
    text = path.read_text(encoding="utf-8")
    old = text

    text = re.sub(r"^\s*wave_correction_report\s*:\s*[^\n]+\n", "", text, flags=re.M)

    if "precision_report" not in text:
        m = re.search(r"class\s+ScenarioOutput[^\n]*:\s*\n", text)
        if m:
            text = text[:m.end()] + "    precision_report: Optional[Dict[str, Any]] = None\n" + text[m.end():]

    if "precision_report" in text and "Dict" not in text:
        text = text.replace("from typing import ", "from typing import Dict, ", 1)
    if "precision_report" in text and "Any" not in text:
        text = text.replace("from typing import ", "from typing import Any, ", 1)

    path.write_text(text, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    return "PATCHED schema public legacy field removed" if text != old else "OK schema already clean"


def insert_helper(text: str) -> str:
    if HELPER_MARK in text or "_v123a_public_precision_report" in text:
        return text
    imports = list(re.finditer(r"^(?:from|import)\s+.*$", text, flags=re.M))
    if imports:
        pos = imports[-1].end()
        return text[:pos] + "\n\n" + HELPER_CODE.strip() + "\n" + text[pos:]
    return HELPER_CODE.strip() + "\n\n" + text


def add_exclude_none(text: str) -> str:
    def repl(m):
        block = m.group(0)
        if "response_model_exclude_none" in block:
            return block
        return block[:-1] + ", response_model_exclude_none=True)"
    return re.sub(r"@router\.(?:post|get|put|patch)\([^\n]*response_model\s*=\s*ScenarioOutput[^\n]*\)", repl, text)


def wrap_returns_in_run_simulation(text: str) -> str:
    m = re.search(
        r"((?:@router\.[^\n]*\n)+\s*(?:async\s+def|def)\s+run_simulation\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\n)",
        text,
    )
    if not m:
        for name in ["output", "result", "response", "scenario_output", "simulation_output"]:
            text = re.sub(
                rf"return\s+{name}\b",
                f"return _v123a_sanitize_simulation_response_public({name})",
                text,
            )
        return text

    start = m.end()
    next_marks = [
        idx for idx in [
            text.find("\n@router.", start),
            text.find("\nasync def ", start),
            text.find("\ndef ", start),
        ]
        if idx != -1
    ]
    end = min(next_marks) if next_marks else len(text)
    body = text[start:end]

    def repl(ret):
        indent = ret.group(1)
        expr = ret.group(2).strip()
        if expr.startswith("_v123a_sanitize_simulation_response_public("):
            return ret.group(0)
        if expr.startswith(("JSONResponse", "FileResponse", "StreamingResponse", "Response", "RedirectResponse")):
            return ret.group(0)
        if expr in {"None", "True", "False"}:
            return ret.group(0)
        return f"{indent}return _v123a_sanitize_simulation_response_public({expr})"

    body2 = re.sub(r"^(\s*)return\s+([^\n#]+)", repl, body, flags=re.M)
    return text[:start] + body2 + text[end:]


def patch_endpoint(root: Path) -> str:
    path = root / "app/api/v1/endpoints/simulation.py"
    if not path.exists():
        return "SKIP endpoint missing"
    backup(path)
    text = path.read_text(encoding="utf-8")
    old = text

    text = text.replace("HELPER = r\n", "")
    text = insert_helper(text)
    text = add_exclude_none(text)
    text = wrap_returns_in_run_simulation(text)
    text = text.replace("wave_correction_report", "precision_report")

    path.write_text(text, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    return "PATCHED endpoint public sanitizer" if text != old else "OK endpoint already sanitized"


def patch_frontend_types(root: Path) -> str:
    path = root / "ui/src/api/types.ts"
    if not path.exists():
        return "SKIP frontend types missing"
    backup(path)
    text = path.read_text(encoding="utf-8")
    old = text
    text = re.sub(r"^\s*wave_correction_report\??\s*:\s*[^;\n]+;?\n?", "", text, flags=re.M)
    if "precision_report" not in text:
        text = re.sub(
            r"(export\s+interface\s+ScenarioOutput\s*\{)",
            r"\1\n  precision_report?: Record<string, unknown> | null;",
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")
    return "PATCHED frontend types" if text != old else "OK frontend types already clean"


def main() -> int:
    root = Path.cwd().resolve()
    messages = [
        remove_broken_v123_script(root),
        patch_schema(root),
        patch_endpoint(root),
        patch_frontend_types(root),
    ]
    print("V123A public precision report sanitizer hotfix applied")
    for msg in messages:
        print(msg)
    print()
    print("Expected after rerun:")
    print("- no public wave_correction_report field")
    print("- precision_report.schema_version = aquanova.precision_report.v123")
    print("- no runtime_bridge/options/model_id/path in public precision_report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
