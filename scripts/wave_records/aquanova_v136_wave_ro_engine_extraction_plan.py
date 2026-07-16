#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import json
import keyword
from collections import defaultdict
from datetime import datetime
from pathlib import Path

GROUP_PATTERNS = {
    "case_config": [
        "case", "schema", "config", "mapping", "settings", "normalize", "validate",
    ],
    "feedwater": [
        "feed", "water", "tds", "ion", "temperature", "temp", "ph", "composition",
        "global_temperature",
    ],
    "membrane": [
        "membrane", "element", "model", "family", "filmtec", "soar", "nf", "ro",
    ],
    "stages": [
        "stage", "pass", "vessel", "pv", "array", "recovery", "flow", "pressure",
    ],
    "chemicals": [
        "chemical", "chemistry", "adjustment", "acid", "caustic", "antiscalant",
        "dose", "dosing", "calcite", "alkalinity",
    ],
    "reports": [
        "report", "pdf", "export", "save", "artifact", "summary", "output",
        "validate",
    ],
    "runner": [
        "run", "configure", "execute", "main", "engine", "automation", "uia",
    ],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


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


def classify_function(name: str) -> tuple[str, int, list[str]]:
    lower = name.lower()
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for group, pats in GROUP_PATTERNS.items():
        group_hits = [p for p in pats if p in lower]
        hits[group] = group_hits
        scores[group] = len(group_hits)

    best = max(scores, key=scores.get)
    score = scores[best]
    if score == 0:
        return "unclear", 0, []
    return best, score, hits[best]


def function_rows(path: Path) -> list[dict]:
    text = read_text(path)
    tree = ast.parse(text, filename=str(path))

    top_func_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    rows = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        used = names_loaded(node)
        defined = names_defined(node)
        ann = annotation_names(node)
        internal_refs = sorted((used - defined - ann) & top_func_names)

        group, score, hit_words = classify_function(node.name)
        loc = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

        risky = []
        lower = node.name.lower()
        if loc > 180:
            risky.append("very_large_function")
        if len(internal_refs) > 8:
            risky.append("many_internal_refs")
        if group == "unclear":
            risky.append("unclear_group")
        if any(x in lower for x in ["configure_schema_ro_case", "run", "main"]):
            risky.append("high_level_entrypoint")
        if any(x in lower for x in ["uia", "click", "window", "dialog"]):
            risky.append("ui_action_context")

        ready = group != "unclear" and len(internal_refs) <= 6 and loc <= 180 and "high_level_entrypoint" not in risky

        rows.append({
            "function": node.name,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "loc": loc,
            "group": group,
            "group_score": score,
            "hit_words": ", ".join(hit_words),
            "internal_refs_count": len(internal_refs),
            "internal_refs": ", ".join(internal_refs[:30]),
            "ready_for_extraction": ready,
            "risk": ", ".join(risky),
        })

    rows.sort(key=lambda r: (r["group"], not r["ready_for_extraction"], -r["loc"], r["function"]))
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

    lines = [
        "# V136 wave_ro_engine extraction plan",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        f"- Functions scanned: `{len(rows)}`",
        "",
        "## Summary by group",
        "",
        "| Group | Functions | Ready candidates | LOC total |",
        "|---|---:|---:|---:|",
    ]

    for group in ["case_config", "feedwater", "membrane", "stages", "chemicals", "reports", "runner", "unclear"]:
        group_rows = by_group.get(group, [])
        lines.append(
            f"| `{group}` | {len(group_rows)} | {sum(1 for r in group_rows if r['ready_for_extraction'])} | {sum(int(r['loc']) for r in group_rows)} |"
        )

    lines += [
        "",
        "## Recommended V137 first extraction",
        "",
        "Prefer a small leaf-helper group, not the main runner.",
        "",
        "Good first targets usually look like:",
        "",
        "```text",
        "temperature/feedwater normalization helpers",
        "membrane name/model mapping helpers",
        "small report/path helpers",
        "```",
        "",
        "Postpone:",
        "",
        "```text",
        "configure_schema_ro_case",
        "_apply_chemical_adjustment",
        "large UIA action functions",
        "anything that opens/clicks WAVE windows",
        "```",
        "",
        "## Ready candidates",
        "",
        "| Group | Function | LOC | Line | Internal refs | Hits |",
        "|---|---|---:|---:|---:|---|",
    ]

    for r in [x for x in rows if x["ready_for_extraction"]][:100]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | {r['lineno']} | {r['internal_refs_count']} | {r['hit_words']} |"
        )

    lines += [
        "",
        "## High-risk / postpone",
        "",
        "| Group | Function | LOC | Line | Risk | Internal refs |",
        "|---|---|---:|---:|---|---:|",
    ]

    high = [r for r in rows if not r["ready_for_extraction"]]
    high.sort(key=lambda r: int(r["loc"]), reverse=True)
    for r in high[:100]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | {r['lineno']} | `{r['risk']}` | {r['internal_refs_count']} |"
        )

    lines += [
        "",
        "## Next patch rule",
        "",
        "V137 should extract only one small group and keep `wave_ro_engine_legacy.py` imports/wrappers for compatibility.",
        "",
        "After every extraction, run:",
        "",
        "```powershell",
        "python .\\scripts\\wave_records\\wave_v135_ro_engine_facade_split_selftest.py",
        "python .\\scripts\\wave_records\\aquanova_v133_batch_refactor_integrity_audit.py",
        "python .\\scripts\\wave_records\\wave_v134e_plan_schema_bridge_static_fix_selftest.py",
        "python .\\scripts\\wave_records\\wave_v134d_batch_plan_schema_self_contained_selftest.py",
        "python .\\scripts\\wave_records\\wave_v132_batch_retry_leaf_extract_selftest.py",
        "python .\\scripts\\wave_records\\wave_v131a_batch_plan_schema_extract_selftest.py",
        "python .\\scripts\\wave_records\\wave_v130a_batch_artifacts_leaf_extract_selftest.py",
        "python .\\scripts\\wave_records\\wave_v128_batch_facade_split_selftest.py",
        "python .\\scripts\\wave_records\\wave_v122_precision_mode_rebrand_selftest.py",
        "python .\\scripts\\wave_records\\wave_v120a_runtime_scope_exact_selftest.py",
        "python .\\scripts\\wave_records\\wave_v118c_runtime_scope_slot_selftest.py",
        "python .\\scripts\\wave_records\\wave_v97_runtime_guard_selftest.py",
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    root = Path.cwd().resolve()
    legacy = root / "scripts" / "wave_records" / "wave_ro_engine_legacy.py"
    out = root / ".refactor_blueprint" / "v136_wave_ro_engine"

    if not legacy.exists():
        raise SystemExit("wave_ro_engine_legacy.py not found. Apply V135 first.")

    out.mkdir(parents=True, exist_ok=True)
    rows = function_rows(legacy)

    write_csv(out / "wave_ro_engine_functions.csv", rows)
    (out / "wave_ro_engine_functions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "WAVE_RO_ENGINE_EXTRACTION_PLAN.md").write_text(make_markdown(root, rows), encoding="utf-8")

    print(f"V136 wave_ro_engine extraction plan complete: {out}")
    print(f"Summary: {out / 'WAVE_RO_ENGINE_EXTRACTION_PLAN.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
