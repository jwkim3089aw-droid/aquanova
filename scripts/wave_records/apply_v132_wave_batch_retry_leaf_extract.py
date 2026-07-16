#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path

TARGET_FUNCTIONS = ['_classify_constraint_adjusted_recovery']
HEADER = '"""Batch retry/recovery classification helpers.\n\nV132 extracted low-risk retry/recovery helpers from ``wave_batch_legacy.py``.\nThe legacy module imports these names back for compatibility.\n"""\nfrom __future__ import annotations\n\nimport re\nfrom typing import Any, Dict, List, Optional, Sequence, Tuple\n\n'

IMPORT_START = "# V132_RETRIES_IMPORT_START"
IMPORT_END = "# V132_RETRIES_IMPORT_END"


def backup(path: Path, tag: str) -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + f".{tag}.bak")
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def top_level_functions(tree: ast.Module):
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)]) + "\n"


def remove_segments(lines: list[str], nodes: list[ast.AST]) -> str:
    current = lines[:]
    spans = sorted([(n.lineno, getattr(n, "end_lineno", n.lineno)) for n in nodes], reverse=True)
    for a, b in spans:
        del current[a - 1:b]
    return "\n".join(current).rstrip() + "\n"


def import_block(names: list[str]) -> str:
    body = ",\n        ".join(names)
    return (
        IMPORT_START + "\n"
        "try:\n"
        "    from batch.retries import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .batch.retries import (\n"
        "        " + body + ",\n"
        "    )\n"
        + IMPORT_END + "\n\n"
    )


def insert_import(text: str, names: list[str]) -> str:
    if IMPORT_START in text:
        return text

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
    retries = wr / "batch" / "retries.py"
    manifest = wr / "batch" / "v132_retries_extraction_manifest.json"

    if not legacy.exists():
        raise SystemExit("wave_batch_legacy.py not found. Apply V128 first.")

    text = legacy.read_text(encoding="utf-8")
    if IMPORT_START in text and manifest.exists():
        print("V132 already applied")
        print(f"manifest={manifest}")
        return 0

    tree = ast.parse(text, filename=str(legacy))
    funcs = top_level_functions(tree)
    names = [name for name in TARGET_FUNCTIONS if name in funcs]
    if not names:
        raise SystemExit("No V132 target functions found.")

    wr.joinpath("batch").mkdir(parents=True, exist_ok=True)
    backup(legacy, "v131a_before_v132")
    backup(retries, "v131a_before_v132")

    lines = text.splitlines()
    retries.write_text(HEADER + "\n\n".join(segment(lines, funcs[n]).rstrip() for n in names) + "\n", encoding="utf-8")

    reduced = remove_segments(lines, [funcs[n] for n in names])
    reduced = insert_import(reduced, names)
    legacy.write_text(reduced, encoding="utf-8")

    data = {
        "schema_version": "aquanova.refactor.v132.retries_extraction",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": len(names),
        "moved_functions": names,
        "legacy": str(legacy),
        "retries": str(retries),
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V132 wave_batch retries extraction applied")
    print("moved_count=" + str(len(names)))
    print("moved_functions=" + ", ".join(names))
    print("manifest=" + str(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
