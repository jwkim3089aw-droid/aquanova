#!/usr/bin/env python3
"""Fresh WAVE process restart/reacquire helpers for production runs.

The V69 monitor/window fixes are preserved here unchanged; V73 only moves them
out of wave_production.py so the production runner is easier to maintain.
"""
from __future__ import annotations

from wave_common import *
from wave_diagnostics import _enum_child_windows, screenshot
from wave_dialogs import resolve_wave_blocking_dialogs, _blocking_wave_dialogs, wait_for_report_loading_spinner
from wave_runtime import record_event
from wave_windows import (
    _get_window_rect,
    native_click_at,
    find_wave_window,
    activate_wave,
    get_monitor_rect_for_window,
    load_points,
    _get_window_text,
    _get_process_path,
    _get_process_id,
    _get_class_name,
    move_window_to_monitor,
    resolve_monitor_rect_by_index,
    list_visible_windows,
)
from wave_production_plan import ProductionItem, PRODUCTION_AUTOMATION_VERSION, _production_family


def _click_production_point(
    hwnd: int,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    name: str,
    *,
    pause: float,
) -> None:
    from wave_interaction import click

    if name not in points:
        raise WaveAutomationError(f"Production case isolation point is missing: {name}")
    resolve_wave_blocking_dialogs(hwnd, monitor, f"production_case_isolation_before_{name}", points)
    click(points, name, pause=pause)
    resolve_wave_blocking_dialogs(hwnd, monitor, f"production_case_isolation_after_{name}", points)

def _dialog_button_click(dialog: WindowInfo, tokens: tuple[str, ...]) -> bool:
    """Click a specific Win32 dialog button by caption substring."""
    wanted = tuple(t.casefold() for t in tokens)
    try:
        children = _enum_child_windows(dialog.hwnd)
    except Exception:
        children = []
    for child in children:
        title = str(child.get("title") or "").strip()
        cls = str(child.get("class_name") or "")
        if not title or "button" not in cls.casefold():
            continue
        folded = title.casefold()
        if any(token in folded for token in wanted):
            rect = child.get("rect") or {}
            if isinstance(rect, dict):
                x = int((int(rect.get("left", 0)) + int(rect.get("right", 0))) / 2)
                y = int((int(rect.get("top", 0)) + int(rect.get("bottom", 0))) / 2)
                native_click_at(x, y)
                time.sleep(0.7)
                return True
    return False

def _dismiss_new_project_save_prompt(
    hwnd: int,
    monitor: Rect,
    context: str,
    *,
    timeout_s: float = 8.0,
) -> list[str]:
    """Dismiss WAVE's save/discard prompt when starting an isolated project.

    Production runs intentionally export PDFs and manifests, not WAVE project
    files.  For a fresh isolated case, the safe deterministic action is therefore
    to discard the previous unsaved WAVE project/case state.
    """
    actions: list[str] = []
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        dialogs = _blocking_wave_dialogs(hwnd)
        if not dialogs:
            return actions
        dialog, text = dialogs[0]
        blob = f"{dialog.title}\n{text}".casefold()
        if wait_for_report_loading_spinner(hwnd, monitor, f"{context}_save_prompt_pre", timeout_s=90.0):
            actions.append("spinner_waited_before_save_prompt")
            continue
        looks_like_save_prompt = any(token in blob for token in (
            "save", "unsaved", "changes", "project", "저장", "변경", "프로젝트",
        ))
        if not looks_like_save_prompt:
            break
        logging.info("Production 새 프로젝트 저장 프롬프트 감지: context=%s title=%r text=%r", context, dialog.title, text)
        record_event("production_new_project_save_prompt_v69", context=context, dialog=dialog, text=text)
        screenshot(f"production_new_project_save_prompt_{re.sub(r'[^A-Za-z0-9_.-]+', '_', context)[:80]}_v69", monitor, hwnd)
        bring_tokens = (
            "don't save", "dont save", "do not save", "no", "아니", "저장 안", "저장하지", "discard",
        )
        if not _dialog_button_click(dialog, bring_tokens):
            bring_window = getattr(__import__('wave_windows'), 'bring_window_to_front')
            bring_window(dialog.hwnd, restore_if_minimized=False)
            # English WAVE builds normally expose Alt+N/No.  If the button text is
            # localized and enumeration did not find it, this is the least risky
            # save-discard accelerator before using a coordinate fallback.
            pyautogui.press("n")
            time.sleep(0.7)
        if ctypes.windll.user32.IsWindow(dialog.hwnd) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
            # Last-resort middle button for standard Save / Don't Save / Cancel
            # prompts.  This branch only runs after the prompt text matched a
            # save/discard question; never use it for arbitrary constraint errors.
            native_click_at(
                dialog.rect.left + round(dialog.rect.width * 0.58),
                dialog.rect.top + round(dialog.rect.height * 0.82),
            )
            time.sleep(0.8)
        if ctypes.windll.user32.IsWindow(dialog.hwnd) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
            raise WaveAutomationError(f"새 프로젝트 저장 프롬프트를 닫지 못했습니다: {dialog.title!r} {text!r}")
        actions.append("discarded_unsaved_project")
    return actions

