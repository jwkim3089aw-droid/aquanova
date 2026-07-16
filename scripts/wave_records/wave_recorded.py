#!/usr/bin/env python3
"""Refactored WAVE automation module: recorded."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import save_click_map, screenshot
from wave_dialogs import resolve_wave_blocking_dialogs
from wave_feed import copy_library_to_feed, prepare_feed_for_profile_replacement, select_library_profile, set_feed_temperature_triplet, verify_numeric_point
from wave_interaction import click, click_expect_new_dialog, click_until_visual_change, replace_value, wait
from wave_ro_ui import add_ro_with_recovery, enter_home_with_recovery, enter_summary_report_with_recovery, open_and_configure_ro_flow, select_combo_exact, set_and_verify_ro_temperature
from wave_runtime import record_event
from wave_windows import _get_window_rect, focus_wave, native_click_at

def configure_recorded_ro_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    logging.info("=== 녹화 기반 RO 사례 입력 시작 ===")
    focus_wave(hwnd)
    # WAVE may eat the first control click when it was not truly foreground.
    rect = _get_window_rect(hwnd)
    native_click_at(rect.left + min(500, rect.width // 2), rect.top + 16)
    wait(0.25)
    screenshot("00_start", monitor, hwnd)

    click_until_visual_change(points, "feed_setup_tab", hwnd, monitor, settings.pause)

    # In batch mode the second case reuses the first case's Feed Water screen.
    # WAVE may copy a new profile field-by-field and validate Design before it has
    # replaced the old Minimum.  Pre-widen the existing range so a valid library
    # profile cannot be blocked by that transient ordering.
    if not settings.add_ro:
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)

    def _open_select_and_copy_profile() -> None:
        library_dialog = click_expect_new_dialog(
            points, "open_water_library", hwnd, monitor, settings.pause
        )
        screenshot("01_water_library_dialog", monitor, hwnd)
        select_library_profile(
            library_dialog, settings.water_profile, settings.long_wait
        )
        screenshot("02_water_profile_selected", monitor, hwnd)
        copy_library_to_feed(library_dialog, settings.long_wait, hwnd, monitor)

    try:
        _open_select_and_copy_profile()
    except LibraryTemperatureTransitionError:
        # Defensive recovery for unexpected profiles/old project state.
        focus_wave(hwnd)
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)
        logging.info("온도 범위 안전화 후 Water Library 복사 재시도")
        record_event("library_copy_retry_after_temperature_transition")
        _open_select_and_copy_profile()

    focus_wave(hwnd)
    screenshot("03_water_profile_loaded", monitor, hwnd)
    save_click_map(
        "feed_water",
        hwnd,
        points,
        ["feed_temp_min", "feed_temp_design", "feed_temp_max", "home_tab"],
    )

    # WAVE validates Minimum <= Design <= Maximum after every field edit. V22
    # chooses min->design->max when lowering and max->design->min when raising,
    # with a guard-envelope retry for unusual profile starting values.
    set_feed_temperature_triplet(
        hwnd,
        monitor,
        points,
        settings.temperature_c,
        settings.pause,
    )

    # Navigate with a message-driven repair loop.  A charge-balance dialog is
    # closed, Adjust All Ions is applied, and the rejected Home click is retried.
    resolve_wave_blocking_dialogs(hwnd, monitor, "before_home_tab", points)
    enter_home_with_recovery(hwnd, monitor, points, settings)
    replace_value(points, "home_feed_flow", settings.feed_flow_m3h, settings.pause)
    resolve_wave_blocking_dialogs(hwnd, monitor, "after_home_feed_flow", points)

    if settings.add_ro:
        add_ro_with_recovery(hwnd, monitor, points, settings)
    else:
        logging.info("기존 RO 공정 사용: --add-ro가 없어 드래그 생략")
    screenshot("04_ro_ready", monitor, hwnd)
    save_click_map(
        "ro_configuration",
        hwnd,
        points,
        [
            "reverse_osmosis_tab",
            "stage_1_radio",
            "ro_feed_flow",
            "ro_recovery",
            "ro_temperature_value",
            "pv_per_stage",
            "elements_per_pv",
            "element_type_combo",
            "summary_report_tab",
        ],
    )

    click_until_visual_change(
        points,
        "reverse_osmosis_tab",
        hwnd,
        monitor,
        settings.pause,
        minimum_change=0.004,
    )
    click(points, "stage_1_radio", settings.pause)

    # These cells open a modal calculator in the installed WAVE build.  Configure
    # the modal first; never type into the owner window while it is disabled.
    open_and_configure_ro_flow(hwnd, monitor, points, settings)

    # WAVE can retain the library's original 15 C pass temperature after the
    # Feed Water page has already been changed to 25/25/25.  Refresh the semantic
    # temperature mode first and use exact UIA editing only as a guarded fallback.
    set_and_verify_ro_temperature(hwnd, monitor, points, settings)
    resolve_wave_blocking_dialogs(hwnd, monitor, "after_ro_temperature", points)

    replace_value(points, "pv_per_stage", settings.pv_per_stage, settings.pause)
    replace_value(points, "elements_per_pv", settings.elements_per_pv, settings.pause)
    verify_numeric_point("pv_per_stage", points["pv_per_stage"], settings.pv_per_stage)
    verify_numeric_point(
        "elements_per_pv", points["elements_per_pv"], settings.elements_per_pv
    )
    select_combo_exact(
        hwnd,
        monitor,
        points,
        "element_type_combo",
        settings.membrane,
        settings.long_wait,
    )
    screenshot("05_ro_configured", monitor, hwnd)

    enter_summary_report_with_recovery(hwnd, monitor, points, settings)
    screenshot("07_report_ready", monitor, hwnd)
    logging.info("=== 녹화 기반 RO 사례 입력 완료 ===")
