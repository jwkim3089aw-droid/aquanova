#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "coverage",
    "htmlcov",
    ".idea",
    ".vscode",
}
LIKELY_ARTIFACT_DIR_NAMES = {
    "results",
    "logs",
    "log",
    "exports",
    "reports",
    "output",
    "outputs",
    "artifacts",
    "screenshots",
    "recordings",
    "downloads",
    "tmp",
    "temp",
    "backup",
    "backups",
}
LARGE_FILE_EXTS = {
    ".zip", ".7z", ".rar", ".tar", ".gz",
    ".pdf", ".xlsx", ".xlsm", ".xls", ".csv",
    ".mp4", ".avi", ".mov", ".mkv", ".webm",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff",
    ".log", ".jsonl",
}


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


def iter_files(root: Path, include_excluded: bool = False) -> Iterable[Path]:
    for cur, dirs, files in os.walk(root):
        cur_path = Path(cur)
        if not include_excluded:
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]
        for name in files:
            yield cur_path / name


def safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def top_dirs(root: Path, include_excluded: bool = False) -> list[dict]:
    sizes = defaultdict(int)
    counts = defaultdict(int)
    for p in iter_files(root, include_excluded=include_excluded):
        st = safe_stat(p)
        if not st:
            continue
        try:
            r = p.relative_to(root)
            top = r.parts[0] if r.parts else "."
        except Exception:
            top = "."
        sizes[top] += st.st_size
        counts[top] += 1
    rows = [
        {"dir": k, "bytes": v, "size": human_size(v), "files": counts[k]}
        for k, v in sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return rows


def directory_sizes(root: Path, include_excluded: bool = False, max_depth: int = 3) -> list[dict]:
    sizes = defaultdict(int)
    counts = defaultdict(int)
    for p in iter_files(root, include_excluded=include_excluded):
        st = safe_stat(p)
        if not st:
            continue
        try:
            parts = p.relative_to(root).parts[:-1]
        except Exception:
            continue
        for depth in range(1, min(max_depth, len(parts)) + 1):
            key = "/".join(parts[:depth])
            sizes[key] += st.st_size
            counts[key] += 1
    rows = [
        {"path": k, "bytes": v, "size": human_size(v), "files": counts[k]}
        for k, v in sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return rows


def extension_summary(root: Path) -> list[dict]:
    c = Counter()
    s = Counter()
    for p in iter_files(root, include_excluded=False):
        st = safe_stat(p)
        if not st:
            continue
        ext = p.suffix.lower() or "[no_ext]"
        c[ext] += 1
        s[ext] += st.st_size
    return [
        {"ext": ext, "files": c[ext], "bytes": s[ext], "size": human_size(s[ext])}
        for ext in sorted(c, key=lambda e: s[e], reverse=True)
    ]


def large_files(root: Path, limit: int = 200) -> list[dict]:
    rows = []
    for p in iter_files(root, include_excluded=False):
        st = safe_stat(p)
        if not st:
            continue
        ext = p.suffix.lower()
        artifact_hint = (
            ext in LARGE_FILE_EXTS
            or any(part.lower() in LIKELY_ARTIFACT_DIR_NAMES for part in p.relative_to(root).parts[:-1])
        )
        rows.append({
            "path": rel(root, p),
            "bytes": st.st_size,
            "size": human_size(st.st_size),
            "ext": ext or "[no_ext]",
            "artifact_hint": artifact_hint,
        })
    rows.sort(key=lambda x: x["bytes"], reverse=True)
    return rows[:limit]


def backup_files(root: Path, limit: int = 500) -> list[dict]:
    patterns = (".bak", ".backup", ".old", ".orig", ".tmp", ".v121", ".v122", ".v123")
    rows = []
    for p in iter_files(root, include_excluded=False):
        name = p.name.lower()
        if any(token in name for token in patterns):
            st = safe_stat(p)
            if st:
                rows.append({"path": rel(root, p), "bytes": st.st_size, "size": human_size(st.st_size)})
    rows.sort(key=lambda x: x["bytes"], reverse=True)
    return rows[:limit]


def python_file_stats(root: Path) -> list[dict]:
    rows = []
    for p in iter_files(root, include_excluded=False):
        if p.suffix.lower() != ".py":
            continue
        st = safe_stat(p)
        if not st:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        loc = sum(1 for line in text.splitlines() if line.strip())
        functions = len(re.findall(r"^\s*def\s+\w+\s*\(", text, flags=re.M))
        classes = len(re.findall(r"^\s*class\s+\w+", text, flags=re.M))
        rows.append({
            "path": rel(root, p),
            "bytes": st.st_size,
            "size": human_size(st.st_size),
            "loc_nonblank": loc,
            "functions": functions,
            "classes": classes,
        })
    rows.sort(key=lambda x: (x["loc_nonblank"], x["bytes"]), reverse=True)
    return rows


def ts_file_stats(root: Path) -> list[dict]:
    rows = []
    for p in iter_files(root, include_excluded=False):
        if p.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        st = safe_stat(p)
        if not st:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        loc = sum(1 for line in text.splitlines() if line.strip())
        components = len(re.findall(r"\bfunction\s+[A-Z]\w+|\bconst\s+[A-Z]\w+\s*=", text))
        hooks = len(re.findall(r"\buse[A-Z]\w+", text))
        rows.append({
            "path": rel(root, p),
            "bytes": st.st_size,
            "size": human_size(st.st_size),
            "loc_nonblank": loc,
            "components_or_exports_hint": components,
            "hooks_hint": hooks,
        })
    rows.sort(key=lambda x: (x["loc_nonblank"], x["bytes"]), reverse=True)
    return rows


def git_status(root: Path) -> dict:
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=15,
        )
        return {
            "available": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip().splitlines()[:500],
            "stderr": r.stderr.strip().splitlines()[:50],
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def duplicate_hash_candidates(root: Path, max_file_mb: int = 20) -> list[dict]:
    # Only hash reasonably small files to keep this fast.
    groups = defaultdict(list)
    max_bytes = max_file_mb * 1024 * 1024
    for p in iter_files(root, include_excluded=False):
        st = safe_stat(p)
        if not st or st.st_size == 0 or st.st_size > max_bytes:
            continue
        ext = p.suffix.lower()
        if ext not in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".css", ".html", ".yml", ".yaml"}:
            continue
        try:
            h = hashlib.sha1(p.read_bytes()).hexdigest()
        except Exception:
            continue
        groups[(st.st_size, h)].append(rel(root, p))
    rows = []
    for (size, h), paths in groups.items():
        if len(paths) > 1:
            rows.append({
                "bytes": size,
                "size": human_size(size),
                "sha1": h,
                "count": len(paths),
                "paths": paths[:20],
            })
    rows.sort(key=lambda x: x["bytes"] * x["count"], reverse=True)
    return rows[:100]


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Project root. Default: current directory.")
    ap.add_argument("--out", default=".refactor_audit", help="Output directory.")
    ap.add_argument("--include-excluded", action="store_true", help="Also scan .venv/node_modules/etc.")
    ap.add_argument("--max-large-files", type=int, default=200)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    started = datetime.now().isoformat(timespec="seconds")
    all_files = list(iter_files(root, include_excluded=args.include_excluded))
    total_bytes = 0
    for p in all_files:
        st = safe_stat(p)
        if st:
            total_bytes += st.st_size

    data = {
        "generated_at": started,
        "root": str(root),
        "include_excluded": args.include_excluded,
        "excluded_dirs": sorted(DEFAULT_EXCLUDE_DIRS),
        "total_scanned_files": len(all_files),
        "total_scanned_bytes": total_bytes,
        "total_scanned_size": human_size(total_bytes),
        "top_dirs": top_dirs(root, include_excluded=args.include_excluded)[:50],
        "directory_sizes": directory_sizes(root, include_excluded=args.include_excluded, max_depth=3)[:300],
        "extension_summary": extension_summary(root),
        "large_files": large_files(root, limit=args.max_large_files),
        "backup_files": backup_files(root),
        "python_files_by_loc": python_file_stats(root)[:200],
        "frontend_files_by_loc": ts_file_stats(root)[:200],
        "duplicate_candidates": duplicate_hash_candidates(root),
        "git_status": git_status(root),
    }

    (out / "refactor_audit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out / "top_dirs.csv", data["top_dirs"])
    write_csv(out / "directory_sizes.csv", data["directory_sizes"])
    write_csv(out / "extension_summary.csv", data["extension_summary"])
    write_csv(out / "large_files.csv", data["large_files"])
    write_csv(out / "backup_files.csv", data["backup_files"])
    write_csv(out / "python_files_by_loc.csv", data["python_files_by_loc"])
    write_csv(out / "frontend_files_by_loc.csv", data["frontend_files_by_loc"])
    write_csv(out / "duplicate_candidates.csv", data["duplicate_candidates"])

    md = []
    md.append("# AquaNova Refactor Audit")
    md.append("")
    md.append(f"- Generated: `{started}`")
    md.append(f"- Root: `{root}`")
    md.append(f"- Scanned files: `{len(all_files)}`")
    md.append(f"- Scanned size: `{human_size(total_bytes)}`")
    md.append("")
    md.append("## Top directories by size")
    md.append("")
    md.append("| Rank | Directory | Size | Files |")
    md.append("|---:|---|---:|---:|")
    for i, row in enumerate(data["top_dirs"][:20], 1):
        md.append(f"| {i} | `{row['dir']}` | {row['size']} | {row['files']} |")
    md.append("")
    md.append("## Largest files")
    md.append("")
    md.append("| Rank | File | Size | Artifact hint |")
    md.append("|---:|---|---:|---|")
    for i, row in enumerate(data["large_files"][:30], 1):
        md.append(f"| {i} | `{row['path']}` | {row['size']} | {row['artifact_hint']} |")
    md.append("")
    md.append("## Largest Python files by LOC")
    md.append("")
    md.append("| Rank | File | LOC | Size | Functions | Classes |")
    md.append("|---:|---|---:|---:|---:|---:|")
    for i, row in enumerate(data["python_files_by_loc"][:30], 1):
        md.append(f"| {i} | `{row['path']}` | {row['loc_nonblank']} | {row['size']} | {row['functions']} | {row['classes']} |")
    md.append("")
    md.append("## Largest frontend files by LOC")
    md.append("")
    md.append("| Rank | File | LOC | Size | Component hint | Hook hint |")
    md.append("|---:|---|---:|---:|---:|---:|")
    for i, row in enumerate(data["frontend_files_by_loc"][:30], 1):
        md.append(f"| {i} | `{row['path']}` | {row['loc_nonblank']} | {row['size']} | {row['components_or_exports_hint']} | {row['hooks_hint']} |")
    md.append("")
    md.append("## Recommended first cleanup targets")
    md.append("")
    md.append("Do not delete anything blindly. Move old generated artifacts to `_archive/` only after checking `large_files.csv` and `backup_files.csv`.")
    md.append("")
    (out / "REFRACTOR_AUDIT_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print(f"AquaNova refactor audit complete: {out}")
    print(f"Scanned size: {human_size(total_bytes)}")
    print(f"Main summary: {out / 'REFRACTOR_AUDIT_SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
