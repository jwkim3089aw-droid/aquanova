#!/usr/bin/env python3
"""Refactored WAVE automation module: dialogs."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import _enum_child_windows, dump_windows, screenshot
from wave_interaction import click, wait
from wave_runtime import record_event
from wave_uia import uia_configure_flow_calculator
from wave_windows import _foreground_window_info, _get_process_id, bring_window_to_front, focus_wave, list_visible_windows, native_click_at

def _find_flow_calculator_dialog(
    wave_hwnd: int, timeout: float = 0.0
) -> Optional[WindowInfo]:
    """Find the WPF Reverse Osmosis Flow Calculator owned by WAVE."""
    deadline = time.time() + max(0.0, timeout)
    wave_pid = _get_process_id(wave_hwnd)
    while True:
        candidates: list[WindowInfo] = []
        foreground = _foreground_window_info()
        if (
            foreground is not None
            and foreground.hwnd != wave_hwnd
            and foreground.process_id == wave_pid
            and "flow calculator" in foreground.title.lower()
        ):
            return foreground
        for item in list_visible_windows():
            if item.hwnd == wave_hwnd or item.process_id != wave_pid:
                continue
            title = item.title.lower()
            if "flow calculator" in title or "reverse osmosis flow" in title:
                candidates.append(item)
        if candidates:
            candidates.sort(
                key=lambda item: item.rect.width * item.rect.height, reverse=True
            )
            return candidates[0]
        if time.time() >= deadline:
            return None
        time.sleep(0.15)


def _wait_window_closed(hwnd: int, timeout: float) -> bool:
    user32 = ctypes.windll.user32
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
            return True
        time.sleep(0.15)
    return False


def configure_flow_calculator_dialog(
    dialog: WindowInfo,
    recovery_pct: str,
    monitor: Rect,
    wave_hwnd: int,
    settings: Settings,
    context: str,
    *,
    target_automation_id: str | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pass_index: int = 1,
) -> None:
    """Set pass recovery and close the modal calculator safely.

    V13 uses UI Automation as the primary path.  The calculator may be placed
    in a DPI-virtualized coordinate space on monitor 2, so GetWindowRect-based
    mouse percentages are not reliable.  A keyboard fallback is kept only for
    environments where UI Automation is unavailable.
    """
    logging.info(
        "Flow Calculator 감지: context=%s hwnd=%s title=%r rect=%s",
        context,
        dialog.hwnd,
        dialog.title,
        dialog.rect,
    )
    record_event("flow_calculator_detected", context=context, dialog=dialog)
    bring_window_to_front(dialog.hwnd)
    screenshot(f"flow_calculator_{context}_before", monitor, wave_hwnd)

    result = uia_configure_flow_calculator(
        dialog.hwnd,
        recovery_pct,
        timeout=max(20.0, settings.long_wait * 5.0),
        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=pass_index,
    )
    logging.info(
        "Flow Calculator UIA 결과: ok=%s actual=%r target_aid=%r chosen=%r score=%r",
        result.get("ok"),
        result.get("actual"),
        result.get("target_automation_id") or target_automation_id,
        result.get("chosen_name") or result.get("chosen_automation_id"),
        result.get("chosen_score"),
    )
    screenshot(f"flow_calculator_{context}_uia_result", monitor, wave_hwnd)

    if result.get("ok"):
        if not _wait_window_closed(dialog.hwnd, max(12.0, settings.long_wait * 3.0)):
            raise WaveAutomationError(
                "Flow Calculator UIA에서 OK를 실행했지만 창이 닫히지 않았습니다. "
                f"UIA 결과={result}"
            )
        wait(max(1.0, settings.pause))
        screenshot(f"flow_calculator_{context}_closed", monitor, wave_hwnd)
        return

    # Do not guess with coordinates or blind Tab sequences.  The dialog is DPI-
    # virtualized on monitor 2; a wrong fallback could overwrite another field.
    # Stop safely and keep the UIA control inventory in the feedback ZIP.
    raise WaveAutomationError(
        "Reverse Osmosis Flow Calculator UI Automation failed. "
        "No coordinate fallback was attempted to avoid changing the wrong field. "
        f"UIA result={result}"
    )


def _dialog_child_texts(hwnd: int) -> list[str]:
    """Collect standard Win32 message text from a dialog without OCR."""
    texts: list[str] = []
    try:
        for child in _enum_child_windows(hwnd):
            text = str(child.get("title") or "").strip()
            if text and text not in texts:
                texts.append(text)
    except Exception as exc:
        record_event("dialog_text_read_failed", hwnd=hwnd, error=repr(exc))
    return texts


def _dialog_text_blob(dialog: WindowInfo) -> str:
    parts = [dialog.title, *_dialog_child_texts(dialog.hwnd)]
    return "\n".join(part for part in parts if part).strip()


def _blocking_wave_dialogs(hwnd: int) -> list[tuple[WindowInfo, str]]:
    """Return visible WAVE modal dialogs, including small generic message boxes.

    WAVE often uses the generic title ``Feed Water`` and puts the real reason only
    in a child Static control.  It also creates 383x143 message boxes, which were
    previously filtered out by the normal top-level window enumerator.
    """
    pid = _get_process_id(hwnd)
    excluded_tokens = (
        "water profile library",
        "flow calculator",
        "save as",
        "다른 이름으로 저장",
        "export",
    )
    candidates: dict[int, WindowInfo] = {}
    for item in list_visible_windows(include_small=True):
        if item.hwnd == hwnd or item.process_id != pid:
            continue
        title = item.title.lower()
        if any(token in title for token in excluded_tokens):
            continue
        # Standard message boxes and small same-process WPF dialogs are treated
        # as modal candidates.  The text classifier below decides what to do.
        if item.class_name == "#32770" or (
            item.rect.width <= 760 and item.rect.height <= 420
        ):
            candidates[item.hwnd] = item

    # A modal can be the foreground window even when enumeration metadata is
    # transient.  Add it directly so it cannot be missed.
    fg = _foreground_window_info()
    if fg and fg.hwnd != hwnd and fg.process_id == pid:
        title = fg.title.lower()
        if not any(token in title for token in excluded_tokens):
            candidates[fg.hwnd] = fg

    result: list[tuple[WindowInfo, str]] = []
    foreground_hwnd = int(ctypes.windll.user32.GetForegroundWindow())
    for item in candidates.values():
        text = _dialog_text_blob(item)
        result.append((item, text))
    result.sort(
        key=lambda pair: (
            pair[0].hwnd == foreground_hwnd,
            pair[0].class_name == "#32770",
            -(pair[0].rect.width * pair[0].rect.height),
        ),
        reverse=True,
    )
    return result



def _is_report_loading_spinner(dialog: WindowInfo, text: str) -> bool:
    blob = f"{dialog.title}\n{text}".lower()
    return (
        "reportloadingspinner" in blob
        or "calculating report" in blob
        or "calculating report..." in blob
    )


def wait_for_report_loading_spinner(
    hwnd: int,
    monitor: Rect,
    context: str,
    *,
    timeout_s: float = 90.0,
) -> list[str]:
    """Wait through WAVE's non-interactive Summary Report calculation overlay.

    UF and CCRO can expose the calculation overlay as a small same-process WPF
    top-level window titled ``ReportLoadingSpinner``.  It must not be closed; it
    has no OK button and normally disappears when report calculation finishes.
    V59 makes this generic so production preflight, case reset and PDF export do
    not mistake the overlay for an unknown modal.
    """
    start = time.time()
    seen = False
    last_blob = ""
    while True:
        spinners: list[str] = []
        for dialog, text in _blocking_wave_dialogs(hwnd):
            if _is_report_loading_spinner(dialog, text):
                spinners.append(f"{dialog.title}: {text}".strip())
        if not spinners:
            if seen:
                time.sleep(0.8)
                elapsed = round(time.time() - start, 2)
                logging.info("Report 계산 대기 완료: context=%s elapsed=%ss", context, elapsed)
                record_event("report_loading_spinner_waited_v59", context=context, elapsed_s=elapsed)
                return ["report_loading_spinner_waited"]
            return []
        if not seen:
            seen = True
            last_blob = " | ".join(spinners)
            logging.info("Report 계산 대기 시작: context=%s dialogs=%s", context, last_blob)
            record_event("report_loading_spinner_seen_v59", context=context, dialogs=spinners)
            screenshot(f"report_loading_spinner_{re.sub(r'[^A-Za-z0-9_.-]+', '_', context)[:80]}_v59", monitor, hwnd)
        if time.time() - start > timeout_s:
            screenshot(f"report_loading_spinner_timeout_{re.sub(r'[^A-Za-z0-9_.-]+', '_', context)[:80]}_v59", monitor, hwnd)
            raise WaveAutomationError(
                f"Report 계산 대기 시간 초과: context={context} timeout={timeout_s}s last={last_blob!r}"
            )
        time.sleep(0.6)

def _close_modal_dialog(dialog: WindowInfo) -> None:
    bring_window_to_front(dialog.hwnd, restore_if_minimized=False)
    pyautogui.press("enter")
    time.sleep(0.45)
    if ctypes.windll.user32.IsWindow(
        dialog.hwnd
    ) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
        ok_point = (
            dialog.rect.left + round(dialog.rect.width * 0.84),
            dialog.rect.top + round(dialog.rect.height * 0.82),
        )
        native_click_at(*ok_point)
        time.sleep(0.55)
    if ctypes.windll.user32.IsWindow(
        dialog.hwnd
    ) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
        raise WaveAutomationError(f"WAVE 모달 창을 닫지 못했습니다: {dialog.title!r}")


def _apply_adjust_all_ions(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    context: str,
) -> None:
    """Apply WAVE's own charge-balance correction and retain an audit trail."""
    focus_wave(hwnd)
    logging.warning("전하수지 자동 복구: Adjust All Ions 실행 (%s)", context)
    record_event(
        "automatic_repair",
        repair="adjust_all_ions",
        context=context,
        point=points["adjust_all_ions"],
    )
    click(points, "adjust_all_ions", pause=1.0)
    time.sleep(0.8)
    screenshot(f"repair_adjust_all_ions_{context}", monitor, hwnd)

    # Some WAVE builds acknowledge the correction with a short confirmation.
    for dialog, text in _blocking_wave_dialogs(hwnd):
        blob = text.lower()
        if any(token in blob for token in ("success", "completed", "adjusted", "확인")):
            _close_modal_dialog(dialog)


