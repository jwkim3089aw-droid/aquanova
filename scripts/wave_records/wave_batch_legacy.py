#!/usr/bin/env python3
"""Refactored WAVE automation module: batch."""
from __future__ import annotations




# V132_RETRIES_IMPORT_START
try:
    from batch.retries import (
        _classify_constraint_adjusted_recovery,
    )
except ImportError:
    from .batch.retries import (
        _classify_constraint_adjusted_recovery,
    )
# V132_RETRIES_IMPORT_END

# V131A_PLAN_SCHEMA_IMPORT_START
try:
    from batch.plan_schema import (
        _choose_stable_global_temperature_mode,
        _settings_from_case,
        WaveAutomationError,
        _canonical_temperature_mode,
        _temperature_variant_suffix,
        _clone_case_for_global_temperature,
        expand_cases_for_wave_global_temperature,
    )
except ImportError:
    from .batch.plan_schema import (
        _choose_stable_global_temperature_mode,
        _settings_from_case,
        WaveAutomationError,
        _canonical_temperature_mode,
        _temperature_variant_suffix,
        _clone_case_for_global_temperature,
        expand_cases_for_wave_global_temperature,
    )
# V131A_PLAN_SCHEMA_IMPORT_END

# V130A_ARTIFACTS_IMPORT_START
try:
    from batch.artifacts import (
        _parse_pdf_summary_number,
        _pdf_percent_values,
        _pdf_pass_summary_lines,
        _pdf_detect_pass_count,
        _pdf_pass_summary_row_text_values,
        _pdf_flow_factor_per_stage_values,
        _pdf_pass_summary_row_values,
        _pdf_flow_per_pass_values,
        _extract_pdf_solubility_warnings,
        _merge_constraint_warnings,
        _extract_pdf_chemical_observations,
        _parse_pdf_number_line,
        _extract_pdf_stage_rows,
    )
except ImportError:
    from .batch.artifacts import (
        _parse_pdf_summary_number,
        _pdf_percent_values,
        _pdf_pass_summary_lines,
        _pdf_detect_pass_count,
        _pdf_pass_summary_row_text_values,
        _pdf_flow_factor_per_stage_values,
        _pdf_pass_summary_row_values,
        _pdf_flow_per_pass_values,
        _extract_pdf_solubility_warnings,
        _merge_constraint_warnings,
        _extract_pdf_chemical_observations,
        _parse_pdf_number_line,
        _extract_pdf_stage_rows,
    )
# V130A_ARTIFACTS_IMPORT_END

import copy

from wave_common import *
from wave_diagnostics import screenshot
from wave_interaction import wait
from wave_pdf import _extract_pdf_text, _number_pattern, dismiss_export_success_dialog, export_pdf
from wave_recorded import configure_recorded_ro_case
from wave_ro_engine import _legacy_compatible, _settings_from_ro_case, _validate_case_automation_support, configure_schema_ro_case
from wave_runtime import record_event
from wave_windows import focus_wave















