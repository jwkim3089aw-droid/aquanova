#!/usr/bin/env python3
"""Refactored WAVE automation module: windows."""
from __future__ import annotations

from wave_common import *
from wave_runtime import record_event, setup_logging

def _require_windows() -> None:
    if os.name != "nt":
        raise WaveAutomationError("이 자동화는 Windows WAVE 환경용입니다.")


def _get_window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _get_class_name(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    if user32.GetClassNameW(hwnd, buffer, len(buffer)) <= 0:
        return ""
    return buffer.value


def _get_process_id(hwnd: int) -> int:
    user32 = ctypes.windll.user32
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _get_window_rect(hwnd: int) -> Rect:
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    raw = RECT()
    user32 = ctypes.windll.user32
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = ctypes.c_bool
    if not user32.GetWindowRect(hwnd, ctypes.byref(raw)):
        raise WaveAutomationError(f"창 위치를 읽지 못했습니다. hwnd={hwnd}")
    return Rect(raw.left, raw.top, raw.right, raw.bottom)


def _get_process_path(hwnd: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetWindowThreadProcessId.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def list_visible_windows(*, include_small: bool = False) -> list[WindowInfo]:
    _require_windows()
    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsWindowVisible.restype = ctypes.c_bool
    windows: list[WindowInfo] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> int:
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = _get_window_text(hwnd)
            if not title:
                return True
            rect = _get_window_rect(hwnd)
            min_width, min_height = (80, 40) if include_small else (250, 150)
            if rect.width < min_width or rect.height < min_height:
                return True
            windows.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    title=title,
                    process_path=_get_process_path(hwnd),
                    rect=rect,
                    process_id=_get_process_id(hwnd),
                    class_name=_get_class_name(hwnd),
                )
            )
        except Exception:
            pass
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(callback, 0)
    return windows


def _foreground_window_info() -> Optional[WindowInfo]:
    try:
        hwnd = int(ctypes.windll.user32.GetForegroundWindow())
        if not hwnd:
            return None
        return WindowInfo(
            hwnd=hwnd,
            title=_get_window_text(hwnd),
            process_path=_get_process_path(hwnd),
            rect=_get_window_rect(hwnd),
            process_id=_get_process_id(hwnd),
            class_name=_get_class_name(hwnd),
        )
    except Exception:
        return None


def _wave_window_score(window: WindowInfo, title_hint: Optional[str]) -> int:
    title = window.title.lower()
    exe = Path(window.process_path).name.lower() if window.process_path else ""
    score = 0
    if "wave" in exe:
        score += 200
    if title_hint and title_hint.lower() in title:
        score += 150
    if "untitled project" in title:
        score += 100
    if re.search(r"\bcase\s*\d+\b", title, re.IGNORECASE):
        score += 50
    if "dupont" in title or "water application value engine" in title:
        score += 80
    # Do not accidentally target a browser or editor merely displaying WAVE text.
    if any(token in exe for token in ("chrome", "msedge", "firefox", "code.exe")):
        score -= 200
    return score


def find_wave_window(title_hint: Optional[str] = None) -> WindowInfo:
    windows = list_visible_windows()
    ranked = sorted(
        ((_wave_window_score(window, title_hint), window) for window in windows),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 50:
        preview = "\n".join(
            f"  hwnd={item.hwnd:<10} title={item.title!r} exe={Path(item.process_path).name!r}"
            for item in windows[:30]
        )
        raise WaveAutomationError(
            "WAVE 창을 찾지 못했습니다. WAVE를 먼저 열고 다시 실행하세요.\n"
            "확인 가능한 창:\n" + (preview or "  (없음)")
        )
    score, selected = ranked[0]
    logging.info(
        "WAVE 창 선택: hwnd=%s score=%s title=%r exe=%r rect=%s",
        selected.hwnd,
        score,
        selected.title,
        selected.process_path,
        selected.rect,
    )
    return selected


def bring_window_to_front(hwnd: int, *, restore_if_minimized: bool = True) -> None:
    """Request foreground activation without a synchronous cross-thread window call.

    WPF modal dialogs disable their owner window.  BringWindowToTop/SetFocus can then
    block inside USER32 while the modal dispatcher is waiting, which is exactly where
    the V9 run hung.  SetWindowPos with SWP_ASYNCWINDOWPOS posts the request instead
    of waiting for the target GUI thread.
    """
    _require_windows()
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    HWND_TOP = 0
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    SWP_ASYNCWINDOWPOS = 0x4000

    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindowAsync.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    if not user32.IsWindow(hwnd):
        raise WaveAutomationError(f"유효하지 않은 창 핸들입니다: hwnd={hwnd}")
    if restore_if_minimized and user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, SW_RESTORE)
        time.sleep(0.20)

    flags = SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW | SWP_ASYNCWINDOWPOS
    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, flags)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.12)
    fg = int(user32.GetForegroundWindow())
    record_event(
        "foreground_request_async",
        target_hwnd=hwnd,
        resulting_hwnd=fg,
        resulting_title=_get_window_text(fg) if fg else "",
    )


