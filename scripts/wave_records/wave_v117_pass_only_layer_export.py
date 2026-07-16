#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records" / "results").exists():
        return cwd
    here = Path(__file__).resolve()
    root = here.parents[2]
    if (root / "scripts" / "wave_records").exists():
        return root
    return cwd


def _latest_file(directory: Path, pattern: str) -> Path:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No file matching {pattern} under {directory}")
    return files[0]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser(description="V117 export pass-only residual layer from V98 + V116 shadow validation.")
    ap.add_argument("--layer", default=None, help="V98 scope residual layer JSON.")
    ap.add_argument("--group-summary", default=None, help="V116 group summary CSV.")
    ap.add_argument("--output", default=None, help="Pass-only layer JSON output path.")
    ap.add_argument("--config-output", default=None, help="Disabled runtime config JSON output path.")
    ap.add_argument("--markdown-output", default=None, help="Markdown report output path.")
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = _project_root()
    default_dir = root / "scripts" / "wave_records" / "results" / "_calibration_v115"

    layer_path = Path(args.layer).resolve() if args.layer else _latest_file(default_dir, "*_v98_scope_residual_layer.json")
    group_path = Path(args.group_summary).resolve() if args.group_summary else _latest_file(default_dir, "*_v116_group_summary.csv")

    out_layer = Path(args.output).resolve() if args.output else default_dir / "wave_v117_pass_only_scope_residual_layer.json"
    out_config = Path(args.config_output).resolve() if args.config_output else default_dir / "wave_v117_runtime_config_DISABLED.json"
    out_md = Path(args.markdown_output).resolve() if args.markdown_output else default_dir / "wave_v117_pass_only_layer_report.md"

    source = json.loads(layer_path.read_text(encoding="utf-8"))
    groups = _read_csv(group_path)

    pass_model_ids = {
        g["model_id"]
        for g in groups
        if str(g.get("shadow_status", "")).lower() == "pass"
    }
    fail_or_review = [
        g for g in groups
        if str(g.get("shadow_status", "")).lower() != "pass"
    ]

    models = source.get("models") or []
    pass_models = [m for m in models if m.get("model_id") in pass_model_ids]
    excluded_models = [m for m in models if m.get("model_id") not in pass_model_ids]

    exported = dict(source)
    exported["schema_version"] = "aquanova.wave_scope_residual_layer.v117_pass_only"
    exported["source_layer_schema_version"] = source.get("schema_version")
    exported["source_layer_path"] = str(layer_path)
    exported["source_shadow_group_summary"] = str(group_path)
    exported["generated_at"] = datetime.now().isoformat(timespec="seconds")
    exported["runtime_enabled_by_default"] = False
    exported["promotion_policy"] = {
        "mode": "pass_only_from_v116_shadow_validation",
        "excluded_statuses": ["review", "fail"],
        "notes": [
            "Runtime remains disabled by default.",
            "RO multistage SEC was excluded due to holdout regression / high corrected MAE.",
            "This layer is suitable for shadow/guarded validation only until runtime benchmark passes.",
        ],
    }
    exported["models"] = pass_models
    exported["excluded_model_ids"] = [m.get("model_id") for m in excluded_models]

    out_layer.parent.mkdir(parents=True, exist_ok=True)
    out_layer.write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding="utf-8")

    config = {
        "schema_version": "aquanova.wave_correction_runtime_config.v117",
        "enabled": False,
        "layer_path": str(out_layer),
        "runtime_mode": "disabled_shadow_only",
        "guard_required": True,
        "notes": [
            "Do not enable runtime automatically.",
            "Run a benchmark/guard validation before using this layer in runtime.",
        ],
    }
    out_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "schema_version": exported["schema_version"],
        "input_model_count": len(models),
        "pass_model_count": len(pass_models),
        "excluded_model_count": len(excluded_models),
        "pass_models_by_process_metric": dict(Counter(f"{m.get('process_type')}.{m.get('metric')}" for m in pass_models)),
        "excluded_model_ids": exported["excluded_model_ids"],
        "runtime_enabled_by_default": False,
    }

    md = [
        "# V117 pass-only scope residual layer",
        "",
        f"- Source layer: `{layer_path.name}`",
        f"- V116 group summary: `{group_path.name}`",
        f"- Input model count: {len(models)}",
        f"- Pass model count: {len(pass_models)}",
        f"- Excluded model count: {len(excluded_models)}",
        f"- Runtime enabled by default: `False`",
        "",
        "## Exported pass models",
    ]
    for m in pass_models:
        md.append(f"- `{m.get('model_id')}`")
    md.append("")
    md.append("## Excluded models")
    for g in fail_or_review:
        md.append(
            f"- `{g.get('model_id')}` status={g.get('shadow_status')} flags={g.get('flags') or '-'}"
        )
    md.append("")
    md.append("## Next step")
    md.append("Run a runtime benchmark/guard validation. Do not enable runtime correction until it passes.")
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"pass_only_layer: {out_layer}")
        print(f"disabled_config: {out_config}")
        print(f"report: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