def resolve_wave_blocking_dialogs(
    hwnd: int,
    monitor: Rect,
    context: str,
    points: dict[str, tuple[int, int]],
    *,
    max_dialogs: int = 6,
) -> list[str]:
    """Resolve known WAVE dialogs by message content; stop on unknown dialogs.

    Rules are deliberately conservative.  Known recoverable conditions are fixed
    and the interrupted UI action is retried.  Unknown messages are bundled and
    stop the run instead of blindly pressing OK and corrupting a DOE case.
    """
    actions: list[str] = []
    for index in range(max_dialogs):
        dialogs = _blocking_wave_dialogs(hwnd)
        if not dialogs:
            break
        dialog, text = dialogs[0]
        blob = text.lower()
        logging.warning(
            "WAVE 모달 감지: context=%s title=%r text=%r rect=%s",
            context,
            dialog.title,
            text,
            dialog.rect,
        )
        record_event(
            "blocking_dialog_detected",
            context=context,
            dialog=dialog,
            text=text,
        )
        screenshot(f"blocking_dialog_{context}_{index + 1}", monitor, hwnd)

        charge_balance = any(
            token in blob
            for token in (
                "charge-balance",
                "charge balance",
                "charge-balance the feedwater",
                "add solutes",
                "adjust solutes",
                "전하수지",
                "전하 균형",
            )
        )
        temperature = any(
            token in blob
            for token in (
                "minimum temperature",
                "maximum temperature",
                "design temperature",
                "temperature warning",
            )
        )
        convergence = any(
            token in blob
            for token in (
                "failed to converge",
                "convergence error",
                "please review your design",
                "수렴",
            )
        )
        nonfatal_ack = any(
            token in blob
            for token in (
                "warning",
                "경고",
                "please note",
                "information",
                "알림",
            )
        )

        process_topology_conflict = any(
            token in blob
            for token in (
                "cannot be added to the system design",
                "ccro is already part of the system",
                "ro cannot be added",
                "uf cannot be added",
                "system design if",
            )
        )

        if _is_report_loading_spinner(dialog, text):
            actions.extend(wait_for_report_loading_spinner(hwnd, monitor, context))
            continue

        if convergence:
            _close_modal_dialog(dialog)
            raise WaveConvergenceError(
                f"WAVE convergence failure: context={context}, title={dialog.title!r}, text={text!r}"
            )
        if process_topology_conflict:
            _close_modal_dialog(dialog)
            actions.append("process_topology_conflict_closed")
            continue
        if charge_balance:
            _close_modal_dialog(dialog)
            _apply_adjust_all_ions(hwnd, monitor, points, context)
            actions.append("adjust_all_ions")
            continue
        if temperature:
            _close_modal_dialog(dialog)
            actions.append("temperature_warning_closed")
            continue
        if nonfatal_ack:
            _close_modal_dialog(dialog)
            actions.append("warning_acknowledged")
            continue

        # Never guess on an unfamiliar constraint/error.  Preserve the text in
        # the exception and feedback ZIP so a new explicit rule can be added.
        raise WaveAutomationError(
            "알 수 없는 WAVE 모달이 나타났습니다. 자동으로 무시하지 않습니다. "
            f"context={context}, title={dialog.title!r}, text={text!r}"
        )
    return actions