def activate_wave(hwnd: int) -> None:
    """Bring WAVE forward and ensure its recorded maximized layout.

    Important: never call SW_RESTORE on an already visible/maximized WAVE window.
    SW_RESTORE changes a maximized window back to its saved 880x710 normal size,
    which was the cause of the maximize -> restore loop seen in the logs.
    """
    _require_windows()
    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow.restype = ctypes.c_bool
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.IsIconic.restype = ctypes.c_bool
    user32.IsZoomed.argtypes = [ctypes.c_void_p]
    user32.IsZoomed.restype = ctypes.c_bool

    SW_RESTORE = 9
    SW_MAXIMIZE = 3

    # Only restore when genuinely minimized. Restoring a visible maximized window
    # would unmaximize it and expose WAVE's saved 880x710 normal rectangle.
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.30)

    bring_window_to_front(hwnd, restore_if_minimized=False)

    rect = _get_window_rect(hwnd)
    already_large = rect.width >= 1100 and rect.height >= 850

    # WAVE can expose a large/maximized-looking 1280x1032 client rectangle while
    # IsZoomed() still returns False. Calling SW_MAXIMIZE in that state occasionally
    # restores WAVE to its saved 880x710 normal rectangle. Trust the measured layout
    # first and only request maximize when the actual rectangle is too small.
    if already_large:
        record_event(
            "maximize_skipped_already_large",
            rect=_json_safe(rect),
            zoomed=bool(user32.IsZoomed(hwnd)),
        )
    else:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        bring_window_to_front(hwnd, restore_if_minimized=False)
        record_event("maximize_requested", rect_before=_json_safe(rect))

    previous = None
    stable_count = 0
    maximize_retries = 0
    started = time.time()
    deadline = started + 6.5
    while time.time() < deadline:
        rect = _get_window_rect(hwnd)
        current = (rect.left, rect.top, rect.right, rect.bottom)
        if current == previous:
            stable_count += 1
        else:
            stable_count = 0
            previous = current
        if stable_count >= 3 and rect.width >= 1100 and rect.height >= 850:
            logging.info(
                "WAVE 최대화 상태 확인: rect=%s zoomed=%s",
                rect,
                bool(user32.IsZoomed(hwnd)),
            )
            return

        # A WPF window can ignore the first maximize request while changing
        # foreground ownership. Retry asynchronously, but never restore a visible
        # large window because that is what exposes the 880x710 saved rectangle.
        elapsed = time.time() - started
        if (
            (rect.width < 1100 or rect.height < 850)
            and maximize_retries < 2
            and elapsed >= 1.2 * (maximize_retries + 1)
        ):
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            bring_window_to_front(hwnd, restore_if_minimized=False)
            maximize_retries += 1
            record_event(
                "maximize_retry",
                retry=maximize_retries,
                rect_before=_json_safe(rect),
            )
        time.sleep(0.2)

    rect = _get_window_rect(hwnd)
    raise WaveAutomationError(
        "WAVE 최대화에 실패했습니다. 현재 창 크기="
        f"{rect.width}x{rect.height}. WAVE를 화면에 복원한 뒤 다시 실행하세요."
    )


def native_move_to(x: int, y: int) -> None:
    """Move on the full Windows virtual desktop, including secondary monitors."""
    user32 = ctypes.windll.user32
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = ctypes.c_bool
    if not user32.SetCursorPos(int(x), int(y)):
        raise WaveAutomationError(f"마우스 이동 실패: ({x}, {y})")


