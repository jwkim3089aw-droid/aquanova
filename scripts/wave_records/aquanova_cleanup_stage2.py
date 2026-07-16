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


def dir_size(path: Path) -> tuple[int, int]:
    total = 0
    count = 0
    if path.is_file():
        return path.stat().st_size, 1
    for cur, _, files in os.walk(path):
        for name in files:
            p = Path(cur) / name
            try:
                total += p.stat().st_size
                count += 1
            except OSError:
                pass
    return total, count


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def collect_dirs(root: Path, include_result_pdfs: bool = False) -> list[dict]:
    rows = []

    auto_root = root / "scripts/wave_records/results/_automation_logs"
    if auto_root.exists():
        for child in sorted(auto_root.iterdir()):
            if not child.exists():
                continue
            if child.is_dir():
                size, files = dir_size(child)
                if files:
                    rows.append({
                        "kind": "dir",
                        "rule": "automation_log_dirs",
                        "path": child.relative_to(root).as_posix(),
                        "bytes": size,
                        "size": human_size(size),
                        "files": files,
                        "reason": "Unzipped automation run folders duplicate source snapshots/events/screenshots and should be outside active repo.",
                    })
            elif child.is_file():
                # Zip files were already handled by V125, but any leftover non-zip files can be moved.
                size = child.stat().st_size
                rows.append({
                    "kind": "file",
                    "rule": "automation_log_leftover_files",
                    "path": child.relative_to(root).as_posix(),
                    "bytes": size,
                    "size": human_size(size),
                    "files": 1,
                    "reason": "Leftover automation log file.",
                })

    if include_result_pdfs:
        result_root = root / "scripts/wave_records/results"
        if result_root.exists():
            for p in sorted(result_root.glob("*.pdf")):
                size = p.stat().st_size
                rows.append({
                    "kind": "file",
                    "rule": "generated_result_pdfs_optional",
                    "path": p.relative_to(root).as_posix(),
                    "bytes": size,
                    "size": human_size(size),
                    "files": 1,
                    "reason": "Generated PDF output; archive if not needed for immediate comparison.",
                })

    rows.sort(key=lambda r: r["bytes"], reverse=True)
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


def summary(out: Path, rows: list[dict], target: Path, applied: bool) -> None:
    total = sum(r["bytes"] for r in rows)
    by_rule = {}
    for r in rows:
        by_rule.setdefault(r["rule"], {"bytes": 0, "count": 0, "files": 0})
        by_rule[r["rule"]]["bytes"] += r["bytes"]
        by_rule[r["rule"]]["count"] += 1
        by_rule[r["rule"]]["files"] += r["files"]

    lines = [
        "# AquaNova Cleanup Stage 2",
        "",
        f"- Applied: `{applied}`",
        f"- Candidates: `{len(rows)}`",
        f"- Candidate size: `{human_size(total)}`",
        f"- Target archive dir: `{target}`",
        "",
        "## By rule",
        "",
        "| Rule | Items | Files inside | Size |",
        "|---|---:|---:|---:|",
    ]
    for rule, s in sorted(by_rule.items(), key=lambda kv: kv[1]["bytes"], reverse=True):
        lines.append(f"| `{rule}` | {s['count']} | {s['files']} | {human_size(s['bytes'])} |")

    lines += [
        "",
        "## Largest candidates",
        "",
        "| Rank | Path | Size | Files | Rule |",
        "|---:|---|---:|---:|---|",
    ]
    for i, r in enumerate(rows[:80], 1):
        lines.append(f"| {i} | `{r['path']}` | {r['size']} | {r['files']} | `{r['rule']}` |")

    if not applied:
        lines += [
            "",
            "## Apply command",
            "",
            "```powershell",
            "python .\\scripts\\wave_records\\aquanova_cleanup_stage2.py --apply",
            "```",
            "",
            "Optional, also archive generated result PDFs:",
            "",
            "```powershell",
            "python .\\scripts\\wave_records\\aquanova_cleanup_stage2.py --include-result-pdfs --apply",
            "```",
        ]
    else:
        lines += [
            "",
            "Files were moved, not deleted. Restore from the manifest if needed.",
        ]

    (out / "CLEANUP_STAGE2_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def move_items(root: Path, rows: list[dict], target: Path) -> list[dict]:
    moved = []
    for r in rows:
        src = root / r["path"]
        dst = target / r["path"]
        r2 = dict(r)
        if not src.exists():
            r2["status"] = "missing"
            moved.append(r2)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        r2["status"] = "moved"
        r2["archive_path"] = str(dst)
        moved.append(r2)
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=".refactor_cleanup_stage2")
    ap.add_argument("--archive-dir", default=None)
    ap.add_argument("--include-result-pdfs", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    ensure_root(root)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    target = Path(args.archive_dir).resolve() if args.archive_dir else root.parent / "AquaNova_archive" / f"generated_stage2_{stamp}"
    if is_under(target, root):
        raise SystemExit(f"Archive dir must be outside repo root: {target}")

    rows = collect_dirs(root, include_result_pdfs=args.include_result_pdfs)
    write_csv(out / "cleanup_stage2_candidates.csv", rows)
    (out / "cleanup_stage2_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary(out, rows, target, applied=False)

    total = sum(r["bytes"] for r in rows)
    print(f"Stage2 candidates: {len(rows)} items, {human_size(total)}")
    print(f"Summary: {out / 'CLEANUP_STAGE2_SUMMARY.md'}")
    print(f"Target archive dir: {target}")

    if not args.apply:
        print("DRY RUN ONLY. Nothing moved.")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    moved = move_items(root, rows, target)
    write_csv(out / "cleanup_stage2_moved_manifest.csv", moved)
    (out / "cleanup_stage2_moved_manifest.json").write_text(json.dumps(moved, ensure_ascii=False, indent=2), encoding="utf-8")
    summary(out, moved, target, applied=True)

    print(f"APPLIED. Moved {sum(1 for r in moved if r.get('status') == 'moved')} items to {target}")
    print(f"Manifest: {out / 'cleanup_stage2_moved_manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
