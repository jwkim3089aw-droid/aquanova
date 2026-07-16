from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.simulation import SimulationRequest
from app.services.simulation.calibration.wave_runtime_correction import (
    load_correction_layer,
)
from app.services.simulation.engine import SimulationEngine
from app.services.simulation.wave_corrected_engine import (
    run_simulation_with_optional_wave_correction,
)

LAYER_PATH = (
    ROOT
    / "app/services/simulation/calibration/layers"
    / "wave_correction_layer_v131.json"
)

OUTPUT_PATH = (
    Path.home()
    / "AppData/Local/Temp"
    / "aquanova_v132_nf_engine_e2e.json"
)


def dump_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="json",
            exclude_none=False,
        )

    if hasattr(value, "dict"):
        return value.dict(
            exclude_none=False,
        )

    return copy.deepcopy(value)


def value_of(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def first_metric(result: Any) -> Any:
    metrics = value_of(
        result,
        "stage_metrics",
        None,
    ) or []

    if not metrics:
        raise AssertionError(
            "Engine result has no stage_metrics"
        )

    return metrics[0]


def metric_values(
    result: Any,
) -> dict[str, float]:
    kpi = value_of(result, "kpi")
    metric = first_metric(result)

    pressure = value_of(
        metric,
        "p_in_bar",
        None,
    )

    product_tds = value_of(
        kpi,
        "prod_tds",
        None,
    )

    sec = value_of(
        kpi,
        "sec_kwhm3",
        None,
    )

    values = {
        "feed_pressure": pressure,
        "product_tds": product_tds,
        "specific_energy": sec,
    }

    for name, value in values.items():
        if value is None:
            raise AssertionError(
                f"Missing real engine metric: {name}"
            )

        value = float(value)

        if not math.isfinite(value):
            raise AssertionError(
                f"Non-finite engine metric: "
                f"{name}={value}"
            )

        values[name] = value

    return values


def close(
    left: Any,
    right: Any,
    tolerance: float = 1e-9,
) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def correction_row(
    report: dict[str, Any],
    metric: str,
) -> dict[str, Any]:
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return dict(row)

    raise AssertionError(
        f"Missing correction row: {metric}\n"
        f"{json.dumps(report, indent=2)}"
    )
def runtime_row_applied(
    row: dict[str, Any],
) -> bool:
    return str(
        row.get("status") or ""
    ).strip().lower() in {
        "applied",
        "corrected",
    }


def runtime_applied_count(
    report: dict[str, Any],
) -> int:
    explicit = report.get(
        "applied_count"
    )

    if explicit is not None:
        return int(explicit)

    return sum(
        1
        for row in report.get(
            "corrections"
        ) or []
        if runtime_row_applied(
            dict(row)
        )
    )


def runtime_shadow_count(
    report: dict[str, Any],
) -> int:
    explicit = report.get(
        "shadow_count"
    )

    if explicit is not None:
        return int(explicit)

    return sum(
        1
        for row in report.get(
            "corrections"
        ) or []
        if str(
            row.get("status") or ""
        ).strip().lower() == "shadow_only"
    )



def normalized_output(
    result: Any,
) -> dict[str, Any]:
    payload = dump_model(result)

    # E2E 계산 결과 비교에서 보고서 필드만 제외한다.
    payload.pop("precision_report", None)

    return payload


def build_payload(
    *,
    membrane_model: str | None,
    precision_enabled: bool,
    case_id: str,
) -> dict[str, Any]:
    stage: dict[str, Any] = {
        "stage_id": f"{case_id}_stage_1",
        "stage_idx": 1,
        "pass_idx": 1,
        "module_type": "NF",
        "feed_flow_m3h": 5.0,
        "recovery_target_pct": 65.0,
        "flow_factor": 0.85,
        "pump_efficiency": 0.80,
        "element_inch": 8,
        "vessel_count": 1,
        "elements_per_vessel": 5,
        "elements": 5,
        "membrane_area_m2_per_element": 37.16,
        "membrane_area_m2": 185.8,
        "design_flux_lmh": 17.5,
        "source_file": "v132_nf_engine_e2e",
        "chemistry": {
            "calibration_e2e_mode": "v132",
        },
    }

    if membrane_model is not None:
        stage["membrane_model"] = membrane_model
    else:
        # 막 이름 누락 안전검증에서도 실제 NF 계산은 가능하게 한다.
        stage.update(
            {
                "membrane_A_lmh_bar": 4.5,
                "membrane_B_lmh": 0.45,
                "membrane_salt_rejection_pct": 90.0,
            }
        )

    return {
        "simulation_id": case_id,
        "project_id": "wave_calibration_v132",
        "scenario_name": case_id,
        "precision_mode_enabled": precision_enabled,
        "wave_correction_enabled": False,
        "calibration_mode": None,
        "feed": {
            "water_type": "RO/NF Well Water",
            "flow_m3h": 5.0,
            "temperature_C": 25.0,
            "ph": 7.5,
            "tds_mgL": 1000.0,
            "pressure_bar": 0.0,
        },
        "stages": [stage],
        "options": {
            "v132_nf_engine_e2e": True,
        },
    }


def assert_engine_normalization_consistent(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    label: str,
) -> None:
    if candidate != reference:
        raise AssertionError(
            f"Engine normalization differs: {label}\n"
            f"reference={json.dumps(reference, indent=2)}\n"
            f"candidate={json.dumps(candidate, indent=2)}"
        )



def run_raw(
    payload: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    request = SimulationRequest(
        **copy.deepcopy(payload)
    )

    result = SimulationEngine().run(
        request
    )

    normalized_request = dump_model(
        request
    )

    return result, normalized_request



def run_optional(
    payload: dict[str, Any],
    *,
    enabled: bool,
    layer: dict[str, Any],
) -> tuple[
    Any,
    dict[str, Any],
    dict[str, Any],
]:
    request = SimulationRequest(
        **copy.deepcopy(payload)
    )

    result, report = (
        run_simulation_with_optional_wave_correction(
            request,
            engine=SimulationEngine(),
            options={
                "enable_wave_correction": enabled,
            },
            correction_layer=layer,
            config={
                "enabled": False,
                "runtime_safety_guards_enabled": True,
            },
        )
    )

    normalized_request = dump_model(
        request
    )

    return (
        result,
        dict(report),
        normalized_request,
    )



def assert_disabled_identity(
    raw: Any,
    off: Any,
    report: dict[str, Any],
    label: str,
) -> None:
    if normalized_output(raw) != normalized_output(off):
        raise AssertionError(
            f"{label}: correction OFF changed "
            "the real engine output"
        )

    if report.get("status") != "disabled":
        raise AssertionError(
            f"{label}: unexpected OFF report\n"
            f"{json.dumps(report, indent=2)}"
        )


def assert_model_scope(
    report: dict[str, Any],
    prefix: str,
) -> None:
    for row in report.get("corrections") or []:
        model_id = str(
            row.get("model_id") or ""
        )

        if model_id and not model_id.startswith(
            prefix
        ):
            raise AssertionError(
                "Cross-membrane model application:\n"
                f"expected_prefix={prefix}\n"
                f"row={json.dumps(row, indent=2)}"
            )


def run_nf270(
    layer: dict[str, Any],
) -> dict[str, Any]:
    raw_payload = build_payload(
        membrane_model="FilmTec NF270-400/34",
        precision_enabled=False,
        case_id="v132_nf270_raw",
    )

    off_payload = build_payload(
        membrane_model="FilmTec NF270-400/34",
        precision_enabled=False,
        case_id="v132_nf270_raw",
    )

    on_payload = build_payload(
        membrane_model="FilmTec NF270-400/34",
        precision_enabled=False,
        case_id="v132_nf270_raw",
    )

    raw, raw_request = run_raw(
        raw_payload
    )

    (
        off,
        off_report,
        off_request,
    ) = run_optional(
        off_payload,
        enabled=False,
        layer=layer,
    )

    (
        on,
        on_report,
        on_request,
    ) = run_optional(
        on_payload,
        enabled=True,
        layer=layer,
    )

    assert_engine_normalization_consistent(
        raw_request,
        off_request,
        "NF270 correction OFF",
    )

    assert_engine_normalization_consistent(
        raw_request,
        on_request,
        "NF270 correction ON",
    )

    assert_disabled_identity(
        raw,
        off,
        off_report,
        "NF270",
    )

    raw_values = metric_values(raw)
    on_values = metric_values(on)

    if on_report.get("status") != "corrected":
        raise AssertionError(
            json.dumps(
                on_report,
                indent=2,
            )
        )

    if runtime_applied_count(on_report) != 3:
        raise AssertionError(
            "NF270 must apply three runtime models\n"
            + json.dumps(
                on_report,
                indent=2,
            )
        )

    if runtime_shadow_count(on_report) != 0:
        raise AssertionError(
            on_report
        )

    for metric_name in (
        "feed_pressure",
        "product_tds",
        "specific_energy",
    ):
        row = correction_row(
            on_report,
            metric_name,
        )

        if not runtime_row_applied(row):
            raise AssertionError(row)

        if not str(
            row.get("model_id") or ""
        ).startswith("v130_nf270_"):
            raise AssertionError(row)

        if close(
            raw_values[metric_name],
            on_values[metric_name],
        ):
            raise AssertionError(
                f"NF270 {metric_name} did not change"
            )

    assert_model_scope(
        on_report,
        "v130_nf270_",
    )

    print(
        "NF270 real-engine normalization PASS"
    )
    print(
        "NF270 real-engine OFF identity PASS"
    )
    print(
        "NF270 real-engine runtime 3/3 PASS"
    )

    return {
        "membrane_model": (
            "FilmTec NF270-400/34"
        ),
        "raw": raw_values,
        "corrected": on_values,
        "report": on_report,
    }



def run_nf90(
    layer: dict[str, Any],
) -> dict[str, Any]:
    raw_payload = build_payload(
        membrane_model="FilmTec NF90-400/34",
        precision_enabled=False,
        case_id="v132_nf90_raw",
    )

    off_payload = build_payload(
        membrane_model="FilmTec NF90-400/34",
        precision_enabled=False,
        case_id="v132_nf90_raw",
    )

    on_payload = build_payload(
        membrane_model="FilmTec NF90-400/34",
        precision_enabled=False,
        case_id="v132_nf90_raw",
    )

    raw, raw_request = run_raw(
        raw_payload
    )

    (
        off,
        off_report,
        off_request,
    ) = run_optional(
        off_payload,
        enabled=False,
        layer=layer,
    )

    (
        on,
        on_report,
        on_request,
    ) = run_optional(
        on_payload,
        enabled=True,
        layer=layer,
    )

    assert_engine_normalization_consistent(
        raw_request,
        off_request,
        "NF90 correction OFF",
    )

    assert_engine_normalization_consistent(
        raw_request,
        on_request,
        "NF90 correction ON",
    )

    assert_disabled_identity(
        raw,
        off,
        off_report,
        "NF90",
    )

    raw_values = metric_values(raw)
    on_values = metric_values(on)

    if on_report.get("status") != "corrected":
        raise AssertionError(
            json.dumps(
                on_report,
                indent=2,
            )
        )

    if runtime_applied_count(on_report) != 2:
        raise AssertionError(
            "NF90 must apply two runtime models\n"
            + json.dumps(
                on_report,
                indent=2,
            )
        )

    if runtime_shadow_count(on_report) != 1:
        raise AssertionError(
            "NF90 must retain one shadow model\n"
            + json.dumps(
                on_report,
                indent=2,
            )
        )

    for metric_name in (
        "feed_pressure",
        "specific_energy",
    ):
        row = correction_row(
            on_report,
            metric_name,
        )

        if not runtime_row_applied(row):
            raise AssertionError(row)

        if not str(
            row.get("model_id") or ""
        ).startswith("v130_nf90_"):
            raise AssertionError(row)

        if close(
            raw_values[metric_name],
            on_values[metric_name],
        ):
            raise AssertionError(
                f"NF90 {metric_name} did not change"
            )

    product = correction_row(
        on_report,
        "product_tds",
    )

    if product.get("status") != "shadow_only":
        raise AssertionError(product)

    if product.get(
        "shadow_corrected_value"
    ) is None:
        raise AssertionError(product)

    if not close(
        raw_values["product_tds"],
        on_values["product_tds"],
    ):
        raise AssertionError(
            "NF90 shadow model changed "
            "public product TDS"
        )

    assert_model_scope(
        on_report,
        "v130_nf90_",
    )

    print(
        "NF90 real-engine normalization PASS"
    )
    print(
        "NF90 real-engine OFF identity PASS"
    )
    print(
        "NF90 real-engine runtime 2/2 PASS"
    )
    print(
        "NF90 real-engine product-TDS shadow PASS"
    )

    return {
        "membrane_model": (
            "FilmTec NF90-400/34"
        ),
        "raw": raw_values,
        "corrected": on_values,
        "shadow_product_tds": product.get(
            "shadow_corrected_value"
        ),
        "report": on_report,
    }



def run_missing_membrane(
    layer: dict[str, Any],
) -> dict[str, Any]:
    payload = build_payload(
        membrane_model=None,
        precision_enabled=False,
        case_id="v132_nf_missing_membrane",
    )

    raw, raw_request = run_raw(
        copy.deepcopy(payload)
    )

    (
        corrected,
        report,
        corrected_request,
    ) = run_optional(
        payload,
        enabled=True,
        layer=layer,
    )

    assert_engine_normalization_consistent(
        raw_request,
        corrected_request,
        "missing membrane correction ON",
    )

    if report.get("status") != (
        "missing_membrane_context"
    ):
        raise AssertionError(
            json.dumps(
                report,
                indent=2,
            )
        )

    if normalized_output(
        raw
    ) != normalized_output(corrected):
        raise AssertionError(
            "Missing membrane context "
            "changed output"
        )

    print(
        "Missing membrane normalization PASS"
    )
    print(
        "Missing membrane real-engine "
        "safety guard PASS"
    )

    return {
        "status": report.get("status"),
        "raw": metric_values(raw),
        "corrected": metric_values(
            corrected
        ),
    }



def main() -> int:
    if not LAYER_PATH.exists():
        raise FileNotFoundError(
            LAYER_PATH
        )

    layer = load_correction_layer(
        LAYER_PATH
    )

    models = list(
        layer.get("models") or []
    )

    if len(models) != 11:
        raise AssertionError(
            f"Expected V131 layer with 11 models, "
            f"actual={len(models)}"
        )

    nf270 = run_nf270(layer)
    nf90 = run_nf90(layer)
    missing = run_missing_membrane(
        layer
    )

    summary = {
        "schema_version": (
            "aquanova.nf_simulation_engine_e2e.v132"
        ),
        "status": "PASS",
        "layer_path": str(LAYER_PATH),
        "model_count": len(models),
        "nf270": nf270,
        "nf90": nf90,
        "missing_membrane": missing,
        "engine_normalization_consistency": "PASS",
        "correction_off_identity": "PASS",
        "cross_membrane_scope": "PASS",
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 100)
    print("V132 NF REAL SIMULATION ENGINE E2E")
    print("=" * 100)
    print(f"layer={LAYER_PATH}")
    print(f"output={OUTPUT_PATH}")
    print("model_count=11")
    print("nf270_runtime=3")
    print("nf90_runtime=2")
    print("nf90_shadow=1")
    print("correction_off_identity=PASS")
    print("engine_normalization_consistency=PASS")
    print("cross_membrane_scope=PASS")
    print("missing_membrane_guard=PASS")
    print(
        "\nV132 NF real SimulationEngine E2E PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
