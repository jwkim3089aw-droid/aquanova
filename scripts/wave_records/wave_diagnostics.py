#!/usr/bin/env python3
"""Refactored WAVE automation module: diagnostics."""
from __future__ import annotations

from wave_common import *
from wave_runtime import record_event
from wave_windows import _foreground_window_info, _get_class_name, _get_cursor_pos, _get_process_id, _get_process_path, _get_window_rect, _get_window_text, list_visible_windows

def dump_windows(label: str) -> Path:
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"windows_{label}.json"
    payload = {
        "foreground": _json_safe(_foreground_window_info()),
        "windows": [_json_safe(item) for item in list_visible_windows()],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _enum_child_windows(hwnd: int) -> list[dict[str, Any]]:
    """Enumerate child HWNDs using a real WinFunction callback.

    Python 3.13 validates callback argument types more strictly than older
    versions. Passing a plain Python function to EnumChildWindows raises
    ``TypeError: expected WinFunctionType instance``. The decorated callback
    must stay alive until EnumChildWindows returns.
    """
    user32 = ctypes.windll.user32
    results: list[dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindowEnabled.argtypes = [wintypes.HWND]
    user32.IsWindowEnabled.restype = wintypes.BOOL

    @callback_type
    def callback(child: int, _lparam: int) -> int:
        try:
            child_hwnd = int(child)
            results.append(
                {
                    "hwnd": child_hwnd,
                    "title": _get_window_text(child_hwnd),
                    "class_name": _get_class_name(child_hwnd),
                    "rect": _json_safe(_get_window_rect(child_hwnd)),
                    "visible": bool(user32.IsWindowVisible(child_hwnd)),
                    "enabled": bool(user32.IsWindowEnabled(child_hwnd)),
                }
            )
        except Exception as exc:
            # A single transient/disposed WPF child must not abort enumeration.
            record_event(
                "child_window_read_failed",
                hwnd=int(child) if child else 0,
                error=f"{type(exc).__name__}: {exc}",
            )
        return 1

    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    ok = user32.EnumChildWindows(wintypes.HWND(hwnd), callback, wintypes.LPARAM(0))
    if not ok:
        error_code = ctypes.get_last_error()
        # EnumChildWindows can return zero even when enumeration completed.
        # Only surface an actual Win32 error code.
        if error_code:
            raise ctypes.WinError(error_code)
    return results


def dump_ui_snapshot(label: str, hwnd: int, monitor: Optional[Rect] = None) -> None:
    """Write best-effort UI diagnostics without ever stopping automation.

    Diagnostic data is auxiliary. A WPF control disappearing during enumeration,
    an unsupported Win32 call, or a Python/Windows version mismatch is recorded
    in the JSON instead of being raised into the main automation path.
    """
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    user32 = ctypes.windll.user32
    errors: list[str] = []

    dpi = None
    try:
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = ctypes.c_uint
        dpi = int(user32.GetDpiForWindow(wintypes.HWND(hwnd)))
    except Exception as exc:
        errors.append(f"GetDpiForWindow: {type(exc).__name__}: {exc}")

    try:
        children = _enum_child_windows(hwnd)
    except Exception as exc:
        children = []
        message = f"EnumChildWindows: {type(exc).__name__}: {exc}"
        errors.append(message)
        logging.warning("UI 자식 창 열거 실패(%s): %s", label, exc)
        record_event(
            "diagnostic_warning",
            label=label,
            operation="EnumChildWindows",
            error=message,
        )

    try:
        foreground = _json_safe(_foreground_window_info())
    except Exception as exc:
        foreground = None
        errors.append(f"foreground: {type(exc).__name__}: {exc}")

    try:
        visible_windows = [_json_safe(item) for item in list_visible_windows()]
    except Exception as exc:
        visible_windows = []
        errors.append(f"visible_windows: {type(exc).__name__}: {exc}")

    wave_payload: dict[str, Any] = {"hwnd": hwnd, "children": children}
    for key, getter in (
        ("title", lambda: _get_window_text(hwnd)),
        ("class_name", lambda: _get_class_name(hwnd)),
        ("process_path", lambda: _get_process_path(hwnd)),
        ("process_id", lambda: _get_process_id(hwnd)),
        ("rect", lambda: _json_safe(_get_window_rect(hwnd))),
    ):
        try:
            wave_payload[key] = getter()
        except Exception as exc:
            wave_payload[key] = None
            errors.append(f"wave.{key}: {type(exc).__name__}: {exc}")

    try:
        cursor = _get_cursor_pos() if "_get_cursor_pos" in globals() else None
    except Exception as exc:
        cursor = None
        errors.append(f"cursor: {type(exc).__name__}: {exc}")

    data: dict[str, Any] = {
        "label": label,
        "foreground": foreground,
        "cursor": cursor,
        "dpi": dpi,
        "dpi_scale": (dpi / 96.0) if dpi else None,
        "virtual_screen": {
            "left": int(user32.GetSystemMetrics(76)),
            "top": int(user32.GetSystemMetrics(77)),
            "width": int(user32.GetSystemMetrics(78)),
            "height": int(user32.GetSystemMetrics(79)),
        },
        "wave": wave_payload,
        "visible_windows": visible_windows,
        "diagnostic_errors": errors,
    }
    if monitor is not None:
        data["monitor"] = _json_safe(monitor)

    path = target_dir / f"ui_{label}.json"
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logging.warning("UI 진단 JSON 저장 실패(%s): %s", label, exc)
        record_event(
            "diagnostic_warning",
            label=label,
            operation="write_ui_snapshot",
            error=f"{type(exc).__name__}: {exc}",
        )


def screenshot(label: str, monitor: Rect, hwnd: Optional[int] = None) -> None:
    try:
        from PIL import ImageGrab

        stamp = datetime.now().strftime("%H%M%S_%f")
        target_dir = STATE.RUN_DIR or LOG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(
            bbox=(monitor.left, monitor.top, monitor.right, monitor.bottom),
            all_screens=True,
        )
        image.save(target_dir / f"{stamp}_{label}_monitor.png")
        if hwnd:
            rect = _get_window_rect(hwnd)
            window_image = ImageGrab.grab(
                bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True
            )
            window_image.save(target_dir / f"{stamp}_{label}_wave.png")
        dump_windows(label)
        if hwnd:
            dump_ui_snapshot(label, hwnd, monitor)
    except Exception as exc:
        logging.warning("스크린샷/진단 저장 실패(%s): %s", label, exc)


def _safe_diagnostic_label(label: str) -> str:
    text = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", str(label)).strip("_.")
    return text[:140] or "state"


def capture_ro_state(
    label: str,
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    expected_stage_counts: Optional[dict[int, int]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Persist a targeted, machine-readable RO-state diagnostic snapshot.

    Unlike ``screenshot`` this captures WPF Value/Selection patterns and the
    ancestor chain at every important input coordinate.  Failures are swallowed
    because diagnostics must never become the reason an automation run stops.
    """
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    STATE.DIAGNOSTIC_SEQUENCE += 1
    sequence = int(STATE.DIAGNOSTIC_SEQUENCE)
    safe = _safe_diagnostic_label(label)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "automation_version": "V52",
        "sequence": sequence,
        "time": datetime.now().isoformat(timespec="milliseconds"),
        "label": label,
        "expected_stage_counts": expected_stage_counts or {},
        "metadata": metadata or {},
    }
    try:
        from wave_uia import uia_snapshot_ro_state

        payload["uia"] = uia_snapshot_ro_state(
            hwnd,
            points,
            expected_stage_counts=expected_stage_counts,
        )
    except Exception as exc:
        payload["uia"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    json_path = target_dir / f"ro_state_{sequence:04d}_{safe}.json"
    try:
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        record_event(
            "diagnostic_warning",
            label=label,
            operation="write_ro_state",
            error=f"{type(exc).__name__}: {exc}",
        )

    # A focused crop makes stage-count/column changes obvious without opening a
    # full-monitor screenshot.  Coordinates are relative to the WAVE window.
    crop_path = target_dir / f"ro_state_{sequence:04d}_{safe}_ro_panel.png"
    try:
        image = _capture_wave_image(hwnd)
        left = max(0, round(image.width * 0.10))
        top = max(0, round(image.height * 0.245))
        right = min(image.width, round(image.width * 0.67))
        bottom = min(image.height, round(image.height * 0.94))
        image.crop((left, top, right, bottom)).save(crop_path)
    except Exception as exc:
        payload.setdefault("capture_errors", []).append(
            f"panel_crop: {type(exc).__name__}: {exc}"
        )

    record_event(
        "ro_state_snapshot_v44",
        sequence=sequence,
        label=label,
        json_path=json_path,
        crop_path=crop_path if crop_path.exists() else None,
        expected_stage_counts=expected_stage_counts or {},
        metadata=metadata or {},
        uia_ok=bool((payload.get("uia") or {}).get("ok")),
    )
    return payload


def diff_ro_states(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    """Write a compact control-value diff between two RO state snapshots."""
    def controls(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        rows = ((payload.get("uia") or {}).get("controls") or [])
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            rect = row.get("rect") or {}
            key = "|".join(
                [
                    str(row.get("control_type") or ""),
                    str(row.get("automation_id") or ""),
                    str(row.get("name") or ""),
                    str(round(float(rect.get("left", 0.0)), 1)),
                    str(round(float(rect.get("top", 0.0)), 1)),
                    str(index if not row.get("automation_id") else ""),
                ]
            )
            result[key] = row
        return result

    before_controls = controls(before)
    after_controls = controls(after)
    changes: list[dict[str, Any]] = []
    fields = ("value", "selected", "selection", "expand_state", "enabled", "offscreen")
    for key in sorted(set(before_controls) | set(after_controls)):
        old = before_controls.get(key)
        new = after_controls.get(key)
        if old is None or new is None:
            changes.append({"key": key, "before": old, "after": new})
            continue
        changed = {
            field: {"before": old.get(field), "after": new.get(field)}
            for field in fields
            if old.get(field) != new.get(field)
        }
        if changed:
            changes.append(
                {
                    "key": key,
                    "control_type": new.get("control_type"),
                    "automation_id": new.get("automation_id"),
                    "name": new.get("name"),
                    "rect": new.get("rect"),
                    "changes": changed,
                }
            )

    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    STATE.DIAGNOSTIC_SEQUENCE += 1
    sequence = int(STATE.DIAGNOSTIC_SEQUENCE)
    safe = _safe_diagnostic_label(label)
    payload = {
        "schema_version": 1,
        "automation_version": "V52",
        "sequence": sequence,
        "time": datetime.now().isoformat(timespec="milliseconds"),
        "label": label,
        "before_sequence": before.get("sequence"),
        "after_sequence": after.get("sequence"),
        "change_count": len(changes),
        "changes": changes,
    }
    path = target_dir / f"ro_state_diff_{sequence:04d}_{safe}.json"
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    record_event(
        "ro_state_diff_v44",
        label=label,
        path=path,
        change_count=len(changes),
        before_sequence=before.get("sequence"),
        after_sequence=after.get("sequence"),
    )
    return payload


def write_convergence_failure_report(
    case: ROCaseConfig,
    *,
    context: str,
    extra: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """Create a single index file linking every deep diagnostic for a case."""
    if STATE.RUN_DIR is None:
        return None
    safe_case = _safe_diagnostic_label(case.case_id)
    state_files = sorted(path.name for path in STATE.RUN_DIR.glob("ro_state_*.json"))
    diff_files = sorted(path.name for path in STATE.RUN_DIR.glob("ro_state_diff_*.json"))
    payload = {
        "schema_version": 1,
        "automation_version": "V52",
        "time": datetime.now().isoformat(timespec="milliseconds"),
        "case_id": case.case_id,
        "context": context,
        "expected": case.to_flat_dict(),
        "state_files": state_files,
        "diff_files": diff_files,
        "extra": extra or {},
    }
    path = STATE.RUN_DIR / f"convergence_failure_{safe_case}.json"
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        record_event(
            "diagnostic_warning",
            operation="write_convergence_failure_report",
            error=f"{type(exc).__name__}: {exc}",
        )
        return None
    record_event(
        "convergence_failure_report_v44",
        case_id=case.case_id,
        context=context,
        path=path,
        state_count=len(state_files),
        diff_count=len(diff_files),
    )
    return path


def _capture_wave_image(hwnd: int):
    from PIL import ImageGrab

    rect = _get_window_rect(hwnd)
    return ImageGrab.grab(
        bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True
    ).convert("RGB")


def _image_change_ratio(before, after) -> float:
    from PIL import ImageChops, ImageStat

    if before.size != after.size:
        return 1.0
    diff = ImageChops.difference(before, after)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / max(1, len(stat.mean))
    return float(mean / 255.0)


def _relative_crop_box(
    hwnd: int,
    absolute_center: tuple[int, int],
    half_width: int,
    half_height: int,
) -> tuple[int, int, int, int]:
    """Return a crop box in WAVE-window image coordinates."""
    rect = _get_window_rect(hwnd)
    cx = int(absolute_center[0] - rect.left)
    cy = int(absolute_center[1] - rect.top)
    left = max(0, cx - half_width)
    top = max(0, cy - half_height)
    right = min(rect.width, cx + half_width)
    bottom = min(rect.height, cy + half_height)
    return left, top, right, bottom


def _green_pixel_fraction(image) -> float:
    """Detect the green RO process icon without OCR or UI Automation.

    WAVE is WPF-based and exposes almost no useful child HWNDs.  The process
    icon, however, has a stable green fill.  Blue feed/product arrows and the
    gray drop target do not satisfy this threshold.
    """
    pixels = image.getdata()
    total = max(1, image.width * image.height)
    green = 0
    for red, channel_green, blue in pixels:
        if (
            channel_green >= 70
            and channel_green - red >= 12
            and channel_green - blue >= 10
        ):
            green += 1
    return green / total


def ro_presence_metrics(
    hwnd: int,
    points: dict[str, tuple[int, int]],
    *,
    label: str,
) -> dict[str, Any]:
    """Measure whether an RO process is actually present on the Home canvas.

    The previous implementation used the mean difference of the entire
    1280x1032 WAVE window.  Adding one small RO icon changed only ~0.003 of the
    full image, so a successful drag was misclassified as failure.  V9 checks
    the local drop zone and the new Reverse Osmosis tab instead.
    """
    from PIL import ImageChops, ImageStat

    image = _capture_wave_image(hwnd)
    process_box = _relative_crop_box(
        hwnd, points["process_drop_point"], half_width=90, half_height=78
    )
    process_crop = image.crop(process_box)
    green_fraction = _green_pixel_fraction(process_crop)

    # The Reverse Osmosis tab appears only after a pressure-membrane process is
    # added.  Save this region as evidence even though color detection is the
    # primary decision signal.
    tab_box = (
        max(0, round(image.width * 0.115)),
        max(0, round(image.height * 0.198)),
        min(image.width, round(image.width * 0.355)),
        min(image.height, round(image.height * 0.245)),
    )

    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S_%f")
    try:
        process_crop.save(target_dir / f"{stamp}_{label}_ro_process_crop.png")
        image.crop(tab_box).save(target_dir / f"{stamp}_{label}_ro_tab_crop.png")
    except Exception as exc:
        logging.warning("RO 검증 crop 저장 실패(%s): %s", label, exc)

    metrics = {
        "green_fraction": green_fraction,
        "process_box": process_box,
        "tab_box": tab_box,
        "present": green_fraction >= 0.015,
    }
    logging.info(
        "RO 실제 상태 확인: label=%s green_fraction=%.5f present=%s",
        label,
        green_fraction,
        metrics["present"],
    )
    record_event("ro_presence_check", label=label, **metrics)
    return metrics


def ro_local_change_ratio(
    before,
    after,
    hwnd: int,
    points: dict[str, tuple[int, int]],
) -> float:
    """Compute image change only around the RO drop target."""
    from PIL import ImageChops, ImageStat

    box = _relative_crop_box(
        hwnd, points["process_drop_point"], half_width=100, half_height=85
    )
    crop_before = before.crop(box)
    crop_after = after.crop(box)
    if crop_before.size != crop_after.size:
        return 1.0
    diff = ImageChops.difference(crop_before, crop_after)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / max(1, len(stat.mean))
    return float(mean / 255.0)


def save_coordinate_manifest(
    hwnd: int, points: dict[str, tuple[int, int]], label: str = "startup"
) -> None:
    """Persist the exact absolute/relative coordinates used by this run."""
    target_dir = STATE.RUN_DIR or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    rect = _get_window_rect(hwnd)
    payload = {
        "label": label,
        "calibration_version": CALIBRATION_VERSION,
        "reference_size": [REFERENCE_WIDTH, REFERENCE_HEIGHT],
        "window_rect": _json_safe(rect),
        "points": {
            name: {
                "absolute": [int(x), int(y)],
                "relative": [int(x - rect.left), int(y - rect.top)],
                "normalized": [
                    round((x - rect.left) / max(1, rect.width), 8),
                    round((y - rect.top) / max(1, rect.height), 8),
                ],
            }
            for name, (x, y) in points.items()
        },
    }
    (target_dir / f"coordinate_manifest_{label}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_click_map(
    label: str,
    hwnd: int,
    points: dict[str, tuple[int, int]],
    names: Optional[list[str]] = None,
) -> None:
    """Save a WAVE screenshot annotated with the exact target points."""
    try:
        from PIL import ImageDraw

        image = _capture_wave_image(hwnd)
        rect = _get_window_rect(hwnd)
        draw = ImageDraw.Draw(image)
        selected = names or list(points)
        for index, name in enumerate(selected):
            if name not in points:
                continue
            x, y = points[name]
            rx, ry = x - rect.left, y - rect.top
            radius = 7
            draw.ellipse(
                (rx - radius, ry - radius, rx + radius, ry + radius),
                outline=(255, 0, 0),
                width=3,
            )
            # Alternate label offset to reduce overlap in dense areas.
            oy = -18 if index % 2 == 0 else 8
            draw.text((rx + 9, ry + oy), name, fill=(255, 0, 0))
        target_dir = STATE.RUN_DIR or LOG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        image.save(target_dir / f"click_map_{label}.png")
    except Exception as exc:
        logging.warning("클릭 좌표 지도 저장 실패(%s): %s", label, exc)


def save_point_probe(label: str, hwnd: int, point: tuple[int, int]) -> None:
    """Save a small cross-haired crop around an intended click target."""
    try:
        from PIL import ImageGrab, ImageDraw

        x, y = point
        half_w, half_h = 150, 90
        image = ImageGrab.grab(
            bbox=(x - half_w, y - half_h, x + half_w, y + half_h),
            all_screens=True,
        ).convert("RGB")
        draw = ImageDraw.Draw(image)
        cx, cy = half_w, half_h
        draw.line((cx - 18, cy, cx + 18, cy), fill=(255, 0, 0), width=3)
        draw.line((cx, cy - 18, cx, cy + 18), fill=(255, 0, 0), width=3)
        draw.text((8, 8), f"{label} @ ({x}, {y})", fill=(255, 0, 0))
        target_dir = STATE.RUN_DIR or LOG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%H%M%S_%f")
        image.save(target_dir / f"{stamp}_probe_{label}.png")
    except Exception as exc:
        logging.warning("클릭 지점 확대 저장 실패(%s): %s", label, exc)
