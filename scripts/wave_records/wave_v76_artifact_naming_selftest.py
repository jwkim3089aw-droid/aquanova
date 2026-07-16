#!/usr/bin/env python3
"""V76 artifact naming selftest.

This is intentionally static/import-light so it can run before WAVE is opened.
It checks that UF/CCRO validation and summary artifacts are written with the
actual PDF stem, while preserving the legacy latest-summary aliases.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _require(text: str, needle: str, file_name: str) -> None:
    if needle not in text:
        raise SystemExit(f"V76 selftest FAIL: missing {needle!r} in {file_name}")


def main() -> None:
    uf = (ROOT / "wave_uf.py").read_text(encoding="utf-8")
    ccro = (ROOT / "wave_ccro.py").read_text(encoding="utf-8")

    for file_name, text, prefix in (
        ("wave_uf.py", uf, "uf"),
        ("wave_ccro.py", ccro, "ccro"),
    ):
        _require(text, "safe_pdf = _safe_name(path.stem)", file_name)
        _require(text, "safe_case = _safe_name(case.case_id)", file_name)
        _require(text, 'f"exported_pdf_text_{safe_pdf}.txt"', file_name)
        _require(text, f'f"{prefix}_pdf_validation_{{safe_pdf}}.json"', file_name)
        _require(text, "if safe_case != safe_pdf:", file_name)
        _require(text, "safe_pdf = _safe_name(target.stem)", file_name)
        _require(text, f'f"{prefix}_video_case_summary_{{safe_pdf}}.json"', file_name)

    _require(uf, '"uf_video_case_summary.json"', "wave_uf.py")
    _require(ccro, '"ccro_video_case_summary.json"', "wave_ccro.py")
    print("V76 artifact naming selftest PASS")


if __name__ == "__main__":
    main()
