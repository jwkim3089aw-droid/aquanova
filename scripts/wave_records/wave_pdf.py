#!/usr/bin/env python3
"""Refactored WAVE automation module: pdf."""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import _capture_wave_image, _image_change_ratio, dump_windows, save_click_map, screenshot
from wave_dialogs import _close_modal_dialog, _dialog_text_blob, _wait_for_pdf_save_dialog, wait_for_report_loading_spinner
from wave_interaction import _visible_window_handles, click, wait
from wave_runtime import record_event
from wave_windows import _set_clipboard_unicode, bring_window_to_front, focus_wave, get_monitor_rect_for_window, list_visible_windows

def wait_for_file(path: Path, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.25)
    return False


def open_pdf_save_dialog(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    settings: Settings,
    retries: int = 3,
) -> WindowInfo:
    """Open Export to PDF without requiring the Report tab to visually change.

    WAVE automatically activates the Report ribbon after Summary Report is
    calculated. Clicking an already-active tab produces almost no pixel change,
    which previously caused a false failure. Here success is defined by the
    actual Save As dialog appearing.
    """
    for attempt in range(1, retries + 1):
        focus_wave(wave_window.hwnd)

        before_image = _capture_wave_image(wave_window.hwnd)
        click(points, "report_ribbon_tab", settings.pause)
        wait(max(0.8, settings.pause))
        after_image = _capture_wave_image(wave_window.hwnd)
        ratio = _image_change_ratio(before_image, after_image)
        logging.info(
            "Report 리본 준비 attempt=%s change_ratio=%.5f "
            "(이미 활성 상태면 0에 가까워도 정상)",
            attempt,
            ratio,
        )
        record_event(
            "report_ribbon_ready",
            attempt=attempt,
            change_ratio=ratio,
            active_tab_may_already_be_selected=True,
        )
        screenshot(
            f"08_report_ribbon_attempt_{attempt}",
            monitor,
            wave_window.hwnd,
        )

        wait_for_report_loading_spinner(
            wave_window.hwnd,
            monitor,
            f"before_export_to_pdf_attempt_{attempt}",
            timeout_s=max(90.0, settings.long_wait * 10.0),
        )
        handles_before = _visible_window_handles()
        click(points, "export_to_pdf", settings.pause)
        dialog = _wait_for_pdf_save_dialog(
            wave_window,
            handles_before,
            timeout=max(6.0, settings.long_wait * 2),
        )
        if dialog is not None:
            logging.info(
                "Export to PDF 성공: attempt=%s hwnd=%s title=%r class=%r rect=%s",
                attempt,
                dialog.hwnd,
                dialog.title,
                dialog.class_name,
                dialog.rect,
            )
            record_event(
                "pdf_save_dialog_detected",
                attempt=attempt,
                dialog=dialog,
            )
            return dialog

        logging.warning(
            "Export to PDF 후 저장창 미감지: attempt=%s. Report 리본을 다시 준비합니다.",
            attempt,
        )
        record_event("pdf_save_dialog_missing", attempt=attempt)
        screenshot(
            f"09_save_dialog_missing_attempt_{attempt}",
            monitor,
            wave_window.hwnd,
        )

    dump_windows("save_dialog_missing_final")
    raise WaveAutomationError(
        "Report 리본은 열렸지만 Export to PDF 후 Windows 저장 대화상자를 "
        f"{retries}회 모두 찾지 못했습니다."
    )


def _extract_pdf_text(path: Path) -> tuple[str, str]:
    """Extract native PDF text using PyMuPDF first, then pypdf as fallback."""
    try:
        import fitz  # type: ignore

        document = fitz.open(path)
        try:
            return "\n".join(page.get_text("text") for page in document), "PyMuPDF"
        finally:
            document.close()
    except Exception as fitz_exc:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return (
                "\n".join(page.extract_text() or "" for page in reader.pages),
                "pypdf",
            )
        except Exception as pypdf_exc:
            raise WaveAutomationError(
                "PDF 내용 검증용 텍스트 추출에 실패했습니다. "
                f"PyMuPDF={fitz_exc!r}; pypdf={pypdf_exc!r}"
            ) from pypdf_exc


