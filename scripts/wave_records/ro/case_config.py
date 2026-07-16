from __future__ import annotations


# V161A_RO_CASE_CONFIG_SETTINGS_IMPORT_START
try:
    from wave_common import Settings
except ImportError:
    try:
        from ..wave_common import Settings
    except ImportError:
        from scripts.wave_records.wave_common import Settings
# V161A_RO_CASE_CONFIG_SETTINGS_IMPORT_END

"""Planned home for RO case config helpers. V135 scaffold only."""

try:
    from ro.membrane import _ro_diagnostic_points
except ImportError:
    from .membrane import _ro_diagnostic_points

from wave_diagnostics import (
    _capture_wave_image,
    _image_change_ratio,
    capture_ro_state,
    diff_ro_states,
    screenshot,
    write_convergence_failure_report,
)

# V142_RO_CASE_CONFIG_CAPTURE_STATE_APPLIED

def _capture_case_ro_state(
    label: str,
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    *,
    pass_index: Optional[int] = None,
    pass_config: Optional[ROPassConfig] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return capture_ro_state(
        label,
        hwnd,
        monitor,
        _ro_diagnostic_points(
            hwnd,
            points,
            pass_index=pass_index,
            pass_config=pass_config,
        ),
        expected_stage_counts={
            index: config.stage_count
            for index, config in enumerate(case.passes, start=1)
        },
        metadata={
            "case_id": case.case_id,
            "pass_index": pass_index,
            **(metadata or {}),
        },
    )

from wave_feed import _read_numeric_point, copy_library_to_feed, prepare_feed_for_profile_replacement, select_library_profile, set_feed_temperature_envelope, verify_numeric_point

from wave_interaction import click, click_expect_new_dialog, click_until_visual_change, replace_value, wait

# V143A_RO_CASE_CONFIG_VERIFY_INPUTS_APPLIED

def _select_pass(*args, **kwargs):
    """Bridge to a legacy UI helper left in wave_ro_engine_legacy during staged refactor."""
    try:
        from wave_ro_engine_legacy import _select_pass as _legacy_impl
    except ImportError:
        from ..wave_ro_engine_legacy import _select_pass as _legacy_impl
    return _legacy_impl(*args, **kwargs)

def _verify_case_operating_inputs(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
    *,
    context: str,
) -> None:
    """Verify sticky pass-level inputs after the final Recovery commit."""
    global_temperature = float(case.passes[0].temperature_c)
    for pass_index, pass_config in enumerate(case.passes, start=1):
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.5, settings.pause))
        verify_numeric_point(
            f"{context}_p{pass_index}_recovery",
            points["ro_recovery"],
            pass_config.recovery_pct,
        )
        verify_numeric_point(
            f"{context}_p{pass_index}_flow_factor",
            points["ro_flow_factor"],
            pass_config.flow_factor,
        )
        verify_numeric_point(
            f"{context}_p{pass_index}_pass_back_pressure",
            points["ro_pass_back_pressure"],
            pass_config.permeate_back_pressure_bar,
        )
        verify_numeric_point(
            f"{context}_p{pass_index}_temperature",
            points["ro_temperature_value"],
            global_temperature,
        )
    screenshot(f"{context}_operating_inputs", monitor, hwnd)

# V149_RO_CASE_CONFIG_VALIDATE_SUPPORT_APPLIED

def WaveAutomationError(*args, **kwargs):
    """Lazy factory for the legacy WaveAutomationError exception instance."""
    try:
        from wave_ro_engine_legacy import WaveAutomationError as _Exc
    except ImportError:
        from ..wave_ro_engine_legacy import WaveAutomationError as _Exc
    return _Exc(*args, **kwargs)

def _has_flow_optimization(*args, **kwargs):
    """Bridge to ro.feedwater while avoiding top-level module coupling."""
    try:
        from ro.feedwater import _has_flow_optimization as _impl
    except ImportError:
        from .feedwater import _has_flow_optimization as _impl
    return _impl(*args, **kwargs)

