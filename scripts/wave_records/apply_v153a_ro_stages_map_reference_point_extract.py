#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
import py_compile
from datetime import datetime
from pathlib import Path

TARGET_FUNCTION = "_map_reference_point"
TARGET_FILE_REL = Path("ro") / "stages.py"

FALLBACK_IMPORT_MARKER_START = "# V153_RO_STAGES_IMPORT_START"
FALLBACK_IMPORT_MARKER_END = "# V153_RO_STAGES_IMPORT_END"
EXTRACT_MARKER = "# V153_RO_STAGES_MAP_REFERENCE_POINT_APPLIED"
MANIFEST_NAME = "v153_ro_stages_map_reference_point_manifest.json"

REFERENCE_NAMES = {"REFERENCE_WIDTH", "REFERENCE_HEIGHT"}

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


def node_source(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)])


def import_sources(tree: ast.Module, lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}

    def record_import_node(n: ast.AST, src: str) -> None:
        if isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name.split(".")[0]] = src
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    out[a.asname or a.name] = src

    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            record_import_node(n, node_source(lines, n))
        elif isinstance(n, ast.Try):
            src = node_source(lines, n)
            for sub in n.body + [s for h in n.handlers for s in h.body]:
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    record_import_node(sub, src)
    return out


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


def remove_spans(lines: list[str], nodes: list[ast.AST]) -> str:
    spans = sorted(
        [(getattr(n, "lineno", 1), getattr(n, "end_lineno", getattr(n, "lineno", 1))) for n in nodes],
        reverse=True,
    )
    current = lines[:]
    for start, end in spans:
        del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def import_marker_pairs() -> list[tuple[str, str]]:
    return [
        ("# V153_RO_STAGES_IMPORT_START", "# V153_RO_STAGES_IMPORT_END"),
        ("# V152_RO_STAGES_IMPORT_START", "# V152_RO_STAGES_IMPORT_END"),
        ("# V151_RO_STAGES_IMPORT_START", "# V151_RO_STAGES_IMPORT_END"),
        ("# V150_RO_STAGES_IMPORT_START", "# V150_RO_STAGES_IMPORT_END"),
        ("# V148_RO_STAGES_IMPORT_START", "# V148_RO_STAGES_IMPORT_END"),
        ("# V145A_RO_STAGES_IMPORT_START", "# V145A_RO_STAGES_IMPORT_END"),
        ("# V145_RO_STAGES_IMPORT_START", "# V145_RO_STAGES_IMPORT_END"),
        ("# V140_RO_STAGES_IMPORT_START", "# V140_RO_STAGES_IMPORT_END"),
    ]


def parse_imported_names(text: str) -> list[str]:
    names: list[str] = []
    for start_marker, end_marker in import_marker_pairs():
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


def active_import_markers(text: str) -> tuple[str, str]:
    for start_marker, end_marker in import_marker_pairs():
        if start_marker in text and end_marker in text:
            return start_marker, end_marker
    return FALLBACK_IMPORT_MARKER_START, FALLBACK_IMPORT_MARKER_END


def import_block(names: list[str], start_marker: str, end_marker: str) -> str:
    body = ",\n        ".join(names)
    return (
        start_marker + "\n"
        "try:\n"
        "    from ro.stages import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .ro.stages import (\n"
        "        " + body + ",\n"
        "    )\n"
        + end_marker + "\n\n"
    )


def replace_or_insert_import(text: str, names: list[str]) -> str:
    start_marker, end_marker = active_import_markers(text)
    if start_marker in text and end_marker in text:
        start = text.index(start_marker)
        end = text.index(end_marker, start) + len(end_marker)
        while end < len(text) and text[end] in "\r\n":
            end += 1
        return text[:start] + import_block(names, start_marker, end_marker) + text[end:]

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

    return "\n".join(lines[:insert_at] + ["", import_block(names, start_marker, end_marker).rstrip(), ""] + lines[insert_at:]).rstrip() + "\n"


