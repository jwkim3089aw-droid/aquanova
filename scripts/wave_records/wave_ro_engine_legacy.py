#!/usr/bin/env python3
"""Refactored WAVE automation module: ro_engine."""
from __future__ import annotations







# V156_RO_REPORTS_IMPORT_START
try:
    from ro.reports import (
        enter_summary_report_case,
    )
except ImportError:
    from .ro.reports import (
        enter_summary_report_case,
    )
# V156_RO_REPORTS_IMPORT_END

# V147_RO_RUNNER_IMPORT_START
try:
    from ro.runner import (
        _legacy_compatible,
        _find_new_wave_dialog,
    )
except ImportError:
    from .ro.runner import (
        _legacy_compatible,
        _find_new_wave_dialog,
    )
# V147_RO_RUNNER_IMPORT_END

# V149_RO_CASE_CONFIG_IMPORT_START
try:
    from ro.case_config import (
        _capture_case_ro_state,
        _verify_case_operating_inputs,
        _validate_case_automation_support,
        _settings_from_ro_case,
        _configure_pass_screen,
        open_and_configure_ro_flow_case,
    )
except ImportError:
    from .ro.case_config import (
        _capture_case_ro_state,
        _verify_case_operating_inputs,
        _validate_case_automation_support,
        _settings_from_ro_case,
        _configure_pass_screen,
        open_and_configure_ro_flow_case,
    )
# V149_RO_CASE_CONFIG_IMPORT_END

# V141_RO_MEMBRANE_IMPORT_START
try:
    from ro.membrane import (
        _ro_diagnostic_points,
        _reconcile_ro_pass_topology,
        _verify_stage_grid_membranes,
    )
except ImportError:
    from .ro.membrane import (
        _ro_diagnostic_points,
        _reconcile_ro_pass_topology,
        _verify_stage_grid_membranes,
    )
# V141_RO_MEMBRANE_IMPORT_END

# V148_RO_STAGES_IMPORT_START
try:
    from ro.stages import (
        _stage_grid_points,
        _stabilize_after_flow_commit,
        _select_pass,
        _set_stage_count,
        _stage_cell_point,
        _add_second_pass,
        _configure_stage_grid,
        _map_reference_point,
        _restore_stage_topologies_after_flow_commit,
    )
except ImportError:
    from .ro.stages import (
        _stage_grid_points,
        _stabilize_after_flow_commit,
        _select_pass,
        _set_stage_count,
        _stage_cell_point,
        _add_second_pass,
        _configure_stage_grid,
        _map_reference_point,
        _restore_stage_topologies_after_flow_commit,
    )
# V148_RO_STAGES_IMPORT_END

# V138_RO_FEEDWATER_IMPORT_START
try:
    from ro.feedwater import (
        _has_flow_optimization,
    )
except ImportError:
    from .ro.feedwater import (
        _has_flow_optimization,
    )
# V138_RO_FEEDWATER_IMPORT_END

from wave_common import *
from wave_diagnostics import (
    _capture_wave_image,
    _image_change_ratio,
    capture_ro_state,
    diff_ro_states,
    screenshot,
    write_convergence_failure_report,
)
from wave_dialogs import _blocking_wave_dialogs, _close_modal_dialog, _find_flow_calculator_dialog, _wait_window_closed, configure_flow_calculator_dialog, resolve_wave_blocking_dialogs
from wave_feed import _read_numeric_point, copy_library_to_feed, prepare_feed_for_profile_replacement, select_library_profile, set_feed_temperature_envelope, verify_numeric_point
from wave_interaction import click, click_expect_new_dialog, click_until_visual_change, replace_value, wait
from wave_ro_ui import _restore_wave_after_combo, add_ro_with_recovery, enter_home_with_recovery, open_and_configure_ro_flow, select_combo_exact, set_and_verify_ro_temperature_mode
from wave_runtime import record_event
from wave_uia import uia_configure_chemical_adjustment, uia_configure_flow_calculator_recoveries, uia_configure_special_feature_dialog, uia_read_combo_candidates, uia_reconcile_ro_pass_count
from wave_windows import _foreground_window_info, _get_process_id, _get_window_rect, focus_wave, list_visible_windows, native_click_at




