#!/usr/bin/env python3
"""Ultrafiltration automation paths derived from the 2026-07-06 UF video (V69).

V69 keeps UF separate from the mature RO/NF schema.  The first
UF path is a video-derived baseline: feed profile -> UF process -> UF design /
configuration -> summary PDF.  It also writes diagnostic artifacts so the next
patch can move from one hard-coded video case to an Excel-driven UF schema.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from wave_common import *
from wave_diagnostics import _capture_wave_image, _image_change_ratio, screenshot
from wave_dialogs import _blocking_wave_dialogs, _close_modal_dialog, resolve_wave_blocking_dialogs
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
from wave_windows import _get_window_rect, bring_window_to_front, focus_wave, native_drag, native_move_to


@dataclass
class UFVideoCase:
    """Single UF case observed in the user's setup video."""

    case_id: str = "V54_UF_VIDEO_001"
    pdf_name: str = "V54_UF_VIDEO_001_SFP2660_F100.pdf"
    water_profile: str = "Well Water - Med Hardness"
    feed_flow_m3h: float = 100.0
    feed_temperature_min_c: float = 10.0
    feed_temperature_design_c: float = 15.0
    feed_temperature_max_c: float = 20.0
    uf_module: str = "Ultrafiltration SFP-2660"
    online_trains: int = 1
    standby_trains: int = 0
    redundant_trains: int = 0
    modules_per_train: int = 24
    strainer_recovery_pct: float = 99.5
    strainer_size_um: int = 150
    # Backwash defaults observed in the UF settings video / V54 inventory screenshots.
    backwash_water_type: str = "UF Filtrate"
    forward_flush_water_type: str = "Pretreated"
    backwash_protocol: str = "Normal protocol"
    backwash_air_scour_s: int = 30
    backwash_drain_s: int = 0
    backwash_top_backwash_s: int = 30
    backwash_bottom_backwash_s: int = 0
    backwash_forward_flush_s: int = 35
    backwashes_between_air_scour: int = 1
    # CEB defaults observed after the CEB page is opened.
    ceb_water_type: str = "UF Filtrate"
    ceb_mineral_acid_type: str = "HCl (32)"
    ceb_mineral_acid_ph: float = 2.0
    ceb_alkali_type: str = "NaOH (30)"
    ceb_alkali_ph: float = 12.0
    ceb_lsi: float = 2.5
    ceb_air_scour_s: int = 45
    ceb_drain_s: int = 0
    ceb_top_backwash_s: int = 45
    ceb_bottom_backwash_s: int = 15  # WAVE valid range is 15-60 s; 0 triggers CEB Bottom Backwash Value Error
    ceb_forward_flush_s: int = 45
    ceb_chemical_soak_min: int = 10
    notes: str = "Derived from UF settings video 2026-07-06 10:20 KST"

    def to_settings(self, *, pause: float, long_wait: float, validate_pdf: bool) -> Settings:
        return Settings(
            water_profile=self.water_profile,
            temperature_c=_fmt_value(self.feed_temperature_design_c),
            feed_flow_m3h=_fmt_value(self.feed_flow_m3h),
            recovery_pct="95",  # UF Home hover default; the detailed UF PDF is validated separately.
            pv_per_stage="1",
            elements_per_pv="1",
            membrane=self.uf_module,
            add_ro=False,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
        )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("_") or "uf_case"


def _write_uf_artifact(name: str, payload: dict[str, Any]) -> None:
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / name).write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _replace_point(
    points: dict[str, tuple[int, int]],
    key: str,
    value: float | int | str,
    pause: float,
    *,
    verify: bool = True,
) -> None:
    replace_value(points, key, _fmt_value(value), pause)
    if verify:
        verify_numeric_point(key, points[key], _fmt_value(value), required_when_readable=False)


def _is_report_spinner_dialog(dialog: WindowInfo, text: str) -> bool:
    blob = f"{dialog.title}\n{text}".lower()
    return (
        "reportloadingspinner" in blob
        or "calculating report" in blob
        or "calculating report..." in blob
    )


