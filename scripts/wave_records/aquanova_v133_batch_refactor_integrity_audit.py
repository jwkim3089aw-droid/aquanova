#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import csv
import importlib
import json
import keyword
import sys
from datetime import datetime
from pathlib import Path

MODULES = ["batch.artifacts", "batch.plan_schema", "batch.retries"]

ALLOWED_GLOBALS = set(dir(builtins)) | {
    "re", "os", "json", "csv", "math", "time", "datetime", "Path", "Counter", "defaultdict",
    "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable", "Iterator", "Sequence",
    "Mapping", "MutableMapping", "Union", "ROCaseConfig", "None", "True", "False",
}


def collect_target_names(target: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            out.add(n.id)
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


def analyze_file(path: Path, module_name: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(text, filename=str(path))
    module_defs = module_defined_names(tree)
    rows = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        free = names_loaded(node) - names_defined(node) - annotation_names(node)
        unresolved = sorted(x for x in (free - module_defs - ALLOWED_GLOBALS) if x and not keyword.iskeyword(x))
        rows.append({
            "module": module_name,
            "function": node.name,
            "line": node.lineno,
            "loc": (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1,
            "unresolved_count": len(unresolved),
            "unresolved": ", ".join(unresolved),
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def smoke_imports(root: Path) -> list[dict]:
    wr = root / "scripts" / "wave_records"
    sys.path.insert(0, str(wr))
    rows = []
    for name in MODULES + ["wave_batch"]:
        try:
            mod = importlib.import_module(name)
            funcs = [x for x in dir(mod) if not x.startswith("__") and callable(getattr(mod, x, None))]
            rows.append({"module": name, "status": "PASS", "callable_count": len(funcs), "error": ""})
        except Exception as e:
            rows.append({"module": name, "status": "FAIL", "callable_count": 0, "error": repr(e)})
    return rows


def make_md(root: Path, unresolved_rows: list[dict], import_rows: list[dict]) -> str:
    bad = [r for r in unresolved_rows if r["unresolved_count"]]
    lines = [
        "# V133 Batch Refactor Integrity Audit",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        "",
        "## Import smoke",
        "",
        "| Module | Status | Callable count | Error |",
        "|---|---|---:|---|",
    ]
    for r in import_rows:
        lines.append(f"| `{r['module']}` | `{r['status']}` | {r['callable_count']} | `{r['error']}` |")
    lines += ["", "## Extracted module unresolved-name scan", ""]
    if not bad:
        lines += ["PASS: no unresolved global names were detected in extracted batch modules.", "", "You can continue with the next extraction."]
    else:
        lines += [
            "REVIEW: unresolved names were detected. Fix these before extracting more functions.",
            "",
            "| Module | Function | Line | Unresolved names |",
            "|---|---|---:|---|",
        ]
        for r in bad:
            lines.append(f"| `{r['module']}` | `{r['function']}` | {r['line']} | `{r['unresolved']}` |")
    return "\n".join(lines)


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    out = root / ".refactor_blueprint" / "v133_batch_integrity"
    out.mkdir(parents=True, exist_ok=True)

    unresolved_rows = []
    for mod in MODULES:
        path = wr / Path(*mod.split(".")).with_suffix(".py")
        if path.exists():
            unresolved_rows.extend(analyze_file(path, mod))
        else:
            unresolved_rows.append({"module": mod, "function": "<missing module>", "line": 0, "loc": 0, "unresolved_count": 1, "unresolved": f"missing file {path}"})

    import_rows = smoke_imports(root)

    write_csv(out / "extracted_module_unresolved_names.csv", unresolved_rows)
    write_csv(out / "import_smoke.csv", import_rows)
    (out / "batch_integrity_audit.json").write_text(json.dumps({
        "schema_version": "aquanova.refactor.v133.batch_integrity_audit",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "unresolved_rows": unresolved_rows,
        "import_rows": import_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "BATCH_REFACTOR_INTEGRITY_AUDIT.md").write_text(make_md(root, unresolved_rows, import_rows), encoding="utf-8")

    bad_count = sum(1 for r in unresolved_rows if r["unresolved_count"])
    fail_count = sum(1 for r in import_rows if r["status"] != "PASS")
    print(f"V133 batch integrity audit complete: {out}")
    print(f"unresolved_function_rows={bad_count}")
    print(f"import_failures={fail_count}")
    print(f"summary={out / 'BATCH_REFACTOR_INTEGRITY_AUDIT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
