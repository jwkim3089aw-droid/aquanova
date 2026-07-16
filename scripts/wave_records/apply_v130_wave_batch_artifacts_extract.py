#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
from datetime import datetime
from pathlib import Path

TARGET_FUNCTIONS = ['_parse_pdf_summary_number', '_pdf_percent_values', '_pdf_pass_summary_lines', '_pdf_detect_pass_count', '_pdf_pass_summary_row_text_values', '_pdf_flow_factor_per_stage_values', '_pdf_pass_summary_row_values', '_pdf_flow_per_pass_values', '_validate_pdf_recoveries', '_extract_pdf_design_warnings', '_extract_pdf_solubility_warnings', '_merge_constraint_warnings', '_extract_pdf_chemical_observations', '_parse_pdf_number_line', '_extract_pdf_stage_rows', 'write_ro_catalog_artifacts']
ARTIFACTS_HEADER = '"""Batch output/PDF artifact helpers.\n\nV130 extracted low-risk artifact helpers from ``wave_batch_legacy.py``.\nThe legacy module imports these names back for compatibility, so existing\ncallers should keep working.\n\nKeep this module free of WAVE UI desktop automation side effects.\n"""\nfrom __future__ import annotations\n\nimport csv\nimport json\nimport math\nimport os\nimport re\nimport time\nfrom collections import Counter, defaultdict\nfrom datetime import datetime\nfrom pathlib import Path\nfrom typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple, Union\n\n'

ALLOWED_EXTERNALS = set(dir(builtins)) | {
    "re", "os", "json", "csv", "math", "time", "datetime", "Path", "Counter",
    "defaultdict", "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable",
    "Iterator", "Sequence", "Mapping", "MutableMapping", "Union",
    "None", "True", "False",
}

IMPORT_MARKER_START = "# V130_ARTIFACTS_IMPORT_START"
IMPORT_MARKER_END = "# V130_ARTIFACTS_IMPORT_END"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def backup(path: Path, tag: str) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + f".{tag}.bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_segment(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1:end]) + "\n"


def names_loaded(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.add(n.id)
    return out


def names_defined(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Param)):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.alias):
            out.add(n.asname or n.name.split(".")[0])
    return out


def free_names(node: ast.AST) -> set[str]:
    return names_loaded(node) - names_defined(node)


def resolve_safe_move_set(funcs: dict[str, ast.AST]) -> tuple[list[str], list[dict]]:
    candidates = [name for name in TARGET_FUNCTIONS if name in funcs]
    moved: set[str] = set(candidates)
    skipped: list[dict] = []

    changed = True
    while changed:
        changed = False
        for name in list(moved):
            fn = funcs[name]
            unresolved = free_names(fn) - moved - ALLOWED_EXTERNALS
            unresolved = {x for x in unresolved if x and not keyword.iskeyword(x)}
            if unresolved:
                moved.remove(name)
                skipped.append({
                    "function": name,
                    "reason": "unresolved_external_names",
                    "unresolved": sorted(unresolved),
                })
                changed = True

    return [name for name in TARGET_FUNCTIONS if name in moved], skipped


def remove_spans(lines: list[str], nodes: list[ast.AST]) -> str:
    remove_ranges = []
    for node in nodes:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        remove_ranges.append((start, end))
    remove_ranges.sort(reverse=True)

    current = lines[:]
    for start, end in remove_ranges:
        del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def import_block(names: list[str]) -> str:
    body = ",\n        ".join(names)
    return (
        IMPORT_MARKER_START + "\n"
        "try:\n"
        "    from batch.artifacts import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .batch.artifacts import (\n"
        "        " + body + ",\n"
        "    )\n"
        + IMPORT_MARKER_END + "\n\n"
    )


def insert_import(text: str, names: list[str]) -> str:
    if IMPORT_MARKER_START in text:
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

    new_lines = lines[:insert_at] + ["", import_block(names).rstrip(), ""] + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def main() -> int:
    root = Path.cwd().resolve()
    wave_records = root / "scripts" / "wave_records"
    legacy = wave_records / "wave_batch_legacy.py"
    artifacts = wave_records / "batch" / "artifacts.py"
    manifest_path = wave_records / "batch" / "v130_artifacts_extraction_manifest.json"

    if not legacy.exists():
        raise SystemExit("wave_batch_legacy.py not found. Apply V128 first.")

    wave_records.joinpath("batch").mkdir(parents=True, exist_ok=True)

    legacy_text = read_text(legacy)
    if IMPORT_MARKER_START in legacy_text and manifest_path.exists():
        print("V130 already appears applied")
        print(f"manifest: {manifest_path}")
        return 0

    tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(tree)
    lines = legacy_text.splitlines()

    moved_names, skipped = resolve_safe_move_set(funcs)
    if not moved_names:
        raise SystemExit(f"No safe artifact functions could be moved. Skipped={skipped}")

    moved_nodes = [funcs[name] for name in moved_names]
    moved_sources = [get_segment(lines, funcs[name]) for name in moved_names]

    backup(legacy, "v129_before_v130")
    backup(artifacts, "v129_before_v130")

    artifacts_text = ARTIFACTS_HEADER + "\n\n".join(src.rstrip() for src in moved_sources) + "\n"
    artifacts.write_text(artifacts_text, encoding="utf-8")

    reduced = remove_spans(lines, moved_nodes)
    reduced = insert_import(reduced, moved_names)
    legacy.write_text(reduced, encoding="utf-8")

    manifest = {
        "schema_version": "aquanova.refactor.v130.artifacts_extraction",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "legacy": str(legacy),
        "artifacts": str(artifacts),
        "moved_count": len(moved_names),
        "moved_functions": moved_names,
        "skipped": skipped,
        "note": "wave_batch_legacy imports moved functions back from batch.artifacts for compatibility.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V130 wave_batch artifacts extraction applied")
    print(f"moved_count={len(moved_names)}")
    print("moved_functions=" + ", ".join(moved_names))
    if skipped:
        print(f"skipped_count={len(skipped)}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
