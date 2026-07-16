from __future__ import annotations

"""Planned home for RO stage/pass configuration helpers. V135 scaffold only."""

# V140_RO_STAGES_STAGE_GRID_POINTS_APPLIED


def _stage_grid_points(
    hwnd: int,
    pass_config: ROPassConfig,
) -> list[dict[str, Any]]:
    layout: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(pass_config.stages, start=1):
        layout.append(
            {
                "stage_index": stage_index,
                "stage": stage,
                "pv": _stage_cell_point(
                    hwnd, 600, pass_config.stage_count, stage_index
                ),
                "elements": _stage_cell_point(
                    hwnd, 635, pass_config.stage_count, stage_index
                ),
                "membrane": _stage_cell_point(
                    hwnd, 666, pass_config.stage_count, stage_index
                ),
                "stage_back_pressure": _stage_cell_point(
                    hwnd, 786, pass_config.stage_count, stage_index
                ),
                "boost_pressure": _stage_cell_point(
                    hwnd, 821, pass_config.stage_count, stage_index
                ),
                "flow_factor": _stage_cell_point(
                    hwnd, 921, pass_config.stage_count, stage_index
                ),
            }
        )
    return layout

# V145A_RO_STAGES_STABILIZE_AFTER_FLOW_COMMIT_APPLIED

def _verify_case_operating_inputs(*args, **kwargs):
    """Bridge to ro.case_config while avoiding top-level circular imports."""
    try:
        from ro.case_config import _verify_case_operating_inputs as _impl
    except ImportError:
        from .case_config import _verify_case_operating_inputs as _impl
    return _impl(*args, **kwargs)

def _reassert_global_temperature_after_flow_commit(*args, **kwargs):
    """Bridge to a legacy helper left in wave_ro_engine_legacy during staged refactor."""
    try:
        from wave_ro_engine_legacy import _reassert_global_temperature_after_flow_commit as _legacy_impl
    except ImportError:
        from ..wave_ro_engine_legacy import _reassert_global_temperature_after_flow_commit as _legacy_impl
    return _legacy_impl(*args, **kwargs)


def _stabilize_after_flow_commit(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
    *,
    context: str,
) -> None:
    """Restore topology and sticky inputs after a Flow Calculator commit."""
    _restore_stage_topologies_after_flow_commit(
        hwnd, monitor, points, case, settings, context=context
    )
    _reassert_global_temperature_after_flow_commit(
        hwnd, monitor, points, case, settings, context=context
    )
    _verify_case_operating_inputs(
        hwnd, monitor, points, case, settings, context=context
    )

# V148_RO_STAGES_SELECT_AND_COUNT_APPLIED

def WaveAutomationError(*args, **kwargs):
    """Lazy factory for the legacy WaveAutomationError exception instance."""
    try:
        from wave_ro_engine_legacy import WaveAutomationError as _Exc
    except ImportError:
        from ..wave_ro_engine_legacy import WaveAutomationError as _Exc
    return _Exc(*args, **kwargs)

from wave_interaction import click, click_expect_new_dialog, click_until_visual_change, replace_value, wait

def _select_pass(
    points: dict[str, tuple[int, int]], pass_index: int, pause: float
) -> None:
    if pass_index not in (1, 2):
        raise WaveAutomationError(f"Pass index must be 1 or 2, got {pass_index}")
    click(points, f"pass_{pass_index}_tab", pause=pause)

def _set_stage_count(
    points: dict[str, tuple[int, int]], stage_count: int, pause: float
) -> None:
    if not 1 <= stage_count <= 5:
        raise WaveAutomationError(f"Stage count must be 1..5, got {stage_count}")
    click(points, f"stage_{stage_count}_radio", pause=pause)

# V150_RO_STAGES_STAGE_CELL_POINT_APPLIED


