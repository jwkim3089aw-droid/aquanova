#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
from datetime import datetime
from pathlib import Path

# V134 failed safely because it did not include the dependency class/global names.
# V134A moves the class dependency plus the temperature/case expansion cluster.
TARGET_NAMES = [
    "WaveAutomationError",
    "_canonical_temperature_mode",
    "_temperature_variant_suffix",
    "_clone_case_for_global_temperature",
    "expand_cases_for_wave_global_temperature",
]

IMPORT_MARKER_START = "# V131A_PLAN_SCHEMA_IMPORT_START"
IMPORT_MARKER_END = "# V131A_PLAN_SCHEMA_IMPORT_END"
MANIFEST_NAME = "v134a_plan_schema_cluster_extraction_manifest.json"

ALLOWED_EXTERNALS = set(dir(builtins)) | {
    "re", "os", "json", "csv", "math", "time", "datetime", "Path", "Counter",
    "defaultdict", "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable",
    "Iterator", "Sequence", "Mapping", "MutableMapping", "Union",
    "None", "True", "False", "ROCaseConfig", "copy",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def backup(path: Path, tag: str) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + f".{tag}.bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def collect_target_names(target: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


def module_defined_names(tree: ast.Module) -> set[str]:
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                out.update(collect_target_names(t))
        elif isinstance(n, ast.AnnAssign):
            out.update(collect_target_names(n.target))
        elif isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    out.add(a.asname or a.name)
    return out


def top_level_defs(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
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

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for a in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
            out.add(a.arg)
        if node.args.vararg:
            out.add(node.args.vararg.arg)
        if node.args.kwarg:
            out.add(node.args.kwarg.arg)

    if isinstance(node, ast.ClassDef):
        out.add(node.name)

    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Param)):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.alias):
            out.add(n.asname or n.name.split(".")[0])
        elif isinstance(n, ast.For):
            out.update(collect_target_names(n.target))
        elif isinstance(n, ast.comprehension):
            out.update(collect_target_names(n.target))
        elif isinstance(n, ast.With):
            for item in n.items:
                if item.optional_vars is not None:
                    out.update(collect_target_names(item.optional_vars))
        elif isinstance(n, ast.NamedExpr):
            out.update(collect_target_names(n.target))
    return out


def annotation_names(node: ast.AST) -> set[str]:
    out: set[str] = set()

    def visit_ann(ann):
        if ann is None:
            return
        for n in ast.walk(ann):
            if isinstance(n, ast.Name):
                out.add(n.id)

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for a in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
            visit_ann(a.annotation)
        if node.args.vararg:
            visit_ann(node.args.vararg.annotation)
        if node.args.kwarg:
            visit_ann(node.args.kwarg.annotation)
        visit_ann(node.returns)

    for n in ast.walk(node):
        if isinstance(n, ast.AnnAssign):
            visit_ann(n.annotation)
    return out


def free_names(node: ast.AST) -> set[str]:
    return names_loaded(node) - names_defined(node) - annotation_names(node)


def resolve_safe_move_set(
    legacy_defs: dict[str, ast.AST],
    plan_schema_existing_defs: set[str],
) -> tuple[list[str], list[dict]]:
    candidates = [name for name in TARGET_NAMES if name in legacy_defs]

    # Require the error class to move together if _canonical uses it.
    if "_canonical_temperature_mode" in candidates and "WaveAutomationError" not in candidates and "WaveAutomationError" not in plan_schema_existing_defs:
        return [], [{
            "function": "_canonical_temperature_mode",
            "reason": "WaveAutomationError_dependency_not_found_as_top_level_def",
            "unresolved": ["WaveAutomationError"],
        }]

    moved: set[str] = set(candidates)
    skipped: list[dict] = []

    changed = True
    while changed:
        changed = False
        for name in list(moved):
            node = legacy_defs[name]
            unresolved = (
                free_names(node)
                - moved
                - plan_schema_existing_defs
                - ALLOWED_EXTERNALS
            )
            unresolved = {x for x in unresolved if x and not keyword.iskeyword(x)}
            if unresolved:
                moved.remove(name)
                skipped.append({
                    "function": name,
                    "reason": "unresolved_external_names",
                    "unresolved": sorted(unresolved),
                })
                changed = True

    ordered = [name for name in TARGET_NAMES if name in moved]
    return ordered, skipped


