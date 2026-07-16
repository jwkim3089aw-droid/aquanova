#!/usr/bin/env python3
"""Refactored WAVE automation module: ro_ui."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import _capture_wave_image, _image_change_ratio, ro_local_change_ratio, ro_presence_metrics, save_point_probe, screenshot
from wave_dialogs import _blocking_wave_dialogs, _find_flow_calculator_dialog, configure_flow_calculator_dialog, resolve_wave_blocking_dialogs
from wave_feed import _read_numeric_point, verify_numeric_point
from wave_interaction import click, replace_value, wait
from wave_runtime import record_event
from wave_uia import uia_probe_point, uia_select_combo_exact
from wave_windows import _foreground_window_info, _get_window_rect, bring_window_to_front, focus_wave, native_click_at, native_drag, native_move_to

def open_and_configure_ro_flow(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Open the calculator from RO Feed Flow/Recovery instead of typing into it.

    In this WAVE build those green cells are commands, not ordinary edit boxes.
    Clicking Feed Flow opens a modal calculator.  V9 treated it as an edit field,
    then tried to refocus the disabled owner window and waited indefinitely.
    """
    for source_name in ("ro_feed_flow", "ro_recovery"):
        if _find_flow_calculator_dialog(hwnd, timeout=0.0) is None:
            click(points, source_name, pause=0.25)
        dialog = _find_flow_calculator_dialog(hwnd, timeout=4.0)
        if dialog is not None:
            configure_flow_calculator_dialog(
                dialog, settings.recovery_pct, monitor, hwnd, settings, source_name
            )
            focus_wave(hwnd)
            return
    raise WaveAutomationError(
        "RO Feed Flow/Recovery 클릭 후 Reverse Osmosis Flow Calculator를 찾지 못했습니다."
    )


