#!/usr/bin/env python3
"""Closed Circuit Reverse Osmosis video-derived automation path (V55).

V55 intentionally starts CCRO with a conservative, single-pass baseline.  The
user's 2026-07-06 video showed WAVE entering an effectively endless Summary
Report calculation after a risky 2-pass / 90%+ setting combination.  This module
therefore prioritizes deterministic state reconciliation and diagnostics before
expanding CCRO into the Excel schema.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from wave_common import *
from wave_diagnostics import _capture_wave_image, _image_change_ratio, screenshot
from wave_dialogs import (
    _find_flow_calculator_dialog,
    _wait_window_closed,
    configure_flow_calculator_dialog,
    resolve_wave_blocking_dialogs,
)
from wave_feed import (
    copy_library_to_feed,
    prepare_feed_for_profile_replacement,
    select_library_profile,
    set_feed_temperature_envelope,
    verify_numeric_point,
)
from wave_interaction import click, click_expect_new_dialog, click_until_visual_change, replace_value, wait
from wave_pdf import _extract_pdf_text, _number_pattern, dismiss_export_success_dialog, export_pdf
from wave_ro_ui import enter_home_with_recovery, select_combo_exact, select_combo_text
from wave_runtime import record_event
from wave_uia import uia_reconcile_ro_pass_count
from wave_windows import _foreground_window_info, _get_process_id, _get_window_rect, bring_window_to_front, focus_wave, list_visible_windows, native_click_at, native_drag, native_move_to


@dataclass
class CCROVideoCase:
    """Conservative CCRO case derived from the user's CCRO settings video."""

    case_id: str = "V55_CCRO_VIDEO_SAFE_001"
    pdf_name: str = "V55_CCRO_VIDEO_SAFE_001_SOAR5000i_F100_R75.pdf"
    water_profile: str = "Well Water - Med Hardness"
    feed_flow_m3h: float = 100.0
    recovery_pct: float = 75.0
    # V111: CCRO PF Cycle fields in Flow Calculator
    pf_feed_ratio_pct: float = 120.0
    pf_recovery_pct: float = 20.0
    feed_temperature_min_c: float = 10.0
    feed_temperature_design_c: float = 15.0
    feed_temperature_max_c: float = 20.0
    temperature_mode: str = "Design"
    pass_count: int = 1
    stage_count: int = 1
    flow_factor: float = 0.85
    pass_back_pressure_bar: float = 0.0
    pv_per_stage: int = 10
    elements_per_pv: int = 5
    element_type: str = "FilmTec™ SOAR 5000i"
    # V55: optional controlled 2-pass CCRO probe.  Keep Pass 2 deliberately mild.
    pass2_recovery_pct: float = 50.0
    pass2_stage_count: int = 1
    pass2_flow_factor: float = 0.85
    pass2_back_pressure_bar: float = 0.0
    pass2_pv_per_stage: int = 6
    pass2_elements_per_pv: int = 5
    pass2_stage_back_pressure_bar: float = 0.0
    pass2_stage_flow_factor: float = 0.85
    notes: str = (
        "V55 CCRO baseline/probe.  1-pass can be swept up to high recovery; "
        "2-pass is enabled only as a conservative probe because the user video "
        "showed 2-pass / 90% settings producing extreme Pass 2 flux and long "
        "Summary Report calculation."
    )

    def to_settings(self, *, pause: float, long_wait: float, validate_pdf: bool) -> Settings:
        return Settings(
            water_profile=self.water_profile,
            temperature_c=_fmt_value(self.feed_temperature_design_c),
            feed_flow_m3h=_fmt_value(self.feed_flow_m3h),
            recovery_pct=_fmt_value(self.recovery_pct),
            pv_per_stage=_fmt_value(self.pv_per_stage),
            elements_per_pv=_fmt_value(self.elements_per_pv),
            membrane=self.element_type,
            add_ro=False,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
        )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("_") or "ccro_case"


def _write_ccro_artifact(name: str, payload: dict[str, Any]) -> None:
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / name).write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _is_report_spinner_dialog(dialog: WindowInfo, text: str) -> bool:
    blob = f"{dialog.title}\n{text}".lower()
    return (
        "reportloadingspinner" in blob
        or "calculating report" in blob
        or "calculating report..." in blob
    )


def _dialog_text_blob(dialog: WindowInfo) -> str:
    # Small helper avoids importing private dialog child readers.  The title is
    # enough for ReportLoadingSpinner; generic modal text is handled by the
    # existing resolver.
    return str(dialog.title or "")