def _validate_case_automation_support(
    case: ROCaseConfig, *, allow_experimental: bool
) -> None:
    case.validate()
    if any(_has_flow_optimization(p) for p in case.passes):
        raise WaveAutomationError(
            f"{case.case_id}: Bypass/Permeate Split/Concentrate Recycle fields are "
            "catalogued but intentionally fail-closed in V52 until a dedicated "
            "Flow Calculator feedback run confirms their AutomationIds."
        )
    if case.automation_tier == "experimental" and not allow_experimental:
        raise WaveAutomationError(
            f"{case.case_id}: experimental RO settings are present (2-pass/boost-pressure/chemical-degas). "
            "Review the generated catalog and rerun with --allow-experimental-ro."
        )

# V154_RO_CASE_CONFIG_SETTINGS_FROM_CASE_APPLIED

def _fmt_value(*args, **kwargs):
    """Late-bound bridge to a legacy attribute during staged refactor."""
    try:
        import wave_ro_engine_legacy as _legacy
    except ImportError:
        from .. import wave_ro_engine_legacy as _legacy
    return getattr(_legacy, '_fmt_value')(*args, **kwargs)

def _settings_from_ro_case(
    case: ROCaseConfig,
    *,
    add_ro: bool,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
) -> Settings:
    p1 = case.passes[0]
    s1 = p1.stages[0]
    return Settings(
        water_profile=case.water_profile,
        temperature_c=_fmt_value(case.feed_temperature_c),
        feed_flow_m3h=_fmt_value(case.feed_flow_m3h),
        recovery_pct=_fmt_value(p1.recovery_pct),
        pv_per_stage=_fmt_value(s1.pv),
        elements_per_pv=_fmt_value(s1.elements_per_pv),
        membrane=s1.membrane,
        add_ro=add_ro,
        pause=pause,
        long_wait=long_wait,
        validate_pdf=validate_pdf,
    )

# V155_RO_CASE_CONFIG_CONFIGURE_PASS_SCREEN_APPLIED

def _configure_stage_grid(*args, **kwargs):
    """Runtime bridge to ro.stages._configure_stage_grid."""
    try:
        from ro.stages import _configure_stage_grid as _impl
    except ImportError:
        from .stages import _configure_stage_grid as _impl
    return _impl(*args, **kwargs)

def set_and_verify_ro_temperature_mode(*args, **kwargs):
    """Runtime bridge to ro.stages.set_and_verify_ro_temperature_mode."""
    try:
        from ro.stages import set_and_verify_ro_temperature_mode as _impl
    except ImportError:
        from .stages import set_and_verify_ro_temperature_mode as _impl
    return _impl(*args, **kwargs)

def _configure_pass_screen(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pass_index: int,
    pass_config: ROPassConfig,
    base_settings: Settings,
) -> None:
    _select_pass(points, pass_index, base_settings.pause)
    wait(max(0.8, base_settings.pause))
    pass_settings = Settings(
        water_profile=base_settings.water_profile,
        temperature_c=_fmt_value(pass_config.temperature_c),
        feed_flow_m3h=base_settings.feed_flow_m3h,
        recovery_pct=_fmt_value(pass_config.recovery_pct),
        pv_per_stage=_fmt_value(pass_config.stages[0].pv),
        elements_per_pv=_fmt_value(pass_config.stages[0].elements_per_pv),
        membrane=pass_config.stages[0].membrane,
        add_ro=base_settings.add_ro,
        pause=base_settings.pause,
        long_wait=base_settings.long_wait,
        validate_pdf=False,
    )
    # These controls are sticky across batch cases.  Always write defaults too;
    # otherwise a previous 0.88/1.05 flow factor or 0.30 bar back pressure leaks
    # into the next case even when the next row requests the WAVE default.
    replace_value(
        points,
        "ro_flow_factor",
        _fmt_value(pass_config.flow_factor),
        base_settings.pause,
    )
    verify_numeric_point(
        f"p{pass_index}_ro_flow_factor",
        points["ro_flow_factor"],
        pass_config.flow_factor,
    )
    replace_value(
        points,
        "ro_pass_back_pressure",
        _fmt_value(pass_config.permeate_back_pressure_bar),
        base_settings.pause,
    )
    verify_numeric_point(
        f"p{pass_index}_ro_pass_back_pressure",
        points["ro_pass_back_pressure"],
        pass_config.permeate_back_pressure_bar,
    )
    set_and_verify_ro_temperature_mode(
        hwnd,
        monitor,
        points,
        pass_config.temperature_mode,
        pass_config.temperature_c,
        pass_settings,
        label=f"pass{pass_index}",
    )
    _configure_stage_grid(hwnd, monitor, points, pass_index, pass_config, base_settings)

