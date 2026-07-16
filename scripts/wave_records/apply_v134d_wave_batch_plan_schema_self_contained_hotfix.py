#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path

TARGET_FUNCTIONS = [
    "_canonical_temperature_mode",
    "_temperature_variant_suffix",
    "_clone_case_for_global_temperature",
    "expand_cases_for_wave_global_temperature",
]

IMPORT_MARKER_START = "# V131A_PLAN_SCHEMA_IMPORT_START"
IMPORT_MARKER_END = "# V131A_PLAN_SCHEMA_IMPORT_END"
PLAN_MARKER = "# V134D_PLAN_SCHEMA_SELF_CONTAINED_APPLIED"
MANIFEST_NAME = "v134d_plan_schema_self_contained_manifest.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def backup(path: Path, tag: str) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + f".{tag}.bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_segment(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1:end]) + "\n"


def remove_spans(lines: list[str], nodes: list[ast.AST]) -> str:
    spans = sorted(
        [(getattr(n, "lineno", 1), getattr(n, "end_lineno", getattr(n, "lineno", 1))) for n in nodes],
        reverse=True,
    )
    current = lines[:]
    for start, end in spans:
        del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def ensure_line_after_future(text: str, line_to_add: str) -> str:
    if line_to_add in text:
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("from __future__ import"):
            lines.insert(i + 1, line_to_add)
            return "\n".join(lines).rstrip() + "\n"
    lines.insert(0, line_to_add)
    return "\n".join(lines).rstrip() + "\n"


def ensure_error_bridge(text: str) -> str:
    if "V134D WaveAutomationError bridge" in text:
        return text
    bridge_lines = [
        "",
        "# V134D WaveAutomationError bridge",
        "try:",
        "    from wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]",
        "except Exception:",
        "    try:",
        "        from ..wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]",
        "    except Exception:",
        "        class WaveAutomationError(RuntimeError):",
        "            pass",
        "",
    ]
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("from __future__ import"):
            insert_at = i + 1
            break
    return "\n".join(lines[:insert_at] + bridge_lines + lines[insert_at:]).rstrip() + "\n"


def parse_imported_plan_schema_names(text: str) -> list[str]:
    if IMPORT_MARKER_START not in text or IMPORT_MARKER_END not in text:
        return []
    start = text.index(IMPORT_MARKER_START)
    end = text.index(IMPORT_MARKER_END, start)
    block = text[start:end]
    names: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s in {"try:", "except ImportError:"}:
            continue
        if s.startswith("from ") or s in {"(", ")"}:
            continue
        name = s.rstrip(",").strip()
        if name and name.isidentifier() and name not in names:
            names.append(name)
    return names


def import_block(names: list[str]) -> str:
    body = ",\n        ".join(names)
    return (
        IMPORT_MARKER_START + "\n"
        "try:\n"
        "    from batch.plan_schema import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .batch.plan_schema import (\n"
        "        " + body + ",\n"
        "    )\n"
        + IMPORT_MARKER_END + "\n\n"
    )


def replace_or_insert_plan_schema_import(text: str, names: list[str]) -> str:
    if IMPORT_MARKER_START in text and IMPORT_MARKER_END in text:
        start = text.index(IMPORT_MARKER_START)
        end = text.index(IMPORT_MARKER_END, start) + len(IMPORT_MARKER_END)
        while end < len(text) and text[end] in "\r\n":
            end += 1
        return text[:start] + import_block(names) + text[end:]

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!") or "coding" in lines[insert_at][:40]
    ):
        insert_at += 1

    try:
        tree = ast.parse(text)
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(getattr(tree.body[0], "value", None), ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            insert_at = max(insert_at, getattr(tree.body[0], "end_lineno", tree.body[0].lineno))
    except SyntaxError:
        pass

    while insert_at < len(lines):
        stripped = lines[insert_at].strip()
        if not stripped:
            insert_at += 1
            continue
        if stripped.startswith("from __future__ import"):
            insert_at += 1
            continue
        break

    return "\n".join(lines[:insert_at] + ["", import_block(names).rstrip(), ""] + lines[insert_at:]).rstrip() + "\n"


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    legacy = wr / "wave_batch_legacy.py"
    plan_schema = wr / "batch" / "plan_schema.py"
    manifest = wr / "batch" / MANIFEST_NAME

    if not legacy.exists():
        raise SystemExit("wave_batch_legacy.py not found. Apply V128 first.")
    if not plan_schema.exists():
        raise SystemExit("batch/plan_schema.py not found. Apply V131A first.")

    legacy_text = read_text(legacy)
    plan_text = read_text(plan_schema)

    if PLAN_MARKER in plan_text and manifest.exists():
        print("V134D already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    missing = [name for name in TARGET_FUNCTIONS if name not in funcs]
    if missing:
        raise SystemExit(f"V134D target functions not found in legacy: {missing}")

    backup(legacy, "v134c_failed_before_v134d")
    backup(plan_schema, "v134c_failed_before_v134d")

    legacy_lines = legacy_text.splitlines()
    moved_sources = [get_segment(legacy_lines, funcs[name]).rstrip() for name in TARGET_FUNCTIONS]

    plan_text = ensure_line_after_future(plan_text, "import copy")
    plan_text = ensure_error_bridge(plan_text)
    plan_text = plan_text.rstrip() + "\n\n" + PLAN_MARKER + "\n\n" + "\n\n".join(moved_sources) + "\n"
    plan_schema.write_text(plan_text, encoding="utf-8")

    reduced = remove_spans(legacy_lines, [funcs[name] for name in TARGET_FUNCTIONS])

    old_import_names = parse_imported_plan_schema_names(reduced)
    combined: list[str] = []
    for name in old_import_names + ["WaveAutomationError"] + TARGET_FUNCTIONS:
        if name not in combined:
            combined.append(name)

    reduced = replace_or_insert_plan_schema_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    # Compile immediately before claiming success.
    import py_compile
    py_compile.compile(str(plan_schema), doraise=True)
    py_compile.compile(str(legacy), doraise=True)

    data = {
        "schema_version": "aquanova.refactor.v134d.plan_schema_self_contained",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": len(TARGET_FUNCTIONS),
        "moved_functions": TARGET_FUNCTIONS,
        "legacy": str(legacy),
        "plan_schema": str(plan_schema),
        "note": "V134D avoids dependency discovery and makes plan_schema self-contained with copy and WaveAutomationError bridge. _write_two_case_summary/run_two_ro_cases remain legacy.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V134D wave_batch plan_schema self-contained extraction applied")
    print("moved_count=" + str(len(TARGET_FUNCTIONS)))
    print("moved_functions=" + ", ".join(TARGET_FUNCTIONS))
    print("manifest=" + str(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