def find_save_dialog(
    wave_window: WindowInfo, timeout: float = 10.0
) -> Optional[WindowInfo]:
    deadline = time.time() + timeout
    last_candidates: list[WindowInfo] = []
    while time.time() < deadline:
        candidates: list[WindowInfo] = []
        for item in list_visible_windows():
            if item.hwnd == wave_window.hwnd:
                continue
            title = item.title.lower()
            same_process = item.process_id == wave_window.process_id
            looks_like_dialog = item.class_name == "#32770"
            looks_like_save = any(
                token in title for token in ("save", "저장", "export", "pdf")
            )
            if (same_process and looks_like_dialog) or looks_like_save:
                candidates.append(item)
        if candidates:
            candidates.sort(
                key=lambda item: (
                    item.process_id == wave_window.process_id,
                    item.class_name == "#32770",
                ),
                reverse=True,
            )
            dialog = candidates[0]
            logging.info(
                "저장 대화상자 감지: hwnd=%s title=%r class=%r rect=%s",
                dialog.hwnd,
                dialog.title,
                dialog.class_name,
                dialog.rect,
            )
            bring_window_to_front(dialog.hwnd)
            return dialog
        last_candidates = candidates
        time.sleep(0.25)
    dump_windows("save_dialog_missing")
    logging.warning(
        "저장 대화상자를 감지하지 못했습니다. 피드백 번들에 창 목록을 저장했습니다."
    )
    return None