# V159_RO_CASE_CONFIG_OPEN_FLOW_CASE_APPLIED

import logging

def _find_flow_calculator_dialog(*args, **kwargs):
    """Runtime bridge to ro.reports._find_flow_calculator_dialog."""
    try:
        from ro.reports import _find_flow_calculator_dialog as _impl
    except ImportError:
        from .reports import _find_flow_calculator_dialog as _impl
    return _impl(*args, **kwargs)

def _wait_window_closed(*args, **kwargs):
    """Runtime bridge to ro.reports._wait_window_closed."""
    try:
        from ro.reports import _wait_window_closed as _impl
    except ImportError:
        from .reports import _wait_window_closed as _impl
    return _impl(*args, **kwargs)

def focus_wave(*args, **kwargs):
    """Runtime bridge to ro.membrane.focus_wave."""
    try:
        from ro.membrane import focus_wave as _impl
    except ImportError:
        from .membrane import focus_wave as _impl
    return _impl(*args, **kwargs)

def open_and_configure_ro_flow(*args, **kwargs):
    """Runtime bridge to ro.stages.open_and_configure_ro_flow."""
    try:
        from ro.stages import open_and_configure_ro_flow as _impl
    except ImportError:
        from .stages import open_and_configure_ro_flow as _impl
    return _impl(*args, **kwargs)

def uia_configure_flow_calculator_recoveries(*args, **kwargs):
    """Runtime bridge to ro.reports.uia_configure_flow_calculator_recoveries."""
    try:
        from ro.reports import uia_configure_flow_calculator_recoveries as _impl
    except ImportError:
        from .reports import uia_configure_flow_calculator_recoveries as _impl
    return _impl(*args, **kwargs)

def open_and_configure_ro_flow_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
    *,
    context: str = "schema_case",
) -> None:
    if case.pass_count == 1:
        open_and_configure_ro_flow(hwnd, monitor, points, settings)
        return
    for source_name in ("ro_feed_flow", "ro_recovery"):
        if _find_flow_calculator_dialog(hwnd, timeout=0.0) is None:
            click(points, source_name, pause=0.25)
        dialog = _find_flow_calculator_dialog(hwnd, timeout=4.0)
        if dialog is None:
            continue
        logging.info("다중 Pass Flow Calculator 감지: %s", dialog)
        result = uia_configure_flow_calculator_recoveries(
            dialog.hwnd,
            [p.recovery_pct for p in case.passes],
            timeout=max(25.0, settings.long_wait * 6.0),
        )
        screenshot(f"flow_calculator_{context}_multi", monitor, hwnd)
        if not result.get("ok"):
            raise WaveAutomationError(f"다중 Pass Flow Calculator 설정 실패: {result}")
        if not _wait_window_closed(dialog.hwnd, max(15.0, settings.long_wait * 3.0)):
            raise WaveAutomationError(
                "다중 Pass Flow Calculator OK 후 창이 닫히지 않았습니다."
            )
        focus_wave(hwnd)
        return
    raise WaveAutomationError("Reverse Osmosis Flow Calculator를 찾지 못했습니다.")
