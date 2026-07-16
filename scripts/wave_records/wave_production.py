#!/usr/bin/env python3
"""V73 split production runner.

This module keeps the public API used by wave_cli.py, but delegates plan parsing,
checkpoint/manifest persistence, and WAVE restart/reacquire logic to focused
modules.
"""
from __future__ import annotations

from wave_common import *
from wave_batch import run_ro_excel_batch
from wave_dialogs import resolve_wave_blocking_dialogs, wait_for_report_loading_spinner
from wave_runtime import record_event
from wave_ro_engine import _validate_case_automation_support
from wave_uf import run_uf_video_case
from wave_ccro import run_ccro_video_case
from wave_windows import focus_wave, resolve_monitor_rect_by_index
from wave_production_plan import (
    PRODUCTION_AUTOMATION_VERSION,
    ProductionItem,
    load_production_plan,
    write_production_plan_example,
    dry_run_production_plan,
    _production_family,
    _plan_requires_case_isolation,
)
from wave_production_state import (
    _default_checkpoint_path,
    _load_checkpoint,
    _write_checkpoint,
    _write_manifest,
    _checkpoint_status,
    _mark_checkpoint_item,
)
from wave_production_restart import _start_fresh_production_case


def _run_one_item(
    item: ProductionItem,
    *,
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    pause: float,
    long_wait: float,
    validate_pdf: bool,
) -> list[Path]:
    if item.kind == "ro_excel":
        if item.ro_case is None:
            raise WaveAutomationError(f"{item.key}: ro_case가 준비되지 않았습니다.")
        raw = item.raw
        return run_ro_excel_batch(
            wave_window,
            monitor,
            points,
            [item.ro_case],
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
            allow_experimental=bool(raw.get("allow_experimental_ro", True)),
            allow_experimental_batch=bool(raw.get("allow_experimental_batch", True)),
            continue_on_convergence=bool(raw.get("continue_on_convergence", False)),
        )
    if item.kind == "uf_video":
        raw = item.raw
        return run_uf_video_case(
            wave_window,
            monitor,
            points,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
            module=raw.get("module") or raw.get("uf_module"),
            pdf_name=raw.get("pdf_name") or raw.get("uf_pdf_name"),
            water_profile=raw.get("water_profile") or raw.get("uf_water_profile"),
            feed_flow_m3h=raw.get("feed_flow_m3h") or raw.get("feed_flow") or raw.get("uf_feed_flow"),
        )
    if item.kind == "ccro_video":
        raw = item.raw
        return run_ccro_video_case(
            wave_window,
            monitor,
            points,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
            element_type=raw.get("element_type") or raw.get("ccro_element"),
            pdf_name=raw.get("pdf_name") or raw.get("ccro_pdf_name"),
            water_profile=raw.get("water_profile") or raw.get("ccro_water_profile"),
            feed_flow_m3h=raw.get("feed_flow_m3h") or raw.get("feed_flow") or raw.get("ccro_feed_flow"),
            recovery_pct=raw.get("recovery_pct") or raw.get("ccro_recovery"),
            pass_count=raw.get("pass_count") or raw.get("ccro_pass_count"),
            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
            pf_feed_ratio_pct=(
                raw.get("pf_feed_ratio_pct")
                or raw.get("ccro_pf_feed_ratio_pct")
                or raw.get("target_pf_feed_ratio_pct")
            ),
            pf_recovery_pct=(
                raw.get("pf_recovery_pct")
                or raw.get("ccro_pf_recovery_pct")
                or raw.get("target_pf_recovery_pct")
            ),
            # V101 PLAN FIELD PASSTHROUGH
            pv_per_stage=(raw.get("pv_per_stage") or raw.get("ccro_pv_per_stage") or raw.get("pvs_per_stage")),
            elements_per_pv=(raw.get("elements_per_pv") or raw.get("ccro_elements_per_pv") or raw.get("elements_per_vessel")),
            flow_factor=(raw.get("flow_factor") or raw.get("ccro_flow_factor") or raw.get("ro_flow_factor")),
            pass_back_pressure_bar=(raw.get("pass_back_pressure_bar") or raw.get("ccro_pass_back_pressure_bar") or raw.get("ro_pass_back_pressure")),
            stage_back_pressure_bar=(raw.get("stage_back_pressure_bar") or raw.get("ccro_stage_back_pressure_bar") or raw.get("stage_back_pressure_row")),
            stage_flow_factor=(raw.get("stage_flow_factor") or raw.get("ccro_stage_flow_factor") or raw.get("stage_flow_factor_row")),
            pass2_pv_per_stage=(raw.get("pass2_pv_per_stage") or raw.get("ccro_pass2_pv_per_stage")),
            pass2_elements_per_pv=(raw.get("pass2_elements_per_pv") or raw.get("ccro_pass2_elements_per_pv")),
        )
    raise WaveAutomationError(f"지원하지 않는 Production item kind={item.kind!r}")

