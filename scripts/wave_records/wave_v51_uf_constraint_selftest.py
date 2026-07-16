#!/usr/bin/env python3
"""Offline checks for V52 UF CEB allowed-range reconciliation."""
from __future__ import annotations

from pathlib import Path

from wave_common import DEFAULT_POINTS
from wave_uf import UFVideoCase, _replace_uf_point, _resolve_uf_modals


def test_ceb_bottom_backwash_default_is_valid() -> None:
    case = UFVideoCase()
    assert case.case_id.startswith("V")
    assert case.pdf_name.startswith("V")
    assert 15 <= case.ceb_bottom_backwash_s <= 60
    assert case.ceb_bottom_backwash_s == 15


def test_ceb_points_exist() -> None:
    required = [
        "uf_ceb_bottom_backwash_sec",
        "uf_ceb_forward_flush_sec",
        "uf_ceb_chemical_soak_min",
        "summary_report_tab",
    ]
    missing = [key for key in required if key not in DEFAULT_POINTS]
    assert not missing, missing


def test_uf_constraint_modal_recovery_is_scoped() -> None:
    text = Path(__file__).with_name("wave_uf.py").read_text(encoding="utf-8")
    assert "uf_constraint_value_error_closed" in text
    assert "outside the allowed range" in text
    assert "after_write_" in text
    assert "after_verify_" in text
    assert "resolve_wave_blocking_dialogs(hwnd, monitor, context, points)" in text
    assert callable(_resolve_uf_modals)
    assert callable(_replace_uf_point)


if __name__ == "__main__":
    test_ceb_bottom_backwash_default_is_valid()
    test_ceb_points_exist()
    test_uf_constraint_modal_recovery_is_scoped()
    print("V52 UF constraint reconciliation selftest PASS")