def _visible_same_process_dialogs(hwnd: int) -> list[WindowInfo]:
    pid = _get_process_id(hwnd)
    dialogs: list[WindowInfo] = []
    fg = _foreground_window_info()
    if fg is not None and fg.hwnd != hwnd and fg.process_id == pid:
        dialogs.append(fg)
    for item in list_visible_windows():
        if item.hwnd == hwnd or item.process_id != pid:
            continue
        if item not in dialogs:
            dialogs.append(item)
    return dialogs


def _wait_for_ccro_report_spinner(
    hwnd: int,
    monitor: Rect,
    context: str,
    *,
    timeout_s: float = 120.0,
) -> list[str]:
    """Wait through CCRO Summary Report calculation without treating it as a modal.

    If WAVE cannot finish within the timeout, fail deliberately with a screenshot
    instead of letting the automation appear to hang forever.
    """
    start = time.time()
    seen = False
    last_blob = ""
    while True:
        spinners: list[str] = []
        for dialog in _visible_same_process_dialogs(hwnd):
            text = _dialog_text_blob(dialog)
            if _is_report_spinner_dialog(dialog, text):
                spinners.append(f"{dialog.title}: {text}".strip())
        if not spinners:
            if seen:
                wait(1.0)
                elapsed = round(time.time() - start, 2)
                logging.info("CCRO Report 계산 대기 완료: context=%s elapsed=%ss", context, elapsed)
                record_event("ccro_report_spinner_waited_v55", context=context, elapsed_s=elapsed)
                return ["ccro_report_spinner_waited"]
            return []
        if not seen:
            seen = True
            last_blob = " | ".join(spinners)
            logging.info("CCRO Report 계산 대기 시작: context=%s dialogs=%s", context, last_blob)
            record_event("ccro_report_spinner_seen_v55", context=context, dialogs=spinners)
            screenshot(f"ccro_report_spinner_{_safe_name(context)}_v55", monitor, hwnd)
        if time.time() - start > timeout_s:
            screenshot(f"ccro_report_spinner_timeout_{_safe_name(context)}_v55", monitor, hwnd)
            raise WaveAutomationError(
                f"CCRO Report 계산 대기 시간 초과: context={context} timeout={timeout_s}s. "
                "설정 조합이 WAVE 계산을 끝내지 못하는 것으로 보입니다. "
                "1-pass, 낮은 recovery, 충분한 element area로 재시도하세요. "
                f"last={last_blob!r}"
            )
        wait(0.7)



def _close_ccro_total_cycles_error_dialogs(
    hwnd: int,
    monitor: Rect,
    context: str,
) -> list[str]:
    """Close CCRO Total Cycles error message boxes that WAVE can spawn out-of-process.

    The 2026-07-06 2-pass probe showed a standard ``#32770`` dialog whose
    process metadata was not the WAVE PID.  The generic WAVE modal resolver is
    intentionally same-process only, so CCRO handles this specific title here.
    """
    actions: list[str] = []
    for dialog in list_visible_windows(include_small=True):
        title = str(dialog.title or "").strip()
        if title.lower() != "total cycles error":
            continue
        logging.warning(
            "CCRO Total Cycles Error 자동 확인: context=%s hwnd=%s rect=%s",
            context,
            dialog.hwnd,
            dialog.rect,
        )
        record_event(
            "ccro_total_cycles_error_acknowledged_v55",
            context=context,
            dialog=dialog,
        )
        screenshot(f"ccro_total_cycles_error_{_safe_name(context)}_v55", monitor, hwnd)
        try:
            bring_window_to_front(dialog.hwnd, restore_if_minimized=False)
            pyautogui.press("enter")
            wait(0.45)
            if ctypes.windll.user32.IsWindow(dialog.hwnd) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
                native_click_at(
                    dialog.rect.left + round(dialog.rect.width * 0.82),
                    dialog.rect.top + round(dialog.rect.height * 0.78),
                )
                wait(0.45)
        except Exception as exc:
            raise WaveAutomationError(f"CCRO Total Cycles Error 창을 닫지 못했습니다: {exc!r}")
        actions.append("ccro_total_cycles_error_acknowledged")
    return actions


def _resolve_ccro_modals(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    context: str,
) -> list[str]:
    actions: list[str] = []
    actions.extend(_close_ccro_total_cycles_error_dialogs(hwnd, monitor, context))
    actions.extend(_wait_for_ccro_report_spinner(hwnd, monitor, context))
    try:
        actions.extend(resolve_wave_blocking_dialogs(hwnd, monitor, context, points))
    except WaveAutomationError:
        spinner_actions = _wait_for_ccro_report_spinner(hwnd, monitor, context)
        if spinner_actions:
            actions.extend(spinner_actions)
        else:
            raise
    if actions:
        logging.info("CCRO 모달 자동 처리: context=%s actions=%s", context, actions)
        record_event("ccro_modal_resolved_v55", context=context, actions=actions)
    return actions