def _write_two_case_summary(summary: dict[str, Any]) -> None:
    if STATE.RUN_DIR is None:
        return
    (STATE.RUN_DIR / "two_ro_batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_two_ro_cases(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    *,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
) -> list[Path]:
    """Run the two RO conditions shown in the supplied screen recording.

    Case 1 creates/configures the RO process. Case 2 deliberately reuses that
    same process and only replaces the feed profile and operating conditions,
    which is the workflow demonstrated in the video.
    """
    summary: dict[str, Any] = {
        "schema_version": 1,
        "batch": "two_ro_cases_2026-07-01_video",
        "status": "running",
        "cases": [],
    }
    targets: list[Path] = []
    _write_two_case_summary(summary)

    for index, case in enumerate(TWO_RO_CASES, start=1):
        settings = _settings_from_case(
            case,
            add_ro=index == 1,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=validate_pdf,
        )
        entry: dict[str, Any] = {
            "index": index,
            "case_id": case["case_id"],
            "status": "running",
            "expected": {
                key: case[key]
                for key in (
                    "water_profile",
                    "temperature_c",
                    "feed_flow_m3h",
                    "recovery_pct",
                    "pv_per_stage",
                    "elements_per_pv",
                    "membrane",
                    "pdf_name",
                )
            },
        }
        summary["cases"].append(entry)
        _write_two_case_summary(summary)
        logging.info(
            "=== RO 배치 조건 %s/2 시작: %s | profile=%s flow=%s T=%s R=%s PV=%s Els=%s membrane=%s ===",
            index,
            case["case_id"],
            settings.water_profile,
            settings.feed_flow_m3h,
            settings.temperature_c,
            settings.recovery_pct,
            settings.pv_per_stage,
            settings.elements_per_pv,
            settings.membrane,
        )
        record_event("batch_case_start", case=entry)

        try:
            configure_recorded_ro_case(wave_window.hwnd, monitor, points, settings)
            target = export_pdf(
                wave_window, monitor, points, case["pdf_name"], settings
            )
            dismiss_export_success_dialog(wave_window, monitor)
            entry.update(
                status="success",
                pdf=str(target),
                size_bytes=target.stat().st_size,
            )
            targets.append(target)
            record_event("batch_case_success", case=entry)
            logging.info("=== RO 배치 조건 %s/2 완료: %s ===", index, target)
            _write_two_case_summary(summary)
            if index < len(TWO_RO_CASES):
                focus_wave(wave_window.hwnd)
                screenshot(f"batch_case_{index}_complete", monitor, wave_window.hwnd)
                time.sleep(max(0.8, pause))
        except Exception as exc:
            entry.update(status="failed", error=repr(exc))
            summary["status"] = "failed"
            summary["failed_case"] = case["case_id"]
            _write_two_case_summary(summary)
            record_event("batch_case_failed", case=entry, error=repr(exc))
            raise

    summary["status"] = "success"
    summary["pdfs"] = [str(path) for path in targets]
    _write_two_case_summary(summary)
    logging.info("=== RO 2조건 배치 완료: %s ===", [str(path) for path in targets])
    return targets



















def _validate_pdf_recoveries(
    normalized: str,
    case: ROCaseConfig,
    tolerance_pct_points: float = 0.25,
) -> tuple[dict[str, bool], dict[str, Any]]:
    """Validate each pass recovery using printed and flow-derived values.

    Priority is the pass-specific ``Pass Recovery`` value.  As independent
    evidence, recovery is also derived from the printed ``Permeate Flow per
    Pass`` / ``Feed Flow per Pass`` values.  A single-pass report may additionally
    use system-level recovery labels.  The tolerance is in percentage points and
    is deliberately smaller than half a percent, so a materially wrong setting
    still fails closed while ordinary one-decimal WAVE rounding passes.
    """
    pass_recoveries = _pdf_pass_summary_row_values(
        normalized, "Pass Recovery", case.pass_count
    )
    if not pass_recoveries:
        pass_recoveries = _pdf_percent_values(normalized, r"\bPass\s+Recovery\b")
    system_recoveries = []
    for label_pattern in (
        r"\bRO\s+System\s+Recovery\b",
        r"\bNet\s+RO\s+System\s+Recovery\b",
        r"\bRO\s+Recovery\b",
    ):
        system_recoveries.extend(_pdf_percent_values(normalized, label_pattern))

    feed_flows = _pdf_flow_per_pass_values(
        normalized, "Feed Flow per Pass", case.pass_count
    )
    permeate_flows = _pdf_flow_per_pass_values(
        normalized, "Permeate Flow per Pass", case.pass_count
    )
    derived_recoveries: list[float] = []
    for feed, permeate in zip(feed_flows, permeate_flows):
        if feed > 0:
            derived_recoveries.append(permeate / feed * 100.0)

    checks: dict[str, bool] = {}
    details: dict[str, Any] = {
        "tolerance_pct_points": tolerance_pct_points,
        "printed_pass_recoveries": pass_recoveries,
        "printed_system_recoveries": system_recoveries,
        "feed_flow_per_pass": feed_flows,
        "permeate_flow_per_pass": permeate_flows,
        "derived_pass_recoveries": derived_recoveries,
        "passes": {},
    }

    for index, pass_config in enumerate(case.passes, start=1):
        expected = float(pass_config.recovery_pct)
        observed: list[dict[str, Any]] = []
        if index <= len(pass_recoveries):
            observed.append(
                {"source": "Pass Recovery", "value": pass_recoveries[index - 1]}
            )
        if index <= len(derived_recoveries):
            observed.append(
                {"source": "flow-derived", "value": derived_recoveries[index - 1]}
            )
        if case.pass_count == 1:
            observed.extend(
                {"source": "system recovery", "value": value}
                for value in system_recoveries
            )

        mode = _canonical_temperature_mode(pass_config.temperature_mode)
        strict_target_match = mode in {"Design", "Specify"}
        values = [float(item["value"]) for item in observed]
        if strict_target_match:
            passed = any(
                abs(value - expected) <= tolerance_pct_points + 1e-9
                for value in values
            )
        else:
            # Minimum/Maximum are off-design WAVE calculations.  The Flow
            # Calculator target is verified in the live UI, but the report may
            # legitimately print a different achieved recovery at the selected
            # extreme temperature.  Require physical values and agreement
            # between printed and flow-derived evidence instead of a false exact
            # target match.
            physical = bool(values) and all(0.0 < value < 100.0 for value in values)
            consistent = len(values) < 2 or max(values) - min(values) <= 0.35
            passed = physical and consistent
        key = f"pass{index}_recovery"
        checks[key] = passed
        details["passes"][key] = {
            "expected_input_target": expected,
            "temperature_mode": mode,
            "temperature_c": float(pass_config.temperature_c),
            "strict_target_match": strict_target_match,
            "observed": observed,
            "passed": passed,
        }
        logging.info(
            "PDF Recovery 검증: %s expected=%.3f observed=%s tolerance=%.3f passed=%s",
            key,
            expected,
            [round(float(item["value"]), 4) for item in observed],
            tolerance_pct_points,
            passed,
        )

    return checks, details


