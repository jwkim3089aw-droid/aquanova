#!/usr/bin/env python3
"""Refactored WAVE automation module: interaction."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import _capture_wave_image, _image_change_ratio, save_point_probe, screenshot
from wave_runtime import record_event
from wave_windows import _foreground_window_info, _get_process_id, _get_window_rect, bring_window_to_front, list_visible_windows, native_click_at

def wait(seconds: float) -> None:
    time.sleep(seconds)


def click(points: dict[str, tuple[int, int]], name: str, pause: float = 0.5) -> None:
    x, y = points[name]
    if STATE.ACTIVE_WAVE_HWND:
        fg_now = _foreground_window_info()
        parent_pid = _get_process_id(STATE.ACTIVE_WAVE_HWND)
        if (
            fg_now is not None
            and fg_now.hwnd != STATE.ACTIVE_WAVE_HWND
            and fg_now.process_id == parent_pid
        ):
            raise WaveAutomationError(
                "WAVE 모달 창이 열린 상태에서 본체 좌표 클릭을 시도했습니다: "
                f"title={fg_now.title!r}, next={name!r}"
            )
        bring_window_to_front(STATE.ACTIVE_WAVE_HWND)
    fg_before = _foreground_window_info()
    logging.info("native click %-20s (%s, %s)", name, x, y)
    record_event("click", name=name, point=(x, y), foreground_before=fg_before)
    save_point_probe(name, STATE.ACTIVE_WAVE_HWND or 0, (x, y))
    native_click_at(x, y)
    wait(pause)
    record_event("click_result", name=name, foreground_after=_foreground_window_info())


def click_until_visual_change(
    points: dict[str, tuple[int, int]],
    name: str,
    hwnd: int,
    monitor: Rect,
    pause: float = 0.7,
    retries: int = 3,
    minimum_change: float = 0.006,
) -> None:
    for attempt in range(1, retries + 1):
        bring_window_to_front(hwnd)
        before = _capture_wave_image(hwnd)
        click(points, name, pause=pause)
        after = _capture_wave_image(hwnd)
        ratio = _image_change_ratio(before, after)
        logging.info("화면 변화 확인 %s attempt=%s ratio=%.5f", name, attempt, ratio)
        record_event("visual_change", name=name, attempt=attempt, ratio=ratio)
        screenshot(f"verify_{name}_attempt{attempt}", monitor, hwnd)
        if ratio >= minimum_change:
            return
        # Some WAVE controls consume the first click only to activate the window.
        title_rect = _get_window_rect(hwnd)
        native_click_at(
            title_rect.left + min(500, title_rect.width // 2), title_rect.top + 16
        )
        time.sleep(0.25)
    raise WaveAutomationError(
        f"{name} 클릭 후 화면이 바뀌지 않았습니다. 첫 실패 단계에서 중단했습니다."
    )


def _visible_window_handles() -> set[int]:
    return {item.hwnd for item in list_visible_windows()}


def click_expect_new_dialog(
    points: dict[str, tuple[int, int]],
    name: str,
    hwnd: int,
    monitor: Rect,
    pause: float = 0.7,
    retries: int = 5,
) -> WindowInfo:
    """Click a WAVE command and require a real new top-level dialog.

    WAVE's WPF ribbon can shift a command by a few pixels while the overall
    window rectangle remains unchanged.  For known wide commands, try several
    points that are all safely inside the command instead of repeating one bad
    coordinate.
    """
    base_x, base_y = points[name]
    offsets = CONTROL_FALLBACK_OFFSETS.get(name, [(0, 0)])
    candidate_points = [(base_x + dx, base_y + dy) for dx, dy in offsets]
    # Respect an explicitly larger retry count while never discarding the
    # command-specific candidates.
    attempts = max(retries, len(candidate_points))
    tried: list[tuple[int, int]] = []

    for attempt in range(1, attempts + 1):
        point = candidate_points[min(attempt - 1, len(candidate_points) - 1)]
        tried.append(point)
        before = _visible_window_handles()
        bring_window_to_front(hwnd)
        logging.info(
            "dialog command click %s attempt=%s point=%s", name, attempt, point
        )
        record_event(
            "dialog_click_candidate",
            name=name,
            attempt=attempt,
            point=point,
            offsets=offsets,
        )
        save_point_probe(f"{name}_attempt{attempt}", hwnd, point)
        native_click_at(*point)
        wait(pause)

        deadline = time.time() + 3.5
        while time.time() < deadline:
            visible = list_visible_windows()
            candidates = [
                item
                for item in visible
                if item.hwnd not in before and item.hwnd != hwnd
            ]
            if not candidates:
                candidates = [
                    item
                    for item in visible
                    if item.hwnd != hwnd
                    and (
                        item.process_id == _get_process_id(hwnd)
                        or item.class_name == "#32770"
                    )
                    and (
                        "library" in item.title.lower()
                        or "water" in item.title.lower()
                        or "profile" in item.title.lower()
                    )
                ]
            if candidates:
                candidates.sort(
                    key=lambda item: (
                        item.process_id == _get_process_id(hwnd),
                        "library" in item.title.lower(),
                        item.rect.width * item.rect.height,
                    ),
                    reverse=True,
                )
                dialog = candidates[0]
                logging.info("대화상자 확인: %s", dialog)
                record_event(
                    "dialog_detected",
                    source=name,
                    dialog=dialog,
                    attempt=attempt,
                    click_point=point,
                )
                bring_window_to_front(dialog.hwnd)
                screenshot(f"dialog_{name}_attempt{attempt}", monitor, hwnd)
                return dialog
            time.sleep(0.2)

        screenshot(f"dialog_missing_{name}_attempt{attempt}", monitor, hwnd)
        # Refocus through the title bar without restoring/unmaximizing WAVE.
        title_rect = _get_window_rect(hwnd)
        native_click_at(
            title_rect.left + min(500, title_rect.width // 2),
            title_rect.top + 16,
        )
        time.sleep(0.25)

    raise WaveAutomationError(
        f"{name} 클릭 후 Water Library 대화상자를 찾지 못했습니다. "
        f"시도 좌표={tried}"
    )


def replace_value(
    points: dict[str, tuple[int, int]], name: str, value: str, pause: float = 0.5
) -> None:
    click(points, name, pause=0.15)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(str(value), interval=0.04)
    pyautogui.press("tab")
    wait(pause)
