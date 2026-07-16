#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import csv
import json
import keyword
from datetime import datetime
from pathlib import Path
from typing import Any


GROUP_TARGETS = {
    "case_config": Path("ro") / "case_config.py",
    "feedwater": Path("ro") / "feedwater.py",
    "membrane": Path("ro") / "membrane.py",
    "stages": Path("ro") / "stages.py",
    "chemicals": Path("ro") / "chemicals.py",
    "reports": Path("ro") / "reports.py",
    "runner": Path("ro") / "runner.py",
    "unclear": Path("ro") / "runner.py",
}

NAME_GROUP_OVERRIDES = {
    "configure_schema_ro_case": "case_config",
    "open_and_configure_ro_flow_case": "case_config",
    "_settings_from_ro_case": "case_config",
    "_configure_pass_screen": "case_config",
    "_validate_case_automation_support": "case_config",

    "_reassert_global_temperature_after_flow_commit": "feedwater",
    "_has_flow_optimization": "feedwater",

    "_reconcile_ro_pass_topology": "membrane",
    "_verify_stage_grid_membranes": "membrane",
    "_repair_missing_element_type_dialog": "membrane",
    "_ro_diagnostic_points": "membrane",

    "_select_pass": "stages",
    "_set_stage_count": "stages",
    "_add_second_pass": "stages",
    "_stage_cell_point": "stages",
    "_stage_grid_points": "stages",
    "_verify_stage_grid_numeric_values": "stages",
    "_write_stage_numeric_with_retry": "stages",
    "_restore_stage_topologies_after_flow_commit": "stages",
    "_stabilize_after_flow_commit": "stages",
    "_configure_stage_grid": "stages",
    "_replace_value_at_point": "stages",
    "_map_reference_point": "stages",

    "_apply_chemical_adjustment": "chemicals",
    "_find_chemical_dialog": "chemicals",

    "enter_summary_report_case": "reports",

    "_find_new_wave_dialog": "unclear",
    "_apply_special_features": "unclear",
    "_legacy_compatible": "runner",
}

RISKY_UNKNOWN_NAMES = {
    "STATE",
    "pyautogui",
    "time",
    "WaveAutomationError",
    "LibraryTemperatureTransitionError",
    "_fmt_value",
    "REFERENCE_WIDTH",
    "REFERENCE_HEIGHT",
}

UI_HINT_NAMES = {
    "click",
    "screenshot",
    "wait",
    "verify_numeric_point",
    "pyautogui",
    "_select_pass",
    "_replace_value_at_point",
    "_find_new_wave_dialog",
    "_find_chemical_dialog",
}

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


def top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


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


def free_names(node: ast.AST) -> set[str]:
    return {
        x for x in (names_loaded(node) - names_defined(node) - annotation_names(node))
        if x and not keyword.iskeyword(x)
    }