def _replace_value_at_point(point: tuple[int, int], value: Any, pause: float) -> None:
    if STATE.ACTIVE_WAVE_HWND:
        focus_wave(STATE.ACTIVE_WAVE_HWND)
    native_click_at(*point)
    time.sleep(0.12)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(_fmt_value(value), interval=0.04)
    pyautogui.press("tab")
    wait(pause)





























def _verify_stage_grid_numeric_values(
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
    _select_pass(points, pass_index, settings.pause)
    wait(max(0.6, settings.pause))
    layout = _stage_grid_points(hwnd, pass_config)
    changed = False
    for item in layout:
        stage_index = int(item["stage_index"])
        stage = item["stage"]
        expected_fields: list[tuple[str, str, float | int]] = [
            ("pv", "pv", stage.pv),
            ("elements", "elements", stage.elements_per_pv),
            (
                "stage_back_pressure",
                "stage_back_pressure",
                0.0 if stage.stage_back_pressure_bar is None else stage.stage_back_pressure_bar,
            ),
            (
                "flow_factor",
                "flow_factor",
                pass_config.flow_factor if stage.flow_factor is None else stage.flow_factor,
            ),
        ]
        # Stage 1 boost pressure is N/A in WAVE.  Later stages retain their old
        # value across batch cases unless explicitly reset to zero.
        if stage_index > 1:
            expected_fields.append(
                (
                    "boost_pressure",
                    "boost_pressure",
                    0.0 if stage.boost_pressure_bar is None else stage.boost_pressure_bar,
                )
            )
        for field, point_key, expected in expected_fields:
            point = item[point_key]
            actual = _read_numeric_point(
                f"{context}_p{pass_index}s{stage_index}_{field}", point
            )
            record_event(
                "stage_numeric_observation_v44",
                context=context,
                pass_index=pass_index,
                expected_stage_count=pass_config.stage_count,
                stage_index=stage_index,
                field=field,
                point=point,
                expected=float(expected),
                actual=actual,
                layout={
                    str(int(row["stage_index"])): {
                        key: row[key]
                        for key in (
                            "pv", "elements", "membrane", "stage_back_pressure",
                            "boost_pressure", "flow_factor"
                        )
                    }
                    for row in layout
                },
            )
            if actual is None or abs(actual - float(expected)) > 0.06:
                if not repair:
                    raise WaveAutomationError(
                        f"p{pass_index}s{stage_index}_{field} 최종 검증 실패: "
                        f"expected={float(expected):g}, actual={actual}"
                    )
                logging.warning(
                    "Stage 값이 이전 사례/자동 재계산으로 변경됨; 재입력: "
                    "pass=%s stage=%s field=%s expected=%s actual=%s point=%s stage_count=%s",
                    pass_index,
                    stage_index,
                    field,
                    _fmt_value(expected),
                    actual,
                    point,
                    pass_config.stage_count,
                )
                before_repair = capture_ro_state(
                    f"{context}_p{pass_index}s{stage_index}_{field}_before_repair",
                    hwnd,
                    monitor,
                    _ro_diagnostic_points(
                        hwnd, points, pass_index=pass_index, pass_config=pass_config
                    ),
                    expected_stage_counts={pass_index: pass_config.stage_count},
                    metadata={
                        "context": context,
                        "pass_index": pass_index,
                        "stage_index": stage_index,
                        "field": field,
                        "expected": float(expected),
                        "actual": actual,
                        "point": point,
                    },
                )
                _replace_value_at_point(point, expected, settings.pause)
                changed = True
                resolve_wave_blocking_dialogs(
                    hwnd, monitor, f"{context}_repair_p{pass_index}s{stage_index}_{field}", points
                )
                verify_numeric_point(
                    f"{context}_repair_p{pass_index}s{stage_index}_{field}",
                    point,
                    expected,
                )
                after_repair = capture_ro_state(
                    f"{context}_p{pass_index}s{stage_index}_{field}_after_repair",
                    hwnd,
                    monitor,
                    _ro_diagnostic_points(
                        hwnd, points, pass_index=pass_index, pass_config=pass_config
                    ),
                    expected_stage_counts={pass_index: pass_config.stage_count},
                    metadata={
                        "context": context,
                        "pass_index": pass_index,
                        "stage_index": stage_index,
                        "field": field,
                        "expected": float(expected),
                        "point": point,
                    },
                )
                diff_ro_states(
                    before_repair,
                    after_repair,
                    label=f"{context}_p{pass_index}s{stage_index}_{field}_repair",
                )
    screenshot(f"{context}_pass_{pass_index}_stage_values", monitor, hwnd)
    return changed


def _write_stage_numeric_with_retry(
    hwnd: int,
    points: dict[str, tuple[int, int]],
    pass_index: int,
    name: str,
    point: tuple[int, int],
    value: float | int,
    pause: float,
) -> None:
    """Write a stage-grid number with foreground and pass-selection recovery."""
    last_error: Optional[BaseException] = None
    for attempt in range(1, 4):
        try:
            _restore_wave_after_combo(hwnd, f"{name}_attempt_{attempt}")
            if attempt > 1 and pass_index > 1:
                _select_pass(points, pass_index, pause)
                wait(max(0.5, pause))
            _replace_value_at_point(point, value, pause)
            verify_numeric_point(name, point, value)
            if attempt > 1:
                logging.info(
                    "Stage 숫자 재입력 성공: %s=%s attempt=%s",
                    name,
                    _fmt_value(value),
                    attempt,
                )
            return
        except WaveAutomationError as exc:
            last_error = exc
            logging.warning(
                "Stage 숫자 입력 재시도: name=%s expected=%s attempt=%s error=%s",
                name,
                _fmt_value(value),
                attempt,
                exc,
            )
            pyautogui.press("esc")
            time.sleep(0.25)
    raise WaveAutomationError(
        f"{name} 값을 3회 입력했지만 확정되지 않았습니다: expected={_fmt_value(value)}; "
        f"last_error={last_error}"
    )








def _find_chemical_dialog(wave_hwnd: int, timeout: float = 5.0) -> Optional[WindowInfo]:
    """Resolve either a titled dialog or WAVE's untitled chemical overlay HWND.

    In the user's WAVE 2022 build the Chemical Adjustment surface is visually
    embedded over the main project window, but Win32 exposes it as a separate,
    foreground ``HwndWrapper`` whose title is empty.  ``list_visible_windows``
    intentionally omits untitled windows, so the V42 title-only resolver handed
    the main project HWND to UIA and saw only the ribbon's Add Chemicals/Degas
    button.  V52 treats a newly focused same-process WPF HWND with a substantial
    client area as the authoritative chemical host.
    """
    deadline = time.time() + timeout
    pid = _get_process_id(wave_hwnd)
    wave_rect = _get_window_rect(wave_hwnd)
    last_foreground: Optional[WindowInfo] = None
    while time.time() < deadline:
        foreground = _foreground_window_info()
        if foreground is not None:
            last_foreground = foreground
            same_process = foreground.process_id == pid
            separate_hwnd = foreground.hwnd != wave_hwnd
            substantial = (
                foreground.rect.width >= max(500, int(wave_rect.width * 0.55))
                and foreground.rect.height >= max(350, int(wave_rect.height * 0.45))
            )
            wpf_host = "hwndwrapper" in foreground.class_name.casefold()
            titled = "chemical adjustment" in foreground.title.casefold()
            if same_process and separate_hwnd and substantial and (wpf_host or titled):
                record_event(
                    "chemical_host_resolved_v44",
                    strategy="foreground_same_process_overlay",
                    wave_hwnd=wave_hwnd,
                    selected=foreground,
                )
                return foreground

        for item in list_visible_windows(include_small=True):
            if (
                item.hwnd != wave_hwnd
                and item.process_id == pid
                and "chemical adjustment" in item.title.casefold()
            ):
                record_event(
                    "chemical_host_resolved_v44",
                    strategy="titled_top_level_window",
                    wave_hwnd=wave_hwnd,
                    selected=item,
                )
                return item
        time.sleep(0.15)

    record_event(
        "chemical_host_not_resolved_v44",
        wave_hwnd=wave_hwnd,
        last_foreground=last_foreground,
    )
    return None


def _apply_chemical_adjustment(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
) -> None:
    cfg = case.chemical
    force_reconcile = bool(getattr(case, "_force_chemical_reconcile", False))
    if not cfg.enabled and not force_reconcile:
        return
    if force_reconcile:
        logging.info(
            "Chemical 사례 상태 정규화 시작: case=%s requested_enabled=%s",
            case.case_id,
            cfg.enabled,
        )
    click(points, "add_chemicals_degas", pause=settings.pause)
    dialog = _find_chemical_dialog(hwnd, timeout=3.5)
    if dialog is None:
        chemical_hwnd = hwnd
        host_strategy = "main_window_fallback"
        logging.warning(
            "Chemical Adjustment 전용 HWND를 찾지 못해 메인 WAVE HWND로 진단 시도: "
            "case=%s host_hwnd=%s",
            case.case_id,
            hwnd,
        )
    else:
        chemical_hwnd = dialog.hwnd
        host_strategy = (
            "untitled_foreground_overlay" if not dialog.title.strip() else "titled_dialog"
        )
        logging.info(
            "Chemical Adjustment 호스트 감지: case=%s strategy=%s hwnd=%s "
            "title=%r class=%r rect=%s",
            case.case_id,
            host_strategy,
            dialog.hwnd,
            dialog.title,
            dialog.class_name,
            dialog.rect,
        )

    host_probe = {
        "case_id": case.case_id,
        "wave_hwnd": hwnd,
        "selected_hwnd": chemical_hwnd,
        "strategy": host_strategy,
        "selected_window": dialog,
        "foreground": _foreground_window_info(),
        "visible_titled_windows": list_visible_windows(include_small=True),
    }
    record_event("chemical_host_probe_v44", **host_probe)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / f"chemical_host_{case.case_id}.json").write_text(
            json.dumps(host_probe, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    screenshot(f"chemical_{case.case_id}_before", monitor, hwnd)
    result = uia_configure_chemical_adjustment(chemical_hwnd, case)

    # A race can briefly leave the main project HWND selected.  Retry once with
    # the current same-process foreground overlay, preserving both probe results.
    retry_result: Optional[dict[str, Any]] = None
    if not result.get("ok"):
        foreground = _foreground_window_info()
        if (
            foreground is not None
            and foreground.hwnd not in {hwnd, chemical_hwnd}
            and foreground.process_id == _get_process_id(hwnd)
        ):
            logging.warning(
                "Chemical Adjustment UIA 1차 실패 후 foreground HWND 재시도: "
                "case=%s first_hwnd=%s retry_hwnd=%s title=%r class=%r rect=%s",
                case.case_id,
                chemical_hwnd,
                foreground.hwnd,
                foreground.title,
                foreground.class_name,
                foreground.rect,
            )
            retry_result = uia_configure_chemical_adjustment(foreground.hwnd, case)
            record_event(
                "chemical_adjustment_retry_v44",
                case_id=case.case_id,
                first_hwnd=chemical_hwnd,
                retry_hwnd=foreground.hwnd,
                first_result=result,
                retry_result=retry_result,
            )
            if retry_result.get("ok"):
                result = retry_result
                chemical_hwnd = foreground.hwnd
                dialog = foreground

    if not result.get("ok"):
        raise WaveAutomationError(
            "Chemical Adjustment UIA 실패. 상세 진단은 "
            f"chemical_{case.case_id}.json 및 chemical_host_{case.case_id}.json 참조: "
            f"first={result}; retry={retry_result}"
        )
    required_fields: set[str] = set()
    if cfg.acid_enabled:
        required_fields.update({"acid_enabled", "acid_type", "acid_target_ph"})
    if cfg.degas_enabled:
        required_fields.update({"degas_enabled", "degas_mode", "degas_value"})
    if cfg.base_enabled:
        required_fields.update({"base_enabled", "base_type", "base_target_ph"})
    if cfg.antiscalant_enabled:
        required_fields.update(
            {"antiscalant_enabled", "antiscalant_type", "antiscalant_dose_mg_l"}
        )
    if cfg.dechlorinator_enabled:
        required_fields.update(
            {
                "dechlorinator_enabled",
                "dechlorinator_type",
                "dechlorinator_dose_mg_l",
            }
        )
    if cfg.temperature_mode:
        required_fields.add("chemical_temperature_mode")
        if cfg.temperature_mode.strip().casefold() == "specify":
            required_fields.add("chemical_temperature_c")
    if cfg.recovery_mode:
        required_fields.add("chemical_recovery_mode")
        if cfg.recovery_mode.strip().casefold() == "specify":
            required_fields.add("chemical_recovery_value_pct")
    applied_fields = {
        str(item.get("field"))
        for item in result.get("applied", [])
        if isinstance(item, dict)
    }
    missing_fields = sorted(required_fields - applied_fields)
    if missing_fields:
        raise WaveAutomationError(
            f"Chemical Adjustment 입력 검증 누락: {missing_fields}; result={result}"
        )
    logging.info(
        "Chemical Adjustment UIA 검증 성공: case=%s fields=%s "
        "reconciled=%s mode_before=%s mode_after=%s",
        case.case_id,
        sorted(applied_fields),
        bool(result.get("reconcile_all_modes", False)),
        result.get("mode_state_before"),
        result.get("mode_state_after"),
    )
    if not result.get("close_verified", False):
        raise WaveAutomationError(
            f"Chemical Adjustment OK 후 패널 종료를 검증하지 못했습니다: {result}"
        )
    if dialog is not None and not _wait_window_closed(dialog.hwnd, 12.0):
        raise WaveAutomationError("Chemical Adjustment OK 후 별도 창이 닫히지 않았습니다.")
    focus_wave(hwnd)
    screenshot(f"chemical_{case.case_id}_applied", monitor, hwnd)





def _apply_special_features(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
) -> None:
    cfg = case.special_features
    if not cfg.enabled:
        return

    requests: list[dict[str, Any]] = []
    if cfg.compaction_enabled:
        requests.append(
            {
                "point": "compaction",
                "feature": "Compaction",
                "patterns": ("compaction",),
                "mode": cfg.compaction_mode,
                "value": cfg.compaction_value,
            }
        )
    if cfg.toc_rejection_enabled:
        requests.append(
            {
                "point": "ro_toc_rejection",
                "feature": "RO TOC Rejection",
                "patterns": ("toc", "rejection"),
                "mode": None,
                "value": cfg.toc_rejection_pct,
            }
        )

    for request in requests:
        before = {item.hwnd for item in list_visible_windows(include_small=True)}
        click(points, str(request["point"]), pause=settings.pause)
        dialog = _find_new_wave_dialog(
            hwnd,
            before,
            title_patterns=tuple(request["patterns"]),
            timeout=6.0,
        )
        if dialog is None:
            raise WaveAutomationError(
                f"{request['feature']} 버튼 후 설정 창을 찾지 못했습니다. "
                "V52 진단 로그의 window inventory를 확인하세요."
            )
        screenshot(
            f"special_{case.case_id}_{request['point']}_before", monitor, hwnd
        )
        result = uia_configure_special_feature_dialog(
            dialog.hwnd,
            feature=str(request["feature"]),
            mode=request["mode"],
            value=request["value"],
        )
        if not result.get("ok"):
            raise WaveAutomationError(
                f"{request['feature']} UIA 실패: {result}"
            )
        if not _wait_window_closed(dialog.hwnd, 12.0):
            raise WaveAutomationError(
                f"{request['feature']} OK 후 창이 닫히지 않았습니다."
            )
        focus_wave(hwnd)
        screenshot(
            f"special_{case.case_id}_{request['point']}_applied", monitor, hwnd
        )
        logging.info(
            "RO 특수 기능 적용 성공: case=%s feature=%s applied=%s",
            case.case_id,
            request["feature"],
            result.get("applied"),
        )

def _repair_missing_element_type_dialog(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
) -> bool:
    pattern = re.compile(
        r"Please\s+specify\s+Element\s+Type\s+in\s+Pass\s+(\d+)\s+Stage\s+(\d+)",
        re.IGNORECASE,
    )
    for dialog, text in _blocking_wave_dialogs(hwnd):
        match = pattern.search(text)
        if not match:
            continue
        pass_index = int(match.group(1))
        stage_index = int(match.group(2))
        if not (1 <= pass_index <= case.pass_count):
            raise WaveAutomationError(
                f"WAVE가 존재하지 않는 Pass의 Element Type 누락을 보고했습니다: {text!r}"
            )
        pass_config = case.passes[pass_index - 1]
        if not (1 <= stage_index <= pass_config.stage_count):
            raise WaveAutomationError(
                f"WAVE가 존재하지 않는 Stage의 Element Type 누락을 보고했습니다: {text!r}"
            )
        stage = pass_config.stages[stage_index - 1]
        logging.warning(
            "Summary 진입 전 Element Type 자동 복구: case=%s pass=%s stage=%s membrane=%r",
            case.case_id,
            pass_index,
            stage_index,
            stage.membrane,
        )
        record_event(
            "missing_element_type_repair_v31",
            case_id=case.case_id,
            pass_index=pass_index,
            stage_index=stage_index,
            membrane=stage.membrane,
            dialog=text,
        )
        _close_modal_dialog(dialog)
        focus_wave(hwnd)
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.7, settings.pause))
        layout = _stage_grid_points(hwnd, pass_config)
        item = layout[stage_index - 1]
        dynamic = dict(points)
        key = f"p{pass_index}s{stage_index}_membrane"
        dynamic[key] = item["membrane"]
        select_combo_exact(hwnd, monitor, dynamic, key, stage.membrane, settings.long_wait)
        _write_stage_numeric_with_retry(
            hwnd, points, pass_index, f"p{pass_index}s{stage_index}_pv",
            item["pv"], stage.pv, settings.pause,
        )
        _write_stage_numeric_with_retry(
            hwnd, points, pass_index, f"p{pass_index}s{stage_index}_elements",
            item["elements"], stage.elements_per_pv, settings.pause,
        )
        _verify_stage_grid_membranes(
            hwnd, monitor, points, pass_index, pass_config, settings,
            repair=False, context="summary_missing_element_repair",
        )
        _verify_stage_grid_numeric_values(
            hwnd, monitor, points, pass_index, pass_config, settings,
            repair=True, context="summary_missing_element_repair",
        )
        open_and_configure_ro_flow_case(
            hwnd, monitor, points, case, settings,
            context=f"summary_missing_element_p{pass_index}s{stage_index}",
        )
        _stabilize_after_flow_commit(
            hwnd,
            monitor,
            points,
            case,
            settings,
            context=f"summary_missing_element_p{pass_index}s{stage_index}_v44",
        )
        if case.pass_count > 1:
            _select_pass(points, 1, settings.pause)
        return True
    return False



