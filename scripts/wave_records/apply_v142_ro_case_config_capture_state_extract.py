#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
import py_compile
from datetime import datetime
from pathlib import Path

TARGET_FUNCTION = "_capture_case_ro_state"
TARGET_FILE_REL = Path("ro") / "case_config.py"

IMPORT_MARKER_START = "# V142_RO_CASE_CONFIG_IMPORT_START"
IMPORT_MARKER_END = "# V142_RO_CASE_CONFIG_IMPORT_END"
EXTRACT_MARKER = "# V142_RO_CASE_CONFIG_CAPTURE_STATE_APPLIED"
MANIFEST_NAME = "v142_ro_case_config_capture_state_manifest.json"

ALLOWED_GLOBALS = set(dir(builtins)) | {
    "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable", "Iterator",
    "Sequence", "Mapping", "MutableMapping", "Union", "Path", "datetime",
    "None", "True", "False",
}

KNOWN_RO_DEP_IMPORTS = {
    "_ro_diagnostic_points": (
        "try:\n"
        "    from ro.membrane import _ro_diagnostic_points\n"
        "except ImportError:\n"
        "    from .membrane import _ro_diagnostic_points\n"
    ),
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


def remove_span(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    current = lines[:]
    del current[start - 1:end]
    return "\n".join(current).rstrip() + "\n"


def parse_imported_names(text: str) -> list[str]:
    names: list[str] = []
    marker_pairs = [
        ("# V142_RO_CASE_CONFIG_IMPORT_START", "# V142_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137_RO_CASE_CONFIG_IMPORT_START", "# V137_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137A_RO_CASE_CONFIG_IMPORT_START", "# V137A_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137B_RO_CASE_CONFIG_IMPORT_START", "# V137B_RO_CASE_CONFIG_IMPORT_END"),
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
        "    from ro.case_config import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .ro.case_config import (\n"
        "        " + body + ",\n"
        "    )\n"
        + IMPORT_MARKER_END + "\n\n"
    )


def replace_or_insert_import(text: str, names: list[str]) -> str:
    marker_pairs = [
        ("# V142_RO_CASE_CONFIG_IMPORT_START", "# V142_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137_RO_CASE_CONFIG_IMPORT_START", "# V137_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137A_RO_CASE_CONFIG_IMPORT_START", "# V137A_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137B_RO_CASE_CONFIG_IMPORT_START", "# V137B_RO_CASE_CONFIG_IMPORT_END"),
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


def ensure_case_config_header(text: str) -> str:
    if text.strip():
        if "from __future__ import annotations" not in text:
            return 'from __future__ import annotations\n\n' + text.rstrip() + "\n\n"
        return text.rstrip() + "\n\n"
    return (
        '"""RO case configuration helpers extracted from wave_ro_engine_legacy."""\n'
        "from __future__ import annotations\n\n"
    )


def ensure_dependency_imports(text: str, explicit_blocks: list[str], known_deps: list[str]) -> str:
    additions: list[str] = []

    current_defs = module_defined_names(ast.parse(text, filename="<case_config>"))
    for dep in known_deps:
        if dep not in current_defs and dep in KNOWN_RO_DEP_IMPORTS:
            additions.append(KNOWN_RO_DEP_IMPORTS[dep].rstrip())

    for block in explicit_blocks:
        # Avoid duplicate exact block.
        if block.strip() and block.strip() not in text:
            additions.append(block.strip())

    if not additions:
        return text
    return text.rstrip() + "\n\n" + "\n\n".join(additions) + "\n"


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    legacy = wr / "wave_ro_engine_legacy.py"
    case_config = wr / TARGET_FILE_REL
    manifest = wr / "ro" / MANIFEST_NAME

    if not legacy.exists():
        raise SystemExit("wave_ro_engine_legacy.py not found. Apply V135 first.")
    if not case_config.exists():
        raise SystemExit("ro/case_config.py not found. Apply V135 first.")

    legacy_text = read_text(legacy)
    case_text = read_text(case_config)

    if EXTRACT_MARKER in case_text and manifest.exists():
        print("V142 already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    if TARGET_FUNCTION not in funcs:
        raise SystemExit(f"{TARGET_FUNCTION} not found in wave_ro_engine_legacy.py")

    target_node = funcs[TARGET_FUNCTION]
    case_tree = ast.parse(case_text, filename=str(case_config))
    case_defs = module_defined_names(case_tree)
    imports = import_sources(legacy_tree, legacy_text.splitlines())

    target_free = free_names(target_node)
    known_ro_deps = sorted(name for name in target_free if name in KNOWN_RO_DEP_IMPORTS)
    explicit_import_deps = sorted(
        name for name in target_free
        if name in imports and name not in case_defs and name not in known_ro_deps
    )

    unresolved = (
        target_free
        - set(known_ro_deps)
        - set(explicit_import_deps)
        - case_defs
        - ALLOWED_GLOBALS
    )
    unresolved = sorted(x for x in unresolved if x and not keyword.iskeyword(x))
    if unresolved:
        raise SystemExit(
            f"V142 target is not safe to move. function={TARGET_FUNCTION} unresolved={unresolved}"
        )

    backup(legacy, "v141_before_v142")
    backup(case_config, "v141_before_v142")

    legacy_lines = legacy_text.splitlines()
    source = get_segment(legacy_lines, target_node).rstrip()
    explicit_blocks = [imports[name] for name in explicit_import_deps]

    case_text = ensure_case_config_header(case_text)
    case_text = ensure_dependency_imports(case_text, explicit_blocks, known_ro_deps)
    case_text = case_text.rstrip() + "\n\n" + EXTRACT_MARKER + "\n\n" + source + "\n"
    case_config.write_text(case_text, encoding="utf-8")

    reduced = remove_span(legacy_lines, target_node)
    old_names = parse_imported_names(reduced)
    combined: list[str] = []
    for name in old_names + [TARGET_FUNCTION]:
        if name not in combined:
            combined.append(name)
    reduced = replace_or_insert_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    py_compile.compile(str(case_config), doraise=True)
    py_compile.compile(str(legacy), doraise=True)

    data = {
        "schema_version": "aquanova.refactor.v142.ro_case_config_capture_state_extract",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": 1,
        "moved_functions": [TARGET_FUNCTION],
        "known_ro_dependencies": known_ro_deps,
        "explicit_import_dependencies": explicit_import_deps,
        "legacy": str(legacy),
        "case_config": str(case_config),
        "note": "Extracts _capture_case_ro_state after V141 moved _ro_diagnostic_points into ro.membrane.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V142 RO case_config capture-state extraction applied")
    print("moved_count=1")
    print(f"moved_functions={TARGET_FUNCTION}")
    print("known_ro_dependencies=" + (", ".join(known_ro_deps) if known_ro_deps else ""))
    print("explicit_import_dependencies=" + (", ".join(explicit_import_deps) if explicit_import_deps else ""))
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
