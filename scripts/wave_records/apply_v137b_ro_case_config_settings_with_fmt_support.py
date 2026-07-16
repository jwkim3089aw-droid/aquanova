#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
import py_compile
from datetime import datetime
from pathlib import Path

TARGET_FUNCTION = "_settings_from_ro_case"
SUPPORT_NAME = "_fmt_value"
TARGET_FILE_REL = Path("ro") / "case_config.py"

IMPORT_MARKER_START = "# V137B_RO_CASE_CONFIG_IMPORT_START"
IMPORT_MARKER_END = "# V137B_RO_CASE_CONFIG_IMPORT_END"
EXTRACT_MARKER = "# V137B_RO_CASE_CONFIG_SETTINGS_APPLIED"
MANIFEST_NAME = "v137b_ro_case_config_settings_manifest.json"

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


def node_defines_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(name in collect_target_names(t) for t in node.targets)
    if isinstance(node, ast.AnnAssign):
        return name in collect_target_names(node.target)
    if isinstance(node, ast.AugAssign):
        return name in collect_target_names(node.target)
    if isinstance(node, ast.Import):
        for a in node.names:
            if (a.asname or a.name.split(".")[0]) == name:
                return True
    if isinstance(node, ast.ImportFrom):
        for a in node.names:
            if a.name != "*" and (a.asname or a.name) == name:
                return True
    return False


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


def find_support_node(tree: ast.Module, name: str) -> ast.AST | None:
    for node in tree.body:
        if node_defines_name(node, name):
            return node
    return None


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
        ("# V137_RO_CASE_CONFIG_IMPORT_START", "# V137_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137A_RO_CASE_CONFIG_IMPORT_START", "# V137A_RO_CASE_CONFIG_IMPORT_END"),
        (IMPORT_MARKER_START, IMPORT_MARKER_END),
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
        ("# V137_RO_CASE_CONFIG_IMPORT_START", "# V137_RO_CASE_CONFIG_IMPORT_END"),
        ("# V137A_RO_CASE_CONFIG_IMPORT_START", "# V137A_RO_CASE_CONFIG_IMPORT_END"),
        (IMPORT_MARKER_START, IMPORT_MARKER_END),
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
        print("V137B already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    if TARGET_FUNCTION not in funcs:
        raise SystemExit(f"{TARGET_FUNCTION} not found in wave_ro_engine_legacy.py")

    legacy_lines = legacy_text.splitlines()
    target_node = funcs[TARGET_FUNCTION]
    support_node = find_support_node(legacy_tree, SUPPORT_NAME)

    case_tree = ast.parse(case_text, filename=str(case_config))
    case_defs = module_defined_names(case_tree)

    free = free_names(target_node)
    needs_support = SUPPORT_NAME in free
    if needs_support and SUPPORT_NAME not in case_defs and support_node is None:
        raise SystemExit(
            f"{TARGET_FUNCTION} needs {SUPPORT_NAME}, but {SUPPORT_NAME} was not found as a top-level function/import/assignment. "
            "Run: Select-String -Path .\\scripts\\wave_records\\wave_ro_engine_legacy.py -Pattern '_fmt_value' -Context 3,3"
        )

    provided_names = set(case_defs)
    if support_node is not None:
        provided_names.add(SUPPORT_NAME)

    unresolved = (
        free
        - provided_names
        - ALLOWED_GLOBALS
    )
    unresolved = sorted(x for x in unresolved if x and not keyword.iskeyword(x))
    if unresolved:
        raise SystemExit(
            f"V137B target is not safe to move. function={TARGET_FUNCTION} unresolved={unresolved}"
        )

    backup(legacy, "v137a_failed_before_v137b")
    backup(case_config, "v137a_failed_before_v137b")

    additions: list[str] = []
    copied_support = False
    if needs_support and SUPPORT_NAME not in case_defs and support_node is not None:
        additions.append(get_segment(legacy_lines, support_node).rstrip())
        copied_support = True
    additions.append(get_segment(legacy_lines, target_node).rstrip())

    case_text = ensure_case_config_header(case_text)
    case_text = case_text.rstrip() + "\n\n" + EXTRACT_MARKER + "\n\n" + "\n\n".join(additions) + "\n"
    case_config.write_text(case_text, encoding="utf-8")

    # Remove only the main target. Keep _fmt_value in legacy if it existed there;
    # this avoids breaking other legacy helpers that may still use it.
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
        "schema_version": "aquanova.refactor.v137b.ro_case_config_settings_with_fmt_support",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": 1,
        "moved_functions": [TARGET_FUNCTION],
        "copied_support_count": 1 if copied_support else 0,
        "copied_support_names": [SUPPORT_NAME] if copied_support else [],
        "legacy": str(legacy),
        "case_config": str(case_config),
        "note": "V137/V137A failed safely because _fmt_value was not a top-level function. V137B copies the top-level support definition/import/assignment when found, but only removes _settings_from_ro_case from legacy.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V137B RO case_config settings extraction applied")
    print("moved_count=1")
    print(f"moved_functions={TARGET_FUNCTION}")
    print("copied_support_count=" + str(1 if copied_support else 0))
    if copied_support:
        print(f"copied_support_names={SUPPORT_NAME}")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