def _click_ccro(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    key: str,
    *,
    pause: float,
    context: str | None = None,
) -> None:
    label = context or key
    _resolve_ccro_modals(hwnd, monitor, points, f"before_{label}")
    click(points, key, pause=pause)
    _resolve_ccro_modals(hwnd, monitor, points, f"after_{label}")


def _replace_ccro_point(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    key: str,
    value: float | int | str,
    pause: float,
    *,
    verify: bool = True,
    context: str | None = None,
) -> None:
    label = context or key
    _resolve_ccro_modals(hwnd, monitor, points, f"before_{label}")
    replace_value(points, key, _fmt_value(value), pause)
    _resolve_ccro_modals(hwnd, monitor, points, f"after_write_{label}")
    if verify:
        verify_numeric_point(key, points[key], _fmt_value(value), required_when_readable=False)
    _resolve_ccro_modals(hwnd, monitor, points, f"after_verify_{label}")


def _select_combo_with_fallback(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    key: str,
    target: str,
    long_wait: float,
    pause: float,
) -> dict[str, Any]:
    try:
        result = select_combo_exact(hwnd, monitor, points, key, target, long_wait)
        result["fallback_used"] = False
        return result
    except Exception as exc:
        logging.warning(
            "CCRO ComboBox 정확 선택 실패; keyboard fallback 사용: key=%s target=%r error=%s",
            key,
            target,
            exc,
        )
        record_event("ccro_combo_exact_fallback_v55", key=key, target=target, error=repr(exc))
        select_combo_text(points, key, target, pause=max(1.0, pause))
        screenshot(f"ccro_combo_{key}_fallback", monitor, hwnd)
        return {"ok": True, "method": "keyboard_fallback", "target": target, "fallback_used": True}


def _yellow_pixel_fraction(image) -> float:
    total = max(1, image.width * image.height)
    yellow = 0
    for red, green, blue in image.getdata():
        if red >= 165 and green >= 120 and blue <= 95 and red - blue >= 95:
            yellow += 1
    return yellow / total


def ccro_presence_metrics(
    hwnd: int,
    points: dict[str, tuple[int, int]],
    *,
    label: str,
) -> dict[str, Any]:
    image = _capture_wave_image(hwnd)
    rect = _get_window_rect(hwnd)
    cx = int(points["process_drop_point"][0] - rect.left)
    cy = int(points["process_drop_point"][1] - rect.top)
    process_box = (
        max(0, cx - 130),
        max(0, cy - 120),
        min(image.width, cx + 130),
        min(image.height, cy + 120),
    )
    crop = image.crop(process_box)
    yellow_fraction = _yellow_pixel_fraction(crop)
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S_%f")
    try:
        crop.save(target_dir / f"{stamp}_{label}_ccro_process_crop.png")
    except Exception as exc:
        logging.warning("CCRO 검증 crop 저장 실패(%s): %s", label, exc)
    metrics = {
        "yellow_fraction": yellow_fraction,
        "process_box": process_box,
        "present": yellow_fraction >= 0.010,
    }
    logging.info(
        "CCRO 실제 상태 확인: label=%s yellow_fraction=%.5f present=%s",
        label,
        yellow_fraction,
        metrics["present"],
    )
    record_event("ccro_presence_check_v55", label=label, **metrics)
    return metrics


