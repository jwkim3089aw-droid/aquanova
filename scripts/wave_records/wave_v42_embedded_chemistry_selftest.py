#!/usr/bin/env python3
"""Offline structural checks for V52 Chemical Adjustment host/diagnostics support."""
from pathlib import Path


def main() -> None:
    engine = Path(__file__).with_name("wave_ro_engine.py").read_text(encoding="utf-8")
    uia = Path(__file__).with_name("wave_uia.py").read_text(encoding="utf-8")
    for token in (
        "chemical_host_resolved_v44",
        "foreground_same_process_overlay",
        "chemical_host_probe_v44",
        "chemical_adjustment_retry_v44",
        "untitled_foreground_overlay",
        "close_verified",
    ):
        assert token in engine, token
    for token in (
        "embedded_wpf_overlay",
        "chemicalModePattern",
        "chemical_embedded_panel_not_found_mode_buttons",
        "mode_button_source",
        "supported_patterns",
        "parent_path",
        "host_diagnostics",
        "script_stack",
        "title_plus_geometry",
        "chemical_adjustment_not_closed_after_ok",
        "IsOffscreen=True",
    ):
        assert token in uia, token
    assert "item.hwnd != wave_hwnd" in engine  # titled top-level path remains available
    print("V52 Chemical Adjustment host/diagnostics self-test OK")


if __name__ == "__main__":
    main()
