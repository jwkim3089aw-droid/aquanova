from __future__ import annotations

"""Planned home for RO high-level runner helpers. V135 scaffold only."""

# V147_RO_RUNNER_LEGACY_COMPATIBLE_APPLIED

def _has_flow_optimization(*args, **kwargs):
    """Bridge to ro.feedwater while keeping runner import-order independent."""
    try:
        from ro.feedwater import _has_flow_optimization as _impl
    except ImportError:
        from .feedwater import _has_flow_optimization as _impl
    return _impl(*args, **kwargs)

def _legacy_compatible(case: ROCaseConfig) -> bool:
    if (
        case.pass_count != 1
        or case.chemical.acid_enabled
        or case.chemical.base_enabled
        or case.chemical.degas_enabled
        or case.chemical.antiscalant_enabled
        or case.chemical.dechlorinator_enabled
        or bool(case.chemical.temperature_mode)
        or bool(case.chemical.recovery_mode)
        or case.special_features.enabled
    ):
        return False
    p = case.passes[0]
    s = p.stages[0]
    return (
        p.stage_count == 1
        and abs(p.flow_factor - 0.85) < 1e-9
        and abs(p.permeate_back_pressure_bar) < 1e-9
        and s.stage_back_pressure_bar is None
        and s.boost_pressure_bar is None
        and s.flow_factor is None
        and not _has_flow_optimization(p)
    )

# V161_RO_RUNNER_FIND_NEW_DIALOG_APPLIED

import time

def _get_process_id(*args, **kwargs):
    """Runtime bridge to ro.reports._get_process_id."""
    try:
        from ro.reports import _get_process_id as _impl
    except ImportError:
        from .reports import _get_process_id as _impl
    return _impl(*args, **kwargs)

def list_visible_windows(*args, **kwargs):
    """Runtime bridge to ro.reports.list_visible_windows."""
    try:
        from ro.reports import list_visible_windows as _impl
    except ImportError:
        from .reports import list_visible_windows as _impl
    return _impl(*args, **kwargs)

def _find_new_wave_dialog(
    wave_hwnd: int,
    before_hwnds: set[int],
    *,
    title_patterns: tuple[str, ...],
    timeout: float = 6.0,
) -> Optional[WindowInfo]:
    deadline = time.time() + timeout
    pid = _get_process_id(wave_hwnd)
    patterns = tuple(item.casefold() for item in title_patterns)
    while time.time() < deadline:
        candidates: list[WindowInfo] = []
        for item in list_visible_windows(include_small=True):
            if item.hwnd == wave_hwnd or item.process_id != pid:
                continue
            title = item.title.casefold()
            if item.hwnd not in before_hwnds or any(pattern in title for pattern in patterns):
                candidates.append(item)
        if candidates:
            candidates.sort(
                key=lambda item: (
                    any(pattern in item.title.casefold() for pattern in patterns),
                    item.hwnd not in before_hwnds,
                    item.rect.width * item.rect.height,
                ),
                reverse=True,
            )
            return candidates[0]
        time.sleep(0.15)
    return None