def _get_cursor_pos() -> tuple[int, int]:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def native_click_at(x: int, y: int) -> None:
    user32 = ctypes.windll.user32
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    native_move_to(x, y)
    time.sleep(0.08)
    actual = _get_cursor_pos()
    record_event("cursor_move", intended=(x, y), actual=actual)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def native_drag(
    start_xy: tuple[int, int], end_xy: tuple[int, int], duration: float = 0.8
) -> None:
    user32 = ctypes.windll.user32
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    sx, sy = start_xy
    ex, ey = end_xy
    native_move_to(sx, sy)
    time.sleep(0.12)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    steps = max(10, int(duration / 0.02))
    for index in range(1, steps + 1):
        ratio = index / steps
        native_move_to(round(sx + (ex - sx) * ratio), round(sy + (ey - sy) * ratio))
        time.sleep(duration / steps)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)



def list_monitor_rects() -> list[Rect]:
    """Return visible monitor rectangles in stable left/top order.

    V69 note: on the user's Windows 11/Python 3.13 rig, MonitorFromWindow worked
    but EnumDisplayMonitors occasionally returned TRUE with zero callbacks.  This
    function therefore uses void-pointer signatures, captures the callback rect
    as a secondary source, and leaves final fallback policy to
    resolve_monitor_rect_by_index().
    """
    _require_windows()

    class RECT_WIN(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT_WIN),
            ("rcWork", RECT_WIN),
            ("dwFlags", ctypes.c_ulong),
        ]

    user32 = ctypes.windll.user32
    rects: list[Rect] = []
    seen: set[tuple[int, int, int, int]] = set()

    def add_rect(left: int, top: int, right: int, bottom: int) -> None:
        rect = Rect(int(left), int(top), int(right), int(bottom))
        if rect.width <= 0 or rect.height <= 0:
            return
        key = (rect.left, rect.top, rect.right, rect.bottom)
        if key not in seen:
            seen.add(key)
            rects.append(rect)

    # Use c_void_p instead of wintypes.HMONITOR/HDC here.  It is more tolerant
    # across Python/ctypes builds and still matches the Win32 ABI pointer width.
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(RECT_WIN),
        ctypes.c_void_p,
    )

    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    @callback_type
    def callback(hmonitor: int, _hdc: int, lprc: Any, _lparam: int) -> int:
        try:
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                r = info.rcMonitor
                add_rect(r.left, r.top, r.right, r.bottom)
                return True
            if lprc:
                r = lprc.contents
                add_rect(r.left, r.top, r.right, r.bottom)
        except Exception as exc:
            logging.debug("모니터 callback 처리 실패: %r", exc)
        return True

    user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, callback_type, ctypes.c_void_p]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    ok = bool(user32.EnumDisplayMonitors(None, None, callback, None))
    if not ok:
        logging.warning("EnumDisplayMonitors 호출 실패; fallback 정책으로 진행합니다.")
    rects = sorted(rects, key=lambda r: (r.left, r.top, r.right, r.bottom))
    logging.info("감지된 모니터 목록: %s", rects)
    return rects


def resolve_monitor_rect_by_index(index: int | None, *, fallback: Rect | None = None) -> Rect:
    """Resolve an operator-facing 1-based monitor index to a Rect.

    If Windows monitor enumeration is empty but the current WAVE window already
    supplied a monitor fallback, use that fallback instead of failing before the
    production runner can start.  This preserves the user's display-2 workflow:
    the initial WAVE window is already on display 2, so its monitor is the safest
    restart target even when EnumDisplayMonitors is unavailable.
    """
    if index is None:
        if fallback is None:
            raise WaveAutomationError("모니터 index와 fallback이 모두 없습니다.")
        return fallback
    monitors = list_monitor_rects()
    if index >= 1 and index <= len(monitors):
        return monitors[index - 1]
    if fallback is not None:
        record_event(
            "monitor_index_fallback_v69",
            requested_index=index,
            detected_count=len(monitors),
            detected_monitors=_json_safe(monitors),
            fallback=_json_safe(fallback),
            reason="EnumDisplayMonitors returned no usable target; using current WAVE monitor",
        )
        logging.warning(
            "모니터 번호 %s 해석 실패(detected=%s). 현재 WAVE 모니터 fallback 사용: %s",
            index,
            monitors,
            fallback,
        )
        return fallback
    raise WaveAutomationError(
        f"요청한 모니터 번호가 범위를 벗어났습니다: {index}. "
        f"감지된 모니터 수={len(monitors)} 목록={monitors}"
    )