def _stage_cell_point(
    hwnd: int,
    row_y_reference: int,
    stage_count: int,
    stage_index: int,
) -> tuple[int, int]:
    if not 1 <= stage_index <= stage_count <= 5:
        raise WaveAutomationError(
            f"invalid stage coordinate request: stage={stage_index}/{stage_count}"
        )
    # The editable stage grid starts after the row-label column and ends at
    # the right edge of the Stage area.  V22/V23 used 252..716, which happened
    # to land inside the first two columns but placed the third-stage point in
    # Stage 2.  The bounds below are measured in the 1280x1032 WAVE reference
    # frame and remain valid for 1-5 stages through window-relative mapping.
    table_left = 293
    table_right = 832
    x = round(
        table_left + (stage_index - 0.5) * (table_right - table_left) / stage_count
    )
    return _map_reference_point(hwnd, x, row_y_reference)

# V151_RO_STAGES_ADD_SECOND_PASS_APPLIED

def _capture_wave_image(*args, **kwargs):
    """Runtime bridge to ro.case_config._capture_wave_image."""
    try:
        from ro.case_config import _capture_wave_image as _impl
    except ImportError:
        from .case_config import _capture_wave_image as _impl
    return _impl(*args, **kwargs)

def _image_change_ratio(*args, **kwargs):
    """Runtime bridge to ro.case_config._image_change_ratio."""
    try:
        from ro.case_config import _image_change_ratio as _impl
    except ImportError:
        from .case_config import _image_change_ratio as _impl
    return _impl(*args, **kwargs)

def screenshot(*args, **kwargs):
    """Runtime bridge to ro.case_config.screenshot."""
    try:
        from ro.case_config import screenshot as _impl
    except ImportError:
        from .case_config import screenshot as _impl
    return _impl(*args, **kwargs)

from wave_diagnostics import (
    _capture_wave_image,
    _image_change_ratio,
    capture_ro_state,
    diff_ro_states,
    screenshot,
    write_convergence_failure_report,
)

from wave_runtime import record_event

def _add_second_pass(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pause: float,
) -> None:
    before = _capture_wave_image(hwnd)
    click(points, "add_pass", pause=pause)
    wait(max(1.0, pause))
    after = _capture_wave_image(hwnd)
    ratio = _image_change_ratio(before, after)
    record_event("add_pass", change_ratio=ratio)
    screenshot("add_pass_result", monitor, hwnd)
    if ratio < 0.002:
        raise WaveAutomationError(
            "Add Pass 클릭 후 화면 변화가 없어 Pass 2가 추가되지 않은 것으로 판단했습니다."
        )

# V152_RO_STAGES_CONFIGURE_STAGE_GRID_APPLIED

def verify_numeric_point(*args, **kwargs):
    """Runtime bridge to ro.case_config.verify_numeric_point."""
    try:
        from ro.case_config import verify_numeric_point as _impl
    except ImportError:
        from .case_config import verify_numeric_point as _impl
    return _impl(*args, **kwargs)

def _replace_value_at_point(*args, **kwargs):
    """Bridge to a legacy helper left in wave_ro_engine_legacy during staged refactor."""
    try:
        from wave_ro_engine_legacy import _replace_value_at_point as _legacy_impl
    except ImportError:
        from ..wave_ro_engine_legacy import _replace_value_at_point as _legacy_impl
    return _legacy_impl(*args, **kwargs)

def _verify_stage_grid_numeric_values(*args, **kwargs):
    """Bridge to a legacy helper left in wave_ro_engine_legacy during staged refactor."""
    try:
        from wave_ro_engine_legacy import _verify_stage_grid_numeric_values as _legacy_impl
    except ImportError:
        from ..wave_ro_engine_legacy import _verify_stage_grid_numeric_values as _legacy_impl
    return _legacy_impl(*args, **kwargs)

def _write_stage_numeric_with_retry(*args, **kwargs):
    """Bridge to a legacy helper left in wave_ro_engine_legacy during staged refactor."""
    try:
        from wave_ro_engine_legacy import _write_stage_numeric_with_retry as _legacy_impl
    except ImportError:
        from ..wave_ro_engine_legacy import _write_stage_numeric_with_retry as _legacy_impl
    return _legacy_impl(*args, **kwargs)

from wave_ro_ui import _restore_wave_after_combo, add_ro_with_recovery, enter_home_with_recovery, open_and_configure_ro_flow, select_combo_exact, set_and_verify_ro_temperature_mode