def loc(node: ast.AST) -> int:
    return (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1


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
            out[name] = p.stem
    return out


def risk_tags(
    name: str,
    free: set[str],
    unresolved: set[str],
    bridge_legacy: set[str],
    explicit_imports: set[str],
    node: ast.AST,
) -> list[str]:
    tags: list[str] = []
    l = loc(node)
    if l >= 120:
        tags.append("large_function")
    elif l >= 70:
        tags.append("medium_large_function")
    if name == "configure_schema_ro_case":
        tags.append("high_level_entrypoint")
    if name.startswith("_find_") or "dialog" in name or free & UI_HINT_NAMES:
        tags.append("ui_action_context")
    if unresolved & RISKY_UNKNOWN_NAMES:
        tags.append("risky_unknown_global")
    if "_fmt_value" in unresolved or "_fmt_value" in free:
        tags.append("fmt_dependency")
    if "WaveAutomationError" in unresolved or "WaveAutomationError" in free:
        tags.append("exception_dependency")
    if len(bridge_legacy) >= 4:
        tags.append("many_bridge_refs")
    if explicit_imports:
        tags.append("needs_import_copy")
    return tags


def score_candidate(row: dict[str, Any]) -> tuple[int, int, int, int]:
    # Lower is better.
    risk = set(row["risk"])
    risk_score = 0
    for tag in risk:
        risk_score += {
            "ui_action_context": 2,
            "needs_import_copy": 1,
            "medium_large_function": 2,
            "large_function": 5,
            "high_level_entrypoint": 10,
            "many_bridge_refs": 4,
            "fmt_dependency": 8,
            "exception_dependency": 3,
            "risky_unknown_global": 8,
        }.get(tag, 1)
    return (risk_score, row["loc"], len(row["bridge_legacy_refs"]), len(row["bridge_ro_refs"]))


def main() -> int:
    root = Path.cwd().resolve()
    wr = root / "scripts" / "wave_records"
    legacy = wr / "wave_ro_engine_legacy.py"
    ro_dir = wr / "ro"
    out_dir = root / ".refactor_blueprint" / "v146_ro_bridge_candidates"

    if not legacy.exists():
        raise SystemExit("wave_ro_engine_legacy.py not found. Apply V135 first.")
    if not ro_dir.exists():
        raise SystemExit("scripts/wave_records/ro not found. Apply V135 first.")

    out_dir.mkdir(parents=True, exist_ok=True)

    legacy_text = read_text(legacy)
    legacy_lines = legacy_text.splitlines()
    tree = ast.parse(legacy_text, filename=str(legacy))
    funcs = top_level_functions(tree)
    imports = import_sources(tree, legacy_lines)
    ro_index = build_ro_index(ro_dir)

    rows: list[dict[str, Any]] = []
    for name, node in funcs.items():
        free = free_names(node)
        group = NAME_GROUP_OVERRIDES.get(name, "unclear")
        target_rel = GROUP_TARGETS.get(group, GROUP_TARGETS["unclear"])
        target = wr / target_rel

        target_defs: set[str] = set()
        if target.exists():
            try:
                target_defs = module_defined_names(ast.parse(read_text(target), filename=str(target)))
            except Exception:
                target_defs = set()

        bridge_ro = {
            x for x in free
            if x in ro_index and x not in target_defs and x != name
        }
        bridge_legacy = {
            x for x in free
            if x in funcs and x != name and x not in target_defs and x not in bridge_ro
        }
        explicit_imports = {
            x for x in free
            if x in imports and x not in target_defs and x not in bridge_ro and x not in bridge_legacy
        }

        unresolved = (
            free
            - target_defs
            - ALLOWED_GLOBALS
            - set(imports)
            - set(funcs)
            - set(ro_index)
        )

        row = {
            "group": group,
            "function": name,
            "loc": loc(node),
            "target_module": str(target_rel).replace("\\", "/"),
            "free_names": sorted(free),
            "bridge_legacy_refs": sorted(bridge_legacy),
            "bridge_ro_refs": sorted(bridge_ro),
            "explicit_imports": sorted(explicit_imports),
            "unknown_globals": sorted(unresolved),
            "risk": risk_tags(name, free, unresolved, bridge_legacy, explicit_imports, node),
        }
        row["bridgeable"] = not row["unknown_globals"]
        row["strict_ready"] = not row["unknown_globals"] and not row["bridge_legacy_refs"] and not row["bridge_ro_refs"]
        rows.append(row)

    bridgeable = [r for r in rows if r["bridgeable"] and not r["strict_ready"]]
    bridgeable.sort(key=score_candidate)
    strict = [r for r in rows if r["strict_ready"]]
    strict.sort(key=score_candidate)
    blocked = [r for r in rows if r["unknown_globals"]]
    blocked.sort(key=lambda r: (len(r["unknown_globals"]), r["loc"]))

    # CSV summary
    csv_path = out_dir / "ro_bridge_candidates.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "group", "function", "loc", "target_module", "strict_ready", "bridgeable",
            "bridge_legacy_refs", "bridge_ro_refs", "explicit_imports", "unknown_globals", "risk",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in strict + bridgeable + blocked:
            w.writerow({
                **{k: r[k] for k in ["group", "function", "loc", "target_module", "strict_ready", "bridgeable"]},
                "bridge_legacy_refs": ", ".join(r["bridge_legacy_refs"]),
                "bridge_ro_refs": ", ".join(r["bridge_ro_refs"]),
                "explicit_imports": ", ".join(r["explicit_imports"]),
                "unknown_globals": ", ".join(r["unknown_globals"]),
                "risk": ", ".join(r["risk"]),
            })

    json_path = out_dir / "ro_bridge_candidates.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# V146 RO bridge-aware extraction planner",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Root: `{root}`",
        f"- Functions scanned: `{len(rows)}`",
        f"- Strict ready candidates: `{len(strict)}`",
        f"- Bridgeable candidates: `{len(bridgeable)}`",
        f"- Blocked by unknown globals: `{len(blocked)}`",
        "",
        "## Recommended bridge-aware candidates",
        "",
        "These are candidates with no unknown globals after allowing runtime bridges.",
        "",
        "| Rank | Group | Function | LOC | Target | Legacy bridges | RO bridges | Imports | Risk |",
        "|---:|---|---|---:|---|---|---|---|---|",
    ]
    for i, r in enumerate((strict + bridgeable)[:20], start=1):
        md_lines.append(
            f"| {i} | `{r['group']}` | `{r['function']}` | {r['loc']} | `{r['target_module']}` | "
            f"`{', '.join(r['bridge_legacy_refs'])}` | `{', '.join(r['bridge_ro_refs'])}` | "
            f"`{', '.join(r['explicit_imports'])}` | `{', '.join(r['risk'])}` |"
        )

    md_lines += [
        "",
        "## Blocked by unknown globals",
        "",
        "| Group | Function | LOC | Unknown globals | Internal refs / bridges possible | Risk |",
        "|---|---|---:|---|---|---|",
    ]
    for r in blocked:
        possible = sorted(set(r["bridge_legacy_refs"]) | set(r["bridge_ro_refs"]))
        md_lines.append(
            f"| `{r['group']}` | `{r['function']}` | {r['loc']} | `{', '.join(r['unknown_globals'])}` | "
            f"`{', '.join(possible)}` | `{', '.join(r['risk'])}` |"
        )

    md_lines += [
        "",
        "## Notes",
        "",
        "- Prefer small bridgeable rows with few bridges.",
        "- Avoid moving `_fmt_value`, `WaveAutomationError`, `STATE`, `pyautogui`, `time` dependent functions until those globals are explicit.",
        "- Use runtime bridges for cross-RO references when top-level imports would create cycles.",
    ]

    md_path = out_dir / "RO_BRIDGE_AWARE_EXTRACTION_PLAN.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"V146 RO bridge-aware extraction plan complete: {out_dir}")
    print(f"strict_ready={len(strict)}")
    print(f"bridgeable_candidates={len(bridgeable)}")
    print(f"blocked_by_unknown_globals={len(blocked)}")
    print(f"summary={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