def ensure_stages_header(text: str) -> str:
    if text.strip():
        if "from __future__ import annotations" not in text:
            return 'from __future__ import annotations\n\n' + text.rstrip() + "\n\n"
        return text.rstrip() + "\n\n"
    return (
        '"""RO stage/grid helpers extracted from wave_ro_engine_legacy."""\n'
        "from __future__ import annotations\n\n"
    )


def remove_existing_target_defs(text: str, names: set[str]) -> str:
    tree = ast.parse(text)
    funcs = top_level_functions(tree)
    nodes = [funcs[name] for name in names if name in funcs]
    if not nodes:
        return text
    return remove_spans(text.splitlines(), nodes)


def top_level_assignment_nodes(tree: ast.Module, wanted: set[str]) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        target_names: set[str] = set()
        if isinstance(node, ast.Assign):
            for t in node.targets:
                target_names.update(collect_target_names(t))
        elif isinstance(node, ast.AnnAssign):
            target_names.update(collect_target_names(node.target))
        else:
            continue
        for name in wanted & target_names:
            out[name] = node
    return out


def lazy_reference_helpers() -> str:
    return (
        "def _legacy_reference_width():\n"
        "    try:\n"
        "        from wave_ro_engine_legacy import REFERENCE_WIDTH as _value\n"
        "    except ImportError:\n"
        "        from ..wave_ro_engine_legacy import REFERENCE_WIDTH as _value\n"
        "    return _value\n\n"
        "def _legacy_reference_height():\n"
        "    try:\n"
        "        from wave_ro_engine_legacy import REFERENCE_HEIGHT as _value\n"
        "    except ImportError:\n"
        "        from ..wave_ro_engine_legacy import REFERENCE_HEIGHT as _value\n"
        "    return _value"
    )