def _reassert_global_temperature_after_flow_commit(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
    *,
    context: str,
) -> None:
    """Restore and persistence-test RO temperature after Flow Calculator.

    WAVE restores ``Specify`` to the source profile temperature when the
    multi-pass Flow Calculator is committed.  V36 re-entered the value once on
    Pass 1, but the TextBox had only a transient display value and reverted as
    soon as the pass tab rebound.  V52 retains the persistent per-pass temperature commit, restores multi-stage
    topology before verification, uses the Enter-based commit path, and then performs a complete pass-tab round trip.
    A value is accepted only after it survives that reload.
    """
    expected = float(case.passes[0].temperature_c)
    before_by_pass: list[dict[str, Any]] = []

    # Reapply on each pass.  Minimum/Design/Maximum are global in this WAVE
    # build, while Specify has a pass-bound TextBox; writing every pass is safe
    # for both behaviours and removes any dependency on undocumented binding.
    for pass_index, pass_config in enumerate(case.passes, start=1):
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.55, settings.pause))
        before_state = _capture_case_ro_state(
            f"{context}_p{pass_index}_before_temperature_reassert",
            hwnd,
            monitor,
            points,
            case,
            pass_index=pass_index,
            pass_config=pass_config,
            metadata={"phase": "before_temperature_reassert"},
        )
        before = _read_numeric_point(
            f"{context}_p{pass_index}_temperature_before_reassert",
            points["ro_temperature_value"],
        )
        before_by_pass.append({"pass": pass_index, "temperature_c": before})
        logging.info(
            "Flow Calculator 후 RO 온도 재적용: case=%s pass=%s mode=%s expected=%s actual_before=%s context=%s",
            case.case_id,
            pass_index,
            pass_config.temperature_mode,
            expected,
            before,
            context,
        )
        pass_settings = Settings(
            water_profile=settings.water_profile,
            temperature_c=_fmt_value(expected),
            feed_flow_m3h=settings.feed_flow_m3h,
            recovery_pct=_fmt_value(pass_config.recovery_pct),
            pv_per_stage=_fmt_value(pass_config.stages[0].pv),
            elements_per_pv=_fmt_value(pass_config.stages[0].elements_per_pv),
            membrane=pass_config.stages[0].membrane,
            add_ro=settings.add_ro,
            pause=settings.pause,
            long_wait=settings.long_wait,
            validate_pdf=False,
        )
        set_and_verify_ro_temperature_mode(
            hwnd,
            monitor,
            points,
            pass_config.temperature_mode,
            expected,
            pass_settings,
            label=f"{context}_p{pass_index}",
            force_mode_selection=True,
        )
        after_state = _capture_case_ro_state(
            f"{context}_p{pass_index}_after_temperature_reassert",
            hwnd,
            monitor,
            points,
            case,
            pass_index=pass_index,
            pass_config=pass_config,
            metadata={
                "phase": "after_temperature_reassert",
                "expected_temperature_c": expected,
                "temperature_mode": pass_config.temperature_mode,
            },
        )
        diff_ro_states(
            before_state,
            after_state,
            label=f"{context}_p{pass_index}_temperature_reassert",
        )

    # Authoritative persistence check: tab changes force WAVE to discard any
    # uncommitted display-only value and reload the bound pass model.
    observed: list[dict[str, Any]] = []
    for pass_index in range(1, case.pass_count + 1):
        _select_pass(points, pass_index, settings.pause)
        wait(max(0.65, settings.pause))
        actual = verify_numeric_point(
            f"{context}_p{pass_index}_temperature_after_tab_roundtrip",
            points["ro_temperature_value"],
            expected,
        )
        observed.append({"pass": pass_index, "temperature_c": actual})

    roundtrip_state = _capture_case_ro_state(
        f"{context}_after_temperature_tab_roundtrip",
        hwnd,
        monitor,
        points,
        case,
        pass_index=case.pass_count,
        pass_config=case.passes[-1],
        metadata={"phase": "after_temperature_tab_roundtrip", "observed": observed},
    )
    record_event(
        "ro_temperature_persistent_reassert_v44",
        case_id=case.case_id,
        context=context,
        expected=expected,
        before=before_by_pass,
        observed=observed,
        commit="enter_then_tab_then_pass_roundtrip",
    )
    screenshot(f"{context}_temperature_persistent", monitor, hwnd)