_DESIGN_WARNING_PATTERN = re.compile(
    r"^(?P<message>.+(?:>|<).+(?:Maximum|Minimum)\s+Limit|"
    r".+(?:Pressure Drop|Recovery).+(?:Maximum|Minimum)\s+Limit)$",
    re.I,
)


def _extract_pdf_design_warnings(normalized: str) -> dict[str, Any]:
    """Return structured, best-effort WAVE design warnings from the PDF.

    WAVE prints the warning table cell-by-cell, so this parser deliberately
    preserves a short raw context window instead of assuming a fixed table
    width.  The result is diagnostic metadata; it is never used to prove that
    an input was entered correctly.
    """
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    try:
        start = next(
            index for index, line in enumerate(lines)
            if line.casefold() == "ro design warnings"
        )
    except StopIteration:
        return {"count": 0, "messages": [], "counts_by_message": {}, "items": []}

    items: list[dict[str, Any]] = []
    for index in range(start + 1, len(lines)):
        line = " ".join(lines[index].split())
        match = _DESIGN_WARNING_PATTERN.fullmatch(line)
        if not match:
            continue
        context = lines[index + 1 : index + 11]
        numeric_context: list[float] = []
        for value in context:
            parsed = _parse_pdf_number_line(value)
            if parsed is not None:
                numeric_context.append(parsed)
        items.append(
            {
                "message": match.group("message"),
                "line_index": index,
                "context": context,
                "numeric_context": numeric_context,
            }
        )

    counts: dict[str, int] = {}
    for item in items:
        message = str(item["message"])
        counts[message] = counts.get(message, 0) + 1
    return {
        "count": len(items),
        "messages": sorted(counts),
        "counts_by_message": counts,
        "items": items,
    }