def rewrite_reference_names_for_lazy_getters(source: str) -> str:
    # Fallback only. Keeps module import safe if the reference constants are not
    # statically visible as assignments/imports in legacy. Runtime still resolves
    # them from legacy when the helper is called.
    source = source.replace("REFERENCE_WIDTH", "_legacy_reference_width()")
    source = source.replace("REFERENCE_HEIGHT", "_legacy_reference_height()")
    return source


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
        print("V153/V153A already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_lines = legacy_text.splitlines()
    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    imports = import_sources(legacy_tree, legacy_lines)

    if TARGET_FUNCTION not in funcs:
        raise SystemExit(f"{TARGET_FUNCTION} not found in wave_ro_engine_legacy.py")

    target_node = funcs[TARGET_FUNCTION]
    stages_tree = ast.parse(stages_text, filename=str(stages))
    stages_defs = module_defined_names(stages_tree)

    target_free = free_names(target_node)
    wanted_refs = sorted(name for name in target_free if name in REFERENCE_NAMES and name not in stages_defs)

    assignment_nodes = top_level_assignment_nodes(legacy_tree, set(wanted_refs))
    assigned_refs = sorted(name for name in wanted_refs if name in assignment_nodes)
    imported_refs = sorted(name for name in wanted_refs if name in imports and name not in assignment_nodes)
    unresolved_refs = sorted(name for name in wanted_refs if name not in assignment_nodes and name not in imports)

    unresolved = (
        target_free
        - set(assigned_refs)
        - set(imported_refs)
        - set(unresolved_refs)
        - stages_defs
        - ALLOWED_GLOBALS
    )
    unresolved = sorted(x for x in unresolved if x and not keyword.iskeyword(x))
    if unresolved:
        raise SystemExit(
            f"V153A target is not safe to move. function={TARGET_FUNCTION} unresolved={unresolved}"
        )

    backup(legacy, "v152_before_v153a")
    backup(stages, "v152_before_v153a")

    source = get_segment(legacy_lines, target_node).rstrip()

    stages_text = ensure_stages_header(stages_text)
    # Replace the V150 bridge def _map_reference_point in ro/stages.py with the real function.
    stages_text = remove_existing_target_defs(stages_text, {TARGET_FUNCTION})
    stages_defs_after_bridge_remove = module_defined_names(ast.parse(stages_text, filename=str(stages)))

    blocks = []
    constant_strategy = "none"

    # 1) Best: copy literal top-level assignments if available.
    seen_const_nodes = set()
    copied_constants = []
    for name in assigned_refs:
        node = assignment_nodes[name]
        key = (getattr(node, "lineno", 0), getattr(node, "end_lineno", 0))
        if key in seen_const_nodes:
            continue
        seen_const_nodes.add(key)
        target_names = set()
        if isinstance(node, ast.Assign):
            for t in node.targets:
                target_names.update(collect_target_names(t))
        elif isinstance(node, ast.AnnAssign):
            target_names.update(collect_target_names(node.target))
        if target_names <= stages_defs_after_bridge_remove:
            continue
        blocks.append(get_segment(legacy_lines, node).rstrip())
        copied_constants.extend(sorted(target_names & REFERENCE_NAMES))
    if copied_constants:
        constant_strategy = "assignments"

    # 2) Next best: copy exact import block if references were imported in legacy.
    seen_import_blocks = set()
    explicit_import_dependencies = []
    for name in imported_refs:
        block = imports[name].strip()
        if block and block not in stages_text and block not in seen_import_blocks:
            blocks.append(block)
            seen_import_blocks.add(block)
        explicit_import_dependencies.append(name)
    if explicit_import_dependencies and constant_strategy == "none":
        constant_strategy = "imports"

    # 3) Fallback: rewrite the function to call lazy getters resolving legacy constants at call time.
    lazy_getter_refs = []
    if unresolved_refs:
        blocks.append(lazy_reference_helpers())
        source = rewrite_reference_names_for_lazy_getters(source)
        lazy_getter_refs = unresolved_refs
        if constant_strategy == "none":
            constant_strategy = "lazy_getters"

    additions = blocks + [source]
    stages_text = stages_text.rstrip() + "\n\n" + EXTRACT_MARKER + "\n\n" + "\n\n".join(additions) + "\n"
    stages.write_text(stages_text, encoding="utf-8")

    reduced = remove_spans(legacy_lines, [target_node])
    old_names = parse_imported_names(reduced)
    combined: list[str] = []
    for name in old_names + [TARGET_FUNCTION]:
        if name not in combined:
            combined.append(name)
    reduced = replace_or_insert_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    py_compile.compile(str(stages), doraise=True)
    py_compile.compile(str(legacy), doraise=True)

    active_start, _ = active_import_markers(read_text(legacy))
    data = {
        "schema_version": "aquanova.refactor.v153a.ro_stages_map_reference_point_extract",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": 1,
        "moved_functions": [TARGET_FUNCTION],
        "constant_strategy": constant_strategy,
        "copied_constants": sorted(set(copied_constants)),
        "explicit_import_dependencies": sorted(set(explicit_import_dependencies)),
        "lazy_getter_refs": lazy_getter_refs,
        "active_import_marker": active_start,
        "legacy": str(legacy),
        "stages": str(stages),
        "note": "Moves _map_reference_point into ro.stages. V153A supports constants provided by assignment, import, or lazy legacy getters.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V153A RO stages map-reference-point extraction applied")
    print("moved_count=1")
    print(f"moved_functions={TARGET_FUNCTION}")
    print("constant_strategy=" + constant_strategy)
    print("copied_constants=" + (", ".join(sorted(set(copied_constants))) if copied_constants else ""))
    print("explicit_import_dependencies=" + (", ".join(sorted(set(explicit_import_dependencies))) if explicit_import_dependencies else ""))
    print("lazy_getter_refs=" + (", ".join(lazy_getter_refs) if lazy_getter_refs else ""))
    print(f"active_import_marker={active_start}")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
