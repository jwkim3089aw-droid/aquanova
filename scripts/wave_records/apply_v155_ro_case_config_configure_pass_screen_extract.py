#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
import py_compile
from datetime import datetime
from pathlib import Path

TARGET_FUNCTION = "_configure_pass_screen"
TARGET_FILE_REL = Path("ro") / "case_config.py"

# Preserve the active ro.case_config import marker when one already exists.
FALLBACK_IMPORT_MARKER_START = "# V155_RO_CASE_CONFIG_IMPORT_START"
FALLBACK_IMPORT_MARKER_END = "# V155_RO_CASE_CONFIG_IMPORT_END"
EXTRACT_MARKER = "# V155_RO_CASE_CONFIG_CONFIGURE_PASS_SCREEN_APPLIED"
MANIFEST_NAME = "v155_ro_case_config_configure_pass_screen_manifest.json"

LEGACY_ATTR_BRIDGES = set()

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
        ("# V155_RO_CASE_CONFIG_IMPORT_START", "# V155_RO_CASE_CONFIG_IMPORT_END"),
        ("# V154_RO_CASE_CONFIG_IMPORT_START", "# V154_RO_CASE_CONFIG_IMPORT_END"),
        ("# V149_RO_CASE_CONFIG_IMPORT_START", "# V149_RO_CASE_CONFIG_IMPORT_END"),
        ("# V143A_RO_CASE_CONFIG_IMPORT_START", "# V143A_RO_CASE_CONFIG_IMPORT_END"),
        ("# V143_RO_CASE_CONFIG_IMPORT_START", "# V143_RO_CASE_CONFIG_IMPORT_END"),
        ("# V142_RO_CASE_CONFIG_IMPORT_START", "# V142_RO_CASE_CONFIG_IMPORT_END"),
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
        "    from ro.case_config import (\n"
        "        " + body + ",\n"
        "    )\n"
        "except ImportError:\n"
        "    from .ro.case_config import (\n"
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


def ensure_case_config_header(text: str) -> str:
    if text.strip():
        if "from __future__ import annotations" not in text:
            return 'from __future__ import annotations\n\n' + text.rstrip() + "\n\n"
        return text.rstrip() + "\n\n"
    return (
        '"""RO case configuration helpers extracted from wave_ro_engine_legacy."""\n'
        "from __future__ import annotations\n\n"
    )


