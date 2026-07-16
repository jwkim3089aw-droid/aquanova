#!/usr/bin/env python3
"""Offline checks for V52 UF warning-modal reconciliation."""
from __future__ import annotations

from pathlib import Path

from wave_common import DEFAULT_POINTS
from wave_uf import UFVideoCase, _click_uf, _replace_uf_point, _resolve_uf_modals


def test_modal_helpers_exist() -> None:
    assert callable(_resolve_uf_modals)
    assert callable(_click_uf)
    assert callable(_replace_uf_point)


def test_uf_backwash_points_have_followup_fields() -> None:
    required = [
        "uf_bw_top_backwash_sec",
        "uf_bw_bottom_backwash_sec",
        "uf_bw_forward_flush_sec",
        "uf_bw_between_air_scour",
        "uf_ceb_nav",
        "summary_report_tab",
    ]
    missing = [key for key in required if key not in DEFAULT_POINTS]
    assert not missing, missing


def test_v52_source_resolves_modals_between_uf_edits() -> None:
    text = Path(__file__).with_name("wave_uf.py").read_text(encoding="utf-8")
    assert "def _resolve_uf_modals" in text
    assert "resolve_wave_blocking_dialogs(hwnd, monitor, context, points)" in text
    assert "before_summary_report_tab_v52" in text
    assert '"uf_modal_resolved_v52"' in text
    assert '"uf_bw_forward_flush_sec"' in text
    assert '"uf_ceb_chemical_soak_min"' in text
    # The failing V49 path used bare click() after a warning could be open.
    assert 'click(points, "summary_report_tab"' not in text
    assert 'click(points, "uf_ceb_nav"' not in text


def test_v52_case_defaults() -> None:
    case = UFVideoCase()
    assert case.case_id.startswith("V")
    assert case.pdf_name.startswith("V")
    assert case.backwash_top_backwash_s == 30
    assert case.backwash_forward_flush_s == 35
    assert case.ceb_top_backwash_s == 45
    assert case.ceb_forward_flush_s == 45


if __name__ == "__main__":
    test_modal_helpers_exist()
    test_uf_backwash_points_have_followup_fields()
    test_v52_source_resolves_modals_between_uf_edits()
    test_v52_case_defaults()
    print("V52 UF modal reconciliation selftest PASS")
