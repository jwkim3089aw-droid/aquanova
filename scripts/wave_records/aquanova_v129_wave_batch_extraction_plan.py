#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

GROUP_PATTERNS = {
    "artifacts": [
        "pdf", "export", "report", "artifact", "output", "filename", "file_name",
        "validate", "save", "path", "manifest",
    ],
    "resume": [
        "resume", "checkpoint", "state", "completed", "skip", "done", "progress",
    ],
    "retries": [
        "retry", "attempt", "failure", "failed", "error", "restart", "recover",
    ],
    "plan_schema": [
        "plan", "schema", "case", "excel", "row", "matrix", "load", "parse",
    ],
    "runner": [
        "run", "batch", "production", "orchestrate", "execute", "main",
    ],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def get_source_segment(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1:end]) + "\n"


def names_used(node: ast.AST) -> set[str]:
    used: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used.add(n.id)
    return used


def names_defined(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Param)):
            out.add(n.id)
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
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))

    top_defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    top_func_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    rows = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        source = get_source_segment(lines, node)
        used = names_used(node)
        defined = names_defined(node)
        internal_refs = sorted((used - defined) & top_func_names)
        group, score, hit_words = classify_function(node.name)
        loc = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

        # Very conservative readiness scoring.
        risky = []
        if "driver" in used or "app" in used or "desktop" in used or "uia" in node.name.lower():
            risky.append("ui_or_driver_context")
        if loc > 180:
            risky.append("very_large_function")
        if len(internal_refs) > 8:
            risky.append("many_internal_refs")
        if group == "unclear":
            risky.append("unclear_group")

        # Candidate extraction is low risk only if it has a clear group and limited refs.
        ready = group != "unclear" and len(internal_refs) <= 6 and loc <= 220

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
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "# V129 wave_batch extraction plan",
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
    for group in ["artifacts", "resume", "retries", "plan_schema", "runner", "unclear"]:
        group_rows = by_group.get(group, [])
        lines.append(
            f"| `{group}` | {len(group_rows)} | {sum(1 for r in group_rows if r['ready_for_extraction'])} | {sum(int(r['loc']) for r in group_rows)} |"
        )

    lines += [
        "",
        "## Recommended V130 first extraction",
        "",
        "Start with `artifacts` only if the ready list includes PDF/output validation helpers with limited internal dependencies.",
        "",
        "Good first targets usually look like:",
        "",
        "```text",
        "validate_exported_pdf_case",
        "find/export/report path helpers",
        "manifest/output filename helpers",
        "```",
        "",
        "Do not extract large runner functions yet:",
        "",
        "```text",
        "run_ro_excel_batch",
        "production/batch orchestration",
        "retry/restart loops",
        "```",
        "",
        "## Ready candidates",
        "",
        "| Group | Function | LOC | Line | Internal refs | Hits |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in [x for x in rows if x["ready_for_extraction"]][:80]:
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
    for r in high[:80]:
        lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | {r['lineno']} | {r['risk']} | {r['internal_refs_count']} |"
        )

    lines += [
        "",
        "## Next patch rule",
        "",
        "V130 should extract only one group and keep `wave_batch_legacy.py` wrappers for compatibility. After every extraction, run:",
        "",
        "```powershell",
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
    legacy = root / "scripts" / "wave_records" / "wave_batch_legacy.py"
    out = root / ".refactor_blueprint" / "v129_wave_batch"

    if not legacy.exists():
        raise SystemExit("wave_batch_legacy.py not found. Apply V128 first.")

    out.mkdir(parents=True, exist_ok=True)
    rows = function_rows(legacy)

    write_csv(out / "wave_batch_functions.csv", rows)
    (out / "wave_batch_functions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "WAVE_BATCH_EXTRACTION_PLAN.md").write_text(make_markdown(root, rows), encoding="utf-8")

    print(f"V129 wave_batch extraction plan complete: {out}")
    print(f"Summary: {out / 'WAVE_BATCH_EXTRACTION_PLAN.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