from wave_dialogs import _blocking_wave_dialogs, _close_modal_dialog, _find_flow_calculator_dialog, _wait_window_closed, configure_flow_calculator_dialog, resolve_wave_blocking_dialogs

def _configure_stage_grid(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pass_index: int,
    pass_config: ROPassConfig,
    settings: Settings,
) -> None:
    _set_stage_count(points, pass_config.stage_count, settings.pause)
    wait(max(0.6, settings.pause))
    layout = _stage_grid_points(hwnd, pass_config)

    # WAVE can auto-size PV counts when an Element Type changes.  Commit every
    # membrane first, then write all numeric topology values afterwards.  This
    # prevents a later-stage membrane selection from silently resetting an
    # earlier stage from (for example) PV=3 back to PV=1.
    for item in layout:
        stage_index = int(item["stage_index"])
        stage = item["stage"]
        dynamic = dict(points)
        key = f"p{pass_index}s{stage_index}_membrane"
        dynamic[key] = item["membrane"]
        select_combo_exact(
            hwnd, monitor, dynamic, key, stage.membrane, settings.long_wait
        )

    # Commit PV and Elements/PV only after all membrane-triggered auto-sizing is
    # finished.  Exact UIA ListItems can be virtualized near the taskbar, so
    # restore WAVE foreground before numeric edits and retry swallowed writes.
    _restore_wave_after_combo(hwnd, f"pass{pass_index}_stage_numeric_begin")
    if pass_index > 1:
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.5, settings.pause))
    for item in layout:
        stage_index = int(item["stage_index"])
        stage = item["stage"]
        _write_stage_numeric_with_retry(
            hwnd,
            points,
            pass_index,
            f"p{pass_index}s{stage_index}_pv",
            item["pv"],
            stage.pv,
            settings.pause,
        )
        _write_stage_numeric_with_retry(
            hwnd,
            points,
            pass_index,
            f"p{pass_index}s{stage_index}_elements",
            item["elements"],
            stage.elements_per_pv,
            settings.pause,
        )

    for item in layout:
        stage_index = int(item["stage_index"])
        stage = item["stage"]
        stage_back_pressure = (
            0.0 if stage.stage_back_pressure_bar is None else stage.stage_back_pressure_bar
        )
        point = item["stage_back_pressure"]
        _replace_value_at_point(point, stage_back_pressure, settings.pause)
        verify_numeric_point(
            f"p{pass_index}s{stage_index}_stage_back_pressure",
            point,
            stage_back_pressure,
        )

        if stage_index > 1:
            boost_pressure = (
                0.0 if stage.boost_pressure_bar is None else stage.boost_pressure_bar
            )
            point = item["boost_pressure"]
            _replace_value_at_point(point, boost_pressure, settings.pause)
            resolve_wave_blocking_dialogs(
                hwnd, monitor, f"p{pass_index}s{stage_index}_boost_pressure", points
            )
            verify_numeric_point(
                f"p{pass_index}s{stage_index}_boost_pressure",
                point,
                boost_pressure,
            )

        stage_flow_factor = (
            pass_config.flow_factor if stage.flow_factor is None else stage.flow_factor
        )
        point = item["flow_factor"]
        _replace_value_at_point(point, stage_flow_factor, settings.pause)
        resolve_wave_blocking_dialogs(
            hwnd, monitor, f"p{pass_index}s{stage_index}_flow_factor", points
        )
        verify_numeric_point(
            f"p{pass_index}s{stage_index}_flow_factor",
            point,
            stage_flow_factor,
        )

    # One final read catches any WAVE-side recalculation caused by pressure or
    # flow-factor edits before leaving the RO screen.
    _verify_stage_grid_numeric_values(
        hwnd,
        monitor,
        points,
        pass_index,
        pass_config,
        settings,
        repair=True,
        context="schema_stage_commit",
    )
    screenshot(f"schema_pass_{pass_index}_stages_configured", monitor, hwnd)

# V153_RO_STAGES_MAP_REFERENCE_POINT_APPLIED