def add_ccro_if_missing(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    initial = ccro_presence_metrics(hwnd, points, label="before_ccro_drag")
    if initial["present"]:
        logging.info("CCRO 공정이 이미 존재합니다. 중복 드래그를 생략합니다.")
        record_event("ccro_add_skipped_v55", reason="already_present", metrics=initial)
        return
    last_metrics: dict[str, Any] = initial
    for attempt in range(1, 4):
        logging.info(
            "CCRO 아이콘 native drag attempt=%s: %s -> %s",
            attempt,
            points["ccro_icon"],
            points["process_drop_point"],
        )
        before = _capture_wave_image(hwnd)
        bring_window_to_front(hwnd)
        native_drag(points["ccro_icon"], points["process_drop_point"], duration=1.1)
        wait(max(2.5, settings.long_wait))
        actions = _resolve_ccro_modals(hwnd, monitor, points, f"after_ccro_drag_attempt_{attempt}")
        rect = _get_window_rect(hwnd)
        native_move_to(rect.left + min(620, rect.width // 2), rect.top + 16)
        wait(0.35)
        after = _capture_wave_image(hwnd)
        ratio = _image_change_ratio(before, after)
        metrics = ccro_presence_metrics(hwnd, points, label=f"after_ccro_drag_attempt_{attempt}")
        last_metrics = metrics
        record_event("ccro_drag_result_v55", attempt=attempt, change_ratio=ratio, metrics=metrics, actions=actions)
        if metrics["present"] or ratio >= 0.012:
            logging.info("CCRO 공정 추가 성공 확인: attempt=%s", attempt)
            screenshot(f"ccro_drag_success_{attempt}", monitor, hwnd)
            return
        screenshot(f"ccro_drag_retry_{attempt}", monitor, hwnd)
    raise WaveAutomationError(f"CCRO 아이콘 드래그 후 실제 CCRO 공정을 확인하지 못했습니다: {last_metrics}")


def _reconcile_ccro_pass_count(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    expected_pass_count: int,
    settings: Settings,
) -> dict[str, Any]:
    result = uia_reconcile_ro_pass_count(
        hwnd, expected_pass_count, timeout=max(25.0, settings.long_wait * 6.0)
    )
    if not result.get("ok") or int(result.get("actual", -1)) != expected_pass_count:
        raise WaveAutomationError(
            f"CCRO Pass topology reconciliation failed: expected={expected_pass_count}, result={result}"
        )
    focus_wave(hwnd)
    wait(max(0.8, settings.pause))
    _click_ccro(hwnd, monitor, points, "pass_1_tab", pause=settings.pause, context="ccro_pass_1_after_reconcile")
    screenshot("ccro_pass_topology_reconciled_v55", monitor, hwnd)
    logging.info(
        "CCRO Pass 상태 정규화 성공: expected=%s actual=%s action=%s",
        expected_pass_count,
        result.get("actual"),
        result.get("action"),
    )
    record_event("ccro_pass_count_reconciled_v55", result=result)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "ccro_pass_count_reconcile.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def _configure_ccro_flow_calculator(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    recovery_pct: float,
    settings: Settings,
    pass_label: str,
    pf_feed_ratio_pct: float | None = None,
    pf_recovery_pct: float | None = None,
) -> dict[str, Any] | None:
    """Open CCRO Flow Calculator and set the currently selected pass recovery.

    V55 keeps the original V53 single-pass path but also allows a cautious
    Pass-2 probe.  The same UIA recovery selector is used after selecting the
    target pass tab, and the context label records which pass was targeted.
    """
    context = f"ccro_{pass_label}_recovery_v55"
    target_automation_id = "txtRecovery2" if pass_label == "pass2" else "txtRecovery1"
    _click_ccro(hwnd, monitor, points, "ro_feed_flow", pause=settings.pause, context=f"{context}_open")
    dialog = _find_flow_calculator_dialog(hwnd, timeout=max(4.0, settings.long_wait))
    if dialog is None:
        logging.warning("CCRO Flow Calculator가 열리지 않았습니다. pass=%s 기존 recovery 값을 유지합니다.", pass_label)
        screenshot(f"ccro_flow_calculator_not_found_{pass_label}_v55", monitor, hwnd)
        return None
    configure_flow_calculator_dialog(
        dialog,
        _fmt_value(recovery_pct),
        monitor,
        hwnd,
        settings,
        context,
        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=2 if pass_label == "pass2" else 1,
    )
    if not _wait_window_closed(dialog.hwnd, max(12.0, settings.long_wait * 3.0)):
        raise WaveAutomationError(f"CCRO Flow Calculator가 OK 후 닫히지 않았습니다. pass={pass_label}")
    focus_wave(hwnd)
    wait(max(1.0, settings.pause))
    screenshot(f"ccro_flow_calculator_closed_{pass_label}_v55", monitor, hwnd)
    record_event(
        "ccro_flow_calculator_configured_v55",
        pass_label=pass_label,
        recovery_pct=recovery_pct,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
    )
    return {
        "configured": True,
        "pass_label": pass_label,
        "target_recovery_pct": recovery_pct,
        "target_pf_feed_ratio_pct": pf_feed_ratio_pct,
        "target_pf_recovery_pct": pf_recovery_pct,
    }


def _configure_ccro_selected_pass_fields(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: CCROVideoCase,
    settings: Settings,
    *,
    pass_index: int,
    recovery_pct: float,
    pv_per_stage: int,
    elements_per_pv: int,
    flow_factor: float,
    pass_back_pressure_bar: float,
    stage_back_pressure_bar: float,
    stage_flow_factor: float,
    pf_feed_ratio_pct: float | None = None,
    pf_recovery_pct: float | None = None,
) -> dict[str, Any]:
    """Configure visible fields for the currently selected CCRO pass.

    V86 fixes a WAVE guardrail discovered by the V84 CCRO flow sweep:
    the CCRO Flow Calculator can refuse to open with
    ``Please specify Element Type in Pass 1 Stage 1`` when it is clicked before
    the Stage 1 element is explicitly selected.  Earlier F100 cases sometimes
    worked because WAVE kept a usable default, but F70/F85/F115/F130 showed the
    dependency clearly.  Therefore the order is deliberately:

    1. select pass tab
    2. select Stage 1 element and stage sizing fields
    3. open Flow Calculator and set recovery

    Do not move the flow-calculator call back above the element selection.
    """
    pass_label = f"pass{pass_index}"
    tab_name = "pass_1_tab" if pass_index == 1 else "pass_2_tab"
    _click_ccro(hwnd, monitor, points, tab_name, pause=settings.pause)

    try:
        select_combo_text(points, "ro_temperature_mode", case.temperature_mode, pause=max(0.8, settings.pause))
        _replace_ccro_point(hwnd, monitor, points, "ro_temperature_value", case.feed_temperature_design_c, settings.pause)
    except Exception as exc:
        logging.warning("CCRO temperature mode/value setting warning: pass=%s error=%s", pass_index, exc)
        screenshot(f"ccro_temperature_setting_warning_pass{pass_index}_v55", monitor, hwnd)

    _click_ccro(hwnd, monitor, points, "stage_1_radio", pause=max(0.8, settings.pause))
    _select_combo_with_fallback(
        hwnd,
        monitor,
        points,
        "element_type_combo",
        case.element_type,
        settings.long_wait,
        settings.pause,
    )
    _replace_ccro_point(hwnd, monitor, points, "pv_per_stage", pv_per_stage, settings.pause)
    _replace_ccro_point(hwnd, monitor, points, "elements_per_pv", elements_per_pv, settings.pause)
    _replace_ccro_point(hwnd, monitor, points, "ro_flow_factor", flow_factor, settings.pause)
    _replace_ccro_point(hwnd, monitor, points, "ro_pass_back_pressure", pass_back_pressure_bar, settings.pause)
    try:
        _replace_ccro_point(hwnd, monitor, points, "stage_back_pressure_row", stage_back_pressure_bar, settings.pause)
        _replace_ccro_point(hwnd, monitor, points, "stage_flow_factor_row", stage_flow_factor, settings.pause)
    except Exception as exc:
        logging.warning("CCRO stage pressure/flow-factor setting warning: pass=%s error=%s", pass_index, exc)
        screenshot(f"ccro_stage_optional_setting_warning_pass{pass_index}_v55", monitor, hwnd)

    screenshot(f"ccro_pass{pass_index}_element_ready_before_flow_v86", monitor, hwnd)
    flow_result = _configure_ccro_flow_calculator(
        hwnd,
        monitor,
        points,
        recovery_pct,
        settings,
        pass_label,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
    )

    screenshot(f"ccro_pass{pass_index}_configured_v55", monitor, hwnd)
    return {
        "configured": True,
        "pass_index": pass_index,
        "recovery_pct": recovery_pct,
        "flow_calculator": flow_result,
        "pv_per_stage": pv_per_stage,
        "elements_per_pv": elements_per_pv,
        "flow_factor": flow_factor,
        "pf_feed_ratio_pct": pf_feed_ratio_pct,
        "pf_recovery_pct": pf_recovery_pct,
        "element_before_flow_calculator_v86": True,
    }

def configure_ccro_video_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: CCROVideoCase,
    settings: Settings,
) -> None:
    logging.info("=== CCRO 사례 입력 시작: %s ===", case.case_id)
    record_event("ccro_case_start_v55", case=asdict(case))
    _write_ccro_artifact("ccro_case_input.json", {"schema_version": 1, "case": asdict(case)})
    _resolve_ccro_modals(hwnd, monitor, points, "ccro_case_start_v55")

    # Feed setup path, same as the validated UF/RO profile workflow.
    try:
        click_until_visual_change(
            points,
            "feed_setup_tab",
            hwnd,
            monitor,
            pause=settings.pause,
            retries=3,
            minimum_change=0.003,
        )
    except WaveAutomationError as exc:
        logging.warning("Feed Setup tab may already be active; continuing: %s", exc)
        _click_ccro(hwnd, monitor, points, "feed_setup_tab", pause=settings.pause)
        screenshot("ccro_feed_setup_after_already_active_fallback", monitor, hwnd)
    try:
        dialog = click_expect_new_dialog(points, "open_water_library", hwnd, monitor, pause=settings.pause)
        select_library_profile(dialog, case.water_profile, settings.pause)
        copy_library_to_feed(dialog, settings.long_wait, hwnd, monitor)
    except LibraryTemperatureTransitionError:
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)
        dialog = click_expect_new_dialog(points, "open_water_library", hwnd, monitor, pause=settings.pause)
        select_library_profile(dialog, case.water_profile, settings.pause)
        copy_library_to_feed(dialog, settings.long_wait, hwnd, monitor)
    set_feed_temperature_envelope(
        hwnd,
        monitor,
        points,
        case.feed_temperature_min_c,
        case.feed_temperature_design_c,
        case.feed_temperature_max_c,
        settings.pause,
        context=f"ccro_{case.case_id}_feed_temperature",
    )

    # Home canvas and process insertion.
    enter_home_with_recovery(hwnd, monitor, points, settings)
    _replace_ccro_point(hwnd, monitor, points, "home_feed_flow", case.feed_flow_m3h, settings.pause, verify=False)
    add_ccro_if_missing(hwnd, monitor, points, settings)

    # CCRO page.  Reconcile Pass count before touching recovery/element fields.
    # Default remains 1-pass, but V55 can run a conservative 2-pass probe.
    _click_ccro(hwnd, monitor, points, "ccro_tab", pause=max(1.0, settings.pause))
    screenshot("ccro_tab_opened_v55", monitor, hwnd)
    _reconcile_ccro_pass_count(hwnd, monitor, points, case.pass_count, settings)

    pass_results: list[dict[str, Any]] = []
    _click_ccro(hwnd, monitor, points, "pass_1_tab", pause=settings.pause)
    pass_results.append(
        _configure_ccro_selected_pass_fields(
            hwnd,
            monitor,
            points,
            case,
            settings,
            pass_index=1,
            recovery_pct=case.recovery_pct,
            pv_per_stage=case.pv_per_stage,
            elements_per_pv=case.elements_per_pv,
            flow_factor=case.flow_factor,
            pass_back_pressure_bar=case.pass_back_pressure_bar,
            stage_back_pressure_bar=0.0,
            stage_flow_factor=case.flow_factor,
            pf_feed_ratio_pct=case.pf_feed_ratio_pct,
            pf_recovery_pct=case.pf_recovery_pct,
        )
    )

    if case.pass_count >= 2:
        logging.info(
            "CCRO V55 2-Pass 보수 프로브 설정: pass1_recovery=%s pass2_recovery=%s pass2_pv=%s pass2_elements=%s",
            case.recovery_pct,
            case.pass2_recovery_pct,
            case.pass2_pv_per_stage,
            case.pass2_elements_per_pv,
        )
        _click_ccro(hwnd, monitor, points, "pass_2_tab", pause=max(1.0, settings.pause))
        pass_results.append(
            _configure_ccro_selected_pass_fields(
                hwnd,
                monitor,
                points,
                case,
                settings,
                pass_index=2,
                recovery_pct=case.pass2_recovery_pct,
                pv_per_stage=case.pass2_pv_per_stage,
                elements_per_pv=case.pass2_elements_per_pv,
                flow_factor=case.pass2_flow_factor,
                pass_back_pressure_bar=case.pass2_back_pressure_bar,
                stage_back_pressure_bar=case.pass2_stage_back_pressure_bar,
                stage_flow_factor=case.pass2_stage_flow_factor,
                pf_feed_ratio_pct=case.pf_feed_ratio_pct,
                pf_recovery_pct=case.pf_recovery_pct,
            )
        )
        _click_ccro(hwnd, monitor, points, "pass_1_tab", pause=settings.pause)

    screenshot("ccro_configured_v55", monitor, hwnd)
    _write_ccro_artifact(
        "ccro_video_case_config_summary.json",
        {"schema_version": 1, "case": asdict(case), "passes": pass_results},
    )

    # Summary Report: wait through spinner but do not let it hang indefinitely.
    _resolve_ccro_modals(hwnd, monitor, points, "before_ccro_summary_report_tab_v55")
    _click_ccro(hwnd, monitor, points, "summary_report_tab", pause=max(1.5, settings.pause), context="ccro_summary_report_tab")
    _wait_for_ccro_report_spinner(hwnd, monitor, "after_ccro_summary_report_tab_v55", timeout_s=max(120.0, settings.long_wait * 25.0))
    wait(settings.long_wait)
    screenshot("ccro_summary_report_v55", monitor, hwnd)
    logging.info("=== CCRO 사례 입력 완료: %s ===", case.case_id)
    record_event("ccro_case_configured_v55", case=asdict(case), passes=pass_results)



