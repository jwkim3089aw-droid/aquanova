#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import csv
import json
import keyword
from collections import defaultdict
from datetime import datetime
from pathlib import Path

GROUP_PATTERNS = {
    "case_config": ["case", "schema", "config", "mapping", "settings", "normalize", "validate"],
    "feedwater": ["feed", "water", "tds", "ion", "temperature", "temp", "ph", "composition", "global_temperature", "flow_optimization"],
    "membrane": ["membrane", "element", "model", "family", "filmtec", "soar", "nf", "ro"],
    "stages": ["stage", "pass", "vessel", "pv", "array", "recovery", "flow", "pressure"],
    "chemicals": ["chemical", "chemistry", "adjustment", "acid", "caustic", "antiscalant", "dose", "dosing", "calcite", "alkalinity"],
    "reports": ["report", "pdf", "export", "save", "artifact", "summary", "output"],
    "runner": ["run", "configure", "execute", "main", "engine", "automation", "uia"],
}

ALLOWED_BUILTINS = set(dir(builtins)) | {"None", "True", "False"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def collect_target_names(target: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


def top_level_defs_and_imports(tree: ast.Module, lines: list[str]) -> tuple[set[str], dict[str, str], set[str]]:
    defined: set[str] = set()
    import_sources: dict[str, str] = {}
    star_import_modules: set[str] = set()

    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                defined.update(collect_target_names(t))
        elif isinstance(n, ast.AnnAssign):
            defined.update(collect_target_names(n.target))
        elif isinstance(n, ast.AugAssign):
            defined.update(collect_target_names(n.target))
        elif isinstance(n, ast.Import):
            src = "\n".join(lines[n.lineno - 1:getattr(n, "end_lineno", n.lineno)])
            for a in n.names:
                name = a.asname or a.name.split(".")[0]
                defined.add(name)
                import_sources[name] = src
        elif isinstance(n, ast.ImportFrom):
            src = "\n".join(lines[n.lineno - 1:getattr(n, "end_lineno", n.lineno)])
            for a in n.names:
                if a.name == "*":
                    mod = "." * n.level + (n.module or "")
                    star_import_modules.add(mod)
                    continue
                name = a.asname or a.name
                defined.add(name)
                import_sources[name] = src

    return defined, import_sources, star_import_modules


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


def function_free_names(node: ast.AST) -> set[str]:
    return names_loaded(node) - names_defined(node) - annotation_names(node)


def classify_function(name: str) -> tuple[str, int, list[str]]:
    lower = name.lower()
    best_group = "unclear"
    best_hits: list[str] = []
    for group, pats in GROUP_PATTERNS.items():
        hits = [p for p in pats if p in lower]
        if len(hits) > len(best_hits):
            best_group = group
            best_hits = hits
    if not best_hits:
        return "unclear", 0, []
    return best_group, len(best_hits), best_hits


def ro_module_defined_names(wr: Path) -> set[str]:
    out: set[str] = set()
    ro_dir = wr / "ro"
    if not ro_dir.exists():
        return out
    for path in ro_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        defs, _, _ = top_level_defs_and_imports(tree, lines)
        out.update(defs)
    return out


def function_rows(root: Path) -> list[dict]:
    wr = root / "scripts" / "wave_records"
    legacy = wr / "wave_ro_engine_legacy.py"
    text = read_text(legacy)
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(legacy))

    module_defs, import_sources, star_imports = top_level_defs_and_imports(tree, lines)
    ro_defs = ro_module_defined_names(wr)
    top_func_names = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    rows: list[dict] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        free = {x for x in function_free_names(node) if x and not keyword.iskeyword(x)}
        internal_refs = sorted(free & top_func_names)
        ro_refs = sorted((free - set(internal_refs)) & ro_defs)
        imported_refs = sorted((free - set(internal_refs) - set(ro_refs)) & set(import_sources))
        unknown_globals = sorted(free - set(internal_refs) - set(ro_refs) - set(imported_refs) - ALLOWED_BUILTINS)

        group, score, hit_words = classify_function(node.name)
        loc = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

        risk: list[str] = []
        lower = node.name.lower()
        if loc > 160:
            risk.append("very_large_function")
        if len(internal_refs) > 6:
            risk.append("many_internal_refs")
        if unknown_globals:
            risk.append("unknown_global_dependency")
        if group == "unclear":
            risk.append("unclear_group")
        if any(x in lower for x in ["configure_schema_ro_case", "run", "main"]):
            risk.append("high_level_entrypoint")
        if any(x in lower for x in ["uia", "click", "window", "dialog"]):
            risk.append("ui_action_context")

        # A conservative extraction candidate:
        # - no unknown global dependencies
        # - small enough
        # - few same-file refs
        # - not the main entrypoint
        ready = (
            not unknown_globals
            and loc <= 90
            and len(internal_refs) <= 1
            and "high_level_entrypoint" not in risk
            and group != "unclear"
        )

        rows.append({
            "function": node.name,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "loc": loc,
            "group": group,
            "group_score": score,
            "hit_words": ", ".join(hit_words),
            "ready_dependency_aware": ready,
            "internal_refs_count": len(internal_refs),
            "internal_refs": ", ".join(internal_refs),
            "ro_module_refs_count": len(ro_refs),
            "ro_module_refs": ", ".join(ro_refs),
            "imported_refs_count": len(imported_refs),
            "imported_refs": ", ".join(imported_refs),
            "unknown_globals_count": len(unknown_globals),
            "unknown_globals": ", ".join(unknown_globals),
            "risk": ", ".join(risk),
        })

    rows.sort(key=lambda r: (not r["ready_dependency_aware"], r["group"], int(r["loc"]), r["function"]))
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


def make_markdown(root: Path, rows: list[dict]) -> str:
    by_group = defaultdict(list)
    for r in rows:
        by_group[r["group"]].append(r)

    ready = [r for r in rows if r["ready_dependency_aware"]]
    blocked = [r for r in rows if not r["ready_dependency_aware"]]

    lines = [
        "# V139 RO engine dependency-aware extraction plan",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        f"- Functions scanned: `{len(rows)}`",
        f"- Dependency-aware ready candidates: `{len(ready)}`",
        "",
        "## Summary by group",
        "",
        "| Group | Functions | Ready | Unknown-global blocked | LOC total |",
        "|---|---:|---:|---:|---:|",
    ]

    for group in ["case_config", "feedwater", "membrane", "stages", "chemicals", "reports", "runner", "unclear"]:
        group_rows = by_group.get(group, [])
        lines.append(
            f"| `{group}` | {len(group_rows)} | "
            f"{sum(1 for r in group_rows if r['ready_dependency_aware'])} | "
            f"{sum(1 for r in group_rows if int(r['unknown_globals_count']) > 0)} | "
            f"{sum(int(r['loc']) for r in group_rows)} |"
        )

    lines += [
        "",
        "## Recommended next extraction candidates",
        "",
        "Pick one small row from here. Do not extract high-level UI runners yet.",
        "",
        "| Group | Function | LOC | Internal refs | Imported refs | RO refs |",
        "|---|---|---:|---:|---|---|",
    ]

    for r in ready[:40]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | {r['internal_refs_count']} | `{r['imported_refs']}` | `{r['ro_module_refs']}` |"
        )

    lines += [
        "",
        "## Blocked because of unknown globals",
        "",
        "These are exactly the functions likely to fail like `_settings_from_ro_case` did.",
        "",
        "| Group | Function | LOC | Unknown globals | Internal refs | Risk |",
        "|---|---|---:|---|---|---|",
    ]

    unknown_blocked = [r for r in blocked if int(r["unknown_globals_count"]) > 0]
    unknown_blocked.sort(key=lambda r: (r["unknown_globals"], int(r["loc"])))
    for r in unknown_blocked[:80]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | `{r['unknown_globals']}` | `{r['internal_refs']}` | `{r['risk']}` |"
        )

    lines += [
        "",
        "## Large/high-risk postpone list",
        "",
        "| Group | Function | LOC | Risk | Internal refs | Unknown globals |",
        "|---|---|---:|---|---|---|",
    ]

    high = sorted(blocked, key=lambda r: int(r["loc"]), reverse=True)
    for r in high[:60]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | `{r['risk']}` | `{r['internal_refs']}` | `{r['unknown_globals']}` |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- `_settings_from_ro_case` should remain postponed while `_fmt_value` is unknown/global.",
        "- Prefer functions with `Unknown globals` empty.",
        "- UI functions can still be moved later, but only after their imported dependencies are explicit.",
    ]
    return "\n".join(lines)


def main() -> int:
    root = Path.cwd().resolve()
    legacy = root / "scripts" / "wave_records" / "wave_ro_engine_legacy.py"
    out = root / ".refactor_blueprint" / "v139_wave_ro_engine_dependency_plan"

    if not legacy.exists():
        raise SystemExit("wave_ro_engine_legacy.py not found. Apply V135 first.")

    out.mkdir(parents=True, exist_ok=True)
    rows = function_rows(root)

    write_csv(out / "wave_ro_engine_dependency_functions.csv", rows)
    (out / "wave_ro_engine_dependency_functions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "WAVE_RO_ENGINE_DEPENDENCY_EXTRACTION_PLAN.md").write_text(make_markdown(root, rows), encoding="utf-8")

    print(f"V139 RO engine dependency-aware plan complete: {out}")
    print(f"Summary: {out / 'WAVE_RO_ENGINE_DEPENDENCY_EXTRACTION_PLAN.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
