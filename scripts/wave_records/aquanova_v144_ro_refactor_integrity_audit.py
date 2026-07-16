#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import csv
import importlib
import json
import keyword
import py_compile
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


EXPECTED_EXPORTS = {
    "ro.feedwater": ["_has_flow_optimization"],
    "ro.stages": ["_stage_grid_points"],
    "ro.membrane": ["_ro_diagnostic_points"],
    "ro.case_config": ["_capture_case_ro_state", "_verify_case_operating_inputs"],
    "wave_ro_engine": [
        "configure_schema_ro_case",
        "_has_flow_optimization",
        "_stage_grid_points",
        "_ro_diagnostic_points",
        "_capture_case_ro_state",
        "_verify_case_operating_inputs",
    ],
}

MODULES_TO_IMPORT = [
    "ro.case_config",
    "ro.feedwater",
    "ro.membrane",
    "ro.stages",
    "ro.chemicals",
    "ro.reports",
    "ro.runner",
    "wave_ro_engine",
    "wave_ro_engine_legacy",
]

ALLOWED_GLOBALS = set(dir(builtins)) | {
    "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable", "Iterator",
    "Sequence", "Mapping", "MutableMapping", "Union", "Path", "datetime",
    "None", "True", "False",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def collect_target_names(target: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


def module_defined_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
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
                elif isinstance(sub, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    if isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            out.update(collect_target_names(t))
                    elif isinstance(sub, ast.AnnAssign):
                        out.update(collect_target_names(sub.target))
                    elif isinstance(sub, ast.AugAssign):
                        out.update(collect_target_names(sub.target))
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.add(sub.name)
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

    def visit_ann(ann: ast.AST | None) -> None:
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


def function_free_names(node: ast.AST) -> set[str]:
    return names_loaded(node) - names_defined(node) - annotation_names(node)


def scan_unresolved(path: Path) -> list[dict[str, Any]]:
    text = read_text(path)
    tree = ast.parse(text, filename=str(path))
    module_defs = module_defined_names(tree)
    rows: list[dict[str, Any]] = []

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        free = {
            x for x in function_free_names(node)
            if x and not keyword.iskeyword(x)
        }
        unresolved = sorted(free - module_defs - ALLOWED_GLOBALS)
        if unresolved:
            rows.append({
                "file": str(path),
                "function": node.name,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "loc": (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1,
                "unresolved": ", ".join(unresolved),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = ["file", "function", "lineno", "end_lineno", "loc", "unresolved"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def import_smoke(wr: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sys.path.insert(0, str(wr))
    for name in MODULES_TO_IMPORT:
        try:
            mod = importlib.import_module(name)
            rows.append({"module": name, "ok": True, "error": ""})
        except Exception as exc:
            rows.append({
                "module": name,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return rows


def expected_export_rows(wr: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sys.path.insert(0, str(wr))
    for mod_name, names in EXPECTED_EXPORTS.items():
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            for name in names:
                rows.append({
                    "module": mod_name,
                    "name": name,
                    "ok": False,
                    "error": f"module import failed: {type(exc).__name__}: {exc}",
                })
            continue
        for name in names:
            rows.append({
                "module": mod_name,
                "name": name,
                "ok": hasattr(mod, name),
                "error": "" if hasattr(mod, name) else "missing attribute",
            })
    return rows


def py_compile_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in paths:
        try:
            py_compile.compile(str(p), doraise=True)
            ast.parse(read_text(p), filename=str(p))
            rows.append({"file": str(p), "ok": True, "error": ""})
        except Exception as exc:
            rows.append({"file": str(p), "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def make_markdown(
    root: Path,
    compile_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    export_rows: list[dict[str, Any]],
    unresolved_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# V144 RO refactor integrity audit",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        f"- Compile failures: `{sum(1 for r in compile_rows if not r['ok'])}`",
        f"- Import failures: `{sum(1 for r in import_rows if not r['ok'])}`",
        f"- Expected export failures: `{sum(1 for r in export_rows if not r['ok'])}`",
        f"- Unresolved function rows: `{len(unresolved_rows)}`",
        "",
        "## Compile / parse",
        "",
        "| File | OK | Error |",
        "|---|---:|---|",
    ]
    for r in compile_rows:
        lines.append(f"| `{r['file']}` | {r['ok']} | `{r['error']}` |")

    lines += [
        "",
        "## Import smoke",
        "",
        "| Module | OK | Error |",
        "|---|---:|---|",
    ]
    for r in import_rows:
        lines.append(f"| `{r['module']}` | {r['ok']} | `{r['error']}` |")

    lines += [
        "",
        "## Expected exports",
        "",
        "| Module | Name | OK | Error |",
        "|---|---|---:|---|",
    ]
    for r in export_rows:
        lines.append(f"| `{r['module']}` | `{r['name']}` | {r['ok']} | `{r['error']}` |")

    lines += [
        "",
        "## Static unresolved globals in extracted RO modules",
        "",
    ]
    if not unresolved_rows:
        lines.append("PASS: no unresolved global names in extracted RO module functions.")
    else:
        lines += [
            "| File | Function | LOC | Unresolved |",
            "|---|---|---:|---|",
        ]
        for r in unresolved_rows:
            lines.append(f"| `{r['file']}` | `{r['function']}` | {r['loc']} | `{r['unresolved']}` |")

    ok = (
        not any(not r["ok"] for r in compile_rows)
        and not any(not r["ok"] for r in import_rows)
        and not any(not r["ok"] for r in export_rows)
        and not unresolved_rows
    )
    lines += [
        "",
        "## Verdict",
        "",
        "PASS" if ok else "CHECK REQUIRED",
    ]
    return "\n".join(lines)


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    ro_dir = wr / "ro"
    out = root / ".refactor_blueprint" / "v144_ro_integrity"

    if not wr.exists():
        raise SystemExit("scripts/wave_records not found")
    if not ro_dir.exists():
        raise SystemExit("scripts/wave_records/ro not found. Apply V135 first.")

    out.mkdir(parents=True, exist_ok=True)

    py_paths = sorted(ro_dir.glob("*.py")) + [
        wr / "wave_ro_engine.py",
        wr / "wave_ro_engine_legacy.py",
    ]
    py_paths = [p for p in py_paths if p.exists()]

    compile = py_compile_rows(py_paths)
    imports = import_smoke(wr)
    exports = expected_export_rows(wr)
    unresolved: list[dict[str, Any]] = []
    for p in sorted(ro_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        unresolved.extend(scan_unresolved(p))

    write_csv(out / "ro_unresolved_globals.csv", unresolved)
    (out / "ro_unresolved_globals.json").write_text(json.dumps(unresolved, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ro_import_smoke.json").write_text(json.dumps(imports, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ro_expected_exports.json").write_text(json.dumps(exports, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "RO_REFACTOR_INTEGRITY_AUDIT.md").write_text(
        make_markdown(root, compile, imports, exports, unresolved),
        encoding="utf-8",
    )

    print(f"V144 RO refactor integrity audit complete: {out}")
    print(f"unresolved_function_rows={len(unresolved)}")
    print(f"import_failures={sum(1 for r in imports if not r['ok'])}")
    print(f"expected_export_failures={sum(1 for r in exports if not r['ok'])}")
    print(f"summary={out / 'RO_REFACTOR_INTEGRITY_AUDIT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