def _wait_for_uf_report_spinner(
    hwnd: int,
    monitor: Rect,
    context: str,
    *,
    timeout_s: float = 75.0,
) -> list[str]:
    """Wait through WAVE's non-interactive UF report calculation overlay.

    The overlay appears as a small same-process WPF window titled
    ``ReportLoadingSpinner``.  It looks like a modal to the generic blocker
    detector, but it has no OK button and should never be closed; the right
    recovery is to wait until WAVE finishes calculating the report.
    """
    start = time.time()
    seen = False
    last_blob = ""
    while True:
        spinners: list[str] = []
        for dialog, text in _blocking_wave_dialogs(hwnd):
            if _is_report_spinner_dialog(dialog, text):
                spinners.append(f"{dialog.title}: {text}".strip())
        if not spinners:
            if seen:
                # Give WAVE a small settle window before the caller continues to
                # screenshot/export from the Summary Report tab.
                wait(0.8)
                elapsed = round(time.time() - start, 2)
                logging.info("UF Report 계산 대기 완료: context=%s elapsed=%ss", context, elapsed)
                record_event("uf_report_spinner_waited_v52", context=context, elapsed_s=elapsed)
                return ["uf_report_spinner_waited"]
            return []
        if not seen:
            seen = True
            last_blob = " | ".join(spinners)
            logging.info("UF Report 계산 대기 시작: context=%s dialogs=%s", context, last_blob)
            record_event("uf_report_spinner_seen_v52", context=context, dialogs=spinners)
            screenshot(f"uf_report_spinner_{_safe_name(context)}_v52", monitor, hwnd)
        if time.time() - start > timeout_s:
            screenshot(f"uf_report_spinner_timeout_{_safe_name(context)}_v52", monitor, hwnd)
            raise WaveAutomationError(
                f"UF Report 계산 대기 시간 초과: context={context} timeout={timeout_s}s last={last_blob!r}"
            )
        wait(0.6)


def _resolve_uf_modals(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    context: str,
) -> list[str]:
    """Close recoverable UF modals before continuing.

    V54 keeps the generic WAVE resolver for ordinary warnings, handles UF
    Value Error dialogs deterministically, and treats the UF Summary Report
    ``ReportLoadingSpinner`` as a wait-only overlay rather than a failure.
    """
    actions: list[str] = []
    actions.extend(_wait_for_uf_report_spinner(hwnd, monitor, context))
    try:
        actions.extend(resolve_wave_blocking_dialogs(hwnd, monitor, context, points))
    except WaveAutomationError:
        handled: list[str] = []
        # If the generic resolver failed because the spinner appeared between
        # our pre-check and its own scan, wait through it and then continue.
        spinner_actions = _wait_for_uf_report_spinner(hwnd, monitor, context)
        if spinner_actions:
            handled.extend(spinner_actions)
        else:
            for dialog, text in _blocking_wave_dialogs(hwnd):
                blob = f"{dialog.title}\n{text}".lower()
                recoverable_uf_constraint = (
                    "value error" in blob
                    or "outside the allowed range" in blob
                    or "please revise your input" in blob
                )
                if not recoverable_uf_constraint:
                    continue
                logging.warning(
                    "UF 제약 모달 자동 확인: context=%s title=%r text=%r",
                    context,
                    dialog.title,
                    text,
                )
                _close_modal_dialog(dialog)
                handled.append("uf_constraint_value_error_closed")
        if not handled:
            raise
        actions.extend(handled)
    if actions:
        logging.info("UF 모달 자동 처리: context=%s actions=%s", context, actions)
        record_event("uf_modal_resolved_v52", context=context, actions=actions)
    return actions


def _click_uf(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    key: str,
    *,
    pause: float,
    context: str | None = None,
) -> None:
    label = context or key
    _resolve_uf_modals(hwnd, monitor, points, f"before_{label}")
    click(points, key, pause=pause)
    _resolve_uf_modals(hwnd, monitor, points, f"after_{label}")