def move_window_to_monitor(hwnd: int, target_monitor: Rect, *, maximize: bool = True) -> Rect:
    """Move WAVE to a target monitor and optionally maximize there.

    Windows normally maximizes a window on the monitor containing its restored
    rectangle.  Therefore this function first restores the window, moves the
    restored rectangle into the target monitor, then maximizes.  This prevents a
    relaunched WAVE process from staying on display 1 when the production runner
    should operate on display 2.
    """
    _require_windows()
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    if not user32.IsWindow(hwnd):
        raise WaveAutomationError(f"유효하지 않은 창 핸들입니다: hwnd={hwnd}")

    SW_RESTORE = 9
    SW_MAXIMIZE = 3
    HWND_TOP = 0
    SWP_SHOWWINDOW = 0x0040
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.30)

    width = min(1280, max(900, target_monitor.width - 80))
    height = min(1032, max(700, target_monitor.height - 80))
    x = target_monitor.left + max(0, round((target_monitor.width - width) / 2))
    y = target_monitor.top + max(0, round((target_monitor.height - height) / 2))
    ok = user32.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(width), int(height), SWP_SHOWWINDOW)
    if not ok:
        raise WaveAutomationError(f"WAVE 창을 대상 모니터로 이동하지 못했습니다: monitor={target_monitor}")
    time.sleep(0.35)
    if maximize:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.35)
    bring_window_to_front(hwnd, restore_if_minimized=False)
    rect = _get_window_rect(hwnd)
    record_event(
        "wave_window_moved_to_monitor_v69",
        hwnd=hwnd,
        target_monitor=_json_safe(target_monitor),
        rect_after=_json_safe(rect),
        maximize=maximize,
    )
    logging.info("WAVE 창 대상 모니터 이동 완료: monitor=%s rect=%s", target_monitor, rect)
    return rect

def get_monitor_rect_for_window(hwnd: int) -> Rect:
    _require_windows()

    class RECT_WIN(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT_WIN),
            ("rcWork", RECT_WIN),
            ("dwFlags", ctypes.c_ulong),
        ]

    MONITOR_DEFAULTTONEAREST = 2
    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = ctypes.c_bool
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        raise WaveAutomationError("WAVE가 있는 모니터를 찾지 못했습니다.")
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise WaveAutomationError("모니터 좌표를 읽지 못했습니다.")
    rect = info.rcMonitor
    result = Rect(rect.left, rect.top, rect.right, rect.bottom)
    logging.info("WAVE 모니터 좌표: %s (%sx%s)", result, result.width, result.height)
    return result


def _set_clipboard_unicode(text: str) -> None:
    """Put Unicode text on the Windows clipboard safely on 64-bit Python."""
    _require_windows()
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    GMEM_ZEROINIT = 0x0040

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    # Explicit pointer-sized signatures are required on 64-bit Python.
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    if not handle:
        raise WaveAutomationError("클립보드 메모리 할당 실패")

    clipboard_owns_handle = False
    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise WaveAutomationError("클립보드 메모리 잠금 실패")
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)

        opened = False
        for _ in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.05)
        if not opened:
            raise WaveAutomationError("클립보드를 열 수 없습니다.")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                raise WaveAutomationError("클립보드 데이터 설정 실패")
            clipboard_owns_handle = True
        finally:
            user32.CloseClipboard()
    finally:
        if not clipboard_owns_handle:
            kernel32.GlobalFree(handle)


def _default_normalized_points() -> dict[str, tuple[float, float]]:
    return {
        key: (x / REFERENCE_WIDTH, y / REFERENCE_HEIGHT)
        for key, (x, y) in DEFAULT_POINTS.items()
    }


def _map_normalized_points(
    normalized: dict[str, tuple[float, float]], window_rect: Rect
) -> dict[str, tuple[int, int]]:
    return {
        key: (
            window_rect.left + round(nx * window_rect.width),
            window_rect.top + round(ny * window_rect.height),
        )
        for key, (nx, ny) in normalized.items()
    }


