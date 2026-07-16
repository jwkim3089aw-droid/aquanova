#!/usr/bin/env python3
"""Refactored WAVE automation module: cli."""
from __future__ import annotations

from wave_common import *
from wave_batch import expand_cases_for_wave_global_temperature, run_ro_excel_batch, run_two_ro_cases, write_ro_catalog_artifacts
from wave_uf import run_uf_video_case
from wave_ccro import run_ccro_video_case
from wave_production import dry_run_production_plan, run_production_plan, write_production_plan_example
from wave_diagnostics import dump_ui_snapshot, save_click_map, save_coordinate_manifest, screenshot
from wave_dialogs import _find_flow_calculator_dialog, _wait_window_closed, configure_flow_calculator_dialog
from wave_pdf import dismiss_export_success_dialog, export_pdf
from wave_recorded import configure_recorded_ro_case
from wave_ro_engine import _validate_case_automation_support
from wave_runtime import create_feedback_bundle, setup_logging
from wave_uia import uia_configure_flow_calculator_recoveries
from wave_windows import _get_class_name, _get_process_id, _get_process_path, _get_window_rect, _get_window_text, _require_windows, activate_wave, bring_window_to_front, calibrate, countdown, find_wave_window, focus_wave, get_monitor_rect_for_window, list_visible_windows, load_points


def _dismiss_ccro_startup_total_cycles_error() -> list[str]:
    """Close stale CCRO Total Cycles error boxes before startup dialog cleanup."""
    actions: list[str] = []
    for dialog in list_visible_windows(include_small=True):
        if str(dialog.title or "").strip().lower() != "total cycles error":
            continue
        logging.warning("시작 시 CCRO Total Cycles Error 잔존 창을 닫습니다: hwnd=%s rect=%s", dialog.hwnd, dialog.rect)
        try:
            bring_window_to_front(dialog.hwnd, restore_if_minimized=False)
            pyautogui.press("enter")
            time.sleep(0.45)
        except Exception as exc:
            raise WaveAutomationError(f"시작 시 Total Cycles Error 창을 닫지 못했습니다: {exc!r}")
        actions.append("startup_total_cycles_error_acknowledged")
    return actions


def _dismiss_ccro_startup_flow_calculator(dialog: WindowInfo) -> bool:
    """Close a stale CCRO Flow Calculator left by a previous failed probe.

    Running the next CCRO case will reopen the calculator with pass-specific
    targeting.  Dismissing the stale dialog avoids applying the wrong startup
    recovery value to an old 2-pass layout.
    """
    title = str(dialog.title or "").lower()
    if "ccro flow calculator" not in title:
        return False
    logging.warning("시작 시 열린 CCRO Flow Calculator를 닫고 새 CCRO 사례에서 다시 설정합니다.")
    bring_window_to_front(dialog.hwnd)
    pyautogui.press("esc")
    time.sleep(0.8)
    if ctypes.windll.user32.IsWindow(dialog.hwnd) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
        pyautogui.hotkey("alt", "f4")
        time.sleep(0.8)
    if ctypes.windll.user32.IsWindow(dialog.hwnd) and ctypes.windll.user32.IsWindowVisible(dialog.hwnd):
        logging.warning("CCRO Flow Calculator가 Esc/Alt+F4 후에도 열려 있습니다. 이후 단계에서 재사용을 시도합니다.")
        return False
    return True