def configure_schema_ro_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: ROCaseConfig,
    settings: Settings,
) -> None:
    """Generic RO path for multi-stage/pass and optional chemistry cases."""
    logging.info(
        "=== Schema RO 사례 입력 시작: %s tier=%s ===",
        case.case_id,
        case.automation_tier,
    )
    focus_wave(hwnd)
    rect = _get_window_rect(hwnd)
    native_click_at(rect.left + min(500, rect.width // 2), rect.top + 16)
    wait(0.25)
    click_until_visual_change(points, "feed_setup_tab", hwnd, monitor, settings.pause)
    if not settings.add_ro:
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)

    def load_profile() -> None:
        dialog = click_expect_new_dialog(
            points, "open_water_library", hwnd, monitor, settings.pause
        )
        select_library_profile(dialog, case.water_profile, settings.long_wait)
        copy_library_to_feed(dialog, settings.long_wait, hwnd, monitor)

    try:
        load_profile()
    except LibraryTemperatureTransitionError:
        focus_wave(hwnd)
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)
        load_profile()

    focus_wave(hwnd)
    set_feed_temperature_envelope(
        hwnd,
        monitor,
        points,
        case.resolved_feed_temperature_min_c,
        case.feed_temperature_design_c,
        case.resolved_feed_temperature_max_c,
        settings.pause,
        context=f"schema_{case.case_id}_feed_temperature",
    )
    enter_home_with_recovery(hwnd, monitor, points, settings)
    replace_value(
        points, "home_feed_flow", _fmt_value(case.feed_flow_m3h), settings.pause
    )
    if settings.add_ro:
        add_ro_with_recovery(hwnd, monitor, points, settings)
    click_until_visual_change(
        points,
        "reverse_osmosis_tab",
        hwnd,
        monitor,
        settings.pause,
        minimum_change=0.004,
    )
    # V52: WAVE persists pass topology across cases.  Reconcile every case,
    # including a single-case run started from an existing two-pass project.
    _reconcile_ro_pass_topology(
        hwnd, monitor, points, case.pass_count, settings
    )
    open_and_configure_ro_flow_case(hwnd, monitor, points, case, settings)
    for pass_index, pass_config in enumerate(case.passes, start=1):
        _configure_pass_screen(hwnd, monitor, points, pass_index, pass_config, settings)

    # Stage-count and membrane edits can make WAVE recalculate flow targets.
    # Reassert requested recoveries after topology is final, then confirm that
    # the flow update did not alter PV/Elements values.
    logging.info("Stage 토폴로지 확정 후 Recovery 재확정: %s", case.case_id)
    open_and_configure_ro_flow_case(hwnd, monitor, points, case, settings)
    _stabilize_after_flow_commit(
        hwnd,
        monitor,
        points,
        case,
        settings,
        context="post_recovery_v44",
    )
    # Verify the displayed Element Type as well as numbers.  If a membrane is
    # repaired, reassert Recovery and repeat until the coupled state converges.
    for integrity_cycle in range(1, 4):
        repaired_state = False
        for pass_index, pass_config in enumerate(case.passes, start=1):
            repaired_state = (
                _verify_stage_grid_membranes(
                    hwnd,
                    monitor,
                    points,
                    pass_index,
                    pass_config,
                    settings,
                    repair=True,
                    context=f"post_recovery_cycle_{integrity_cycle}",
                )
                or repaired_state
            )
            repaired_state = (
                _verify_stage_grid_numeric_values(
                    hwnd,
                    monitor,
                    points,
                    pass_index,
                    pass_config,
                    settings,
                    repair=True,
                    context=f"post_recovery_cycle_{integrity_cycle}",
                )
                or repaired_state
            )
        if not repaired_state:
            logging.info(
                "다중 Pass 최종 Stage 무결성 확정: case=%s cycle=%s",
                case.case_id,
                integrity_cycle,
            )
            break
        logging.info(
            "막/Stage 값 재설정 후 Recovery 재확정: case=%s cycle=%s",
            case.case_id,
            integrity_cycle,
        )
        open_and_configure_ro_flow_case(
            hwnd,
            monitor,
            points,
            case,
            settings,
            context=f"integrity_cycle_{integrity_cycle}",
        )
        _stabilize_after_flow_commit(
            hwnd,
            monitor,
            points,
            case,
            settings,
            context=f"integrity_cycle_{integrity_cycle}_v44",
        )
    else:
        try:
            _capture_case_ro_state(
                f"{case.case_id}_convergence_failure_final",
                hwnd,
                monitor,
                points,
                case,
                pass_index=case.pass_count,
                pass_config=case.passes[-1],
                metadata={
                    "phase": "convergence_failure_final",
                    "integrity_cycles": 3,
                },
            )
            write_convergence_failure_report(
                case,
                context="multi_pass_integrity_3_cycles",
                extra={
                    "hint": (
                        "Inspect ro_state_diff files in sequence. V52 snapshots include "
                        "actual selected stage radio, WPF control bounds/AutomationIds, "
                        "and every calibrated coordinate ancestor chain."
                    )
                },
            )
        except Exception as diagnostic_exc:
            record_event(
                "diagnostic_warning",
                operation="final_convergence_capture",
                case_id=case.case_id,
                error=f"{type(diagnostic_exc).__name__}: {diagnostic_exc}",
            )
        raise WaveAutomationError(
            f"{case.case_id} 다중 Pass 막/Stage/Recovery 무결성이 3회 내 수렴하지 않았습니다."
        )
    # Return to Pass 1 for deterministic report/chemistry transitions.
    if case.pass_count > 1:
        _select_pass(points, 1, settings.pause)

    # Chemical/Degas is a system-level ribbon dialog, not a per-pass control.
    # Apply it once after all pass/stage settings have been committed.
    _apply_chemical_adjustment(hwnd, monitor, points, case, settings)
    _apply_special_features(hwnd, monitor, points, case, settings)
    enter_summary_report_case(hwnd, monitor, points, case, settings)
    logging.info("=== Schema RO 사례 입력 완료: %s ===", case.case_id)
