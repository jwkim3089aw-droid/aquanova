#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
import py_compile
from datetime import datetime
from pathlib import Path

TARGET_FUNCTION = "_stabilize_after_flow_commit"
TARGET_FILE_REL = Path("ro") / "stages.py"

IMPORT_MARKER_START = "# V145A_RO_STAGES_IMPORT_START"
IMPORT_MARKER_END = "# V145A_RO_STAGES_IMPORT_END"
EXTRACT_MARKER = "# V145A_RO_STAGES_STABILIZE_AFTER_FLOW_COMMIT_APPLIED"
MANIFEST_NAME = "v145a_ro_stages_stabilize_after_flow_commit_manifest.json"

# Larger legacy helpers stay in wave_ro_engine_legacy for now.
BRIDGEABLE_LEGACY_REFS = {
    "_reassert_global_temperature_after_flow_commit",
    "_restore_stage_topologies_after_flow_commit",
}

# Already-extracted helper in ro.case_config. Use a runtime bridge, not a top-level
# import, to avoid circular ro.stages <-> ro.case_config <-> ro.membrane imports.
BRIDGEABLE_RO_CASE_CONFIG_REFS = {
    "_verify_case_operating_inputs",
}

ALLOWED_GLOBALS = set(dir(builtins)) | {
    "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable", "Iterator",
    "Sequence", "Mapping", "MutableMapping", "Union", "Path", "datetime",
    "None", "True", "False",
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
        elif isinstance(n, ast.AugAssign):
            out.update(collect_target_names(n.target))
        elif isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    out.add(a.asname or a.name)
        elif isinstance(n, ast.Try):
            for sub in n.body + [s for h in n.handlers for s in h.body]:
                if isinstance(sub, ast.Import):
                    for a in sub.names:
                        out.add(a.asname or a.name.split(".")[0])
                elif isinstance(sub, ast.ImportFrom):
                    for a in sub.names:
                        if a.name != "*":
                            out.add(a.asname or a.name)
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.add(sub.name)
    return out


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


def remove_span(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    current = lines[:]
    del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def parse_imported_names(text: str) -> list[str]:
    names: list[str] = []
    marker_pairs = [
        ("# V145A_RO_STAGES_IMPORT_START", "# V145A_RO_STAGES_IMPORT_END"),
        ("# V145_RO_STAGES_IMPORT_START", "# V145_RO_STAGES_IMPORT_END"),
        ("# V140_RO_STAGES_IMPORT_START", "# V140_RO_STAGES_IMPORT_END"),
    ]
    for start_marker, end_marker in marker_pairs:
        if start_marker not in text or end_marker not in text:
            continue
        start = text.index(start_marker)
        end = text.index(end_marker, start)
        block = text[start:end]
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
        "    from ro.stages import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .ro.stages import (\n"
        "        " + body + ",\n"
        "    )\n"
        + IMPORT_MARKER_END + "\n\n"
    )


def replace_or_insert_import(text: str, names: list[str]) -> str:
    marker_pairs = [
        ("# V145A_RO_STAGES_IMPORT_START", "# V145A_RO_STAGES_IMPORT_END"),
        ("# V145_RO_STAGES_IMPORT_START", "# V145_RO_STAGES_IMPORT_END"),
        ("# V140_RO_STAGES_IMPORT_START", "# V140_RO_STAGES_IMPORT_END"),
    ]
    for start_marker, end_marker in marker_pairs:
        if start_marker in text and end_marker in text:
            start = text.index(start_marker)
            end = text.index(end_marker, start) + len(end_marker)
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


def ensure_stages_header(text: str) -> str:
    if text.strip():
        if "from __future__ import annotations" not in text:
            return 'from __future__ import annotations\n\n' + text.rstrip() + "\n\n"
        return text.rstrip() + "\n\n"
    return (
        '"""RO stage/grid helpers extracted from wave_ro_engine_legacy."""\n'
        "from __future__ import annotations\n\n"
    )


def make_legacy_bridge(name: str) -> str:
    return (
        "def " + name + "(*args, **kwargs):\n"
        "    \"\"\"Bridge to a legacy helper left in wave_ro_engine_legacy during staged refactor.\"\"\"\n"
        "    try:\n"
        "        from wave_ro_engine_legacy import " + name + " as _legacy_impl\n"
        "    except ImportError:\n"
        "        from ..wave_ro_engine_legacy import " + name + " as _legacy_impl\n"
        "    return _legacy_impl(*args, **kwargs)"
    )


def make_case_config_bridge(name: str) -> str:
    return (
        "def " + name + "(*args, **kwargs):\n"
        "    \"\"\"Bridge to ro.case_config while avoiding top-level circular imports.\"\"\"\n"
        "    try:\n"
        "        from ro.case_config import " + name + " as _impl\n"
        "    except ImportError:\n"
        "        from .case_config import " + name + " as _impl\n"
        "    return _impl(*args, **kwargs)"
    )


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    legacy = wr / "wave_ro_engine_legacy.py"
    stages = wr / TARGET_FILE_REL
    manifest = wr / "ro" / MANIFEST_NAME

    if not legacy.exists():
        raise SystemExit("wave_ro_engine_legacy.py not found. Apply V135 first.")
    if not stages.exists():
        raise SystemExit("ro/stages.py not found. Apply V135 first.")

    legacy_text = read_text(legacy)
    stages_text = read_text(stages)

    if EXTRACT_MARKER in stages_text and manifest.exists():
        print("V145A already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    if TARGET_FUNCTION not in funcs:
        raise SystemExit(f"{TARGET_FUNCTION} not found in wave_ro_engine_legacy.py")

    target_node = funcs[TARGET_FUNCTION]
    stages_tree = ast.parse(stages_text, filename=str(stages))
    stages_defs = module_defined_names(stages_tree)

    target_free = free_names(target_node)
    bridged_legacy_refs = sorted(name for name in target_free if name in BRIDGEABLE_LEGACY_REFS)
    bridged_case_config_refs = sorted(name for name in target_free if name in BRIDGEABLE_RO_CASE_CONFIG_REFS)

    unresolved = (
        target_free
        - set(bridged_legacy_refs)
        - set(bridged_case_config_refs)
        - stages_defs
        - ALLOWED_GLOBALS
    )
    unresolved = sorted(x for x in unresolved if x and not keyword.iskeyword(x))
    if unresolved:
        raise SystemExit(
            f"V145A target is not safe to move. function={TARGET_FUNCTION} unresolved={unresolved}"
        )

    backup(legacy, "v145_failed_before_v145a")
    backup(stages, "v145_failed_before_v145a")

    legacy_lines = legacy_text.splitlines()
    source = get_segment(legacy_lines, target_node).rstrip()

    stages_text = ensure_stages_header(stages_text)
    existing_defs = module_defined_names(ast.parse(stages_text, filename=str(stages)))
    bridge_blocks = []
    for ref in bridged_case_config_refs:
        if ref not in existing_defs:
            bridge_blocks.append(make_case_config_bridge(ref))
    for ref in bridged_legacy_refs:
        if ref not in existing_defs:
            bridge_blocks.append(make_legacy_bridge(ref))

    additions = bridge_blocks + [source]
    stages_text = stages_text.rstrip() + "\n\n" + EXTRACT_MARKER + "\n\n" + "\n\n".join(additions) + "\n"
    stages.write_text(stages_text, encoding="utf-8")

    reduced = remove_span(legacy_lines, target_node)
    old_names = parse_imported_names(reduced)
    combined: list[str] = []
    for name in old_names + [TARGET_FUNCTION]:
        if name not in combined:
            combined.append(name)
    reduced = replace_or_insert_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    py_compile.compile(str(stages), doraise=True)
    py_compile.compile(str(legacy), doraise=True)

    data = {
        "schema_version": "aquanova.refactor.v145a.ro_stages_stabilize_bridge_case_config",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": 1,
        "moved_functions": [TARGET_FUNCTION],
        "bridged_legacy_refs": bridged_legacy_refs,
        "bridged_case_config_refs": bridged_case_config_refs,
        "legacy": str(legacy),
        "stages": str(stages),
        "note": "V145 failed safely because _verify_case_operating_inputs is now in ro.case_config. V145A bridges it at runtime to avoid circular imports.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V145A RO stages stabilize-after-flow extraction applied")
    print("moved_count=1")
    print(f"moved_functions={TARGET_FUNCTION}")
    print("bridged_case_config_refs=" + (", ".join(bridged_case_config_refs) if bridged_case_config_refs else ""))
    print("bridged_legacy_refs=" + (", ".join(bridged_legacy_refs) if bridged_legacy_refs else ""))
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
