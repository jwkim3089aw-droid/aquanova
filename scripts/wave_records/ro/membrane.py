from __future__ import annotations

"""Planned home for RO membrane selection helpers. V135 scaffold only."""

try:
    from ro.stages import _stage_grid_points
except ImportError:
    from .stages import _stage_grid_points

# V141_RO_MEMBRANE_DIAGNOSTIC_POINTS_APPLIED

def _ro_diagnostic_points(
    hwnd: int,
    points: dict[str, tuple[int, int]],
    *,
    pass_index: Optional[int] = None,
    pass_config: Optional[ROPassConfig] = None,
) -> dict[str, tuple[int, int]]:
    """Return a small, labelled point set for deep RO diagnostics."""
    keys = [
        "pass_1_tab",
        "pass_2_tab",
        "stage_1_radio",
        "stage_2_radio",
        "stage_3_radio",
        "stage_4_radio",
        "stage_5_radio",
        "ro_feed_flow",
        "ro_recovery",
        "ro_flow_factor",
        "ro_pass_back_pressure",
        "ro_temperature_mode",
        "ro_temperature_value",
    ]
    result = {key: points[key] for key in keys if key in points}
    if pass_index is not None and pass_config is not None:
        for item in _stage_grid_points(hwnd, pass_config):
            stage_index = int(item["stage_index"])
            for field in (
                "pv",
                "elements",
                "membrane",
                "stage_back_pressure",
                "boost_pressure",
                "flow_factor",
            ):
                result[f"p{pass_index}s{stage_index}_{field}"] = item[field]
    return result

# V157_RO_MEMBRANE_RECONCILE_PASS_TOPOLOGY_APPLIED

import logging

def WaveAutomationError(*args, **kwargs):
    """Runtime bridge to ro.case_config.WaveAutomationError."""
    try:
        from ro.case_config import WaveAutomationError as _impl
    except ImportError:
        from .case_config import WaveAutomationError as _impl
    return _impl(*args, **kwargs)

def _select_pass(*args, **kwargs):
    """Runtime bridge to ro.case_config._select_pass."""
    try:
        from ro.case_config import _select_pass as _impl
    except ImportError:
        from .case_config import _select_pass as _impl
    return _impl(*args, **kwargs)

def focus_wave(*args, **kwargs):
    """Runtime bridge to ro.reports.focus_wave."""
    try:
        from ro.reports import focus_wave as _impl
    except ImportError:
        from .reports import focus_wave as _impl
    return _impl(*args, **kwargs)

def screenshot(*args, **kwargs):
    """Runtime bridge to ro.case_config.screenshot."""
    try:
        from ro.case_config import screenshot as _impl
    except ImportError:
        from .case_config import screenshot as _impl
    return _impl(*args, **kwargs)

def uia_reconcile_ro_pass_count(*args, **kwargs):
    """Runtime bridge to ro.reports.uia_reconcile_ro_pass_count."""
    try:
        from ro.reports import uia_reconcile_ro_pass_count as _impl
    except ImportError:
        from .reports import uia_reconcile_ro_pass_count as _impl
    return _impl(*args, **kwargs)

def wait(*args, **kwargs):
    """Runtime bridge to ro.case_config.wait."""
    try:
        from ro.case_config import wait as _impl
    except ImportError:
        from .case_config import wait as _impl
    return _impl(*args, **kwargs)

def _reconcile_ro_pass_topology(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    expected_pass_count: int,
    settings: Settings,
) -> None:
    """Reconcile stale 1/2-pass WAVE topology without restarting WAVE."""
    result = uia_reconcile_ro_pass_count(
        hwnd, expected_pass_count, timeout=max(25.0, settings.long_wait * 6.0)
    )
    if not result.get("ok") or int(result.get("actual", -1)) != expected_pass_count:
        raise WaveAutomationError(
            f"RO Pass topology reconciliation failed: expected={expected_pass_count}, result={result}"
        )
    focus_wave(hwnd)
    wait(max(0.8, settings.pause))
    _select_pass(points, 1, settings.pause)
    screenshot("ro_pass_topology_reconciled_v52", monitor, hwnd)
    logging.info(
        "RO Pass 상태 정규화 성공: expected=%s actual=%s action=%s",
        expected_pass_count,
        result.get("actual"),
        result.get("action"),
    )