def validate_exported_pdf_case(path: Path, case: ROCaseConfig) -> dict[str, Any]:
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\r", "")
    compact = re.sub(r"[ \t]+", " ", normalized)
    profile_ok = bool(re.search(re.escape(case.water_profile), normalized, re.I))
    expected_temperatures = [float(p.temperature_c) for p in case.passes]
    printed_temperatures = _pdf_pass_summary_row_values(
        normalized, "Temperature", case.pass_count
    )
    if printed_temperatures:
        temp_ok = len(printed_temperatures) == case.pass_count and all(
            abs(actual - expected) <= 0.06
            for actual, expected in zip(printed_temperatures, expected_temperatures)
        )
    else:
        temp_pattern = _number_pattern(_fmt_value(case.passes[0].temperature_c))
        temp_ok = bool(
            re.search(
                rf"Temperature\s*\n?\s*[(]?[°o]?C[)]?\s*\n?\s*{temp_pattern}",
                normalized,
                re.I,
            )
        )
    flow_pattern = _number_pattern(_fmt_value(case.feed_flow_m3h))
    flow_ok = bool(
        re.search(
            rf"Raw Feed to RO System\s*\n\s*{flow_pattern}(?:\s|\n)", normalized, re.I
        )
        or re.search(rf"Net Feed\s*=\s*{flow_pattern}(?:\s|\n)", compact, re.I)
    )
    membranes = sorted({stage.membrane for p in case.passes for stage in p.stages})
    membrane_checks = {
        m: bool(re.search(re.escape(m), normalized, re.I)) for m in membranes
    }
    no_obsolete = not bool(
        re.search(r"(?:obsolete|to be discontinued|china only)", normalized, re.I)
    )
    detected_pass_count = _pdf_detect_pass_count(normalized)
    pass_count_exact = detected_pass_count == case.pass_count
    recoveries, recovery_details = _validate_pdf_recoveries(normalized, case)
    design_warnings = _extract_pdf_design_warnings(normalized)
    solubility_warnings = _extract_pdf_solubility_warnings(normalized)
    constraint_warnings = _merge_constraint_warnings(
        design_warnings, solubility_warnings
    )
    chemical_observations = _extract_pdf_chemical_observations(normalized)
    printed_flow_factors = _pdf_flow_factor_per_stage_values(
        normalized, case.pass_count
    )
    flow_factor_checks: dict[str, bool] = {}
    flow_factor_details: dict[str, Any] = {}
    for pass_index, pass_config in enumerate(case.passes, start=1):
        expected = [
            float(pass_config.flow_factor if stage.flow_factor is None else stage.flow_factor)
            for stage in pass_config.stages
        ]
        actual = (
            printed_flow_factors[pass_index - 1]
            if pass_index <= len(printed_flow_factors)
            else []
        )
        passed = len(actual) == len(expected) and all(
            abs(left - right) <= 0.011 for left, right in zip(actual, expected)
        )
        key = f"pass{pass_index}_flow_factors"
        flow_factor_checks[key] = passed
        flow_factor_details[key] = {
            "expected": expected,
            "printed": actual,
            "passed": passed,
        }
    parsed_stage_rows = {
        p_idx: _extract_pdf_stage_rows(normalized, p_idx, p.stage_count)
        for p_idx, p in enumerate(case.passes, start=1)
    }
    stage_counts: dict[str, bool] = {}
    for p_idx, p in enumerate(case.passes, start=1):
        rows = parsed_stage_rows.get(p_idx, {})
        for s_idx, stage in enumerate(p.stages, start=1):
            actual = rows.get(s_idx)
            prefix = f"pass{p_idx}_stage{s_idx}"
            stage_counts[f"{prefix}_row_present"] = actual is not None
            stage_counts[f"{prefix}_membrane"] = bool(
                actual
                and str(actual.get("membrane", "")).strip().casefold()
                == stage.membrane.strip().casefold()
            )
            stage_counts[f"{prefix}_pv"] = bool(
                actual and int(actual.get("pv", -1)) == int(stage.pv)
            )
            stage_counts[f"{prefix}_elements_per_pv"] = bool(
                actual
                and int(actual.get("elements_per_pv", -1)) == int(stage.elements_per_pv)
            )
    checks: dict[str, Any] = {
        "water_profile": profile_ok,
        "temperature": temp_ok,
        "raw_feed_flow": flow_ok,
        "pass_count_exact": pass_count_exact,
        "no_obsolete_or_restricted_membrane": no_obsolete,
        **{f"membrane_{k}": v for k, v in membrane_checks.items()},
        **recoveries,
        **flow_factor_checks,
        **stage_counts,
    }
    errors = [key for key, value in checks.items() if not value]
    constraint_adjustment = _classify_constraint_adjusted_recovery(
        errors, recovery_details, constraint_warnings
    )
    classification = (
        "constraint_adjusted"
        if constraint_adjustment.get("eligible")
        else ("validated" if not errors else "validation_failed")
    )
    result = {
        "pdf": str(path),
        "provider": provider,
        "case": case.to_flat_dict(),
        "checks": checks,
        "errors": errors,
        "classification": classification,
        "design_warnings": design_warnings,
        "solubility_warnings": solubility_warnings,
        "constraint_warnings": constraint_warnings,
        "chemical_observations": chemical_observations,
        "constraint_adjustment": constraint_adjustment,
        "pass_topology_validation": {
            "expected_pass_count": case.pass_count,
            "detected_pass_count": detected_pass_count,
            "passed": pass_count_exact,
        },
        "temperature_validation": {
            "expected": expected_temperatures,
            "printed": printed_temperatures,
            "passed": temp_ok,
        },
        "recovery_validation": recovery_details,
        "flow_factor_validation": flow_factor_details,
        "stage_rows": parsed_stage_rows,
    }
    if STATE.RUN_DIR is not None:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", case.case_id)
        (STATE.RUN_DIR / f"pdf_validation_{safe}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (STATE.RUN_DIR / f"exported_pdf_text_{safe}.txt").write_text(text, encoding="utf-8")
    record_event("pdf_validation_schema", result=result)
    if classification == "constraint_adjusted":
        deviations = {
            key: value.get("deviation_pct_points")
            for key, value in (constraint_adjustment.get("passes") or {}).items()
        }
        logging.warning(
            "WAVE 제약 조정 결과 허용: case=%s deviations=%s warnings=%s",
            case.case_id,
            deviations,
            constraint_warnings.get("counts_by_message"),
        )
        record_event(
            "pdf_constraint_adjusted_v44",
            case_id=case.case_id,
            pdf=str(path),
            constraint_adjustment=constraint_adjustment,
            design_warnings=design_warnings,
            solubility_warnings=solubility_warnings,
            constraint_warnings=constraint_warnings,
        )
        return result
    if errors:
        raise WaveAutomationError(f"{case.case_id} PDF 검증 실패: {', '.join(errors)}")
    logging.info("Schema PDF 검증 성공: %s", case.case_id)
    return result


def _write_ro_batch_summary(summary: dict[str, Any]) -> None:
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "ro_excel_batch_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _write_ro_extended_preflight(
    cases: list[ROCaseConfig],
    *,
    input_case_count: int | None = None,
    temperature_expansion: list[dict[str, Any]] | None = None,
) -> None:
    payload = {
        "schema_version": 4,
        "automation_version": "V52",
        "input_case_count": len(cases) if input_case_count is None else input_case_count,
        "case_count": len(cases),
        "temperature_expansion": temperature_expansion or [],
        "groups": sorted({case.batch_group for case in cases if case.batch_group}),
        "cases": [case.to_flat_dict() for case in cases],
        "warnings": [
            {
                "case_id": case.case_id,
                "tier": case.automation_tier,
                "message": (
                    "실제 WAVE 무인 배치에서 아직 검증되지 않은 경로입니다."
                    if case.automation_tier in {"new", "experimental"}
                    else ""
                ),
            }
            for case in cases
            if case.automation_tier != "stable"
        ],
    }
    record_event("ro_extended_preflight", payload=payload)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "ro_extended_preflight.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def run_ro_excel_batch(
    wave_window: WindowInfo,
    monitor: Rect,
    points: dict[str, tuple[int, int]],
    cases: list[ROCaseConfig],
    *,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
    allow_experimental: bool,
    allow_experimental_batch: bool,
    continue_on_convergence: bool,
) -> list[Path]:
    if not cases:
        raise WaveAutomationError("Excel/JSON에 Run_Enabled=Y인 RO 사례가 없습니다.")
    input_case_count = len(cases)
    cases, temperature_expansion = expand_cases_for_wave_global_temperature(cases)
    for item in temperature_expansion:
        if len(item["expanded_case_ids"]) > 1:
            logging.warning(
                "WAVE 전역 온도로 사례 자동 분할: source=%s -> %s",
                item["source_case_id"],
                item["expanded_case_ids"],
            )
        for decision in item.get("mode_decisions", []):
            if "normalization" in str(decision.get("reason", "")):
                logging.warning(
                    "WAVE 안정 온도 모드 변환: source=%s requested=%s selected=%s temperature=%s reason=%s",
                    item["source_case_id"],
                    decision.get("requested_modes"),
                    decision.get("selected_mode"),
                    decision.get("temperature_c"),
                    decision.get("reason"),
                )
        record_event("wave_global_temperature_expansion_v44", item=item)
    for case in cases:
        _validate_case_automation_support(case, allow_experimental=allow_experimental)
    groups = {case.batch_group.strip() for case in cases if case.batch_group.strip()}
    if len(groups) > 1:
        raise WaveAutomationError(
            "서로 다른 Batch_Group을 한 번에 실행할 수 없습니다. "
            "--batch-group 또는 --case-id로 한 그룹만 선택하세요: "
            f"{sorted(groups)}"
        )
    chemistry_cases = [
        case
        for case in cases
        if case.chemical.enabled
        or case.special_features.enabled
    ]
    if len(cases) > 1 and chemistry_cases and not allow_experimental_batch:
        raise WaveAutomationError(
            "Chemical/Special Feature 사례는 이전 사례의 설정이 남을 수 있으므로 V52 기본값에서는 "
            "--case-id로 한 개씩 실행하거나, 사례별 상태 정규화를 허용하려면 "
            "--allow-experimental-batch를 추가하세요."
        )
    if allow_experimental_batch:
        # V52: keep one WAVE process alive while making every case idempotent.
        # Even a no-chemical case opens Chemical Adjustment, disables stale
        # panels, restores dialog defaults, verifies the baseline, and closes.
        for case in cases:
            setattr(case, "_force_chemical_reconcile", True)
        logging.info(
            "V52 연속 배치 상태 정규화 활성화: cases=%s; "
            "각 사례 시작 시 Chemical Adjustment 잔존 상태를 초기화합니다.",
            len(cases),
        )
        record_event(
            "chemical_case_state_reconciliation_v45",
            enabled=True,
            case_ids=[case.case_id for case in cases],
        )
    _write_ro_extended_preflight(
        cases,
        input_case_count=input_case_count,
        temperature_expansion=temperature_expansion,
    )
    summary: dict[str, Any] = {
        "schema_version": 4,
        "automation_version": "V52",
        "source": "Excel/JSON schema-driven RO batch",
        "status": "running",
        "input_case_count": input_case_count,
        "case_count": len(cases),
        "temperature_expansion": temperature_expansion,
        "batch_group": next(iter(groups), ""),
        "cases": [],
    }
    _write_ro_batch_summary(summary)
    outputs: list[Path] = []
    for index, case in enumerate(cases, start=1):
        add_ro = index == 1
        settings = _settings_from_ro_case(
            case,
            add_ro=add_ro,
            pause=pause,
            long_wait=long_wait,
            validate_pdf=False,
        )
        entry = {
            "index": index,
            "case_id": case.case_id,
            "source_case_id": getattr(case, "_source_case_id", case.case_id),
            "temperature_variant": {
                "mode": getattr(case, "_temperature_variant_mode", case.passes[0].temperature_mode),
                "temperature_c": getattr(case, "_temperature_variant_c", case.passes[0].temperature_c),
                "expanded": bool(getattr(case, "_temperature_expanded", False)),
                "reason": getattr(case, "_temperature_mode_reason", ""),
            },
            "status": "running",
            "tier": case.automation_tier,
            "input": case.to_flat_dict(),
        }
        summary["cases"].append(entry)
        _write_ro_batch_summary(summary)
        logging.info(
            "=== Excel RO %s/%s: %s tier=%s ===",
            index,
            len(cases),
            case.case_id,
            case.automation_tier,
        )
        try:
            if _legacy_compatible(case):
                configure_recorded_ro_case(wave_window.hwnd, monitor, points, settings)
            else:
                configure_schema_ro_case(
                    wave_window.hwnd, monitor, points, case, settings
                )
            target = export_pdf(wave_window, monitor, points, case.pdf_name, settings)
            dismiss_export_success_dialog(wave_window, monitor)
            validation_result: dict[str, Any] | None = None
            if validate_pdf:
                validation_result = validate_exported_pdf_case(target, case)
            classification = (validation_result or {}).get("classification", "validated")
            entry_status = (
                "constraint_adjusted"
                if classification == "constraint_adjusted"
                else "success"
            )
            entry.update(
                status=entry_status,
                pdf=str(target),
                size_bytes=target.stat().st_size,
                validation_classification=classification,
            )
            if validation_result and classification == "constraint_adjusted":
                entry["constraint_adjustment"] = validation_result.get("constraint_adjustment")
                entry["design_warnings"] = validation_result.get("design_warnings")
                entry["solubility_warnings"] = validation_result.get("solubility_warnings")
                entry["constraint_warnings"] = validation_result.get("constraint_warnings")
            outputs.append(target)
        except WaveConvergenceError as exc:
            entry.update(status="convergence_failed", error=str(exc))
            screenshot(f"convergence_{case.case_id}", monitor, wave_window.hwnd)
            if not continue_on_convergence:
                summary["status"] = "failed"
                summary["failed_case"] = case.case_id
                _write_ro_batch_summary(summary)
                raise
            logging.error(
                "수렴 실패 사례를 기록하고 다음 사례로 진행: %s", case.case_id
            )
        except Exception as exc:
            entry.update(status="failed", error=repr(exc))
            summary["status"] = "failed"
            summary["failed_case"] = case.case_id
            _write_ro_batch_summary(summary)
            raise
        _write_ro_batch_summary(summary)
        if index < len(cases):
            focus_wave(wave_window.hwnd)
            wait(max(0.8, pause))
    statuses = [str(item.get("status", "")) for item in summary["cases"]]
    if statuses and all(status == "success" for status in statuses):
        summary["status"] = "success"
    elif statuses and all(status in {"success", "constraint_adjusted"} for status in statuses):
        summary["status"] = "completed_with_adjustments"
    else:
        summary["status"] = "completed_with_failures"
    summary["constraint_adjusted_cases"] = [
        item["case_id"] for item in summary["cases"]
        if item.get("status") == "constraint_adjusted"
    ]
    summary["pdfs"] = [str(path) for path in outputs]
    _write_ro_batch_summary(summary)
    return outputs


