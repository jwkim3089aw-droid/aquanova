#!/usr/bin/env python3
"""Refactored WAVE automation module: feed."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import screenshot
from wave_dialogs import _blocking_wave_dialogs, _close_modal_dialog, resolve_wave_blocking_dialogs
from wave_interaction import replace_value, wait
from wave_runtime import record_event
from wave_uia import uia_probe_point
from wave_windows import bring_window_to_front, native_click_at

def _probe_text(result: dict[str, Any]) -> str:
    """Return the best non-empty text exposed by a WPF control probe.

    Some WAVE ComboBoxes expose neither SelectionPattern nor ValuePattern after
    an exact native ListItem click.  V26 returned the empty ``value`` field
    immediately and therefore treated a successful exact click as failure, then
    ran the prefix keyboard fallback and overwrote the requested membrane with an
    IG/obsolete sibling.  V27 skips empty fields and falls through to the exact
    ListItem name.
    """
    selected = result.get("selected")
    if isinstance(selected, str) and selected.strip():
        return selected.strip()
    if isinstance(selected, list):
        for item in selected:
            text = str(item or "").strip()
            if text:
                return text
    value = str(result.get("value") or "").strip()
    if value:
        return value
    chosen = str(result.get("chosen") or "").strip()
    if chosen:
        return chosen
    name = result.get("name")
    return str(name or "").strip()


def _parse_first_number(value: str) -> Optional[float]:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def verify_numeric_point(
    name: str,
    point: tuple[int, int],
    expected: str,
    *,
    tolerance: float = 0.06,
    required_when_readable: bool = True,
) -> Optional[float]:
    result = uia_probe_point(point)
    raw = _probe_text(result)
    actual = _parse_first_number(raw)
    expected_value = float(str(expected).replace(",", "."))
    payload = {
        "name": name,
        "expected": expected_value,
        "actual": actual,
        "raw": raw,
        "uia": result,
    }
    record_event("numeric_verification", **payload)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / f"verify_{name}.json").write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if actual is None:
        logging.warning(
            "UIA 숫자 검증 불가: %s expected=%s result=%s", name, expected, result
        )
        return None
    difference = abs(actual - expected_value)
    if difference > tolerance:
        if required_when_readable:
            raise WaveAutomationError(
                f"{name} 값 검증 실패: expected={expected_value:g}, actual={actual:g}"
            )
        logging.warning(
            "입력값 현재 불일치(복구 전): %s expected=%s actual=%s",
            name,
            expected_value,
            actual,
        )
        return actual
    logging.info("입력값 검증 성공: %s=%s", name, actual)
    return actual


def _read_numeric_point(
    name: str,
    point: tuple[int, int],
) -> Optional[float]:
    """Read a numeric WPF control without treating a mismatch as an error."""
    result = uia_probe_point(point)
    raw = _probe_text(result)
    actual = _parse_first_number(raw)
    record_event(
        "numeric_read",
        name=name,
        actual=actual,
        raw=raw,
        uia=result,
    )
    return actual


def set_feed_temperature_envelope(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    minimum_c: float,
    design_c: float,
    maximum_c: float,
    pause: float,
    *,
    context: str = "feed_temperature",
) -> None:
    """Set an arbitrary Feed Water temperature envelope safely.

    WAVE validates ``Minimum <= Design <= Maximum`` after every edit.  V22
    therefore widens the current interval first, moves Design inside that safe
    interval, and only then collapses the lower/upper bounds to the requested
    values.  This works for equal triplets and for inventory-video cases such as
    10/25/35 C used with Minimum/Design/Maximum RO temperature modes.
    """
    minimum = float(minimum_c)
    design = float(design_c)
    maximum = float(maximum_c)
    if not minimum <= design <= maximum:
        raise WaveAutomationError(
            "Feed 온도 범위 오류: Minimum <= Design <= Maximum 이어야 합니다. "
            f"requested={minimum:g}/{design:g}/{maximum:g}"
        )
    names = {
        "min": "feed_temp_min",
        "design": "feed_temp_design",
        "max": "feed_temp_max",
    }

    def snapshot(label: str) -> dict[str, Optional[float]]:
        values = {
            key: _read_numeric_point(f"{context}_{label}_{key}", points[point_name])
            for key, point_name in names.items()
        }
        record_event(
            "feed_temperature_envelope_snapshot",
            context=context,
            label=label,
            values=values,
        )
        return values

    def apply(key: str, value: float, label: str) -> None:
        point_name = names[key]
        logging.info(
            "Feed 온도 범위 입력: %s=%s℃ (%s/%s)",
            key,
            f"{value:g}",
            context,
            label,
        )
        replace_value(points, point_name, f"{value:g}", pause)
        resolve_wave_blocking_dialogs(
            hwnd,
            monitor,
            f"{context}_{label}_{point_name}",
            points,
        )

    before = snapshot("before")
    readable = [value for value in before.values() if value is not None]
    guard_min = min([minimum, design, maximum, *readable])
    guard_max = max([minimum, design, maximum, *readable])
    logging.info(
        "Feed 온도 범위 동적 설정: current=%s/%s/%s guard=%s/%s target=%s/%s/%s",
        before.get("min"),
        before.get("design"),
        before.get("max"),
        f"{guard_min:g}",
        f"{guard_max:g}",
        f"{minimum:g}",
        f"{design:g}",
        f"{maximum:g}",
    )
    record_event(
        "feed_temperature_envelope_plan",
        context=context,
        current=before,
        guard_min=guard_min,
        guard_max=guard_max,
        target={"min": minimum, "design": design, "max": maximum},
    )

    # Invariant-preserving universal order.
    sequence = [
        ("max", guard_max, "guard_max"),
        ("min", guard_min, "guard_min"),
        ("design", design, "design"),
        ("min", minimum, "final_min"),
        ("max", maximum, "final_max"),
    ]
    for key, value, label in sequence:
        apply(key, value, label)

    after = snapshot("after")
    expected = {"min": minimum, "design": design, "max": maximum}
    incomplete = [
        key
        for key, expected_value in expected.items()
        if after.get(key) is None or abs(float(after[key]) - expected_value) > 0.06
    ]
    if incomplete:
        logging.warning(
            "Feed 온도 범위 1차 입력 미완료: context=%s after=%s incomplete=%s; 재시도",
            context,
            after,
            incomplete,
        )
        for key, value, label in sequence:
            apply(key, value, f"retry_{label}")

    verify_numeric_point(f"{context}_min", points["feed_temp_min"], f"{minimum:g}")
    verify_numeric_point(f"{context}_design", points["feed_temp_design"], f"{design:g}")
    verify_numeric_point(f"{context}_max", points["feed_temp_max"], f"{maximum:g}")
    screenshot(f"{context}_set", monitor, hwnd)


def set_feed_temperature_triplet(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    target: str,
    pause: float,
) -> None:
    """Backward-compatible equal Minimum/Design/Maximum setter."""
    target_value = float(str(target).replace(",", "."))
    set_feed_temperature_envelope(
        hwnd,
        monitor,
        points,
        target_value,
        target_value,
        target_value,
        pause,
        context="feed_temperature_triplet",
    )


def select_library_profile(dialog: WindowInfo, text: str, pause: float) -> None:
    # Recording-derived dialog-relative anchors. Dialog may move, so never use WAVE absolute points here.
    combo = (
        dialog.rect.left + round(dialog.rect.width * 0.56),
        dialog.rect.top + round(dialog.rect.height * 0.093),
    )
    bring_window_to_front(dialog.hwnd)
    logging.info("library dialog combo click %s", combo)
    native_click_at(*combo)
    time.sleep(0.25)
    pyautogui.press("home")
    # WAVE uses a non-editable drop-down; key-by-key type-ahead is more reliable
    # than pasting into it. Clipboard paste remains a fallback for future editable controls.
    pyautogui.write(text, interval=0.025)
    pyautogui.press("enter")
    wait(pause)


def _close_water_library_dialog(dialog: WindowInfo) -> None:
    """Close the profile-library dialog without changing the underlying feed again."""
    if not ctypes.windll.user32.IsWindow(dialog.hwnd):
        return
    bring_window_to_front(dialog.hwnd, restore_if_minimized=False)
    pyautogui.press("esc")
    deadline = time.time() + 2.5
    while time.time() < deadline:
        if not ctypes.windll.user32.IsWindow(
            dialog.hwnd
        ) or not ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
            return
        time.sleep(0.15)
    # Dialog-relative Cancel button fallback.  Escape is preferred because it is DPI-independent.
    cancel_point = (
        dialog.rect.left + round(dialog.rect.width * 0.56),
        dialog.rect.top + round(dialog.rect.height * 0.935),
    )
    native_click_at(*cancel_point)
    time.sleep(0.6)


def copy_library_to_feed(
    dialog: WindowInfo,
    pause: float,
    hwnd: int,
    monitor: Rect,
) -> None:
    point = (
        dialog.rect.left + round(dialog.rect.width * 0.88),
        dialog.rect.top + round(dialog.rect.height * 0.935),
    )
    logging.info("Copy To Feed Water click %s", point)
    bring_window_to_front(dialog.hwnd)
    native_click_at(*point)
    deadline = time.time() + max(4.0, pause * 2)
    while time.time() < deadline:
        if not ctypes.windll.user32.IsWindow(
            dialog.hwnd
        ) or not ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
            return

        # Replacing a profile on an already-configured case can momentarily apply
        # the new Design temperature before the new Minimum temperature.  WAVE then
        # raises a modal even though the selected library profile itself is valid.
        # Detect that exact transient condition immediately instead of waiting for a
        # generic "dialog did not close" timeout.
        for modal, text in _blocking_wave_dialogs(hwnd):
            blob = text.lower()
            if any(
                token in blob
                for token in (
                    "design temperature warning",
                    "minimum temperature",
                    "cannot be less than the minimum temperature",
                )
            ):
                logging.warning(
                    "Water Library 교체 중 과도 온도 검증 감지: title=%r text=%r",
                    modal.title,
                    text,
                )
                record_event(
                    "library_copy_temperature_transition",
                    dialog=dialog,
                    modal=modal,
                    text=text,
                )
                screenshot("library_copy_temperature_transition", monitor, hwnd)
                _close_modal_dialog(modal)
                _close_water_library_dialog(dialog)
                raise LibraryTemperatureTransitionError(
                    "기존 Feed의 온도 범위 때문에 Water Library 복사가 중단되었습니다."
                )
        time.sleep(0.2)
    raise WaveAutomationError(
        "Copy To Feed Water 후 Water Library 창이 닫히지 않았습니다."
    )


def prepare_feed_for_profile_replacement(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Widen the current feed temperature envelope before replacing its profile.

    WAVE validates ``Minimum <= Design <= Maximum`` after every single edit.  The
    old fixed order (Maximum -> Design -> Minimum) was safe for 25 C cases but
    failed after a 35/35/35 C case because lowering Design to 25 C while Minimum
    was still 35 C triggered ``Design Temperature Warning``.  V22 expands
    both bounds around the *current* triplet, then moves Design, and finally
    normalizes the temporary envelope to 1/25/45 C.
    """
    desired_min = 1.0
    desired_design = 25.0
    desired_max = 45.0

    current = {
        "min": _read_numeric_point(
            "profile_replace_before_min", points["feed_temp_min"]
        ),
        "design": _read_numeric_point(
            "profile_replace_before_design", points["feed_temp_design"]
        ),
        "max": _read_numeric_point(
            "profile_replace_before_max", points["feed_temp_max"]
        ),
    }
    readable = [value for value in current.values() if value is not None]
    guard_min = min([desired_min, desired_design, desired_max, *readable])
    guard_max = max([desired_min, desired_design, desired_max, *readable])

    logging.info(
        "기존 Feed 프로파일 교체 전 온도 범위 동적 안전화: "
        "current=%s/%s/%s guard=%s/%s final=%s/%s/%s",
        current.get("min"),
        current.get("design"),
        current.get("max"),
        f"{guard_min:g}",
        f"{guard_max:g}",
        f"{desired_min:g}",
        f"{desired_design:g}",
        f"{desired_max:g}",
    )
    record_event(
        "prepare_profile_replacement_temperature_envelope",
        current=current,
        guard_min=guard_min,
        guard_max=guard_max,
        minimum=desired_min,
        design=desired_design,
        maximum=desired_max,
        target=settings.temperature_c,
    )

    def apply(point_name: str, value: float, label: str) -> None:
        logging.info(
            "프로파일 교체 온도 안전화 입력: %s=%s℃ (%s)",
            point_name,
            f"{value:g}",
            label,
        )
        replace_value(points, point_name, f"{value:g}", settings.pause)
        resolve_wave_blocking_dialogs(
            hwnd,
            monitor,
            f"profile_replace_{label}_{point_name}",
            points,
        )

    # Universal safe order for any valid starting triplet:
    #   1) expand upper bound, 2) lower the lower bound,
    #   3) move Design inside the widened interval,
    #   4) collapse to the canonical 1/25/45 temporary envelope.
    apply("feed_temp_max", guard_max, "guard_max")
    apply("feed_temp_min", guard_min, "guard_min")
    apply("feed_temp_design", desired_design, "design")
    apply("feed_temp_min", desired_min, "final_min")
    apply("feed_temp_max", desired_max, "final_max")

    after = {
        "min": _read_numeric_point(
            "profile_replace_after_min", points["feed_temp_min"]
        ),
        "design": _read_numeric_point(
            "profile_replace_after_design", points["feed_temp_design"]
        ),
        "max": _read_numeric_point(
            "profile_replace_after_max", points["feed_temp_max"]
        ),
    }
    expected = {
        "min": desired_min,
        "design": desired_design,
        "max": desired_max,
    }
    incomplete = [
        key
        for key, expected_value in expected.items()
        if after.get(key) is None or abs(float(after[key]) - expected_value) > 0.06
    ]
    if incomplete:
        logging.warning(
            "프로파일 교체 온도 안전화 1차 입력 미완료: after=%s incomplete=%s; "
            "보수적 재시도",
            after,
            incomplete,
        )
        record_event(
            "profile_replacement_temperature_envelope_retry",
            after=after,
            incomplete=incomplete,
        )
        # Repeat the invariant-preserving order.  This also recovers from a field
        # that WPF did not commit on the first focus/Enter cycle.
        apply("feed_temp_max", max(guard_max, desired_max), "retry_guard_max")
        apply("feed_temp_min", min(guard_min, desired_min), "retry_guard_min")
        apply("feed_temp_design", desired_design, "retry_design")
        apply("feed_temp_min", desired_min, "retry_final_min")
        apply("feed_temp_max", desired_max, "retry_final_max")

    verify_numeric_point(
        "profile_replace_safe_min", points["feed_temp_min"], f"{desired_min:g}"
    )
    verify_numeric_point(
        "profile_replace_safe_design",
        points["feed_temp_design"],
        f"{desired_design:g}",
    )
    verify_numeric_point(
        "profile_replace_safe_max", points["feed_temp_max"], f"{desired_max:g}"
    )
    screenshot("profile_replace_temperature_envelope", monitor, hwnd)