def print_windows() -> None:
    _require_windows()
    windows = list_visible_windows()
    print("\n현재 보이는 상위 창 목록")
    for item in windows:
        print(
            f"hwnd={item.hwnd:<10} "
            f"rect=({item.rect.left},{item.rect.top},{item.rect.right},{item.rect.bottom}) "
            f"exe={Path(item.process_path).name or 'N/A':<24} title={item.title}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "WAVE RO/UF/CCRO/PDF 자동화 V69: 기존 단일/2조건 + 확장 Excel/JSON 배치 + "
            "독립 Feed 온도범위 + 1~5 Stage/1~2 Pass + 압력/Flow Factor/Chemical 스키마"
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--calibrate", action="store_true", help="WAVE 창 상대 좌표를 직접 보정"
    )
    mode.add_argument(
        "--run", action="store_true", help="검증된 RO 단일 사례 입력부터 PDF까지 실행"
    )
    mode.add_argument(
        "--run-two-ro-cases",
        action="store_true",
        help="V18에서 검증된 RO 조건 2개를 연속 실행",
    )
    mode.add_argument(
        "--run-ro-excel",
        metavar="PATH",
        help="Excel(.xlsx) 또는 JSON의 RO 사례를 Batch_Order 순서로 실행",
    )
    mode.add_argument(
        "--run-uf-video-case",
        action="store_true",
        help="V69: 2026-07-06 UF 설정 영상 기반 단일 UF 사례를 실행",
    )
    mode.add_argument(
        "--run-ccro-video-case",
        action="store_true",
        help="V69: 2026-07-06 CCRO 설정 영상 기반 보수적 단일 CCRO 사례를 실행",
    )
    mode.add_argument(
        "--run-production-plan",
        metavar="PATH",
        help="V69: RO/NF/UF/CCRO 혼합 production plan JSON을 체크포인트/manifest 기반으로 실행",
    )
    mode.add_argument(
        "--dry-run-production-plan",
        metavar="PATH",
        help="V69: WAVE 조작 없이 production plan JSON을 검증하고 실행 항목을 출력",
    )
    mode.add_argument(
        "--export-production-plan-example",
        action="store_true",
        help="V69: results 폴더에 production plan 예시 JSON을 생성",
    )
    mode.add_argument(
        "--dry-run-ro-excel",
        metavar="PATH",
        help="WAVE를 조작하지 않고 Excel/JSON 스키마·사례만 검증",
    )
    mode.add_argument(
        "--export-ro-catalog",
        action="store_true",
        help="RO UI 카탈로그와 확장 스키마 예시 JSON을 results에 생성",
    )
    mode.add_argument(
        "--export-only",
        action="store_true",
        help="현재 계산 완료 화면에서 PDF 저장만 실행",
    )
    mode.add_argument(
        "--list-windows",
        action="store_true",
        help="자동화가 볼 수 있는 창 제목 목록 출력",
    )
    mode.add_argument(
        "--diagnose-only",
        action="store_true",
        help="WAVE/모니터/창/UI 트리와 스크린샷만 수집",
    )
    parser.add_argument(
        "--ro-sheet",
        default="01_PASS_STAGE",
        help="--run-ro-excel에서 읽을 워크시트명",
    )
    parser.add_argument(
        "--batch-group",
        default=None,
        help="Excel의 Batch_Group 값으로 사례를 필터링",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Excel 배치에서 특정 Case_ID만 실행. 여러 번 지정 가능",
    )
    parser.add_argument(
        "--start-order", type=int, default=None, help="최소 Batch_Order"
    )
    parser.add_argument("--end-order", type=int, default=None, help="최대 Batch_Order")
    parser.add_argument(
        "--allow-experimental-ro",
        action="store_true",
        help="2 Pass/Boost Pressure/Chemical-Degas 등 experimental 설정 실행 허용",
    )
    parser.add_argument(
        "--allow-experimental-batch",
        action="store_true",
        help="Chemical/Degas 등 experimental 사례 여러 개를 한 프로젝트에서 연속 실행(진단 전용)",
    )
    parser.add_argument(
        "--continue-on-convergence",
        action="store_true",
        help="명시적 Convergence Error 사례만 실패 기록 후 다음 사례 진행",
    )
    parser.add_argument(
        "--window-title",
        default=None,
        help="WAVE 창 제목 일부. 자동 감지가 실패할 때 예: 'Untitled Project'",
    )
    parser.add_argument(
        "--pdf-name",
        default="RO_WellWaterMed_BW30_400_R75_T25.pdf",
        help="results 폴더에 저장할 PDF 파일명",
    )
    parser.add_argument(
        "--add-ro",
        action="store_true",
        help="빈 공정 캔버스에서 RO 아이콘을 드래그해 추가",
    )
    parser.add_argument(
        "--pause", type=float, default=0.7, help="일반 클릭 사이 대기시간"
    )
    parser.add_argument(
        "--long-wait", type=float, default=4.0, help="계산/화면전환 대기시간"
    )
    parser.add_argument(
        "--skip-pdf-validation",
        action="store_true",
        help="생성 PDF의 원수/온도/회수율/PV/막 모델 검증을 생략(진단용)",
    )
    parser.add_argument(
        "--uf-module",
        default=None,
        help="--run-uf-video-case에서 선택할 UF Module명. 기본값: Ultrafiltration SFP-2660",
    )
    parser.add_argument(
        "--uf-water-profile",
        default=None,
        help="--run-uf-video-case에서 사용할 Water Library profile. 기본값: Well Water - Med Hardness",
    )
    parser.add_argument(
        "--uf-feed-flow",
        type=float,
        default=None,
        help="--run-uf-video-case에서 사용할 Feed Flow(m3/h). 기본값: 100",
    )
    parser.add_argument(
        "--uf-pdf-name",
        default=None,
        help="--run-uf-video-case 결과 PDF 파일명",
    )
    parser.add_argument(
        "--ccro-element",
        default=None,
        help="--run-ccro-video-case에서 선택할 CCRO Element Type. 기본값: FilmTec™ SOAR 5000i",
    )
    parser.add_argument(
        "--ccro-water-profile",
        default=None,
        help="--run-ccro-video-case에서 사용할 Water Library profile. 기본값: Well Water - Med Hardness",
    )
    parser.add_argument(
        "--ccro-feed-flow",
        type=float,
        default=None,
        help="--run-ccro-video-case에서 사용할 Feed Flow(m3/h). 기본값: 100",
    )
    parser.add_argument(
        "--ccro-recovery",
        type=float,
        default=None,
        help="--run-ccro-video-case에서 사용할 보수적 Pass Recovery(%). 기본값: 75",
    )
    parser.add_argument(
        "--ccro-pass-count",
        type=int,
        choices=(1, 2),
        default=None,
        help="--run-ccro-video-case에서 사용할 CCRO Pass 수. 기본값: 1, V55에서 2-Pass 보수 프로브 지원",
    )
    parser.add_argument(
        "--ccro-pass2-recovery",
        type=float,
        default=None,
        help="--ccro-pass-count 2에서 사용할 Pass 2 Recovery(%). 기본값: 50",
    )
    parser.add_argument(
        "--ccro-pdf-name",
        default=None,
        help="--run-ccro-video-case 결과 PDF 파일명",
    )
    parser.add_argument(
        "--production-checkpoint",
        default=None,
        help="--run-production-plan 체크포인트 JSON 경로. 기본값은 results/_production_state/<plan>_checkpoint_v69.json",
    )
    parser.add_argument(
        "--production-max-attempts",
        type=int,
        default=2,
        help="Production 각 항목 최대 시도 횟수. 기본값 2",
    )
    parser.add_argument(
        "--production-stop-on-failure",
        action="store_true",
        help="Production 항목 최종 실패 시 즉시 중단. 기본값은 실패 기록 후 다음 항목 진행",
    )
    parser.add_argument(
        "--production-rerun-completed",
        action="store_true",
        help="체크포인트에서 이미 success인 항목도 다시 실행",
    )
    parser.add_argument(
        "--production-exit-zero-with-failures",
        action="store_true",
        help="실패 항목이 있어도 전체 실행을 0으로 종료. 기본값은 manifest 작성 후 최종 실패 처리",
    )
    parser.add_argument(
        "--production-restart-monitor-index",
        type=int,
        default=None,
        help="V69: WAVE 재시작 후 강제로 배치할 모니터 번호(1부터). 예: 디스플레이 2는 2",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08

    if args.export_ro_catalog:
        json_path, schema_path = write_ro_catalog_artifacts(RESULTS_DIR)
        print(f"RO UI 카탈로그: {json_path}")
        print(f"RO Excel 스키마 예시: {schema_path}")
        print(f"카탈로그 항목 수: {len(RO_UI_CATALOG)}")
        return 0

    if args.export_production_plan_example:
        example_path = write_production_plan_example(RESULTS_DIR)
        print(f"V69 Production plan 예시: {example_path}")
        return 0

    if args.dry_run_production_plan:
        result = dry_run_production_plan(args.dry_run_production_plan)
        print(
            f"V69 Production plan 검증 완료: {result['case_count']}개 항목 "
            f"name={result.get('name') or '-'}"
        )
        for item in result["items"]:
            print(
                f"  {item['index']:02d}. key={item['key']} kind={item['kind']} "
                f"outputs={item.get('expected_outputs') or []}"
            )
        return 0

    ro_cases: list[ROCaseConfig] = []
    batch_input = args.run_ro_excel or args.dry_run_ro_excel
    if batch_input:
        ro_cases = load_ro_cases(batch_input, args.ro_sheet)
        if args.batch_group is not None:
            wanted_group = str(args.batch_group).strip().casefold()
            ro_cases = [
                case
                for case in ro_cases
                if case.batch_group.strip().casefold() == wanted_group
            ]
            if not ro_cases:
                raise SystemExit(
                    f"Batch_Group={args.batch_group!r}인 실행 사례가 없습니다."
                )
        selected_ids = set(args.case_id or [])
        if selected_ids:
            ro_cases = [case for case in ro_cases if case.case_id in selected_ids]
            missing = selected_ids - {case.case_id for case in ro_cases}
            if missing:
                raise SystemExit(f"Case_ID를 찾지 못했습니다: {sorted(missing)}")
        if args.start_order is not None:
            ro_cases = [
                case for case in ro_cases if case.batch_order >= args.start_order
            ]
        if args.end_order is not None:
            ro_cases = [case for case in ro_cases if case.batch_order <= args.end_order]
        for case in ro_cases:
            _validate_case_automation_support(
                case, allow_experimental=args.allow_experimental_ro
            )

    if args.dry_run_ro_excel:
        input_count = len(ro_cases)
        ro_cases, temperature_expansion = expand_cases_for_wave_global_temperature(ro_cases)
        print(
            f"RO 스키마 검증 완료: 입력 {input_count}개 -> "
            f"WAVE 실제 실행 {len(ro_cases)}개"
        )
        for item in temperature_expansion:
            if len(item["expanded_case_ids"]) > 1:
                print(
                    f"  온도 분할: {item['source_case_id']} -> "
                    f"{', '.join(item['expanded_case_ids'])}"
                )
        for index, case in enumerate(ro_cases, start=1):
            print(
                f"  {index:02d}. order={case.batch_order} id={case.case_id} "
                f"tier={case.automation_tier} group={case.batch_group or '-'} "
                f"passes={case.pass_count} stages={[p.stage_count for p in case.passes]} "
                f"feedT={case.resolved_feed_temperature_min_c:g}/"
                f"{case.feed_temperature_design_c:g}/"
                f"{case.resolved_feed_temperature_max_c:g} "
                f"profile={case.water_profile!r} pdf={case.pdf_name!r}"
            )
        return 0

    if args.list_windows:
        print_windows()
        return 0

    if args.calibrate:
        if PYAUTOGUI_IMPORT_ERROR is not None:
            raise SystemExit(f"pyautogui 초기화 실패: {PYAUTOGUI_IMPORT_ERROR}")
        calibrate(args.window_title)
        return 0

    if PYAUTOGUI_IMPORT_ERROR is not None:
        raise SystemExit(
            "WAVE UI 실행에는 pyautogui가 필요합니다. "
            f"초기화 오류={PYAUTOGUI_IMPORT_ERROR!r}"
        )

    log_path = setup_logging()
    startup_recovery = (
        _fmt_value(ro_cases[0].passes[0].recovery_pct) if ro_cases else "75"
    )
    settings = Settings(
        recovery_pct=startup_recovery,
        add_ro=args.add_ro,
        pause=args.pause,
        long_wait=args.long_wait,
        validate_pdf=bool(
            (args.run or args.run_two_ro_cases or args.run_ro_excel or args.run_uf_video_case or args.run_ccro_video_case or args.run_production_plan)
            and not args.skip_pdf_validation
        ),
    )
    countdown()

    try:
        window = find_wave_window(args.window_title)
        activate_wave(window.hwnd)
        window = WindowInfo(
            hwnd=window.hwnd,
            title=_get_window_text(window.hwnd),
            process_path=_get_process_path(window.hwnd),
            rect=_get_window_rect(window.hwnd),
            process_id=_get_process_id(window.hwnd),
            class_name=_get_class_name(window.hwnd),
        )
        STATE.ACTIVE_WAVE_HWND = window.hwnd
        monitor = get_monitor_rect_for_window(window.hwnd)
        points = load_points(window.rect)

        if args.run_ccro_video_case:
            _dismiss_ccro_startup_total_cycles_error()

        startup_flow_dialog = _find_flow_calculator_dialog(window.hwnd, timeout=0.2)
        if startup_flow_dialog is not None:
            if args.run_ccro_video_case and _dismiss_ccro_startup_flow_calculator(startup_flow_dialog):
                focus_wave(window.hwnd)
            else:
                logging.warning(
                    "시작 시 열린 Flow Calculator를 감지했습니다. 첫 사례 회수율을 적용하고 닫습니다."
                )
                if ro_cases and ro_cases[0].pass_count == 2:
                    result = uia_configure_flow_calculator_recoveries(
                        startup_flow_dialog.hwnd,
                        [p.recovery_pct for p in ro_cases[0].passes],
                    )
                    if not result.get("ok") or not _wait_window_closed(
                        startup_flow_dialog.hwnd, 15.0
                    ):
                        raise WaveAutomationError(
                            f"시작 시 열린 다중 Pass Flow Calculator 정리 실패: {result}"
                        )
                else:
                    configure_flow_calculator_dialog(
                        startup_flow_dialog,
                        settings.recovery_pct,
                        monitor,
                        window.hwnd,
                        settings,
                        "startup_existing",
                    )
                focus_wave(window.hwnd)

        save_coordinate_manifest(window.hwnd, points, "startup")
        save_click_map(
            "startup_home",
            window.hwnd,
            points,
            [
                "feed_setup_tab",
                "home_tab",
                "home_feed_flow",
                "ro_icon",
                "uf_icon",
                "ccro_icon",
                "process_drop_point",
                "reverse_osmosis_tab",
                "ultrafiltration_tab",
                "ccro_tab",
                "report_ribbon_tab",
            ],
        )
        dump_ui_snapshot("startup", window.hwnd, monitor)
        screenshot("startup", monitor, window.hwnd)
        write_ro_catalog_artifacts(STATE.RUN_DIR or RESULTS_DIR)
        logging.info("시작 진단 및 RO 카탈로그 수집 완료")

        if args.diagnose_only:
            bundle = create_feedback_bundle("diagnose")
            print(f"\n진단 완료: {bundle}")
            if STATE.LAST_RUN_ARCHIVE:
                print(f"실행 ZIP: {STATE.LAST_RUN_ARCHIVE}")
            return 0

        targets: list[Path] = []
        if args.run_production_plan:
            targets = run_production_plan(
                window,
                monitor,
                points,
                plan_path=args.run_production_plan,
                checkpoint_path=args.production_checkpoint,
                pause=args.pause,
                long_wait=args.long_wait,
                validate_pdf=not args.skip_pdf_validation,
                max_attempts=args.production_max_attempts,
                stop_on_failure=args.production_stop_on_failure,
                rerun_completed=args.production_rerun_completed,
                exit_zero_with_failures=args.production_exit_zero_with_failures,
                restart_monitor_index=args.production_restart_monitor_index,
            )
        elif args.run_ro_excel:
            targets = run_ro_excel_batch(
                window,
                monitor,
                points,
                ro_cases,
                pause=args.pause,
                long_wait=args.long_wait,
                validate_pdf=not args.skip_pdf_validation,
                allow_experimental=args.allow_experimental_ro,
                allow_experimental_batch=args.allow_experimental_batch,
                continue_on_convergence=args.continue_on_convergence,
            )
        elif args.run_two_ro_cases:
            targets = run_two_ro_cases(
                window,
                monitor,
                points,
                pause=args.pause,
                long_wait=args.long_wait,
                validate_pdf=not args.skip_pdf_validation,
            )
        elif args.run_uf_video_case:
            targets = run_uf_video_case(
                window,
                monitor,
                points,
                pause=args.pause,
                long_wait=args.long_wait,
                validate_pdf=not args.skip_pdf_validation,
                module=args.uf_module,
                pdf_name=args.uf_pdf_name,
                water_profile=args.uf_water_profile,
                feed_flow_m3h=args.uf_feed_flow,
            )
        elif args.run_ccro_video_case:
            targets = run_ccro_video_case(
                window,
                monitor,
                points,
                pause=args.pause,
                long_wait=args.long_wait,
                validate_pdf=not args.skip_pdf_validation,
                element_type=args.ccro_element,
                pdf_name=args.ccro_pdf_name,
                water_profile=args.ccro_water_profile,
                feed_flow_m3h=args.ccro_feed_flow,
                recovery_pct=args.ccro_recovery,
                pass_count=args.ccro_pass_count,
                pass2_recovery_pct=args.ccro_pass2_recovery,
            )
        else:
            if args.run:
                configure_recorded_ro_case(window.hwnd, monitor, points, settings)
            target = export_pdf(window, monitor, points, args.pdf_name, settings)
            dismiss_export_success_dialog(window, monitor)
            targets = [target]
    except KeyboardInterrupt as exc:
        logging.warning("사용자가 Ctrl+C로 자동화를 중단했습니다.")
        try:
            if STATE.ACTIVE_WAVE_HWND:
                monitor_now = get_monitor_rect_for_window(STATE.ACTIVE_WAVE_HWND)
                screenshot("keyboard_interrupt", monitor_now, STATE.ACTIVE_WAVE_HWND)
        except Exception:
            pass
        bundle = create_feedback_bundle("ABORTED", exc)
        print("\n사용자 중단: Ctrl+C")
        if STATE.LAST_RUN_ARCHIVE:
            print(f"실행 ZIP: {STATE.LAST_RUN_ARCHIVE}")
        if bundle:
            print(f"피드백 ZIP: {bundle}")
        return 130
    except pyautogui.FailSafeException as exc:
        logging.error("사용자가 failsafe로 자동화를 중단했습니다.")
        bundle = create_feedback_bundle("ABORTED", exc)
        if STATE.LAST_RUN_ARCHIVE:
            print(f"실행 ZIP: {STATE.LAST_RUN_ARCHIVE}")
        if bundle:
            print(f"피드백 ZIP: {bundle}")
        return 130
    except Exception as exc:
        logging.exception("자동화 실패: %s", exc)
        try:
            if STATE.ACTIVE_WAVE_HWND:
                monitor_now = get_monitor_rect_for_window(STATE.ACTIVE_WAVE_HWND)
                screenshot("fatal_failure", monitor_now, STATE.ACTIVE_WAVE_HWND)
        except Exception:
            pass
        bundle = create_feedback_bundle("FAILED", exc)
        print(f"\n실패: {exc}")
        print(f"실행 자료: {STATE.RUN_DIR or LOG_DIR}")
        if STATE.LAST_RUN_ARCHIVE:
            print(f"실행 ZIP: {STATE.LAST_RUN_ARCHIVE}")
        if bundle:
            print(f"피드백 ZIP: {bundle}")
        return 1

    bundle = create_feedback_bundle("SUCCESS")
    if len(targets) == 1:
        print(f"\n완료: {targets[0]}")
    else:
        print(f"\nRO 배치 완료: {len(targets)}개 PDF")
        for index, target in enumerate(targets, start=1):
            print(f"  조건 {index}: {target}")
    print(f"로그: {log_path}")
    if STATE.LAST_RUN_ARCHIVE:
        print(f"실행 ZIP: {STATE.LAST_RUN_ARCHIVE}")
    if bundle:
        print(f"피드백 ZIP: {bundle}")
    return 0