def load_points(window_rect: Rect) -> dict[str, tuple[int, int]]:
    normalized = _default_normalized_points()
    if CALIBRATION_FILE.exists():
        try:
            raw = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
            if raw.get("version") == CALIBRATION_VERSION:
                stored = raw.get("points_normalized", {})
                parsed = {
                    key: (float(value[0]), float(value[1]))
                    for key, value in stored.items()
                    if key in DEFAULT_POINTS
                }
                # V52: allow older calibration files to coexist with newly added
                # UF controls.  Missing keys fall back to the versioned defaults
                # instead of invalidating the whole calibration payload.
                normalized = dict(normalized)
                normalized.update(parsed)
                missing = sorted(set(DEFAULT_POINTS) - set(parsed))
                logging.info(
                    "V5 WAVE 창 상대 보정 좌표 사용: %s (missing defaults=%s)",
                    CALIBRATION_FILE,
                    missing,
                )
            else:
                logging.warning(
                    "기존 모니터 기준 보정 파일은 WAVE 창 크기가 달라지면 위험하여 무시합니다. "
                    "필요하면 --calibrate를 다시 실행하세요: %s",
                    CALIBRATION_FILE,
                )
        except Exception as exc:
            logging.warning("보정 파일을 읽지 못해 기본 좌표 사용: %s", exc)

    points = _map_normalized_points(normalized, window_rect)
    logging.info(
        "좌표를 WAVE 창에 매핑: origin=(%s,%s), size=%sx%s",
        window_rect.left,
        window_rect.top,
        window_rect.width,
        window_rect.height,
    )
    return points


def calibrate(window_title: Optional[str]) -> None:
    log_path = setup_logging()
    window = find_wave_window(window_title)
    activate_wave(window.hwnd)
    window_rect = _get_window_rect(window.hwnd)

    print("\nWAVE 화면 좌표 보정(V5, WAVE 창 상대좌표)")
    print(f"대상 창: {window.title}")
    print(
        f"대상 WAVE 창: left={window_rect.left}, top={window_rect.top}, "
        f"size={window_rect.width}x{window_rect.height}"
    )
    print("각 안내 위치에 마우스를 올리고 Enter를 누르세요.")
    print("Ctrl+C를 누르면 중단됩니다.\n")

    normalized: dict[str, tuple[float, float]] = {}
    for key, description in CALIBRATION_ORDER:
        input(f"[{key}] {description}에 마우스를 올린 뒤 Enter: ")
        pos = pyautogui.position()
        nx = (int(pos.x) - window_rect.left) / window_rect.width
        ny = (int(pos.y) - window_rect.top) / window_rect.height
        if not (0 <= nx <= 1 and 0 <= ny <= 1):
            raise WaveAutomationError(
                f"마우스가 WAVE 창 밖에 있습니다: ({pos.x}, {pos.y})"
            )
        normalized[key] = (nx, ny)
        print(f"  저장: absolute=({pos.x}, {pos.y}), normalized=({nx:.6f}, {ny:.6f})")

    payload = {
        "version": CALIBRATION_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "window_title": window.title,
        "window_rect_at_calibration": [
            window_rect.left,
            window_rect.top,
            window_rect.right,
            window_rect.bottom,
        ],
        "points_normalized": normalized,
    }
    CALIBRATION_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n보정 완료: {CALIBRATION_FILE}")
    print(f"로그: {log_path}")


def focus_wave(hwnd: int) -> None:
    """Focus WAVE without restoring/unmaximizing it."""
    bring_window_to_front(hwnd)
    rect = _get_window_rect(hwnd)
    if rect.width < 1100 or rect.height < 850:
        logging.warning("WAVE 창이 작아져 다시 최대화합니다: rect=%s", rect)
        activate_wave(hwnd)


def countdown(seconds: int = 5) -> None:
    print("\n자동화를 시작합니다. WAVE를 녹화와 같은 초기 Home 화면에 두세요.")
    print(
        "WAVE가 어느 모니터에 있든 자동으로 복원·최대화한 뒤 V52 전체 실험 RO 배치·독립 Feed 온도범위·1~5 Stage/1~2 Pass·압력/Flow Factor/Chemical·PDF 교차검증으로 조작합니다."
    )
    print("중단하려면 터미널에서 Ctrl+C를 누르세요.")
    for remaining in range(seconds, 0, -1):
        print(f"  {remaining}...")
        time.sleep(1)