def _number_pattern(value: str, decimals: bool = True) -> str:
    number = float(str(value).replace(",", "."))
    if number.is_integer():
        base = str(int(number))
        return rf"{re.escape(base)}(?:[.]0+)?" if decimals else re.escape(base)
    return re.escape(f"{number:g}")


def validate_exported_pdf(path: Path, settings: Settings) -> dict[str, Any]:
    """Fail closed when the generated PDF does not contain the requested case."""
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\r", "")
    compact = re.sub(r"[ \t]+", " ", normalized)
    membrane = re.escape(settings.membrane)
    pv = _number_pattern(settings.pv_per_stage, decimals=False)
    els = _number_pattern(settings.elements_per_pv, decimals=False)
    temp = _number_pattern(settings.temperature_c)
    recovery = _number_pattern(settings.recovery_pct)
    flow = _number_pattern(settings.feed_flow_m3h)
    profile = re.escape(settings.water_profile)

    checks: dict[str, bool] = {
        "water_profile": bool(
            re.search(rf"Stream Name\s*\n\s*{profile}(?:\s|$)", normalized, re.I)
            or re.search(profile, normalized, re.I)
        ),
        "exact_stage_row": bool(
            re.search(
                rf"(?:^|\n)\s*1\s*\n\s*{membrane}\s*\n\s*{pv}\s*\n\s*{els}(?:\s|\n)",
                normalized,
                re.I,
            )
        ),
        "temperature": bool(
            re.search(
                rf"Temperature\s*\n?\s*[(]?[°o]?C[)]?\s*\n?\s*{temp}",
                normalized,
                re.I,
            )
        ),
        "recovery": bool(
            re.search(rf"RO System Recovery\s*\n?\s*{recovery}\s*%", normalized, re.I)
            or re.search(rf"System Recovery\s*\n?\s*{recovery}\s*%", normalized, re.I)
        ),
        "raw_feed_flow": bool(
            re.search(
                rf"Raw Feed to RO System\s*\n\s*{flow}(?:\s|\n)",
                normalized,
                re.I,
            )
            or re.search(rf"Net Feed\s*=\s*{flow}(?:\s|\n)", compact, re.I)
        ),
        "no_obsolete_membrane": not bool(
            re.search(rf"{membrane}[^\n]{{0,40}}(?:obsolete|[- ]IG)", normalized, re.I)
        ),
    }
    errors = [name for name, passed in checks.items() if not passed]
    result = {
        "pdf": str(path),
        "provider": provider,
        "checks": checks,
        "errors": errors,
        "expected": {
            "water_profile": settings.water_profile,
            "temperature_c": settings.temperature_c,
            "feed_flow_m3h": settings.feed_flow_m3h,
            "recovery_pct": settings.recovery_pct,
            "pv_per_stage": settings.pv_per_stage,
            "elements_per_pv": settings.elements_per_pv,
            "membrane": settings.membrane,
        },
    }
    if STATE.RUN_DIR is not None:
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("_") or "case"
        (STATE.RUN_DIR / f"exported_pdf_text_{safe_stem}.txt").write_text(
            text, encoding="utf-8"
        )
        (STATE.RUN_DIR / f"pdf_validation_{safe_stem}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Keep the legacy filenames as the most-recent case for convenient inspection.
        (STATE.RUN_DIR / "exported_pdf_text.txt").write_text(text, encoding="utf-8")
        (STATE.RUN_DIR / "pdf_validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    record_event("pdf_validation", result=result)
    if errors:
        raise WaveAutomationError(
            "PDF 입력값 검증 실패: " + ", ".join(errors) + ". "
            "생성된 PDF와 run_*.zip의 pdf_validation.json을 확인하세요."
        )
    logging.info("PDF 입력값 검증 성공: %s", ", ".join(checks))
    return result


def export_pdf(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pdf_name: str,
    settings: Settings,
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(pdf_name).name
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    target = (RESULTS_DIR / safe_name).resolve()
    if target.exists():
        target.unlink()

    logging.info("=== PDF 내보내기 시작: %s ===", target)
    focus_wave(wave_window.hwnd)

    # Summary Report 계산 완료 시 WAVE가 Report 리본을 이미 활성화하는 경우가
    # 있다. 따라서 탭의 픽셀 변화가 아니라 Save As 대화상자 출현을 성공
    # 조건으로 삼는다.
    dialog = open_pdf_save_dialog(
        wave_window,
        monitor,
        points,
        settings,
        retries=3,
    )
    save_click_map(
        "report_ribbon",
        wave_window.hwnd,
        points,
        ["report_ribbon_tab", "export_to_pdf"],
    )

    logging.info(
        "저장 대화상자 감지: hwnd=%s title=%r class=%r rect=%s",
        dialog.hwnd,
        dialog.title,
        dialog.class_name,
        dialog.rect,
    )
    record_event("save_dialog", dialog=dialog)
    bring_window_to_front(dialog.hwnd)
    dialog_monitor = get_monitor_rect_for_window(dialog.hwnd)
    screenshot("09_save_dialog", dialog_monitor, wave_window.hwnd)

    # In the observed Korean Save As dialog the filename edit is already focused.
    # Direct paste is the primary path; Alt+N/Tab are only fallbacks.
    _set_clipboard_unicode(str(target))
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    pyautogui.press("enter")

    if not wait_for_file(target, timeout=max(20.0, settings.long_wait * 5)):
        bring_window_to_front(dialog.hwnd)
        pyautogui.hotkey("alt", "n")
        time.sleep(0.4)
        _set_clipboard_unicode(str(target))
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(1.0)
        pyautogui.hotkey("alt", "y")
        pyautogui.press("enter")
        wait_for_file(target, timeout=15.0)

    screenshot("10_export_finished", monitor, wave_window.hwnd)
    if not target.exists():
        raise WaveAutomationError(f"PDF가 생성되지 않았습니다: {target}")
    if target.stat().st_size < 10_000:
        raise WaveAutomationError(
            f"PDF 파일 크기가 너무 작습니다: {target.stat().st_size} bytes"
        )
    logging.info("PDF 저장 성공: %s (%s bytes)", target, target.stat().st_size)
    if settings.validate_pdf:
        validate_exported_pdf(target, settings)
    else:
        logging.info(
            "PDF 본문 입력값 검증 생략(--export-only 또는 --skip-pdf-validation)"
        )
    return target


def dismiss_export_success_dialog(
    wave_window: WindowInfo,
    monitor: Rect,
    *,
    timeout: float = 8.0,
) -> bool:
    """Close WAVE's post-export acknowledgement before the next batch case.

    The dialog is titled ``Export To PDF`` and is intentionally excluded from
    the generic warning resolver because it is part of the normal export flow.
    A two-case batch cannot continue while this modal owner window is disabled.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in list_visible_windows(include_small=True):
            if (
                item.hwnd == wave_window.hwnd
                or item.process_id != wave_window.process_id
            ):
                continue
            title = item.title.lower()
            text_blob = _dialog_text_blob(item)
            blob = f"{item.title}\n{text_blob}".lower()
            is_export_ack = "export to pdf" in title or (
                "export" in title
                and any(
                    token in blob
                    for token in (
                        "successfully exported",
                        "successfully export",
                        "exported",
                        "내보내기",
                    )
                )
            )
            if not is_export_ack:
                continue
            logging.info(
                "PDF 내보내기 완료 확인창 닫기: hwnd=%s title=%r text=%r",
                item.hwnd,
                item.title,
                text_blob,
            )
            record_event("export_success_dialog", dialog=item, text=text_blob)
            screenshot("export_success_dialog", monitor, wave_window.hwnd)
            _close_modal_dialog(item)
            focus_wave(wave_window.hwnd)
            return True
        time.sleep(0.2)
    logging.info("PDF 내보내기 완료 확인창이 없거나 이미 닫혔습니다.")
    return False