def write_ro_catalog_artifacts(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_catalog_json(output_dir / "wave_ro_ui_catalog.json")
    schema_path = output_dir / "wave_ro_excel_schema_example.json"
    example = {
        "schema_version": 4,
        "automation_version": "V52",
        "notes": "Extended RO example. Run one Batch_Group and one Pass_Count per fresh WAVE project.",
        "case": {
            "Run_Enabled": "Y",
            "Batch_Order": 1,
            "Batch_Group": "EXT_1PASS",
            "Case_ID": "RO_EXT_EXAMPLE",
            "Recommended_PDF_Name": "RO_EXT_EXAMPLE.pdf",
            "WAVE_Library_Selection": "Well Water - Med Hardness",
            "Feed_Flow_m3h": 100,
            "Temperature_Min_C": 10,
            "Temperature_Design_C": 25,
            "Temperature_Max_C": 35,
            "Pass_Count": 1,
            "Pass1_Recovery_pct": 75,
            "Pass1_Temperature_Mode": "Design",
            "Pass1_Temperature_C": 25,
            "Pass1_Flow_Factor": 0.90,
            "Pass1_Permeate_Back_Pressure_bar": 0.5,
            "Pass1_Stage_Count": 3,
            "P1S1_PV": 6,
            "P1S1_Elements_per_PV": 6,
            "P1S1_Membrane": "BW30-400",
            "P1S2_PV": 3,
            "P1S2_Elements_per_PV": 6,
            "P1S2_Membrane": "BW30-400",
            "P1S2_Stage_Back_Pressure_bar": 0.3,
            "P1S3_PV": 1,
            "P1S3_Elements_per_PV": 6,
            "P1S3_Membrane": "BW30-400",
        },
    }
    schema_path.write_text(
        json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return json_path, schema_path