def _wait_for_pdf_save_dialog(
    wave_window: WindowInfo,
    handles_before: set[int],
    timeout: float,
) -> Optional[WindowInfo]:
    """Wait for the Save As window created by Export to PDF."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        windows = list_visible_windows()
        new_handles = {item.hwnd for item in windows if item.hwnd not in handles_before}
        candidates: list[WindowInfo] = []
        for item in windows:
            if item.hwnd == wave_window.hwnd:
                continue
            title = item.title.lower()
            looks_like_save = any(
                token in title
                for token in (
                    "save",
                    "save as",
                    "저장",
                    "다른 이름으로 저장",
                    "export",
                    "pdf",
                    "파일 이름",
                )
            )
            looks_like_common_dialog = item.class_name == "#32770"
            is_new = item.hwnd in new_handles
            if looks_like_save or (is_new and looks_like_common_dialog):
                candidates.append(item)

        if candidates:
            candidates.sort(
                key=lambda item: (
                    item.hwnd in new_handles,
                    any(
                        token in item.title.lower()
                        for token in ("save", "저장", "pdf", "export")
                    ),
                    item.class_name == "#32770",
                    item.rect.width * item.rect.height,
                ),
                reverse=True,
            )
            return candidates[0]
        time.sleep(0.2)
    return None