def _pdf_has_value_near(label_pattern: str, value: float | int | str, text: str, *, window: int = 180) -> bool:
    value_pattern = _number_pattern(_fmt_value(value))
    return bool(re.search(rf"{label_pattern}[\s\S]{{0,{window}}}?{value_pattern}", text, re.I))


def validate_exported_ccro_pdf(path: Path, case: CCROVideoCase) -> dict[str, Any]:
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\r", "")

    # V109: WAVE/PyMuPDF can extract FilmTec™ as FilmTecΡ or split
    # "FilmTec™ SOAR 5000i" across lines/tabs. Validate element type using
    # both the original regex and a loose alphanumeric canonical form so valid
    # SOAR 4000i/5000i PDFs are not falsely rejected.
    def _canon_element_text(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", " ", value or "").strip().lower()

    element_tokens = [
        case.element_type,
        case.element_type.replace("FilmTec™ ", "").replace("FilmTec ", ""),
    ]
    element_tokens.extend(
        token.replace("™", "").replace("Ρ", "").replace("FilmTec", "").strip()
        for token in list(element_tokens)
    )
    normalized_element_text = _canon_element_text(normalized)
    element_type_ok = any(
        re.search(re.escape(token), normalized, re.I)
        or (_canon_element_text(token) and _canon_element_text(token) in normalized_element_text)
        for token in element_tokens
    )
    pass2_present = bool(re.search(r"\bPass\s*2\b", normalized, re.I))
    pass_count_exact = (not pass2_present) if case.pass_count == 1 else pass2_present
    checks = {
        "ccro_report": bool(re.search(r"Closed\s+Circuit\s+Reverse\s+Osmosis|\bCCRO\b", normalized, re.I)),
        "element_type": element_type_ok,
        "water_profile": bool(re.search(re.escape(case.water_profile), normalized, re.I)),
        "feed_flow_present": _pdf_has_value_near(r"Feed\s+Flow|Feed\s+Rate|Feed", case.feed_flow_m3h, normalized),
        "target_recovery_present": bool(re.search(r"Recovery[\s\S]{0,140}" + _number_pattern(_fmt_value(case.recovery_pct)), normalized, re.I)),
        "pass_count_exact": pass_count_exact,
        "pass2_present": pass2_present,
    }
    if case.pass_count >= 2:
        checks["pass2_recovery_present"] = bool(
            re.search(r"(Pass\s*2|2\s+Pass)[\s\S]{0,900}" + _number_pattern(_fmt_value(case.pass2_recovery_pct)), normalized, re.I)
            or re.search(r"Recovery[\s\S]{0,140}" + _number_pattern(_fmt_value(case.pass2_recovery_pct)), normalized, re.I)
        )
    else:
        checks["pass2_absent"] = not pass2_present

    hard_fields = ("ccro_report", "element_type", "pass_count_exact")
    hard_errors = [name for name in hard_fields if not checks[name]]
    warnings = [name for name, ok in checks.items() if not ok and name not in hard_errors]
    result = {
        "pdf": str(path),
        "provider": provider,
        "case": asdict(case),
        "checks": checks,
        "hard_errors": hard_errors,
        "warnings": warnings,
        "classification": "validated" if not hard_errors else "validation_failed",
    }
    if STATE.RUN_DIR is not None:
        safe = _safe_name(case.case_id)
        (STATE.RUN_DIR / f"exported_pdf_text_{safe}.txt").write_text(text, encoding="utf-8")
        (STATE.RUN_DIR / f"ccro_pdf_validation_{safe}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    record_event("ccro_pdf_validation_v55", result=result)
    if hard_errors:
        raise WaveAutomationError(f"{case.case_id} CCRO PDF 검증 실패: {', '.join(hard_errors)}")
    if warnings:
        logging.warning("CCRO PDF 약한 검증 경고: case=%s warnings=%s", case.case_id, warnings)
    logging.info("CCRO PDF 검증 성공: %s", case.case_id)
    return result



def run_ccro_video_case(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
    element_type: str | None = None,
    pdf_name: str | None = None,
    water_profile: str | None = None,
    feed_flow_m3h: float | None = None,
    recovery_pct: float | None = None,
    pass_count: int | None = None,
    pass2_recovery_pct: float | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pv_per_stage: int | float | str | None = None,
    elements_per_pv: int | float | str | None = None,
    flow_factor: float | str | None = None,
    pass_back_pressure_bar: float | str | None = None,
    stage_back_pressure_bar: float | str | None = None,
    stage_flow_factor: float | str | None = None,
    pass2_pv_per_stage: int | float | str | None = None,
    pass2_elements_per_pv: int | float | str | None = None,
) -> list[Path]:
    case = CCROVideoCase()
    if element_type:
        case.element_type = element_type
    if pdf_name:
        case.pdf_name = pdf_name
    if water_profile:
        case.water_profile = water_profile
    if feed_flow_m3h is not None:
        case.feed_flow_m3h = float(feed_flow_m3h)
    if pass_count is not None:
        case.pass_count = int(pass_count)
        if case.pass_count not in (1, 2):
            raise WaveAutomationError(f"--ccro-pass-count는 1 또는 2만 지원합니다: {case.pass_count}")
    if recovery_pct is not None:
        case.recovery_pct = float(recovery_pct)
    if pass2_recovery_pct is not None:
        case.pass2_recovery_pct = float(pass2_recovery_pct)
    if pf_feed_ratio_pct is not None:
        case.pf_feed_ratio_pct = float(pf_feed_ratio_pct)
    if pf_recovery_pct is not None:
        case.pf_recovery_pct = float(pf_recovery_pct)


    # V101 PLAN FIELD PASSTHROUGH
    # Production plans can now override the conservative CCRO defaults
    # (10 PV x 5 elements).  This is critical for pilot-scale meeting tests,
    # where the intended geometry is 1 PV x 3 elements.
    if pv_per_stage is not None:
        case.pv_per_stage = max(1, int(float(pv_per_stage)))
    if elements_per_pv is not None:
        case.elements_per_pv = max(1, int(float(elements_per_pv)))
    if flow_factor is not None:
        case.flow_factor = float(flow_factor)
        case.pass2_flow_factor = float(flow_factor)
        case.pass2_stage_flow_factor = float(flow_factor)
    if pass_back_pressure_bar is not None:
        case.pass_back_pressure_bar = float(pass_back_pressure_bar)
        case.pass2_back_pressure_bar = float(pass_back_pressure_bar)
    if stage_back_pressure_bar is not None:
        case.pass_back_pressure_bar = float(stage_back_pressure_bar)
        case.pass2_stage_back_pressure_bar = float(stage_back_pressure_bar)
    if stage_flow_factor is not None:
        case.flow_factor = float(stage_flow_factor)
        case.pass2_stage_flow_factor = float(stage_flow_factor)
    if pass2_pv_per_stage is not None:
        case.pass2_pv_per_stage = max(1, int(float(pass2_pv_per_stage)))
    if pass2_elements_per_pv is not None:
        case.pass2_elements_per_pv = max(1, int(float(pass2_elements_per_pv)))

    # Preserve an informative name if the caller changes recovery/topology but
    # does not supply a custom PDF name.
    if not pdf_name and (recovery_pct is not None or feed_flow_m3h is not None or pass_count is not None or pass2_recovery_pct is not None):
        if case.pass_count >= 2:
            case.pdf_name = (
                f"V55_CCRO_2PASS_SOAR5000i_F{int(case.feed_flow_m3h)}_"
                f"R{int(case.recovery_pct)}_P2R{int(case.pass2_recovery_pct)}.pdf"
            )
            case.case_id = "V55_CCRO_2PASS_SAFE_001"
        else:
            case.pdf_name = f"V55_CCRO_VIDEO_SAFE_001_SOAR5000i_F{int(case.feed_flow_m3h)}_R{int(case.recovery_pct)}.pdf"

    settings = case.to_settings(pause=pause, long_wait=long_wait, validate_pdf=False)
    configure_ccro_video_case(wave_window.hwnd, monitor, points, case, settings)
    target = export_pdf(wave_window, monitor, points, case.pdf_name, settings)
    dismiss_export_success_dialog(wave_window, monitor)
    validation: dict[str, Any] | None = None
    if validate_pdf:
        validation = validate_exported_ccro_pdf(target, case)
    _write_ccro_artifact(
        "ccro_video_case_summary.json",
        {
            "schema_version": 1,
            "automation_version": "V55",
            "status": "success",
            "case": asdict(case),
            "pdf": str(target),
            "validation": validation,
        },
    )
    return [target]