def build_ro_index(ro_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(ro_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        try:
            tree = ast.parse(read_text(p), filename=str(p))
        except Exception:
            continue
        for name in module_defined_names(tree):
            out.setdefault(name, p.stem)
    return out


def make_ro_bridge(name: str, module: str) -> str:
    return (
        "def " + name + "(*args, **kwargs):\n"
        f"    \"\"\"Runtime bridge to ro.{module}.{name}.\"\"\"\n"
        "    try:\n"
        f"        from ro.{module} import {name} as _impl\n"
        "    except ImportError:\n"
        f"        from .{module} import {name} as _impl\n"
        "    return _impl(*args, **kwargs)"
    )


def make_legacy_attr_bridge(name: str) -> str:
    return (
        "def " + name + "(*args, **kwargs):\n"
        "    \"\"\"Late-bound bridge to a legacy attribute during staged refactor.\"\"\"\n"
        "    try:\n"
        "        import wave_ro_engine_legacy as _legacy\n"
        "    except ImportError:\n"
        "        from .. import wave_ro_engine_legacy as _legacy\n"
        "    return getattr(_legacy, '" + name + "')(*args, **kwargs)"
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
        print("V155 already applied")
        print(f"manifest={manifest}")
        return 0

    legacy_tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(legacy_tree)
    imports = import_sources(legacy_tree, legacy_text.splitlines())
    ro_index = build_ro_index(wr / "ro")

    if TARGET_FUNCTION not in funcs:
        raise SystemExit(f"{TARGET_FUNCTION} not found in wave_ro_engine_legacy.py")

    target_node = funcs[TARGET_FUNCTION]
    case_tree = ast.parse(case_text, filename=str(case_config))
    case_defs = module_defined_names(case_tree)

    target_free = free_names(target_node)

    bridged_ro_refs = sorted(
        name for name in target_free
        if name in ro_index and name not in case_defs and name != TARGET_FUNCTION
    )
    explicit_import_deps = sorted(
        name for name in target_free
        if name in imports and name not in case_defs and name not in bridged_ro_refs
    )
    bridged_legacy_refs = sorted(
        name for name in target_free
        if name in LEGACY_ATTR_BRIDGES and name not in case_defs
    )

    unresolved = (
        target_free
        - set(bridged_ro_refs)
        - set(explicit_import_deps)
        - set(bridged_legacy_refs)
        - case_defs
        - ALLOWED_GLOBALS
    )
    unresolved = sorted(x for x in unresolved if x and not keyword.iskeyword(x))
    if unresolved:
        raise SystemExit(
            f"V155 target is not safe to move. function={TARGET_FUNCTION} unresolved={unresolved}"
        )

    backup(legacy, "v154_before_v155")
    backup(case_config, "v154_before_v155")

    legacy_lines = legacy_text.splitlines()
    source = get_segment(legacy_lines, target_node).rstrip()

    case_text = ensure_case_config_header(case_text)
    case_defs_after = module_defined_names(ast.parse(case_text, filename=str(case_config)))

    blocks = []
    for ref in bridged_ro_refs:
        if ref not in case_defs_after:
            module = ro_index[ref]
            if module == "case_config":
                raise SystemExit(f"V155 refused to bridge {ref} to ro.case_config because it should already be local.")
            blocks.append(make_ro_bridge(ref, module))

    seen_import_blocks = set()
    for dep in explicit_import_deps:
        block = imports[dep].strip()
        if block and block not in case_text and block not in seen_import_blocks:
            blocks.append(block)
            seen_import_blocks.add(block)

    for ref in bridged_legacy_refs:
        if ref not in case_defs_after:
            blocks.append(make_legacy_attr_bridge(ref))

    additions = blocks + [source]
    case_text = case_text.rstrip() + "\n\n" + EXTRACT_MARKER + "\n\n" + "\n\n".join(additions) + "\n"
    case_config.write_text(case_text, encoding="utf-8")

    reduced = remove_spans(legacy_lines, [target_node])
    old_names = parse_imported_names(reduced)
    combined: list[str] = []
    for name in old_names + [TARGET_FUNCTION]:
        if name not in combined:
            combined.append(name)
    reduced = replace_or_insert_import(reduced, combined)
    legacy.write_text(reduced, encoding="utf-8")

    py_compile.compile(str(case_config), doraise=True)
    py_compile.compile(str(legacy), doraise=True)

    active_start, _ = active_import_markers(read_text(legacy))
    data = {
        "schema_version": "aquanova.refactor.v155.ro_case_config_configure_pass_screen_extract",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "moved_count": 1,
        "moved_functions": [TARGET_FUNCTION],
        "bridged_ro_refs": {name: ro_index[name] for name in bridged_ro_refs},
        "explicit_import_dependencies": explicit_import_deps,
        "bridged_legacy_refs": bridged_legacy_refs,
        "active_import_marker": active_start,
        "legacy": str(legacy),
        "case_config": str(case_config),
        "note": "Moves _configure_pass_screen into ro.case_config after _settings_from_ro_case was extracted.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V155 RO case_config configure-pass-screen extraction applied")
    print("moved_count=1")
    print(f"moved_functions={TARGET_FUNCTION}")
    print("bridged_ro_refs=" + ", ".join(f"{k}->{v}" for k, v in data["bridged_ro_refs"].items()))
    print("explicit_import_dependencies=" + (", ".join(explicit_import_deps) if explicit_import_deps else ""))
    print("bridged_legacy_refs=" + (", ".join(bridged_legacy_refs) if bridged_legacy_refs else ""))
    print(f"active_import_marker={active_start}")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
