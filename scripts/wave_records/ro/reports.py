from __future__ import annotations

"""Planned home for RO report/export helpers. V135 scaffold only."""

# V156_RO_REPORTS_ENTER_SUMMARY_REPORT_CASE_APPLIED

def WaveAutomationError(*args, **kwargs):
    """Runtime bridge to ro.case_config.WaveAutomationError."""
    try:
        from ro.case_config import WaveAutomationError as _impl
    except ImportError:
        from .case_config import WaveAutomationError as _impl
    return _impl(*args, **kwargs)

def _capture_wave_image(*args, **kwargs):
    """Runtime bridge to ro.case_config._capture_wave_image."""
    try:
        from ro.case_config import _capture_wave_image as _impl
    except ImportError:
        from .case_config import _capture_wave_image as _impl
    return _impl(*args, **kwargs)

def _find_flow_calculator_dialog(*args, **kwargs):
    """Runtime bridge to ro.stages._find_flow_calculator_dialog."""
    try:
        from ro.stages import _find_flow_calculator_dialog as _impl
    except ImportError:
        from .stages import _find_flow_calculator_dialog as _impl
    return _impl(*args, **kwargs)

def _fmt_value(*args, **kwargs):
    """Runtime bridge to ro.case_config._fmt_value."""
    try:
        from ro.case_config import _fmt_value as _impl
    except ImportError:
        from .case_config import _fmt_value as _impl
    return _impl(*args, **kwargs)

def _image_change_ratio(*args, **kwargs):
    """Runtime bridge to ro.case_config._image_change_ratio."""
    try:
        from ro.case_config import _image_change_ratio as _impl
    except ImportError:
        from .case_config import _image_change_ratio as _impl
    return _impl(*args, **kwargs)

def _stabilize_after_flow_commit(*args, **kwargs):
    """Runtime bridge to ro.stages._stabilize_after_flow_commit."""
    try:
        from ro.stages import _stabilize_after_flow_commit as _impl
    except ImportError:
        from .stages import _stabilize_after_flow_commit as _impl
    return _impl(*args, **kwargs)

def _wait_window_closed(*args, **kwargs):
    """Runtime bridge to ro.stages._wait_window_closed."""
    try:
        from ro.stages import _wait_window_closed as _impl
    except ImportError:
        from .stages import _wait_window_closed as _impl
    return _impl(*args, **kwargs)

def click(*args, **kwargs):
    """Runtime bridge to ro.case_config.click."""
    try:
        from ro.case_config import click as _impl
    except ImportError:
        from .case_config import click as _impl
    return _impl(*args, **kwargs)

def configure_flow_calculator_dialog(*args, **kwargs):
    """Runtime bridge to ro.stages.configure_flow_calculator_dialog."""
    try:
        from ro.stages import configure_flow_calculator_dialog as _impl
    except ImportError:
        from .stages import configure_flow_calculator_dialog as _impl
    return _impl(*args, **kwargs)

def record_event(*args, **kwargs):
    """Runtime bridge to ro.stages.record_event."""
    try:
        from ro.stages import record_event as _impl
    except ImportError:
        from .stages import record_event as _impl
    return _impl(*args, **kwargs)

def resolve_wave_blocking_dialogs(*args, **kwargs):
    """Runtime bridge to ro.stages.resolve_wave_blocking_dialogs."""
    try:
        from ro.stages import resolve_wave_blocking_dialogs as _impl
    except ImportError:
        from .stages import resolve_wave_blocking_dialogs as _impl
    return _impl(*args, **kwargs)

def screenshot(*args, **kwargs):
    """Runtime bridge to ro.case_config.screenshot."""
    try:
        from ro.case_config import screenshot as _impl
    except ImportError:
        from .case_config import screenshot as _impl
    return _impl(*args, **kwargs)

def wait(*args, **kwargs):
    """Runtime bridge to ro.case_config.wait."""
    try:
        from ro.case_config import wait as _impl
    except ImportError:
        from .case_config import wait as _impl
    return _impl(*args, **kwargs)

from wave_windows import _foreground_window_info, _get_process_id, _get_window_rect, focus_wave, list_visible_windows, native_click_at

from wave_uia import uia_configure_chemical_adjustment, uia_configure_flow_calculator_recoveries, uia_configure_special_feature_dialog, uia_read_combo_candidates, uia_reconcile_ro_pass_count

def _repair_missing_element_type_dialog(*args, **kwargs):
    """Late-bound bridge to a legacy attribute during staged refactor."""
    try:
        import wave_ro_engine_legacy as _legacy
    except ImportError:
        from .. import wave_ro_engine_legacy as _legacy
    return getattr(_legacy, '_repair_missing_element_type_dialog')(*args, **kwargs)

def enter_summary_report_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
) -> None:
    for attempt in range(1, 6):
        before = _capture_wave_image(hwnd)
        click(points, "summary_report_tab", pause=settings.pause)
        dialog = _find_flow_calculator_dialog(hwnd, timeout=2.5)
        if dialog is not None:
            if case.pass_count == 1:
                configure_flow_calculator_dialog(
                    dialog,
                    _fmt_value(case.passes[0].recovery_pct),
                    monitor,
                    hwnd,
                    settings,
                    f"schema_summary_{attempt}",
                )
            else:
                result = uia_configure_flow_calculator_recoveries(
                    dialog.hwnd, [p.recovery_pct for p in case.passes]
                )
                if not result.get("ok") or not _wait_window_closed(dialog.hwnd, 15.0):
                    raise WaveAutomationError(
                        f"Summary Flow Calculator 다중 Pass 처리 실패: {result}"
                    )
            focus_wave(hwnd)
            _stabilize_after_flow_commit(
                hwnd,
                monitor,
                points,
                case,
                settings,
                context=f"summary_flow_calculator_attempt_{attempt}_v44",
            )
            continue
        wait(settings.long_wait)

        # WAVE can reject Summary with a precise missing Element Type message.
        # This is actionable, not an unknown modal: close it, repair exactly the
        # reported pass/stage, reassert recovery, and retry the transition.
        if _repair_missing_element_type_dialog(hwnd, monitor, points, case, settings):
            continue

        ratio = _image_change_ratio(before, _capture_wave_image(hwnd))
        record_event(
            "schema_summary_transition",
            case_id=case.case_id,
            attempt=attempt,
            ratio=ratio,
        )
        screenshot(f"schema_summary_{case.case_id}_{attempt}", monitor, hwnd)
        if ratio >= 0.003:
            resolve_wave_blocking_dialogs(
                hwnd, monitor, f"schema_summary_{case.case_id}", points
            )
            return
    raise WaveAutomationError("Schema RO case가 Summary Report로 전환되지 않았습니다.")