def run_production_plan(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    plan_path: str | Path,
    checkpoint_path: str | Path | None,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
    max_attempts: int,
    stop_on_failure: bool,
    rerun_completed: bool,
    exit_zero_with_failures: bool,
    restart_monitor_index: int | None = None,
) -> list[Path]:
    if max_attempts < 1:
        raise WaveAutomationError("--production-max-attempts는 1 이상이어야 합니다.")
    plan_file = Path(plan_path).expanduser().resolve()
    plan, items = load_production_plan(plan_file)
    checkpoint_file = Path(checkpoint_path).expanduser().resolve() if checkpoint_path else _default_checkpoint_path(plan_file)
    checkpoint = _load_checkpoint(checkpoint_file)
    isolate_process_families = _plan_requires_case_isolation(plan, items)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "automation_version": PRODUCTION_AUTOMATION_VERSION,
        "name": plan.get("name", plan_file.stem),
        "plan_path": str(plan_file),
        "checkpoint_path": str(checkpoint_file),
        "status": "running",
        "started": datetime.now().isoformat(timespec="seconds"),
        "case_count": len(items),
        "max_attempts": max_attempts,
        "stop_on_failure": stop_on_failure,
        "rerun_completed": rerun_completed,
        "validate_pdf": validate_pdf,
        "fresh_project_per_item": isolate_process_families,
        "restart_monitor_index": restart_monitor_index,
        "restart_target_monitor": _json_safe(resolve_monitor_rect_by_index(restart_monitor_index, fallback=monitor)) if isolate_process_families else None,
        "items": [],
    }
    _write_manifest(manifest)
    restart_target_monitor = resolve_monitor_rect_by_index(restart_monitor_index, fallback=monitor) if isolate_process_families else monitor
    record_event("production_plan_start_v69", plan=str(plan_file), checkpoint=str(checkpoint_file), case_count=len(items), fresh_project_per_item=isolate_process_families, restart_monitor_index=restart_monitor_index, restart_target_monitor=_json_safe(restart_target_monitor))

    outputs: list[Path] = []
    failed_keys: list[str] = []
    skipped_keys: list[str] = []
    current_family: str | None = None

    for index, item in enumerate(items, start=1):
        prior_status = _checkpoint_status(checkpoint, item.key)
        if prior_status in {"success", "constraint_adjusted"} and not rerun_completed:
            entry = {
                "index": index,
                "key": item.key,
                "kind": item.kind,
                "status": "skipped_completed",
                "prior_status": prior_status,
                "input": item.manifest_input(),
            }
            manifest["items"].append(entry)
            skipped_keys.append(item.key)
            logging.info("=== Production %s/%s SKIP completed: %s ===", index, len(items), item.key)
            _write_manifest(manifest)
            continue

        entry = {
            "index": index,
            "key": item.key,
            "kind": item.kind,
            "status": "running",
            "attempts": [],
            "input": item.manifest_input(),
        }
        manifest["items"].append(entry)
        _write_manifest(manifest)
        logging.info("=== Production %s/%s START: %s kind=%s ===", index, len(items), item.key, item.kind)

        item_outputs: list[Path] = []
        success = False
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            attempt_entry = {
                "attempt": attempt,
                "started": datetime.now().isoformat(timespec="seconds"),
                "status": "running",
            }
            entry["attempts"].append(attempt_entry)
            entry["status"] = "running"
            _mark_checkpoint_item(checkpoint, item.key, status="running", attempt=attempt, payload={"kind": item.kind})
            _write_checkpoint(checkpoint_file, checkpoint)
            _write_manifest(manifest)
            record_event("production_item_attempt_start_v69", key=item.key, item_kind=item.kind, attempt=attempt)
            try:
                item_family = _production_family(item)
                if isolate_process_families:
                    wave_window, monitor, points = _start_fresh_production_case(
                        wave_window,
                        monitor,
                        points,
                        item=item,
                        attempt=attempt,
                        pause=pause,
                        target_monitor_index=restart_monitor_index,
                        target_monitor_rect=restart_target_monitor,
                    )
                    current_family = item_family
                try:
                    wait_for_report_loading_spinner(
                        wave_window.hwnd,
                        monitor,
                        f"production_{item.key}_attempt_{attempt}_preflight",
                        timeout_s=max(90.0, long_wait * 10.0),
                    )
                    resolve_wave_blocking_dialogs(wave_window.hwnd, monitor, f"production_{item.key}_attempt_{attempt}_preflight", points)
                except WaveConvergenceError:
                    raise
                except Exception as cleanup_exc:
                    logging.warning("Production preflight dialog cleanup skipped: %s", cleanup_exc)
                focus_wave(wave_window.hwnd)
                item_outputs = _run_one_item(
                    item,
                    wave_window=wave_window,
                    monitor=monitor,
                    points=points,
                    pause=pause,
                    long_wait=long_wait,
                    validate_pdf=validate_pdf,
                )
                outputs.extend(item_outputs)
                attempt_entry.update(
                    status="success",
                    finished=datetime.now().isoformat(timespec="seconds"),
                    pdfs=[str(path) for path in item_outputs],
                    size_bytes=[path.stat().st_size for path in item_outputs if path.exists()],
                )
                entry.update(
                    status="success",
                    pdfs=[str(path) for path in item_outputs],
                    finished=datetime.now().isoformat(timespec="seconds"),
                )
                _mark_checkpoint_item(
                    checkpoint,
                    item.key,
                    status="success",
                    attempt=attempt,
                    payload={"kind": item.kind, "pdfs": [str(path) for path in item_outputs]},
                )
                _write_checkpoint(checkpoint_file, checkpoint)
                _write_manifest(manifest)
                record_event("production_item_success_v69", key=item.key, item_kind=item.kind, attempt=attempt, pdfs=[str(path) for path in item_outputs])
                logging.info("=== Production SUCCESS: %s attempt=%s ===", item.key, attempt)
                success = True
                break
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                attempt_entry.update(
                    status="failed",
                    finished=datetime.now().isoformat(timespec="seconds"),
                    error=last_error,
                    traceback=traceback.format_exc(),
                )
                entry.update(status="retrying" if attempt < max_attempts else "failed", error=last_error)
                _mark_checkpoint_item(
                    checkpoint,
                    item.key,
                    status="retrying" if attempt < max_attempts else "failed",
                    attempt=attempt,
                    payload={"kind": item.kind, "error": last_error},
                )
                _write_checkpoint(checkpoint_file, checkpoint)
                _write_manifest(manifest)
                logging.exception("Production item 실패: key=%s attempt=%s/%s error=%s", item.key, attempt, max_attempts, exc)
                record_event("production_item_failed_v69", key=item.key, item_kind=item.kind, attempt=attempt, error=last_error)
                try:
                    screenshot_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.key)[:80]
                    from wave_diagnostics import screenshot
                    screenshot(f"production_failure_{screenshot_label}_attempt_{attempt}", monitor, wave_window.hwnd)
                except Exception:
                    pass
                if attempt < max_attempts:
                    time.sleep(max(2.0, pause))
                    continue
        if not success:
            failed_keys.append(item.key)
            logging.error("=== Production FINAL FAILED: %s error=%s ===", item.key, last_error)
            if stop_on_failure:
                break
        else:
            time.sleep(max(0.8, pause))

    statuses = [str(item.get("status", "")) for item in manifest["items"]]
    completed = [status for status in statuses if status == "success"]
    failed = [status for status in statuses if status == "failed"]
    if failed_keys:
        manifest["status"] = "completed_with_failures" if not stop_on_failure else "failed"
    elif len(completed) + len(skipped_keys) == len(items):
        manifest["status"] = "success"
    else:
        manifest["status"] = "completed_partial"
    manifest["finished"] = datetime.now().isoformat(timespec="seconds")
    manifest["successful_count"] = len(completed)
    manifest["skipped_completed_count"] = len(skipped_keys)
    manifest["failed_count"] = len(failed_keys)
    manifest["failed_keys"] = failed_keys
    manifest["pdfs"] = [str(path) for path in outputs]
    _write_manifest(manifest)
    _write_checkpoint(checkpoint_file, checkpoint)
    record_event("production_plan_finished_v69", status=manifest["status"], failed_keys=failed_keys, pdf_count=len(outputs))

    if failed_keys and not exit_zero_with_failures:
        raise WaveAutomationError(
            f"Production plan completed with failures: {failed_keys}. "
            f"manifest={STATE.RUN_DIR / 'production_manifest_v69.json' if STATE.RUN_DIR else ''}"
        )
    return outputs


__all__ = [
    "ProductionItem",
    "load_production_plan",
    "write_production_plan_example",
    "dry_run_production_plan",
    "run_production_plan",
]