def _window_is_alive(hwnd: int) -> bool:
    try:
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        return bool(user32.IsWindow(hwnd))
    except Exception:
        return False

def _wait_window_gone(hwnd: int, timeout_s: float = 20.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _window_is_alive(hwnd):
            return True
        time.sleep(0.25)
    return not _window_is_alive(hwnd)

def _rebuild_window_info(window: WindowInfo) -> WindowInfo:
    return WindowInfo(
        hwnd=window.hwnd,
        title=_get_window_text(window.hwnd),
        process_path=_get_process_path(window.hwnd),
        rect=_get_window_rect(window.hwnd),
        process_id=_get_process_id(window.hwnd),
        class_name=_get_class_name(window.hwnd) or getattr(window, "class_name", ""),
    )

def _wave_identity_from_title_class_path(*, title: str, class_name: str, process_path: str) -> bool:
    """Return True for WAVE HWNDs even when process-path probing is late/empty.

    On the user's dual-monitor rig WAVE normally relaunches on Windows display 1.
    During that short startup window QueryFullProcessImageNameW may return an
    empty process path even though the HWND title/class already proves it is the
    real WAVE WPF window. V69 therefore identifies candidates by **path OR WPF
    class OR WAVE main-window title**, then moves the acquired window to the
    requested automation monitor afterwards.
    """
    path_l = str(process_path or "").casefold().replace("/", "\\")
    title_l = str(title or "").casefold()
    class_l = str(class_name or "").casefold()
    if "wave.exe" in path_l or "hwndwrapper[wave.exe" in class_l:
        return True
    if title_l.startswith("untitled project"):
        return True
    if "project" in title_l and re.search(r"\bcase\s*\d+\b", title_l, re.IGNORECASE):
        return True
    if "water application value engine" in title_l or "dupont wave" in title_l:
        return True
    return False

def _enum_wave_windows_raw() -> list[dict[str, Any]]:
    """Enumerate WAVE top-level windows without title/size/visibility filters.

    ``list_visible_windows`` intentionally ignores untitled, hidden, or tiny
    windows. WAVE also relaunches on display 1 on the user's rig, while
    production automation should continue on display 2. V69 treats acquisition
    and placement as separate phases: first find the new WAVE HWND anywhere
    using path/title/class evidence, then move it to the requested monitor.
    """
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsWindowEnabled.argtypes = [wintypes.HWND]
    user32.IsWindowEnabled.restype = wintypes.BOOL
    rows: list[dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> int:
        try:
            hwnd_i = int(hwnd)
            title = _get_window_text(hwnd_i)
            class_name = _get_class_name(hwnd_i)
            process_path = _get_process_path(hwnd_i)
            if not _wave_identity_from_title_class_path(title=title, class_name=class_name, process_path=process_path):
                return True
            try:
                rect = _get_window_rect(hwnd_i)
            except Exception:
                rect = Rect(0, 0, 0, 0)
            rows.append({
                "hwnd": hwnd_i,
                "title": title,
                "process_path": process_path,
                "process_id": _get_process_id(hwnd_i),
                "class_name": class_name,
                "rect": rect,
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "iconic": bool(user32.IsIconic(hwnd)),
                "enabled": bool(user32.IsWindowEnabled(hwnd)),
            })
        except Exception:
            pass
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(callback, 0)
    return rows

def _raw_wave_window_info(row: dict[str, Any]) -> WindowInfo:
    rect = row.get("rect")
    if not isinstance(rect, Rect):
        rect = Rect(0, 0, 0, 0)
    return WindowInfo(
        hwnd=int(row.get("hwnd") or 0),
        title=str(row.get("title") or ""),
        process_path=str(row.get("process_path") or ""),
        process_id=int(row.get("process_id") or 0),
        class_name=str(row.get("class_name") or ""),
        rect=rect,
    )

def _raw_wave_snapshot_for_event(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows[:12]:
        out.append({
            "hwnd": row.get("hwnd"),
            "pid": row.get("process_id"),
            "title": row.get("title"),
            "class_name": row.get("class_name"),
            "process_path": row.get("process_path"),
            "rect": _json_safe(row.get("rect")),
            "visible": row.get("visible"),
            "iconic": row.get("iconic"),
            "enabled": row.get("enabled"),
        })
    return out

def _is_wave_splash_window(window: WindowInfo) -> bool:
    title = str(getattr(window, "title", "") or "").casefold()
    class_name = str(getattr(window, "class_name", "") or "").casefold()
    return "splash" in class_name or "잠시 기다" in title or "opening" in title

def _is_wave_main_window(window: WindowInfo) -> bool:
    """Return True only for a *ready* WAVE main window.

    V66/V67 deliberately widened the relaunch inventory so we could see hidden
    WPF HWNDs during startup.  The user's latest run proved why those HWNDs
    must not be accepted as the automation target: WAVE creates a tiny hidden
    ``HwndWrapper[WAVE.exe...]`` while the splash screen is still visible; when
    that placeholder is moved/maximized to monitor 2 it becomes a black WPF
    surface, while the real WAVE project window continues opening on monitor 1.

    V69 keeps the raw inventory for diagnostics, but only treats a candidate as
    usable once it is large enough and has real main-window title evidence.
    This restores the intended sequence: wait for the real display-1 project
    window, then move that real window to the requested automation monitor.
    """
    path = str(getattr(window, "process_path", "") or "").casefold().replace("/", "\\")
    title = str(getattr(window, "title", "") or "")
    class_name = str(getattr(window, "class_name", "") or "")
    rect = getattr(window, "rect", None)
    if _is_wave_splash_window(window):
        return False
    if rect is None or rect.width < 700 or rect.height < 450:
        return False
    title_l = title.casefold()
    class_l = class_name.casefold()
    path_wave = "wave.exe" in path
    class_wave = "hwndwrapper[wave.exe" in class_l
    title_main = (
        title_l.startswith("untitled project")
        or ("project" in title_l and re.search(r"\bcase\s*\d+\b", title_l, re.IGNORECASE))
        or "water application value engine" in title_l
        or "dupont wave" in title_l
    )
    if title_main:
        return True
    # Fallback only after a real title exists.  Never accept a title-empty WPF
    # wrapper; that is the black placeholder seen on monitor 2.
    if path_wave and class_wave and title.strip():
        return True
    if path_wave and "wave" in title_l:
        return True
    return False

def _raw_wave_row_is_ready_enough_for_candidate(row: dict[str, Any]) -> bool:
    """Filter raw WAVE inventory before converting it to a clickable target."""
    try:
        rect = row.get("rect")
        if not isinstance(rect, Rect) or rect.width < 700 or rect.height < 450:
            return False
        if row.get("iconic"):
            return False
        if not row.get("visible"):
            return False
        probe = _raw_wave_window_info(row)
        return _is_wave_main_window(probe)
    except Exception:
        return False

def _score_wave_main_candidate(window: WindowInfo, *, launch_pid: int, old_pid: int) -> tuple[int, int, int]:
    score = 0
    pid = int(getattr(window, "process_id", 0) or 0)
    if launch_pid and pid == launch_pid:
        score += 1000
    if old_pid and pid != old_pid:
        score += 250
    title = str(getattr(window, "title", "") or "").casefold()
    class_name = str(getattr(window, "class_name", "") or "").casefold()
    if "hwndwrapper[wave.exe" in class_name:
        score += 400
    if "project" in title or "case" in title or "untitled" in title:
        score += 200
    rect = getattr(window, "rect", Rect(0, 0, 0, 0))
    return (score, int(rect.width * rect.height), int(getattr(window, "hwnd", 0) or 0))

def _wait_for_restarted_wave_main_window(
    *,
    old_hwnd: int,
    old_pid: int,
    launch_pid: int,
    timeout_s: float = 120.0,
) -> WindowInfo:
    """Wait until the real WPF WAVE main window is ready after relaunch.

    V69 still enumerates raw WAVE HWNDs for diagnostics, but it does **not**
    accept the tiny hidden title-empty WPF wrapper created while the splash is
    visible.  Accepting that wrapper produced the user's monitor-2 black WAVE
    surface.  We now wait for a visible, large, titled project window first,
    regardless of which monitor it opened on.
    """
    deadline = time.time() + timeout_s
    last_error = ""
    splash_seen = False
    last_snapshot: list[dict[str, Any]] = []
    last_diag_at = 0.0
    while time.time() < deadline:
        try:
            visible_windows = list_visible_windows(include_small=True)
            raw_rows = _enum_wave_windows_raw()
            last_snapshot = _raw_wave_snapshot_for_event(raw_rows)

            merged: dict[int, WindowInfo] = {}
            for w in visible_windows:
                merged[int(w.hwnd)] = w
            for row in raw_rows:
                hwnd = int(row.get("hwnd") or 0)
                # Keep raw rows in the event snapshot, but only add them to the
                # clickable candidate pool once they are visibly ready.
                if hwnd and hwnd not in merged and _raw_wave_row_is_ready_enough_for_candidate(row):
                    merged[hwnd] = _raw_wave_window_info(row)
            windows = list(merged.values())

            splash_present = any(
                _wave_identity_from_title_class_path(title=w.title, class_name=w.class_name, process_path=w.process_path)
                and _is_wave_splash_window(w)
                for w in windows
            )
            if splash_present:
                splash_seen = True
            candidates = [w for w in windows if _is_wave_main_window(w)]
            if candidates and not splash_present:
                candidates.sort(key=lambda w: _score_wave_main_candidate(w, launch_pid=launch_pid, old_pid=old_pid), reverse=True)
                chosen = candidates[0]
                chosen_pid = int(getattr(chosen, "process_id", 0) or 0)
                old_gone = not _window_is_alive(old_hwnd)
                chosen_is_not_old_hwnd = int(getattr(chosen, "hwnd", 0) or 0) != int(old_hwnd or 0)
                acquired_by_launch_pid = bool(launch_pid and chosen_pid == launch_pid)
                acquired_after_old_gone = bool(old_gone and chosen_is_not_old_hwnd)
                if acquired_by_launch_pid or acquired_after_old_gone:
                    record_event(
                        "production_wave_main_window_acquired_v69",
                        hwnd=chosen.hwnd,
                        pid=chosen_pid,
                        title=chosen.title,
                        class_name=chosen.class_name,
                        process_path=chosen.process_path,
                        rect=_json_safe(chosen.rect),
                        splash_seen=splash_seen,
                        candidate_count=len(candidates),
                        raw_wave_windows=last_snapshot,
                        old_hwnd_alive=not old_gone,
                        acquisition_policy="any_monitor_then_move",
                        acquired_by_launch_pid=acquired_by_launch_pid,
                        acquired_after_old_gone=acquired_after_old_gone,
                    )
                    return chosen

            now = time.time()
            if raw_rows and now - last_diag_at >= 10.0:
                last_diag_at = now
                record_event(
                    "production_wave_wait_inventory_v69",
                    launch_pid=launch_pid,
                    old_pid=old_pid,
                    old_hwnd=old_hwnd,
                    old_hwnd_alive=_window_is_alive(old_hwnd),
                    splash_seen=splash_seen,
                    candidate_count=len(candidates),
                    splash_present=splash_present,
                    raw_wave_windows=last_snapshot,
                )
        except Exception as exc:
            last_error = repr(exc)
        time.sleep(0.5)
    record_event(
        "production_wave_main_window_timeout_v69",
        launch_pid=launch_pid,
        old_pid=old_pid,
        old_hwnd=old_hwnd,
        old_hwnd_alive=_window_is_alive(old_hwnd),
        splash_seen=splash_seen,
        last_error=last_error,
        raw_wave_windows=last_snapshot,
    )
    raise WaveAutomationError(
        f"WAVE 재시작 후 메인 창을 찾지 못했습니다. "
        f"splash_seen={splash_seen} last_error={last_error} raw_wave_windows={last_snapshot}"
    )

def _restart_wave_process_for_production(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    item: ProductionItem,
    attempt: int,
    pause: float,
    target_monitor_index: int | None = None,
    target_monitor_rect: Rect | None = None,
) -> tuple[WindowInfo, Rect, dict[str, tuple[int, int]], list[str]]:
    """Hard-isolate a production item by restarting WAVE.

    V58 Add Case duplicated the existing topology and V59 Ctrl+N was ignored by
    the observed WAVE build when focus remained inside the Report surface.  The
    only deterministic blank-canvas isolation observed so far is therefore a
    controlled WAVE process restart before each mixed-process production item.
    This is deliberately scoped to production-plan isolation; single RO/NF/UF/
    CCRO commands keep their faster in-process soft reset paths.
    """
    old_hwnd = int(wave_window.hwnd)
    old_pid = int(getattr(wave_window, "process_id", 0) or _get_process_id(old_hwnd))
    exe_path = str(getattr(wave_window, "process_path", "") or _get_process_path(old_hwnd)).strip()
    if not exe_path or not Path(exe_path).exists():
        raise WaveAutomationError(f"WAVE 실행 파일 경로를 찾지 못했습니다: {exe_path!r}")

    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.key)[:80]
    desired_monitor = resolve_monitor_rect_by_index(target_monitor_index, fallback=target_monitor_rect or monitor)
    record_event(
        "production_wave_restart_start_v69",
        key=item.key,
        item_kind=item.kind,
        family=_production_family(item),
        attempt=attempt,
        old_hwnd=old_hwnd,
        old_pid=old_pid,
        exe_path=exe_path,
        target_monitor_index=target_monitor_index,
        target_monitor=_json_safe(desired_monitor),
    )
    try:
        screenshot(f"production_wave_restart_before_{label}_attempt_{attempt}_v69", monitor, old_hwnd)
    except Exception:
        pass

    # First clear benign overlays/prompts so the diagnostic bundle is clean.  Do
    # not depend on Ctrl+N or Add Case; if cleanup itself fails, continue to a
    # forced process termination because production manifests/PDFs are already
    # persisted outside WAVE.
    try:
        wait_for_report_loading_spinner(old_hwnd, monitor, f"production_wave_restart_{item.key}_pre", timeout_s=90.0)
        resolve_wave_blocking_dialogs(old_hwnd, monitor, f"production_wave_restart_{item.key}_pre", points)
    except Exception as exc:
        logging.warning("Production WAVE restart pre-cleanup skipped: %s", exc)

    terminate_result: dict[str, Any] = {}
    if old_pid:
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(old_pid), "/T", "/F"],
                text=True,
                capture_output=True,
                timeout=12,
                check=False,
            )
            terminate_result = {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-1000:],
                "stderr": completed.stderr[-1000:],
            }
        except Exception as exc:
            terminate_result = {"error": repr(exc)}
            logging.warning("WAVE process termination command failed: %s", exc)
    gone = _wait_window_gone(old_hwnd, timeout_s=18.0)
    if not gone:
        raise WaveAutomationError(f"WAVE 이전 창 종료 실패: hwnd={old_hwnd} pid={old_pid} result={terminate_result}")

    launch_result: dict[str, Any] = {}
    try:
        proc = subprocess.Popen(
            [exe_path],
            cwd=str(Path(exe_path).parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        launch_result = {"pid": int(getattr(proc, "pid", 0) or 0)}
    except Exception as exc:
        raise WaveAutomationError(f"WAVE 재시작 실행 실패: {exe_path!r} ({exc!r})") from exc

    launch_pid = int(launch_result.get("pid") or 0)
    new_window = _wait_for_restarted_wave_main_window(
        old_hwnd=old_hwnd,
        old_pid=old_pid,
        launch_pid=launch_pid,
        timeout_s=120.0,
    )

    # WAVE relaunches on the Windows primary monitor (display 1) on the user's
    # rig. That is expected. Acquisition is monitor-agnostic; only after the real
    # main HWND is found do we move it to the requested automation monitor.
    # On some WPF starts, the first main HWND becomes stale immediately after
    # the splash closes; wrap both move and activate so V69 can reacquire the
    # real Untitled Project window instead of burning a production attempt.
    try:
        move_window_to_monitor(new_window.hwnd, desired_monitor, maximize=True)
        activate_wave(new_window.hwnd)
        # After moving between monitors, give WPF a moment to repaint and make
        # sure we did not end up with the title-empty black placeholder.
        for _ in range(24):
            rebuilt = _rebuild_window_info(new_window)
            if _is_wave_main_window(rebuilt):
                new_window = rebuilt
                break
            time.sleep(0.5)
        else:
            raise WaveAutomationError(
                f"WAVE 재시작 창이 아직 실제 메인 화면으로 렌더링되지 않았습니다: "
                f"hwnd={new_window.hwnd} title={_get_window_text(new_window.hwnd)!r} "
                f"rect={_json_safe(_get_window_rect(new_window.hwnd))}"
            )
    except Exception as exc:
        logging.warning("WAVE main HWND became stale during monitor move/activate; reacquiring: %s", exc)
        record_event("production_wave_main_window_reacquire_v69", reason=repr(exc), previous_hwnd=getattr(new_window, "hwnd", None))
        new_window = _wait_for_restarted_wave_main_window(
            old_hwnd=old_hwnd,
            old_pid=old_pid,
            launch_pid=launch_pid,
            timeout_s=35.0,
        )
        move_window_to_monitor(new_window.hwnd, desired_monitor, maximize=True)
        activate_wave(new_window.hwnd)
        new_window = _rebuild_window_info(new_window)
    if _is_wave_splash_window(new_window):
        raise WaveAutomationError(f"WAVE 재시작 대상이 아직 SplashScreen입니다: hwnd={new_window.hwnd} title={new_window.title!r}")
    STATE.ACTIVE_WAVE_HWND = new_window.hwnd
    new_monitor = get_monitor_rect_for_window(new_window.hwnd)
    new_points = load_points(new_window.rect)
    time.sleep(max(1.0, pause))
    try:
        resolve_wave_blocking_dialogs(new_window.hwnd, new_monitor, f"production_wave_restart_{item.key}_post", new_points)
    except Exception as exc:
        logging.warning("Production WAVE restart post-cleanup skipped: %s", exc)
    try:
        screenshot(f"production_wave_restart_after_{label}_attempt_{attempt}_v69", new_monitor, new_window.hwnd)
    except Exception:
        pass

    actions = ["taskkill_wave", "launch_wave", "reacquire_window"]
    record_event(
        "production_wave_restart_done_v69",
        key=item.key,
        item_kind=item.kind,
        family=_production_family(item),
        attempt=attempt,
        old_hwnd=old_hwnd,
        old_pid=old_pid,
        new_hwnd=new_window.hwnd,
        new_pid=new_window.process_id,
        target_monitor_index=target_monitor_index,
        target_monitor=_json_safe(desired_monitor),
        new_monitor=_json_safe(new_monitor),
        new_rect=_json_safe(new_window.rect),
        terminate_result=terminate_result,
        launch_result=launch_result,
        actions=actions,
    )
    logging.info(
        "Production WAVE 재시작 격리 완료: key=%s attempt=%s old_pid=%s new_pid=%s hwnd=%s",
        item.key,
        attempt,
        old_pid,
        new_window.process_id,
        new_window.hwnd,
    )
    return new_window, new_monitor, new_points, actions

def _start_fresh_production_case(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    item: ProductionItem,
    attempt: int,
    pause: float,
    target_monitor_index: int | None = None,
    target_monitor_rect: Rect | None = None,
) -> tuple[WindowInfo, Rect, dict[str, tuple[int, int]]]:
    """Start a truly blank WAVE canvas for a production item.

    V69 uses controlled process restart isolation with splash-screen/main-window reacquisition.  The previous Ctrl+N approach
    did not reset the observed WAVE UI, leaving UF/CCRO topology in place and
    causing RO insertion and CCRO pass reconciliation failures.
    """
    record_event(
        "production_project_reset_start_v69",
        key=item.key,
        item_kind=item.kind,
        family=_production_family(item),
        attempt=attempt,
        strategy="restart_wave_process",
        target_monitor_index=target_monitor_index,
    )
    new_window, new_monitor, new_points, actions = _restart_wave_process_for_production(
        wave_window,
        monitor,
        points,
        item=item,
        attempt=attempt,
        pause=pause,
        target_monitor_index=target_monitor_index,
        target_monitor_rect=target_monitor_rect,
    )
    record_event(
        "production_project_reset_done_v69",
        key=item.key,
        item_kind=item.kind,
        family=_production_family(item),
        attempt=attempt,
        strategy="restart_wave_process",
        target_monitor_index=target_monitor_index,
        actions=actions,
    )
    return new_window, new_monitor, new_points

__all__ = [name for name in globals() if not name.startswith("__")]