# V160_RO_MEMBRANE_VERIFY_STAGE_GRID_MEMBRANES_APPLIED

def record_event(*args, **kwargs):
    """Runtime bridge to ro.reports.record_event."""
    try:
        from ro.reports import record_event as _impl
    except ImportError:
        from .reports import record_event as _impl
    return _impl(*args, **kwargs)

def select_combo_exact(*args, **kwargs):
    """Runtime bridge to ro.stages.select_combo_exact."""
    try:
        from ro.stages import select_combo_exact as _impl
    except ImportError:
        from .stages import select_combo_exact as _impl
    return _impl(*args, **kwargs)

def uia_read_combo_candidates(*args, **kwargs):
    """Runtime bridge to ro.reports.uia_read_combo_candidates."""
    try:
        from ro.reports import uia_read_combo_candidates as _impl
    except ImportError:
        from .reports import uia_read_combo_candidates as _impl
    return _impl(*args, **kwargs)

def _verify_stage_grid_membranes(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pass_index: int,
    pass_config: ROPassConfig,
    settings: Settings,
    *,
    repair: bool,
    context: str,
) -> bool:
    """Verify membranes when UIA exposes evidence; defer unreadable cells to WAVE.

    WAVE's membrane presenter can be visually correct while every UIA readback is
    empty.  Empty evidence is therefore not a mismatch.  A concrete conflicting
    membrane value is repaired immediately; an unreadable value is left intact
    and validated by the Summary transition, whose missing-Element-Type dialog
    identifies the exact Pass and Stage when a commit truly failed.
    """
    _select_pass(points, pass_index, settings.pause)
    wait(max(0.6, settings.pause))
    layout = _stage_grid_points(hwnd, pass_config)
    changed = False
    for item in layout:
        stage_index = int(item["stage_index"])
        stage = item["stage"]
        result = uia_read_combo_candidates(hwnd, item["membrane"])
        displayed = [
            str(v).strip()
            for v in (result.get("displayed") or [])
            if str(v).strip()
        ]
        selected = [
            str(v).strip()
            for v in (result.get("selected") or [])
            if str(v).strip()
        ]
        evidence: list[str] = []
        for value in [*displayed, *selected]:
            if value not in evidence:
                evidence.append(value)
        exact = any(v.casefold() == stage.membrane.casefold() for v in evidence)
        if exact:
            logging.info(
                "Stage 막 UIA 검증 성공: pass=%s stage=%s membrane=%r evidence=%r",
                pass_index,
                stage_index,
                stage.membrane,
                evidence,
            )
            continue

        # A non-exact expanded SelectionItemPattern value can be stale in WAVE's
        # virtualized list.  Only collapsed display evidence is authoritative as
        # a negative; positive exact evidence from either source is accepted.
        unreadable = bool(result.get("readback_unavailable")) or not displayed
        if unreadable:
            logging.warning(
                "Stage 막 UIA readback 없음; Summary 권위 검증으로 연기: "
                "pass=%s stage=%s expected=%r context=%s",
                pass_index,
                stage_index,
                stage.membrane,
                context,
            )
            record_event(
                "membrane_readback_deferred_v32",
                pass_index=pass_index,
                stage_index=stage_index,
                expected=stage.membrane,
                context=context,
                result=result,
            )
            continue

        if not repair:
            raise WaveAutomationError(
                f"p{pass_index}s{stage_index}_membrane 최종 검증 실패: "
                f"expected={stage.membrane!r}, evidence={evidence!r}"
            )
        logging.warning(
            "Stage 막 오선택 감지·재설정: pass=%s stage=%s expected=%r evidence=%r",
            pass_index,
            stage_index,
            stage.membrane,
            evidence,
        )
        dynamic = dict(points)
        key = f"p{pass_index}s{stage_index}_membrane"
        dynamic[key] = item["membrane"]
        select_combo_exact(hwnd, monitor, dynamic, key, stage.membrane, settings.long_wait)
        changed = True
    screenshot(f"{context}_pass_{pass_index}_membranes", monitor, hwnd)
    return changed