def enter_summary_report_with_recovery(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Enter Summary Report, handling a calculator that WAVE may reopen."""
    for attempt in range(1, 4):
        before = _capture_wave_image(hwnd)
        click(points, "summary_report_tab", pause=settings.pause)
        dialog = _find_flow_calculator_dialog(hwnd, timeout=2.5)
        if dialog is not None:
            configure_flow_calculator_dialog(
                dialog,
                settings.recovery_pct,
                monitor,
                hwnd,
                settings,
                f"summary_attempt_{attempt}",
            )
            focus_wave(hwnd)
            continue
        wait(settings.long_wait)
        after = _capture_wave_image(hwnd)
        ratio = _image_change_ratio(before, after)
        logging.info("Summary Report 전환 검증 attempt=%s ratio=%.5f", attempt, ratio)
        record_event("summary_report_transition", attempt=attempt, ratio=ratio)
        screenshot(f"summary_report_attempt_{attempt}", monitor, hwnd)
        if ratio >= 0.003:
            return
    raise WaveAutomationError(
        "Summary Report 화면으로 전환되지 않았습니다. Flow Calculator 처리 후에도 변화가 없습니다."
    )


def set_and_verify_ro_temperature(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
    *,
    force_mode_selection: bool = False,
) -> None:
    """Set the RO pass temperature through WAVE's supported ``Specify`` mode.

    The numeric box beside Temperature is read-only while the mode is Design,
    Minimum, or Maximum.  WAVE exposes a fourth mode, Specify, which makes the
    adjacent value editable.  Earlier revisions either tried to edit the
    read-only box or deferred the mismatch to PDF validation; both approaches
    were wrong for a case that explicitly requests 25 C.

    SelectionItemPattern is not exposed by this WPF ComboBox, so use native
    keyboard navigation.  ``Specify`` is the final list item in this build;
    type-ahead and explicit down-count fallbacks are retained for resilience.
    Every attempt uses Enter to commit the WAVE model and is accepted only after
    the visible numeric value reads back as the requested temperature.  The
    engine then performs a pass-tab round trip to prove persistence.
    """
    mode_point = points["ro_temperature_mode"]
    value_point = points["ro_temperature_value"]
    expected = float(str(settings.temperature_c).replace(",", "."))
    attempts: list[dict[str, Any]] = []

    current = verify_numeric_point(
        "ro_temperature_before_specify",
        value_point,
        settings.temperature_c,
        required_when_readable=False,
    )
    if (
        not force_mode_selection
        and current is not None
        and abs(current - expected) <= 0.06
    ):
        logging.info("RO 온도 이미 목표값: %s℃", current)
        _write_ro_temperature_strategy(
            [{"strategy": "already_matches", "value": current}],
            "already_matches",
            current,
        )
        return

    strategies: list[tuple[str, list[tuple[str, Any]]]] = [
        ("combo_end", [("press", "end"), ("press", "enter")]),
        (
            "combo_typeahead_specify",
            [("write", "Specify"), ("press", "enter")],
        ),
        (
            "combo_home_down_3",
            [("press", "home"), ("press_many", ("down", 3)), ("press", "enter")],
        ),
    ]

    for strategy_name, actions in strategies:
        focus_wave(hwnd)
        save_point_probe(f"ro_temperature_mode_{strategy_name}", hwnd, mode_point)
        native_click_at(*mode_point)
        time.sleep(0.25)
        for action, payload in actions:
            if action == "press":
                pyautogui.press(str(payload))
            elif action == "write":
                pyautogui.write(str(payload), interval=0.06)
            elif action == "press_many":
                key, count = payload
                pyautogui.press(str(key), presses=int(count), interval=0.12)
            time.sleep(0.12)
        wait(0.55)

        mode_probe = uia_probe_point(mode_point)
        value_probe_before = uia_probe_point(value_point)
        attempt: dict[str, Any] = {
            "strategy": strategy_name,
            "mode_probe": mode_probe,
            "value_probe_before": value_probe_before,
        }
        screenshot(f"ro_temperature_{strategy_name}_mode_selected", monitor, hwnd)

        try:
            # V52: WAVE's RO temperature TextBox (AutomationId=txtdifftemp)
            # can display the typed value after a normal Tab/LostFocus while the
            # underlying pass model still keeps the source-profile temperature.
            # Re-selecting the same pass then exposes the old value (12.2 C in
            # V25_2P_005).  This control requires an explicit Enter key to run
            # its own commit handler.  Enter first, then Tab and a neutral click
            # so both the WAVE handler and the WPF binding have completed.
            native_click_at(*value_point)
            time.sleep(0.18)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(str(settings.temperature_c), interval=0.05)
            pyautogui.press("enter")
            wait(max(0.75, settings.pause))
            pyautogui.press("tab")
            wait(0.30)
            native_click_at(points["stage_1_radio"][0], points["stage_1_radio"][1])
            wait(0.55)
            attempt["value_commit"] = "enter_then_tab_then_neutral_click"
            actual = verify_numeric_point(
                "ro_temperature",
                value_point,
                settings.temperature_c,
                required_when_readable=True,
            )
            attempt["actual"] = actual
            attempt["ok"] = actual is not None and abs(actual - expected) <= 0.06
            attempt["value_probe_after"] = uia_probe_point(value_point)
            attempts.append(attempt)
            if attempt["ok"]:
                logging.info(
                    "RO 온도 설정 성공: Specify=%s℃ strategy=%s",
                    actual,
                    strategy_name,
                )
                screenshot("05a_ro_temperature_specified", monitor, hwnd)
                _write_ro_temperature_strategy(attempts, strategy_name, actual)
                return
        except Exception as exc:
            attempt["ok"] = False
            attempt["error"] = repr(exc)
            attempt["value_probe_after"] = uia_probe_point(value_point)
            attempts.append(attempt)
            logging.warning(
                "RO 온도 Specify 시도 실패: strategy=%s error=%s",
                strategy_name,
                exc,
            )
            screenshot(f"ro_temperature_{strategy_name}_failed", monitor, hwnd)

    _write_ro_temperature_strategy(attempts, "failed", current)
    raise WaveAutomationError(
        "RO Temperature를 Specify 모드로 25℃에 설정하지 못했습니다. "
        "run_*.zip의 ro_temperature_strategy.json과 관련 스크린샷을 확인하세요."
    )


def set_and_verify_ro_temperature_mode(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    mode: str,
    temperature_c: float,
    settings: Settings,
    *,
    label: str,
    force_mode_selection: bool = False,
) -> None:
    """Select Minimum/Design/Maximum/Specify and verify the visible value.

    The WPF ComboBox does not expose SelectionItemPattern reliably, so V22 uses
    deterministic keyboard positions observed in the user's inventory video.
    ``Specify`` delegates to the already field-tested numeric entry path.
    """
    normalized = str(mode or "Specify").strip().lower()
    canonical = {
        "minimum": "Minimum",
        "design": "Design",
        "maximum": "Maximum",
        "specify": "Specify",
    }.get(normalized)
    if canonical is None:
        raise WaveAutomationError(f"지원하지 않는 RO Temperature mode: {mode!r}")
    if canonical == "Specify":
        pass_settings = Settings(
            water_profile=settings.water_profile,
            temperature_c=_fmt_value(temperature_c),
            feed_flow_m3h=settings.feed_flow_m3h,
            recovery_pct=settings.recovery_pct,
            pv_per_stage=settings.pv_per_stage,
            elements_per_pv=settings.elements_per_pv,
            membrane=settings.membrane,
            add_ro=settings.add_ro,
            pause=settings.pause,
            long_wait=settings.long_wait,
            validate_pdf=False,
        )
        set_and_verify_ro_temperature(
            hwnd,
            monitor,
            points,
            pass_settings,
            force_mode_selection=force_mode_selection,
        )
        return

    index = {"Minimum": 0, "Design": 1, "Maximum": 2}[canonical]
    mode_point = points["ro_temperature_mode"]
    value_point = points["ro_temperature_value"]
    expected = float(temperature_c)
    attempts: list[dict[str, Any]] = []
    strategies = [
        ("home_index", [("press", "home"), ("down", index), ("press", "enter")]),
        ("typeahead", [("write", canonical), ("press", "enter")]),
    ]
    for strategy, actions in strategies:
        focus_wave(hwnd)
        native_click_at(*mode_point)
        time.sleep(0.2)
        for action, payload in actions:
            if action == "press":
                pyautogui.press(str(payload))
            elif action == "down" and int(payload) > 0:
                pyautogui.press("down", presses=int(payload), interval=0.12)
            elif action == "write":
                pyautogui.write(str(payload), interval=0.06)
            time.sleep(0.12)
        wait(max(0.55, settings.pause))
        actual = verify_numeric_point(
            f"{label}_ro_temperature_{canonical.lower()}",
            value_point,
            _fmt_value(expected),
            required_when_readable=False,
        )
        mode_probe = uia_probe_point(mode_point)
        attempts.append(
            {
                "strategy": strategy,
                "mode": canonical,
                "expected": expected,
                "actual": actual,
                "mode_probe": mode_probe,
            }
        )
        screenshot(
            f"{label}_ro_temperature_mode_{canonical.lower()}_{strategy}",
            monitor,
            hwnd,
        )
        if actual is not None and abs(actual - expected) <= 0.06:
            logging.info(
                "RO 온도 모드 설정 성공: label=%s mode=%s value=%s℃ strategy=%s",
                label,
                canonical,
                actual,
                strategy,
            )
            record_event(
                "ro_temperature_mode",
                label=label,
                mode=canonical,
                expected=expected,
                actual=actual,
                strategy=strategy,
                attempts=attempts,
            )
            return

    # WAVE's Add Pass operation can leave the ComboBox text at ``Design`` while
    # the bound numeric temperature is still the old default (typically 15 C).
    # Selecting the already-selected item does not fire SelectionChanged, so the
    # normal deterministic selections above appear successful but the value never
    # refreshes.  Force one real mode transition and then return to the requested
    # mode.  This is safe for all non-Specify modes because the Feed temperature
    # envelope was already validated before entering the RO screen.
    alternate = {
        "Minimum": "Design",
        "Design": "Minimum",
        "Maximum": "Design",
    }[canonical]
    refresh_trace: list[dict[str, Any]] = []
    for selected_mode in (alternate, canonical):
        selected_index = {"Minimum": 0, "Design": 1, "Maximum": 2}[selected_mode]
        focus_wave(hwnd)
        native_click_at(*mode_point)
        time.sleep(0.2)
        pyautogui.press("home")
        if selected_index > 0:
            pyautogui.press("down", presses=selected_index, interval=0.12)
        pyautogui.press("enter")
        wait(max(0.65, settings.pause))
        intermediate = _read_numeric_point(
            f"{label}_ro_temperature_refresh_{selected_mode.lower()}",
            value_point,
        )
        refresh_trace.append(
            {
                "selected_mode": selected_mode,
                "actual": intermediate,
                "mode_probe": uia_probe_point(mode_point),
            }
        )
        screenshot(
            f"{label}_ro_temperature_mode_{canonical.lower()}_refresh_{selected_mode.lower()}",
            monitor,
            hwnd,
        )

    actual = verify_numeric_point(
        f"{label}_ro_temperature_{canonical.lower()}_after_refresh",
        value_point,
        _fmt_value(expected),
        required_when_readable=False,
    )
    attempts.append(
        {
            "strategy": "forced_mode_refresh",
            "mode": canonical,
            "alternate": alternate,
            "expected": expected,
            "actual": actual,
            "trace": refresh_trace,
        }
    )
    if actual is not None and abs(actual - expected) <= 0.06:
        logging.info(
            "RO 온도 모드 강제 새로고침 성공: label=%s mode=%s value=%s℃ via=%s",
            label,
            canonical,
            actual,
            alternate,
        )
        record_event(
            "ro_temperature_mode",
            label=label,
            mode=canonical,
            expected=expected,
            actual=actual,
            strategy="forced_mode_refresh",
            alternate=alternate,
            attempts=attempts,
        )
        return

    record_event(
        "ro_temperature_mode_failed",
        label=label,
        mode=canonical,
        expected=expected,
        attempts=attempts,
    )
    raise WaveAutomationError(
        f"RO Temperature mode={canonical} 값 검증 실패: expected={expected:g}. "
        "관련 스크린샷과 UIA probe를 확인하세요."
    )


def _write_ro_temperature_strategy(
    attempts: list[dict[str, Any]], final_strategy: str, final_value: Optional[float]
) -> None:
    payload = {
        "final_strategy": final_strategy,
        "final_value": final_value,
        "attempts": attempts,
    }
    record_event("ro_temperature_strategy", **payload)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "ro_temperature_strategy.json").write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _restore_wave_after_combo(hwnd: int, label: str) -> None:
    """Dismiss accidental Windows Task View and restore WAVE foreground.

    V26-V28 could click a virtualized ListItem rectangle clipped to the taskbar.
    The subsequent PV keystrokes then went to Task View and WAVE retained PV=1.
    """
    fg = _foreground_window_info()
    task_view = bool(
        fg
        and (
            fg.class_name == "XamlExplorerHostIslandWindow"
            or "작업 보기" in fg.title
            or fg.title.casefold() == "task view"
        )
    )
    if task_view:
        logging.warning(
            "막 선택 중 Windows Task View 감지·복구: label=%s foreground=%r",
            label,
            fg.title if fg else "",
        )
        record_event("task_view_recovery", label=label, foreground=fg)
        pyautogui.press("esc")
        time.sleep(0.35)
    bring_window_to_front(hwnd, restore_if_minimized=False)
    time.sleep(0.25)


def select_combo_exact(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    name: str,
    target: str,
    pause: float = 1.0,
) -> dict[str, Any]:
    """Select an exact membrane without rejecting an unreadable WPF presenter.

    Exact visible or SelectionItemPattern evidence is preferred.  When WAVE
    exposes no readable selection state, an exact catalog-index commit is kept
    provisionally instead of being overwritten by a weaker second strategy.
    Summary Report validation remains authoritative for provisional commits.
    """
    point = points[name]
    _restore_wave_after_combo(hwnd, f"{name}_before")
    result = uia_select_combo_exact(hwnd, point, target)
    _restore_wave_after_combo(hwnd, f"{name}_after")
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
    evidence = []
    for value in [*displayed, *selected]:
        if value not in evidence:
            evidence.append(value)
    verified = bool(
        result.get("ok")
        and result.get("committed")
        and result.get("verified_exact")
    )
    provisional = bool(
        result.get("ok")
        and result.get("committed")
        and result.get("provisional")
        and result.get("readback_unavailable")
        and str(result.get("method") or "") == "CatalogKeyboardIndexProvisional"
        and not result.get("contradictions")
    )
    if verified or provisional:
        strategy = str(result.get("method") or "UIAExactItem")
        uf_pdf_deferred = bool(
            provisional
            and name in {"uf_design_module_combo", "uf_config_module_combo"}
            and str(target).lower().startswith("ultrafiltration")
        )
        level = (
            "verified"
            if verified
            else ("provisional_pdf_deferred" if uf_pdf_deferred else "provisional_unreadable")
        )
        # UF module ComboBoxes in this WAVE build expose only the catalog data-access
        # object after an exact keyboard commit.  The generated UF PDF validates the
        # actual module later, so keep the event but do not surface it as a warning.
        log = logging.info if (verified or uf_pdf_deferred) else logging.warning
        log(
            "ComboBox 정확 선택 커밋: %s=%r strategy=%s level=%s evidence=%r",
            name,
            target,
            strategy,
            level,
            evidence,
        )
        record_event(
            "combo_exact_committed_v69",
            name=name,
            target=target,
            strategy=strategy,
            verification_level=level,
            pdf_deferred=uf_pdf_deferred,
            displayed=displayed,
            selected=selected,
            target_index=result.get("target_index"),
            result=result,
        )
        wait(pause)
        screenshot(f"exact_combo_{name}_{level}", monitor, hwnd)
        return result

    catalog = [str(v).strip() for v in result.get("catalog", []) if str(v).strip()]
    record_event(
        "combo_exact_failed_v32",
        name=name,
        target=target,
        displayed=displayed,
        selected=selected,
        catalog_count=len(catalog),
        target_index=result.get("target_index"),
        result=result,
    )
    screenshot(f"exact_combo_{name}_failed", monitor, hwnd)
    raise WaveAutomationError(
        f"{name} 막 정확 선택 실패: target={target!r}, displayed={displayed!r}, "
        f"selected={selected!r}, method={result.get('method')!r}, "
        f"transport_error={result.get('error')!r}, transport={result.get('transport')!r}, "
        f"target_index={result.get('target_index')!r}, catalog_count={len(catalog)}, "
        f"contradictions={result.get('contradictions')!r}, "
        f"errors={result.get('pattern_errors')!r}"
    )

def select_combo_text(
    points: dict[str, tuple[int, int]], name: str, text: str, pause: float = 1.0
) -> None:
    """Legacy prefix selection for controls whose values are inherently unique."""
    click(points, name, pause=0.2)
    pyautogui.press("home")
    pyautogui.write(text, interval=0.025)
    pyautogui.press("enter")
    wait(pause)


def enter_home_with_recovery(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Enter Home, repairing charge balance if WAVE blocks the transition."""
    for attempt in range(1, 4):
        before = _capture_wave_image(hwnd)
        click(points, "home_tab", pause=settings.pause)
        time.sleep(0.25)
        actions = resolve_wave_blocking_dialogs(
            hwnd, monitor, f"home_transition_attempt_{attempt}", points
        )
        if "adjust_all_ions" in actions:
            # The rejected Home click did not navigate.  Retry after repair.
            continue
        after = _capture_wave_image(hwnd)
        ratio = _image_change_ratio(before, after)
        logging.info("Home 전환 검증 attempt=%s ratio=%.5f", attempt, ratio)
        record_event("home_transition", attempt=attempt, ratio=ratio, actions=actions)
        screenshot(f"verify_home_transition_attempt{attempt}", monitor, hwnd)
        if ratio >= 0.003 and not _blocking_wave_dialogs(hwnd):
            return
    raise WaveAutomationError("전하수지 복구 후에도 Home 화면으로 전환하지 못했습니다.")


def add_ro_with_recovery(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Add RO and verify the actual WAVE state, not whole-screen change.

    A successful RO drag changes only a very small part of the full WAVE
    screenshot.  The old full-window threshold produced a false failure even
    though the green RO icon and Reverse Osmosis tab were visible.  V9 detects
    the green process icon in the drop zone and accepts a strong local change
    as a secondary signal.
    """
    initial = ro_presence_metrics(hwnd, points, label="before_ro_drag")
    if initial["present"]:
        logging.info(
            "RO 공정이 이미 존재합니다. --add-ro가 지정됐지만 중복 드래그를 생략합니다."
        )
        record_event("ro_add_skipped", reason="already_present", metrics=initial)
        return

    for attempt in range(1, 4):
        logging.info(
            "RO 아이콘 native drag attempt=%s: %s -> %s",
            attempt,
            points["ro_icon"],
            points["process_drop_point"],
        )
        before = _capture_wave_image(hwnd)
        bring_window_to_front(hwnd)
        native_drag(points["ro_icon"], points["process_drop_point"], duration=1.1)
        wait(settings.long_wait)

        actions = resolve_wave_blocking_dialogs(
            hwnd, monitor, f"after_ro_drag_attempt_{attempt}", points
        )
        if "adjust_all_ions" in actions:
            enter_home_with_recovery(hwnd, monitor, points, settings)

        # Move away from the process icon so WAVE's hover tooltip does not
        # obscure the verification crop or the next tab click.
        rect = _get_window_rect(hwnd)
        native_move_to(rect.left + min(620, rect.width // 2), rect.top + 16)
        wait(0.35)

        after = _capture_wave_image(hwnd)
        global_ratio = _image_change_ratio(before, after)
        local_ratio = ro_local_change_ratio(before, after, hwnd, points)
        presence = ro_presence_metrics(
            hwnd, points, label=f"after_ro_drag_attempt_{attempt}"
        )

        record_event(
            "drag_result",
            name="ro_icon",
            attempt=attempt,
            global_ratio=global_ratio,
            local_ratio=local_ratio,
            presence=presence,
            actions=actions,
        )
        logging.info(
            "RO 드래그 검증 attempt=%s global=%.5f local=%.5f green=%.5f",
            attempt,
            global_ratio,
            local_ratio,
            presence["green_fraction"],
        )

        # Primary: stable green RO icon in the drop zone.
        # Secondary: large local canvas change, useful if a future WAVE theme
        # slightly changes the icon color.
        if presence["present"] or local_ratio >= 0.018:
            logging.info("RO 공정 추가 성공 확인: attempt=%s", attempt)
            screenshot(f"ro_drag_success_{attempt}", monitor, hwnd)
            return

        screenshot(f"ro_drag_retry_{attempt}", monitor, hwnd)

        # A successful first drag may have been visually added while an
        # animation was still settling.  Re-check once before performing
        # another drag to avoid inserting duplicates.
        wait(0.7)
        settled = ro_presence_metrics(
            hwnd, points, label=f"settled_after_ro_drag_attempt_{attempt}"
        )
        if settled["present"]:
            logging.info("RO 공정 추가 지연 확인 성공: attempt=%s", attempt)
            return

    raise WaveAutomationError(
        "RO 아이콘 드래그 후 실제 RO 공정을 확인하지 못했습니다. "
        "피드백 ZIP의 ro_process_crop과 ro_tab_crop을 확인하세요."
    )