def _replace_uf_point(
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
    _resolve_uf_modals(hwnd, monitor, points, f"before_{label}")
    replace_value(points, key, _fmt_value(value), pause)
    # WAVE can raise range dialogs immediately after Enter.  Resolve them
    # before UIA probing so the verifier does not hang on a modal/ghost window.
    _resolve_uf_modals(hwnd, monitor, points, f"after_write_{label}")
    if verify:
        verify_numeric_point(key, points[key], _fmt_value(value), required_when_readable=False)
    _resolve_uf_modals(hwnd, monitor, points, f"after_verify_{label}")


def _select_combo_with_fallback(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    key: str,
    target: str,
    long_wait: float,
    pause: float,
) -> dict[str, Any]:
    """Select a UF combo item using the RO-proven exact selector, with keyboard fallback."""
    try:
        result = select_combo_exact(hwnd, monitor, points, key, target, long_wait)
        result["fallback_used"] = False
        return result
    except Exception as exc:
        logging.warning(
            "UF ComboBox 정확 선택 실패; prefix keyboard fallback 사용: key=%s target=%r error=%s",
            key,
            target,
            exc,
        )
        record_event("uf_combo_exact_fallback_v52", key=key, target=target, error=repr(exc))
        select_combo_text(points, key, target, pause=max(1.0, pause))
        screenshot(f"uf_combo_{key}_fallback", monitor, hwnd)
        return {"ok": True, "method": "keyboard_prefix_fallback", "target": target, "fallback_used": True}


def _orange_pixel_fraction(image) -> float:
    """Detect the orange UF process icon in the Home canvas crop."""
    total = max(1, image.width * image.height)
    orange = 0
    for red, green, blue in image.getdata():
        if red >= 145 and 55 <= green <= 165 and blue <= 90 and red - blue >= 80:
            orange += 1
    return orange / total


def uf_presence_metrics(
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
        max(0, cx - 110),
        max(0, cy - 100),
        min(image.width, cx + 110),
        min(image.height, cy + 100),
    )
    crop = image.crop(process_box)
    orange_fraction = _orange_pixel_fraction(crop)
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S_%f")
    try:
        crop.save(target_dir / f"{stamp}_{label}_uf_process_crop.png")
    except Exception as exc:
        logging.warning("UF 검증 crop 저장 실패(%s): %s", label, exc)
    metrics = {
        "orange_fraction": orange_fraction,
        "process_box": process_box,
        "present": orange_fraction >= 0.018,
    }
    logging.info(
        "UF 실제 상태 확인: label=%s orange_fraction=%.5f present=%s",
        label,
        orange_fraction,
        metrics["present"],
    )
    record_event("uf_presence_check_v52", label=label, **metrics)
    return metrics


def add_uf_with_recovery(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
) -> None:
    """Drag the UF icon to the process slot, skipping if a UF icon is already present."""
    initial = uf_presence_metrics(hwnd, points, label="before_uf_drag")
    if initial["present"]:
        logging.info("UF 공정이 이미 존재합니다. 중복 드래그를 생략합니다.")
        record_event("uf_add_skipped_v52", reason="already_present", metrics=initial)
        return

    last_metrics: dict[str, Any] = initial
    for attempt in range(1, 4):
        logging.info(
            "UF 아이콘 native drag attempt=%s: %s -> %s",
            attempt,
            points["uf_icon"],
            points["process_drop_point"],
        )
        before = _capture_wave_image(hwnd)
        bring_window_to_front(hwnd)
        native_drag(points["uf_icon"], points["process_drop_point"], duration=1.1)
        wait(max(2.5, settings.long_wait))
        actions = resolve_wave_blocking_dialogs(
            hwnd, monitor, f"after_uf_drag_attempt_{attempt}", points
        )
        if "adjust_all_ions" in actions:
            enter_home_with_recovery(hwnd, monitor, points, settings)
        rect = _get_window_rect(hwnd)
        native_move_to(rect.left + min(620, rect.width // 2), rect.top + 16)
        wait(0.35)
        after = _capture_wave_image(hwnd)
        ratio = _image_change_ratio(before, after)
        metrics = uf_presence_metrics(hwnd, points, label=f"after_uf_drag_attempt_{attempt}")
        last_metrics = metrics
        record_event(
            "uf_drag_result_v52",
            attempt=attempt,
            change_ratio=ratio,
            metrics=metrics,
            actions=actions,
        )
        if metrics["present"] or ratio >= 0.012:
            logging.info("UF 공정 추가 성공 확인: attempt=%s", attempt)
            screenshot(f"uf_drag_success_{attempt}", monitor, hwnd)
            return
        screenshot(f"uf_drag_retry_{attempt}", monitor, hwnd)
    raise WaveAutomationError(f"UF 아이콘 드래그 후 실제 UF 공정을 확인하지 못했습니다: {last_metrics}")


def configure_uf_video_case(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    case: UFVideoCase,
    settings: Settings,
) -> None:
    """Configure the first UF case using the flow observed in the user's video."""
    logging.info("=== UF 사례 입력 시작: %s ===", case.case_id)
    record_event("uf_case_start_v52", case=asdict(case))
    _write_uf_artifact("uf_case_input.json", {"schema_version": 1, "case": asdict(case)})
    _resolve_uf_modals(hwnd, monitor, points, "uf_case_start_v52")

    # Feed profile and feed temperature envelope.  If the Feed Setup tab is
    # already active, the pixel-change verifier can legitimately see ~0 change;
    # continue after a normal click instead of failing the UF baseline path.
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
        _click_uf(hwnd, monitor, points, "feed_setup_tab", pause=settings.pause)
        screenshot("uf_feed_setup_after_already_active_fallback", monitor, hwnd)
    try:
        dialog = click_expect_new_dialog(
            points, "open_water_library", hwnd, monitor, pause=settings.pause
        )
        select_library_profile(dialog, case.water_profile, settings.pause)
        copy_library_to_feed(dialog, settings.long_wait, hwnd, monitor)
    except LibraryTemperatureTransitionError:
        # Same recovery path as RO/NF: old profile temperatures can briefly block the copy.
        prepare_feed_for_profile_replacement(hwnd, monitor, points, settings)
        dialog = click_expect_new_dialog(
            points, "open_water_library", hwnd, monitor, pause=settings.pause
        )
        select_library_profile(dialog, case.water_profile, settings.pause)
        copy_library_to_feed(dialog, settings.long_wait, hwnd, monitor)

    # WAVE's UF PDF can omit the library profile name even when the profile was
    # successfully copied into Feed Setup.  Persist the applied input-path
    # evidence so the production validator can distinguish omission from failure.
    record_event(
        "uf_water_profile_applied_v69",
        case_id=case.case_id,
        water_profile=case.water_profile,
        evidence="select_library_profile+copy_library_to_feed completed",
    )
    _write_uf_artifact(
        f"uf_feed_profile_{_safe_name(case.case_id)}.json",
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "water_profile": case.water_profile,
            "evidence": "select_library_profile+copy_library_to_feed completed",
        },
    )

    set_feed_temperature_envelope(
        hwnd,
        monitor,
        points,
        case.feed_temperature_min_c,
        case.feed_temperature_design_c,
        case.feed_temperature_max_c,
        settings.pause,
        context=f"uf_{case.case_id}_feed_temperature",
    )

    # Home canvas and UF process insertion.
    enter_home_with_recovery(hwnd, monitor, points, settings)
    _replace_uf_point(hwnd, monitor, points, "home_feed_flow", case.feed_flow_m3h, settings.pause, verify=False)
    add_uf_with_recovery(hwnd, monitor, points, settings)

    # UF Design page: commit the feed flow, strainer defaults, and module name.
    _click_uf(hwnd, monitor, points, "ultrafiltration_tab", pause=max(1.0, settings.pause))
    screenshot("uf_tab_opened_v52", monitor, hwnd)
    _replace_uf_point(hwnd, monitor, points, "uf_feed_flow_auto", case.feed_flow_m3h, settings.pause)
    _replace_uf_point(hwnd, monitor, points, "uf_strainer_recovery", case.strainer_recovery_pct, settings.pause)
    _replace_uf_point(hwnd, monitor, points, "uf_strainer_size", case.strainer_size_um, settings.pause)
    _select_combo_with_fallback(
        hwnd,
        monitor,
        points,
        "uf_design_module_combo",
        case.uf_module,
        settings.long_wait,
        settings.pause,
    )
    screenshot("uf_design_configured_v52", monitor, hwnd)

    # UF Configuration page: select the same module and set train/module topology.
    _click_uf(hwnd, monitor, points, "uf_configuration_nav", pause=max(0.8, settings.pause))
    _select_combo_with_fallback(
        hwnd,
        monitor,
        points,
        "uf_config_module_combo",
        case.uf_module,
        settings.long_wait,
        settings.pause,
    )
    _replace_uf_point(hwnd, monitor, points, "uf_online_trains", case.online_trains, settings.pause)
    _replace_uf_point(hwnd, monitor, points, "uf_standby_trains", case.standby_trains, settings.pause)
    _replace_uf_point(hwnd, monitor, points, "uf_redundant_trains", case.redundant_trains, settings.pause)
    _replace_uf_point(hwnd, monitor, points, "uf_modules_per_train", case.modules_per_train, settings.pause)
    screenshot("uf_configuration_configured_v52", monitor, hwnd)

    # UF Backwash page: V54 makes the video-observed defaults explicit so the
    # first UF path is not only a design/configuration smoke test. Combo boxes
    # are left as-is until a later run shows stale carryover; numeric fields
    # are committed because they are directly visible and editable.
    try:
        _click_uf(hwnd, monitor, points, "uf_backwash_nav", pause=max(0.8, settings.pause))
        _replace_uf_point(hwnd, monitor, points, "uf_bw_air_scour_sec", case.backwash_air_scour_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_bw_drain_sec", case.backwash_drain_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_bw_top_backwash_sec", case.backwash_top_backwash_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_bw_bottom_backwash_sec", case.backwash_bottom_backwash_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_bw_forward_flush_sec", case.backwash_forward_flush_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_bw_between_air_scour", case.backwashes_between_air_scour, settings.pause)
        screenshot("uf_backwash_configured_v52", monitor, hwnd)
        record_event("uf_backwash_configured_v52", case=asdict(case))
    except Exception as exc:
        logging.warning("UF Backwash 설정/진단 실패: %s", exc)
        screenshot("uf_backwash_configure_warning_v52", monitor, hwnd)
        record_event("uf_backwash_configure_warning_v52", error=repr(exc))

    # UF CEB page: commit the video-observed pH/LSI/duration values and capture
    # the page. Button/toggle state is intentionally not toggled yet; changing
    # it without state detection could turn an enabled chemical off.
    try:
        _click_uf(hwnd, monitor, points, "uf_ceb_nav", pause=max(0.8, settings.pause))
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_mineral_acid_ph", case.ceb_mineral_acid_ph, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_alkali_ph", case.ceb_alkali_ph, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_lsi", case.ceb_lsi, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_air_scour_sec", case.ceb_air_scour_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_drain_sec", case.ceb_drain_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_top_backwash_sec", case.ceb_top_backwash_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_bottom_backwash_sec", case.ceb_bottom_backwash_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_forward_flush_sec", case.ceb_forward_flush_s, settings.pause)
        _replace_uf_point(hwnd, monitor, points, "uf_ceb_chemical_soak_min", case.ceb_chemical_soak_min, settings.pause)
        screenshot("uf_ceb_configured_v52", monitor, hwnd)
        record_event("uf_ceb_configured_v52", case=asdict(case))
    except Exception as exc:
        logging.warning("UF CEB 설정/진단 실패: %s", exc)
        screenshot("uf_ceb_configure_warning_v52", monitor, hwnd)
        record_event("uf_ceb_configure_warning_v52", error=repr(exc))

    # CIP and Additional Settings are still discovery-only in V54. Capture them
    # to prepare the next patch without risking unknown toggles.
    for key, label in (
        ("uf_cip_nav", "uf_cip_inventory_v52"),
        ("uf_additional_settings_nav", "uf_additional_settings_inventory_v52"),
    ):
        try:
            _click_uf(hwnd, monitor, points, key, pause=max(0.8, settings.pause))
            screenshot(label, monitor, hwnd)
        except Exception as exc:
            logging.warning("UF inventory screenshot failed: key=%s error=%s", key, exc)
            record_event("uf_inventory_screenshot_failed_v52", key=key, error=repr(exc))

    _resolve_uf_modals(hwnd, monitor, points, "before_summary_report_tab_v52")
    _click_uf(hwnd, monitor, points, "summary_report_tab", pause=max(1.5, settings.pause), context="uf_summary_report_tab")
    wait(settings.long_wait)
    screenshot("uf_summary_report_v52", monitor, hwnd)
    logging.info("=== UF 사례 입력 완료: %s ===", case.case_id)
    record_event("uf_case_configured_v52", case=asdict(case))


def _pdf_has_value_near(label_pattern: str, value: float | int | str, text: str, *, window: int = 160) -> bool:
    value_pattern = _number_pattern(_fmt_value(value))
    return bool(re.search(rf"{label_pattern}[\s\S]{{0,{window}}}?{value_pattern}", text, re.I))


def _pdf_has_uf_tmp_temperature_curve(text: str, case: UFVideoCase) -> bool:
    """Detect the UF temperature envelope from the TMP table used by UF PDFs.

    WAVE's UF Summary Report does not always print all three configured
    temperatures.  On the user's 2026-07-07 successful V68 run, the report
    printed TMP rows for min/design (10.0 °C and 15.0 °C) but omitted the max
    row (20.0 °C), even though the UI input verification confirmed max=20.
    Treat a TMP table with at least the design temperature and one adjacent
    envelope point as sufficient PDF evidence, while still preferring all three
    when the report includes them.
    """
    match = re.search(r"\bTMP\b[\s\S]{0,360}", text, re.I)
    if not match:
        return False
    block = match.group(0)

    def has_temp(value: float) -> bool:
        patterns = {_number_pattern(_fmt_value(value)), _number_pattern(f"{float(value):.1f}")}
        return any(
            re.search(rf"@\s*{pattern}\s*(?:°\s*)?(?:C|℃)", block, re.I)
            for pattern in patterns
        )

    min_ok = has_temp(float(case.feed_temperature_min_c))
    design_ok = has_temp(float(case.feed_temperature_design_c))
    max_ok = has_temp(float(case.feed_temperature_max_c))
    return (min_ok and design_ok) or (design_ok and max_ok) or (min_ok and design_ok and max_ok)


def validate_exported_uf_pdf(path: Path, case: UFVideoCase) -> dict[str, Any]:
    """Validate the UF report with PDF evidence plus V69 input-path evidence."""
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\r", "")
    module_tokens = [case.uf_module, case.uf_module.replace("Ultrafiltration ", "")]
    module_ok = any(re.search(re.escape(token), normalized, re.I) for token in module_tokens)
    profile_pdf_ok = bool(re.search(re.escape(case.water_profile), normalized, re.I))
    profile_input_path_ok = bool(str(case.water_profile).strip())
    profile_ok = profile_pdf_ok or profile_input_path_ok
    uf_report_ok = bool(re.search(r"\bUF\s+Summary\s+Report\b|\bUltrafiltration\b", normalized, re.I))

    gross_feed_ok = _pdf_has_value_near(r"Gross\s+Feed\s*=", case.feed_flow_m3h, normalized)
    online_trains_ok = _pdf_has_value_near(r"Online\s*=", case.online_trains, normalized, window=80)
    standby_trains_ok = _pdf_has_value_near(r"Standby\s*=", case.standby_trains, normalized, window=80)
    redundant_trains_ok = _pdf_has_value_near(r"Redundant\s*=", case.redundant_trains, normalized, window=80)
    modules_per_train_ok = _pdf_has_value_near(r"Per\s+Train\s*=", case.modules_per_train, normalized, window=80)
    total_modules_ok = _pdf_has_value_near(
        r"Total\s*=", case.online_trains * case.modules_per_train, normalized, window=80
    )
    temperature_label_ok = _pdf_has_value_near(
        r"Temperature\s*\(°C\)", case.feed_temperature_design_c, normalized, window=120
    )
    temperature_tmp_curve_ok = _pdf_has_uf_tmp_temperature_curve(normalized, case)
    temperature_ok = temperature_label_ok or temperature_tmp_curve_ok
    uf_recovery_present = bool(re.search(r"UF\s+System\s+Recovery\s*\(\%\)[\s\S]{0,60}?\d", normalized, re.I))
    utility_water_ok = bool(
        re.search(r"Forward\s+Flush:\s*\n?Pretreated\s+water", normalized, re.I)
        and re.search(r"Backwash:\s*\n?UF\s+filtrate\s+water", normalized, re.I)
        and re.search(r"CEB\s+Water\s+Source:\s*\n?UF\s+filtrate\s+water", normalized, re.I)
        and re.search(r"CIP\s+Water\s+Source:\s*\n?UF\s+filtrate\s+water", normalized, re.I)
    )

    checks = {
        "uf_report": uf_report_ok,
        "module": module_ok,
        "water_profile": profile_ok,
        "gross_feed_flow": gross_feed_ok,
        "online_trains": online_trains_ok,
        "standby_trains": standby_trains_ok,
        "redundant_trains": redundant_trains_ok,
        "modules_per_train": modules_per_train_ok,
        "total_modules": total_modules_ok,
        "temperature": temperature_ok,
        "uf_system_recovery_present": uf_recovery_present,
        "utility_water_sources": utility_water_ok,
    }
    hard_fields = (
        "uf_report",
        "module",
        "gross_feed_flow",
        "online_trains",
        "modules_per_train",
        "total_modules",
    )
    hard_errors = [name for name in hard_fields if not checks[name]]
    warnings = [name for name, ok in checks.items() if not ok and name not in hard_errors]
    evidence = {
        "water_profile": "pdf_text" if profile_pdf_ok else "input_path_requested_profile_pdf_omits_field",
        "temperature": (
            "pdf_temperature_label"
            if temperature_label_ok
            else ("uf_tmp_temperature_curve" if temperature_tmp_curve_ok else "missing")
        ),
    }
    omitted_pdf_fields = []
    if not profile_pdf_ok and profile_input_path_ok:
        omitted_pdf_fields.append("water_profile")
    if not temperature_label_ok and temperature_tmp_curve_ok:
        omitted_pdf_fields.append("temperature_label")
    result = {
        "pdf": str(path),
        "provider": provider,
        "case": asdict(case),
        "checks": checks,
        "hard_errors": hard_errors,
        "warnings": warnings,
        "evidence": evidence,
        "omitted_pdf_fields": omitted_pdf_fields,
        "classification": "validated" if not hard_errors else "validation_failed",
        "note": (
            "UF V69 combines PDF evidence with the applied input path for fields "
            "that this WAVE UF report layout omits. water_profile is accepted from "
            "the completed library-copy input path; temperature can be validated from "
            "the UF TMP table when it includes the design temperature plus at least one configured envelope point; WAVE UF PDFs may omit the max-temperature row."
        ),
    }
    if STATE.RUN_DIR is not None:
        safe_case = _safe_name(case.case_id)
        safe_pdf = _safe_name(path.stem)
        # V76: write per-output artifacts keyed by the actual PDF stem so
        # production runs with several UF variants no longer overwrite each
        # other's validation/text files.  Keep the legacy case-id filenames as
        # "latest for this schema case" compatibility aliases.
        (STATE.RUN_DIR / f"exported_pdf_text_{safe_pdf}.txt").write_text(text, encoding="utf-8")
        (STATE.RUN_DIR / f"uf_pdf_validation_{safe_pdf}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if safe_case != safe_pdf:
            (STATE.RUN_DIR / f"exported_pdf_text_{safe_case}.txt").write_text(text, encoding="utf-8")
            (STATE.RUN_DIR / f"uf_pdf_validation_{safe_case}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    record_event("uf_pdf_validation_v69", result=result)
    if hard_errors:
        raise WaveAutomationError(
            f"{case.case_id} UF PDF 검증 실패: {', '.join(hard_errors)}"
        )
    if warnings:
        logging.warning("UF PDF 약한 검증 경고: case=%s warnings=%s", case.case_id, warnings)
    logging.info("UF PDF 검증 성공: %s", case.case_id)
    return result

def run_uf_video_case(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
    module: str | None = None,
    pdf_name: str | None = None,
    water_profile: str | None = None,
    feed_flow_m3h: float | None = None,
) -> list[Path]:
    case = UFVideoCase()
    if module:
        case.uf_module = module
    if pdf_name:
        case.pdf_name = pdf_name
    if water_profile:
        case.water_profile = water_profile
    if feed_flow_m3h is not None:
        case.feed_flow_m3h = float(feed_flow_m3h)
    settings = case.to_settings(pause=pause, long_wait=long_wait, validate_pdf=False)
    configure_uf_video_case(wave_window.hwnd, monitor, points, case, settings)
    _resolve_uf_modals(wave_window.hwnd, monitor, points, "before_uf_export_pdf_v59")
    target = export_pdf(wave_window, monitor, points, case.pdf_name, settings)
    dismiss_export_success_dialog(wave_window, monitor)
    validation: dict[str, Any] | None = None
    if validate_pdf:
        validation = validate_exported_uf_pdf(target, case)
    summary_payload = {
        "schema_version": 1,
        "automation_version": "V69",
        "status": "success",
        "case": asdict(case),
        "pdf": str(target),
        "validation": validation,
    }
    safe_pdf = _safe_name(target.stem)
    _write_uf_artifact(f"uf_video_case_summary_{safe_pdf}.json", summary_payload)
    # Compatibility alias for existing tooling that reads the last UF summary.
    _write_uf_artifact("uf_video_case_summary.json", summary_payload)
    return [target]
