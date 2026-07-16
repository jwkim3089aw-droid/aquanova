#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import subprocess
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".refactor_audit", ".refactor_audit_after_cleanup",
    ".refactor_audit_after_stage2", ".refactor_cleanup", ".refactor_cleanup_stage2",
}


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


def iter_py(root: Path):
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(".py"):
                yield Path(cur) / f


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def module_name(root: Path, p: Path) -> str:
    r = p.relative_to(root).with_suffix("")
    return ".".join(r.parts)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def parse_ast(p: Path):
    try:
        return ast.parse(read_text(p), filename=str(p)), None
    except SyntaxError as e:
        return None, str(e)


def file_metrics(root: Path) -> list[dict]:
    rows = []
    for p in iter_py(root):
        text = read_text(p)
        tree, err = parse_ast(p)
        st = p.stat()
        loc = sum(1 for line in text.splitlines() if line.strip())
        defs = []
        classes = []
        imports = []
        main_guard = "__main__" in text
        if tree:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.Import):
                    imports += [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mod = "." * node.level + (node.module or "")
                    imports.append(mod)
        rows.append({
            "path": rel(root, p),
            "module": module_name(root, p),
            "bytes": st.st_size,
            "size": human_size(st.st_size),
            "loc": loc,
            "top_level_functions": len(defs),
            "top_level_classes": len(classes),
            "main_guard": main_guard,
            "parse_error": err or "",
            "functions": ", ".join(defs[:30]),
            "classes": ", ".join(classes[:20]),
        })
    rows.sort(key=lambda r: (r["loc"], r["bytes"]), reverse=True)
    return rows


def function_metrics(root: Path) -> list[dict]:
    rows = []
    for p in iter_py(root):
        tree, err = parse_ast(p)
        if not tree:
            continue
        text_lines = read_text(p).splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", None) or node.lineno
                loc = end - node.lineno + 1
                rows.append({
                    "path": rel(root, p),
                    "function": node.name,
                    "lineno": node.lineno,
                    "end_lineno": end,
                    "loc": loc,
                    "args": len(getattr(node.args, "args", [])),
                    "decorators": len(node.decorator_list),
                })
    rows.sort(key=lambda r: r["loc"], reverse=True)
    return rows


def import_edges(root: Path) -> list[dict]:
    modules = {module_name(root, p): p for p in iter_py(root)}
    module_set = set(modules)
    rows = []
    for p in iter_py(root):
        src_mod = module_name(root, p)
        tree, err = parse_ast(p)
        if not tree:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    tgt = a.name
                    if tgt in module_set or tgt.split(".")[0] in {"app", "scripts"}:
                        rows.append({"source": src_mod, "target": tgt, "kind": "import", "line": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                level = node.level
                mod = node.module or ""
                if level:
                    # Resolve relative import roughly.
                    parts = src_mod.split(".")[:-1]
                    base = parts[: max(0, len(parts) - level + 1)]
                    tgt = ".".join(base + ([mod] if mod else []))
                else:
                    tgt = mod
                if tgt in module_set or tgt.split(".")[0] in {"app", "scripts"}:
                    rows.append({"source": src_mod, "target": tgt, "kind": "from", "line": node.lineno})
    return rows


def entrypoints(root: Path) -> list[dict]:
    rows = []
    for p in iter_py(root):
        text = read_text(p)
        score = 0
        reasons = []
        if "__main__" in text:
            score += 5
            reasons.append("__main__")
        if "argparse.ArgumentParser" in text or "click.command" in text:
            score += 4
            reasons.append("cli_args")
        if p.name.startswith(("apply_", "wave_v", "aquanova_", "run_")):
            score += 2
            reasons.append("script_name")
        if "pytest" in text or p.name.startswith("test_"):
            score -= 2
            reasons.append("test")
        if score > 0:
            rows.append({
                "path": rel(root, p),
                "score": score,
                "reasons": ", ".join(reasons),
            })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def git_status(root: Path) -> list[str]:
    try:
        r = subprocess.run(["git", "status", "--short"], cwd=str(root), text=True, capture_output=True, timeout=10)
        return r.stdout.strip().splitlines()
    except Exception as e:
        return [f"git unavailable: {e}"]


def blueprint_text(root: Path, files: list[dict], funcs: list[dict], edges: list[dict], entries: list[dict]) -> str:
    top = files[:20]
    fn_top = funcs[:30]
    imports_by_src = Counter(e["source"] for e in edges)
    imported_by = Counter(e["target"] for e in edges)

    lines = []
    lines += [
        "# AquaNova V127 Refactor Blueprint",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        "",
        "## Current conclusion",
        "",
        "Cleanup is now good enough to start real refactoring. The active tree is no longer dominated by ZIP/source-snapshot artifacts.",
        "",
        "Refactor priority should be code complexity, not disk size:",
        "",
        "1. `scripts/wave_records/wave_uia.py`",
        "2. `scripts/wave_records/wave_ro_engine.py`",
        "3. `scripts/wave_records/wave_batch.py`",
        "4. `app/services/simulation/calibration/wave_runtime_correction.py`",
        "5. `app/services/simulation/engine.py`",
        "6. `app/services/simulation/modules/hrro/engine.py`",
        "",
        "## Refactor safety rule",
        "",
        "Do not rewrite behavior first. First split files while preserving public imports and tests. Add wrapper modules that re-export old function names.",
        "",
        "## Proposed target structure",
        "",
        "```text",
        "scripts/wave_records/",
        "  wave_uia.py                         # compatibility wrapper initially",
        "  uia/",
        "    __init__.py",
        "    app_window.py                     # launch/find/restore WAVE windows",
        "    controls.py                       # UIA find/click/type helpers",
        "    screenshots.py                    # capture/debug artifacts",
        "    dialogs.py                        # popup detection/closing",
        "    navigation.py                     # screen/page movement",
        "  wave_ro_engine.py                   # compatibility wrapper initially",
        "  ro/",
        "    __init__.py",
        "    membrane.py",
        "    feedwater.py",
        "    stages.py",
        "    reports.py",
        "    runner.py",
        "  wave_batch.py                       # compatibility wrapper initially",
        "  batch/",
        "    __init__.py",
        "    plan_schema.py",
        "    runner.py",
        "    resume.py",
        "    artifacts.py",
        "    retries.py",
        "",
        "app/services/simulation/",
        "  engine.py                           # facade initially",
        "  core/",
        "    streams.py",
        "    mass_balance.py",
        "    pressure.py",
        "    quality.py",
        "    economics.py",
        "  modules/hrro/",
        "    engine.py                         # facade initially",
        "    cycle.py",
        "    pumps.py",
        "    pf_modes.py",
        "    recovery_control.py",
        "    warnings.py",
        "  calibration/",
        "    runtime_private.py                # public-safe naming later",
        "    scope.py",
        "    residual_models.py",
        "    report.py",
        "```",
        "",
        "## Largest files",
        "",
        "| Rank | File | LOC | Functions | Classes |",
        "|---:|---|---:|---:|---:|",
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"| {i} | `{r['path']}` | {r['loc']} | {r['top_level_functions']} | {r['top_level_classes']} |")

    lines += [
        "",
        "## Largest functions",
        "",
        "| Rank | File | Function | LOC | Line |",
        "|---:|---|---|---:|---:|",
    ]
    for i, r in enumerate(fn_top, 1):
        lines.append(f"| {i} | `{r['path']}` | `{r['function']}` | {r['loc']} | {r['lineno']} |")

    lines += [
        "",
        "## Likely entrypoints",
        "",
        "| Rank | File | Score | Reasons |",
        "|---:|---|---:|---|",
    ]
    for i, r in enumerate(entries[:40], 1):
        lines.append(f"| {i} | `{r['path']}` | {r['score']} | {r['reasons']} |")

    lines += [
        "",
        "## Import hotspots",
        "",
        "Most internal imports from a source module:",
        "",
        "| Module | Internal import edges |",
        "|---|---:|",
    ]
    for mod, count in imports_by_src.most_common(20):
        lines.append(f"| `{mod}` | {count} |")

    lines += [
        "",
        "Most imported internal modules:",
        "",
        "| Module | Imported by edges |",
        "|---|---:|",
    ]
    for mod, count in imported_by.most_common(20):
        lines.append(f"| `{mod}` | {count} |")

    lines += [
        "",
        "## Recommended V128",
        "",
        "Start with a low-risk facade split of `wave_batch.py` or `wave_ro_engine.py`, not `wave_uia.py`.",
        "",
        "`wave_uia.py` is the biggest but most fragile because it touches actual desktop automation. For the first real refactor, create a package and move pure helpers only, leaving UIA action order unchanged.",
        "",
        "Recommended first real code refactor:",
        "",
        "```text",
        "V128: split wave_batch.py into batch/plan_schema.py, batch/resume.py, batch/artifacts.py while keeping wave_batch.py as a wrapper.",
        "```",
        "",
        "Reason: batch logic is easier to test without opening WAVE, and it supports the 10,000-run resume requirement.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=".refactor_blueprint")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    files = file_metrics(root)
    funcs = function_metrics(root)
    edges = import_edges(root)
    entries = entrypoints(root)
    status = git_status(root)

    write_csv(out / "python_files.csv", files)
    write_csv(out / "python_functions.csv", funcs)
    write_csv(out / "import_edges.csv", edges)
    write_csv(out / "entrypoints.csv", entries)
    (out / "git_status_short.txt").write_text("\n".join(status) + "\n", encoding="utf-8")

    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "python_files": files,
        "python_functions": funcs[:500],
        "import_edges": edges,
        "entrypoints": entries,
        "git_status_short": status,
    }
    (out / "refactor_blueprint.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "REFACTOR_BLUEPRINT.md").write_text(blueprint_text(root, files, funcs, edges, entries), encoding="utf-8")

    print(f"V127 refactor blueprint complete: {out}")
    print(f"Summary: {out / 'REFACTOR_BLUEPRINT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
