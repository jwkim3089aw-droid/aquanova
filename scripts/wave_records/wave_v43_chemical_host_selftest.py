#!/usr/bin/env python3
"""Offline regression checks for V52 untitled Chemical Adjustment HWND resolution."""
from __future__ import annotations

import wave_ro_engine as engine
from wave_common import Rect, WindowInfo


def _window(hwnd: int, title: str, pid: int, rect: Rect, class_name: str) -> WindowInfo:
    return WindowInfo(
        hwnd=hwnd,
        title=title,
        process_path=r"C:\Program Files (x86)\Dupont\WAVE\WAVE.exe",
        rect=rect,
        process_id=pid,
        class_name=class_name,
    )


def main() -> None:
    wave = _window(
        100,
        "Untitled Project - Case 1",
        77,
        Rect(1920, 0, 3200, 1032),
        "HwndWrapper[WAVE.exe;;main]",
    )
    overlay = _window(
        200,
        "",
        77,
        Rect(2267, 115, 3494, 917),
        "HwndWrapper[WAVE.exe;;chemical]",
    )

    saved = {
        "fg": engine._foreground_window_info,
        "pid": engine._get_process_id,
        "rect": engine._get_window_rect,
        "list": engine.list_visible_windows,
    }
    try:
        engine._foreground_window_info = lambda: overlay
        engine._get_process_id = lambda hwnd: wave.process_id
        engine._get_window_rect = lambda hwnd: wave.rect
        engine.list_visible_windows = lambda include_small=True: [wave]
        selected = engine._find_chemical_dialog(wave.hwnd, timeout=0.05)
        assert selected is not None
        assert selected.hwnd == overlay.hwnd
        assert selected.title == ""
    finally:
        engine._foreground_window_info = saved["fg"]
        engine._get_process_id = saved["pid"]
        engine._get_window_rect = saved["rect"]
        engine.list_visible_windows = saved["list"]

    source = open(engine.__file__, encoding="utf-8").read()
    assert "chemical_host_" in source
    assert "chemical_adjustment_retry_v44" in source
    print("V52 untitled Chemical Adjustment host self-test OK")


if __name__ == "__main__":
    main()
