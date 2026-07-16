#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

ROOT_MARKERS = ["app", "ui", "scripts"]

MOVE_RULES = [
    {
        "name": "automation_log_archives",
        "reason": "Large WAVE automation source/result zip logs. Safe to move out of active source tree after preserving manifest.",
        "patterns": [
            "scripts/wave_records/results/_automation_logs/*.zip",
        ],
        "default": True,
    },
    {
        "name": "calibration_zip_archives",
        "reason": "Calibration validation zip bundles; useful history but not active runtime source.",
        "patterns": [
            "scripts/wave_records/results/_calibration_v*/**/*.zip",
        ],
        "default": True,
    },
    {
        "name": "root_pipeline_zip",
        "reason": "Root WAVE_PIPELINE.zip duplicates an extracted WAVE_PIPELINE folder; archive outside active source tree.",
        "patterns": [
            "WAVE_PIPELINE.zip",
        ],
        "default": True,
    },
    {
        "name": "old_result_pdfs",
        "reason": "Generated PDF outputs in scripts/wave_records/results; archive to reduce active tree noise.",
        "patterns": [
            "scripts/wave_records/results/*.pdf",
        ],
        "default": False,
    },
    {
        "name": "debug_dumps",
        "reason": "OCR/debug dumps and pytest debug logs; not runtime source.",
        "patterns": [
            "pytestdebug.log",
            "ocr_raw_dump.txt",
            "ocr_dump.txt",
        ],
        "default": True,
    },
    {
        "name": "versioned_backup_files",
        "reason": "Patch-created backups. Keep only outside active tree if no rollback needed.",
        "patterns": [
            "**/*.bak",
            "**/*.backup",
            "**/*.old",
            "**/*.orig",
            "**/*.tmp",
        ],
        "default": False,
    },
]

KEEP_RULES = [
    "app/**",
    "ui/src/**",
    "scripts/wave_records/*.py",
    "scripts/*.py",
    "tests/**",
    ".data/aquanova.db",
    "WAVE_PIPELINE/1_INPUT/*.pdf",
]


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


def ensure_root(root: Path) -> None:
    missing = [m for m in ROOT_MARKERS if not (root / m).exists()]
    if missing:
        raise SystemExit(f"Not an AquaNova root or missing markers: {missing}. Current root={root}")


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def collect_candidates(root: Path, include_optional: bool = False) -> list[dict]:
    rows = []
    seen = set()

    for rule in MOVE_RULES:
        if not rule["default"] and not include_optional:
            continue
        for pattern in rule["patterns"]:
            for path in root.glob(pattern):
                if not path.is_file():
                    continue
                if ".venv" in path.parts or "node_modules" in path.parts:
                    continue
                rel = path.relative_to(root).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                st = path.stat()
                rows.append({
                    "rule": rule["name"],
                    "reason": rule["reason"],
                    "path": rel,
                    "bytes": st.st_size,
                    "size": human_size(st.st_size),
                })

    rows.sort(key=lambda r: r["bytes"], reverse=True)
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


def make_summary(out: Path, rows: list[dict], target_dir: Path, applied: bool) -> None:
    total = sum(r["bytes"] for r in rows)
    by_rule = {}
    for r in rows:
        by_rule.setdefault(r["rule"], {"bytes": 0, "count": 0})
        by_rule[r["rule"]]["bytes"] += r["bytes"]
        by_rule[r["rule"]]["count"] += 1

    lines = [
        "# AquaNova Cleanup Plan",
        "",
        f"- Applied: `{applied}`",
        f"- Candidate files: `{len(rows)}`",
        f"- Candidate size: `{human_size(total)}`",
        f"- Target archive dir: `{target_dir}`",
        "",
        "## By rule",
        "",
        "| Rule | Files | Size |",
        "|---|---:|---:|",
    ]
    for name, stat in sorted(by_rule.items(), key=lambda kv: kv[1]["bytes"], reverse=True):
        lines.append(f"| `{name}` | {stat['count']} | {human_size(stat['bytes'])} |")

    lines += [
        "",
        "## Largest candidates",
        "",
        "| Rank | File | Size | Rule |",
        "|---:|---|---:|---|",
    ]
    for i, r in enumerate(rows[:50], 1):
        lines.append(f"| {i} | `{r['path']}` | {r['size']} | `{r['rule']}` |")

    if not applied:
        lines += [
            "",
            "## Apply command",
            "",
            "```powershell",
            "python .\\scripts\\wave_records\\aquanova_cleanup_plan.py --apply",
            "```",
            "",
            "This moves candidates, it does not delete them.",
        ]
    else:
        lines += [
            "",
            "## Restore note",
            "",
            "Files were moved, not deleted. Use the manifest CSV/JSON to move them back if needed.",
        ]

    (out / "CLEANUP_PLAN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def move_files(root: Path, rows: list[dict], target_dir: Path) -> list[dict]:
    moved = []
    for r in rows:
        src = root / r["path"]
        if not src.exists():
            r2 = dict(r)
            r2["status"] = "missing"
            moved.append(r2)
            continue

        dst = target_dir / r["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        r2 = dict(r)
        r2["status"] = "moved"
        r2["archive_path"] = str(dst)
        moved.append(r2)
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=".refactor_cleanup")
    ap.add_argument("--archive-dir", default=None, help="Default: ../AquaNova_archive/generated_<timestamp> outside repo root")
    ap.add_argument("--include-optional", action="store_true", help="Include PDFs and backup files. Default excludes these.")
    ap.add_argument("--apply", action="store_true", help="Move files. Without this, dry-run only.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    ensure_root(root)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.archive_dir:
        target = Path(args.archive_dir).resolve()
    else:
        target = root.parent / "AquaNova_archive" / f"generated_{stamp}"

    if is_under(target, root):
        raise SystemExit(f"Archive dir must be outside repo root to reduce active tree size: {target}")

    rows = collect_candidates(root, include_optional=args.include_optional)

    write_csv(out / "cleanup_candidates.csv", rows)
    (out / "cleanup_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    make_summary(out, rows, target, applied=False)

    total = sum(r["bytes"] for r in rows)
    print(f"Cleanup candidates: {len(rows)} files, {human_size(total)}")
    print(f"Plan summary: {out / 'CLEANUP_PLAN_SUMMARY.md'}")
    print(f"Target archive dir: {target}")

    if not args.apply:
        print("DRY RUN ONLY. Nothing moved.")
        print("Review the summary, then run with --apply if acceptable.")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    moved = move_files(root, rows, target)
    write_csv(out / "cleanup_moved_manifest.csv", moved)
    (out / "cleanup_moved_manifest.json").write_text(json.dumps(moved, ensure_ascii=False, indent=2), encoding="utf-8")
    make_summary(out, moved, target, applied=True)

    print(f"APPLIED. Moved {sum(1 for r in moved if r.get('status') == 'moved')} files to {target}")
    print(f"Manifest: {out / 'cleanup_moved_manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