def remove_spans(lines: list[str], nodes: list[ast.AST]) -> str:
    spans = sorted(
        [(getattr(n, "lineno", 1), getattr(n, "end_lineno", getattr(n, "lineno", 1))) for n in nodes],
        reverse=True,
    )
    current = lines[:]
    for start, end in spans:
        del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def ensure_copy_import(plan_text: str) -> str:
    if "\nimport copy\n" in plan_text or plan_text.startswith("import copy\n"):
        return plan_text
    lines = plan_text.splitlines()
    insert_at = 0
    while insert_at < len(lines):
        s = lines[insert_at].strip()
        if not s or s.startswith('"""') or s.startswith("V134") or s.startswith("The legacy") or s.startswith("from __future__"):
            insert_at += 1
            continue
        break
    # Safer: just insert after future import if found.
    for i, line in enumerate(lines):
        if line.strip().startswith("from __future__ import"):
            lines.insert(i + 1, "import copy")
            return "\n".join(lines).rstrip() + "\n"
    lines.insert(0, "import copy")
    return "\n".join(lines).rstrip() + "\n"


def parse_imported_plan_schema_names(text: str) -> list[str]:
    if IMPORT_MARKER_START not in text or IMPORT_MARKER_END not in text:
        return []
    start = text.index(IMPORT_MARKER_START)
    end = text.index(IMPORT_MARKER_END, start)
    block = text[start:end]
    names = []
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
    if "V134A_PLAN_SCHEMA_CLUSTER_APPLIED" in read_text(plan_schema) and manifest.exists():
        print("V134A already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    plan_text = read_text(plan_schema)
    plan_tree = ast.parse(plan_text, filename=str(plan_schema))

    legacy_defs = top_level_defs(legacy_tree)
    plan_existing_defs = module_defined_names(plan_tree)

    moved_names, skipped = resolve_safe_move_set(legacy_defs, plan_existing_defs)
    required = {"WaveAutomationError", "_canonical_temperature_mode", "_temperature_variant_suffix"}
    if not required.issubset(set(moved_names)):
        raise SystemExit(f"V134A required target set was not safe. moved={moved_names} skipped={skipped}")

    backup(legacy, "v134_failed_before_v134a")
    backup(plan_schema, "v134_failed_before_v134a")

    legacy_lines = legacy_text.splitlines()
    moved_sources = [get_segment(legacy_lines, legacy_defs[name]).rstrip() for name in moved_names]

    plan_text = ensure_copy_import(plan_text)
    plan_text = plan_text.rstrip() + "\n\n# V134A_PLAN_SCHEMA_CLUSTER_APPLIED\n\n" + "\n\n".join(moved_sources) + "\n"
    plan_schema.write_text(plan_text, encoding="utf-8")

    reduced = remove_spans(legacy_lines, [legacy_defs[name] for name in moved_names])

    old_import_names = parse_imported_plan_schema_names(reduced)
    combined = []
    for name in old_import_names + moved_names:
        if name not in combined:
            combined.append(name)
    reduced = replace_or_insert_plan_schema_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    data = {
        "schema_version": "aquanova.refactor.v134a.plan_schema_cluster_extraction",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": len(moved_names),
        "moved_functions": moved_names,
        "skipped": skipped,
        "legacy": str(legacy),
        "plan_schema": str(plan_schema),
        "note": "V134 failed safely. V134A includes WaveAutomationError and copy dependency, skips STATE-dependent summary writer.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V134A wave_batch plan_schema cluster extraction applied")
    print("moved_count=" + str(len(moved_names)))
    print("moved_functions=" + ", ".join(moved_names))
    if skipped:
        print("skipped_count=" + str(len(skipped)))
        print("skipped_functions=" + ", ".join(item["function"] for item in skipped))
    print("manifest=" + str(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