def _legacy_reference_width():
    try:
        from wave_ro_engine_legacy import REFERENCE_WIDTH as _value
    except ImportError:
        from ..wave_ro_engine_legacy import REFERENCE_WIDTH as _value
    return _value

def _legacy_reference_height():
    try:
        from wave_ro_engine_legacy import REFERENCE_HEIGHT as _value
    except ImportError:
        from ..wave_ro_engine_legacy import REFERENCE_HEIGHT as _value
    return _value

def _get_window_rect(*args, **kwargs):
    """Late-bound bridge to a legacy attribute during staged refactor."""
    try:
        import wave_ro_engine_legacy as _legacy
    except ImportError:
        from .. import wave_ro_engine_legacy as _legacy
    return getattr(_legacy, '_get_window_rect')(*args, **kwargs)

def _map_reference_point(hwnd: int, x: int, y: int) -> tuple[int, int]:
    rect = _get_window_rect(hwnd)
    return (
        rect.left + round(x * rect.width / _legacy_reference_width()),
        rect.top + round(y * rect.height / _legacy_reference_height()),
    )

# V158_RO_STAGES_RESTORE_TOPOLOGIES_APPLIED

import logging

def _capture_case_ro_state(*args, **kwargs):
    """Runtime bridge to ro.case_config._capture_case_ro_state."""
    try:
        from ro.case_config import _capture_case_ro_state as _impl
    except ImportError:
        from .case_config import _capture_case_ro_state as _impl
    return _impl(*args, **kwargs)

def logging(*args, **kwargs):
    """Runtime bridge to ro.membrane.logging."""
    try:
        from ro.membrane import logging as _impl
    except ImportError:
        from .membrane import logging as _impl
    return _impl(*args, **kwargs)

def _restore_stage_topologies_after_flow_commit(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
    *,
    context: str,
) -> None:
    """Rebuild every multi-stage pass after committing the Flow Calculator.

    In the observed WAVE build, accepting the multi-pass Flow Calculator can
    silently collapse a 2+ stage pass back to one stage while leaving Recovery
    and the visible pass-level values intact.  Reading the grid with coordinates
    calculated for the requested stage count then aliases several expected
    columns onto the single surviving Stage 1 cell.  The old integrity loop
    consequently alternated values such as PV=4 and PV=2 forever.

    Re-select the requested stage count and rebuild the complete stage grid
    before any coordinate-based verification.  One-stage passes are left
    untouched because they cannot suffer this column-aliasing failure.
    """
    restored: list[dict[str, Any]] = []
    for pass_index, pass_config in enumerate(case.passes, start=1):
        if pass_config.stage_count <= 1:
            continue
        logging.warning(
            "Flow Calculator 후 다중 Stage 토폴로지 재적용: "
            "case=%s pass=%s expected_stages=%s context=%s",
            case.case_id,
            pass_index,
            pass_config.stage_count,
            context,
        )
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.65, settings.pause))
        before_restore = _capture_case_ro_state(
            f"{context}_p{pass_index}_before_topology_restore",
            hwnd,
            monitor,
            points,
            case,
            pass_index=pass_index,
            pass_config=pass_config,
            metadata={"phase": "before_topology_restore"},
        )
        _configure_stage_grid(
            hwnd, monitor, points, pass_index, pass_config, settings
        )
        after_restore = _capture_case_ro_state(
            f"{context}_p{pass_index}_after_topology_restore",
            hwnd,
            monitor,
            points,
            case,
            pass_index=pass_index,
            pass_config=pass_config,
            metadata={"phase": "after_topology_restore"},
        )
        diff_ro_states(
            before_restore,
            after_restore,
            label=f"{context}_p{pass_index}_topology_restore",
        )
        restored.append(
            {
                "pass": pass_index,
                "stage_count": pass_config.stage_count,
                "pvs": [stage.pv for stage in pass_config.stages],
                "membranes": [stage.membrane for stage in pass_config.stages],
            }
        )

    record_event(
        "ro_stage_topology_reassert_v44",
        case_id=case.case_id,
        context=context,
        restored=restored,
    )
    if restored:
        screenshot(f"{context}_stage_topologies_restored", monitor, hwnd)
