from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

E2E_HELPER_PATH = (
    ROOT
    / "scripts/wave_records"
    / "wave_v132_nf_simulation_engine_e2e.py"
)

CANONICAL_LAYER_PATH = (
    ROOT
    / "app/services/simulation/calibration/layers"
    / "wave_correction_layer_v131.json"
)

DATA_DIR = ROOT / ".data"

RUNTIME_LAYER_PATH = (
    DATA_DIR
    / "wave_correction_layer.json"
)

RUNTIME_CONFIG_PATH = (
    DATA_DIR
    / "wave_correction_runtime_config.json"
)

OUTPUT_PATH = (
    Path.home()
    / "AppData/Local/Temp"
    / "aquanova_v132_nf_api_e2e.json"
)


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "aquanova_v132_api_e2e_helper",
        E2E_HELPER_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Cannot import E2E helper: "
            f"{E2E_HELPER_PATH}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(module)

    return module


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


def strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): strip_none(child)
            for key, child in value.items()
            if child is not None
        }

    if isinstance(value, list):
        return [
            strip_none(child)
            for child in value
        ]

    return value


def comparable_output(
    value: Any,
) -> dict[str, Any]:
    payload = strip_none(
        dump_model(value)
    )

    if not isinstance(payload, dict):
        raise AssertionError(
            "Scenario output is not a mapping"
        )

    payload.pop("scenario_id", None)
    payload.pop("precision_report", None)

    return payload


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


def response_values(
    payload: dict[str, Any],
) -> dict[str, float]:
    metrics = payload.get(
        "stage_metrics"
    ) or []

    if not metrics:
        raise AssertionError(
            "API response has no stage_metrics"
        )

    kpi = payload.get("kpi") or {}

    values = {
        "feed_pressure": (
            metrics[0].get("p_in_bar")
        ),
        "product_tds": (
            kpi.get("prod_tds")
        ),
        "specific_energy": (
            kpi.get("sec_kwhm3")
        ),
    }

    for name, value in values.items():
        if value is None:
            raise AssertionError(
                f"API response missing metric: {name}"
            )

        numeric = float(value)

        if not math.isfinite(numeric):
            raise AssertionError(
                f"API response metric is not finite: "
                f"{name}={numeric}"
            )

        values[name] = numeric

    return values


def find_fastapi_app():
    candidates = [
        ("app.main", "app"),
        ("app.main", "application"),
        ("main", "app"),
        ("main", "application"),
    ]

    errors = []

    for module_name, attribute in candidates:
        try:
            module = importlib.import_module(
                module_name
            )

            candidate = getattr(
                module,
                attribute,
                None,
            )

            if candidate is not None and hasattr(
                candidate,
                "routes",
            ):
                return candidate

        except Exception as exc:
            errors.append(
                f"{module_name}.{attribute}: "
                f"{exc.__class__.__name__}: {exc}"
            )

    raise RuntimeError(
        "FastAPI application not found:\n"
        + "\n".join(errors)
    )


def find_run_route(app: Any) -> tuple[str, Any]:
    matches = []

    for route in getattr(app, "routes", []):
        endpoint = getattr(
            route,
            "endpoint",
            None,
        )

        methods = {
            str(method).upper()
            for method in (
                getattr(route, "methods", None)
                or set()
            )
        }

        path = str(
            getattr(route, "path", "")
        )

        endpoint_name = str(
            getattr(
                endpoint,
                "__name__",
                "",
            )
        )

        if (
            "POST" in methods
            and endpoint_name == "run_simulation"
        ):
            matches.append(
                (path, endpoint)
            )

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one POST route for "
            f"run_simulation, actual={matches}"
        )

    return matches[0]


def public_shadow_count(
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


def precision_summary(
    report: dict[str, Any],
) -> dict[str, Any]:
    corrections = list(
        report.get("corrections") or []
    )

    return {
        "schema_version": report.get(
            "schema_version"
        ),
        "status": report.get("status"),
        "process_type": report.get(
            "process_type"
        ),
        "membrane_model": report.get(
            "membrane_model"
        ),
        "applied_count": report.get(
            "applied_count"
        ),
        "shadow_count": public_shadow_count(
            report
        ),
        "model_ids": [
            row.get("model_id")
            for row in corrections
            if row.get("model_id")
        ],
        "row_statuses": {
            str(row.get("metric")): str(
                row.get("status") or ""
            )
            for row in corrections
        },
    }


def assert_precision_report(
    report: Any,
    *,
    applied_count: int,
    shadow_count: int,
    membrane_prefix: str,
) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise AssertionError(
            "Precision API response has no "
            "precision_report mapping"
        )

    if report.get("status") != "corrected":
        raise AssertionError(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )

    actual_applied = int(
        report.get("applied_count") or 0
    )

    actual_shadow = public_shadow_count(
        report
    )

    if actual_applied != applied_count:
        raise AssertionError(
            f"Unexpected applied_count: "
            f"{actual_applied} != {applied_count}"
        )

    if actual_shadow != shadow_count:
        raise AssertionError(
            f"Unexpected shadow_count: "
            f"{actual_shadow} != {shadow_count}"
        )

    corrections = list(
        report.get("corrections") or []
    )

    wrong_models = [
        str(row.get("model_id"))
        for row in corrections
        if (
            row.get("model_id")
            and not str(
                row.get("model_id")
            ).startswith(membrane_prefix)
        )
    ]

    if wrong_models:
        raise AssertionError(
            "Cross-membrane models in API report: "
            f"{wrong_models}"
        )

    return precision_summary(report)


def install_temporary_runtime_layer() -> dict[str, Any]:
    if not CANONICAL_LAYER_PATH.exists():
        raise FileNotFoundError(
            CANONICAL_LAYER_PATH
        )

    state = {
        "data_dir_existed": (
            DATA_DIR.exists()
        ),
        "layer_existed": (
            RUNTIME_LAYER_PATH.exists()
        ),
        "config_existed": (
            RUNTIME_CONFIG_PATH.exists()
        ),
        "layer_bytes": (
            RUNTIME_LAYER_PATH.read_bytes()
            if RUNTIME_LAYER_PATH.exists()
            else None
        ),
        "config_bytes": (
            RUNTIME_CONFIG_PATH.read_bytes()
            if RUNTIME_CONFIG_PATH.exists()
            else None
        ),
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copyfile(
        CANONICAL_LAYER_PATH,
        RUNTIME_LAYER_PATH,
    )

    RUNTIME_CONFIG_PATH.write_text(
        json.dumps(
            {
                "enabled": False,
                "runtime_safety_guards_enabled": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return state


def restore_runtime_layer(
    state: dict[str, Any],
) -> None:
    if state["layer_existed"]:
        RUNTIME_LAYER_PATH.write_bytes(
            state["layer_bytes"]
        )
    elif RUNTIME_LAYER_PATH.exists():
        RUNTIME_LAYER_PATH.unlink()

    if state["config_existed"]:
        RUNTIME_CONFIG_PATH.write_bytes(
            state["config_bytes"]
        )
    elif RUNTIME_CONFIG_PATH.exists():
        RUNTIME_CONFIG_PATH.unlink()

    if (
        not state["data_dir_existed"]
        and DATA_DIR.exists()
        and not any(DATA_DIR.iterdir())
    ):
        DATA_DIR.rmdir()


def direct_raw_output(
    payload: dict[str, Any],
) -> Any:
    from app.schemas.simulation import (
        SimulationRequest,
    )
    from app.services.simulation.engine import (
        SimulationEngine,
    )

    request = SimulationRequest(
        **copy.deepcopy(payload)
    )

    return SimulationEngine().run(
        request
    )


def post_json(
    client: Any,
    route_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        route_path,
        json=copy.deepcopy(payload),
    )

    if response.status_code != 200:
        raise AssertionError(
            f"POST {route_path} failed: "
            f"{response.status_code}\n"
            f"{response.text}"
        )

    body = response.json()

    if not isinstance(body, dict):
        raise AssertionError(
            "API response is not a JSON object"
        )

    return body


def assert_default_api_raw(
    payload: dict[str, Any],
    api_result: dict[str, Any],
) -> None:
    direct_result = direct_raw_output(
        payload
    )

    if comparable_output(
        api_result
    ) != comparable_output(direct_result):
        raise AssertionError(
            "Default API /run output differs from "
            "raw SimulationEngine output"
        )

    if "precision_report" in api_result:
        raise AssertionError(
            "Default API request unexpectedly returned "
            "precision_report"
        )


def run_nf270(
    helper: Any,
    client: Any,
    route_path: str,
) -> dict[str, Any]:
    raw_payload = helper.build_payload(
        membrane_model="FilmTec NF270-400/34",
        precision_enabled=False,
        case_id="v132_api_nf270",
    )

    precision_payload = copy.deepcopy(
        raw_payload
    )

    precision_payload[
        "precision_mode_enabled"
    ] = True

    raw_body = post_json(
        client,
        route_path,
        raw_payload,
    )

    precision_body = post_json(
        client,
        route_path,
        precision_payload,
    )

    assert_default_api_raw(
        raw_payload,
        raw_body,
    )

    raw_values = response_values(
        raw_body
    )

    precision_values = response_values(
        precision_body
    )

    for metric in (
        "feed_pressure",
        "product_tds",
        "specific_energy",
    ):
        if close(
            raw_values[metric],
            precision_values[metric],
        ):
            raise AssertionError(
                f"NF270 API precision did not "
                f"change {metric}"
            )

    report_summary = assert_precision_report(
        precision_body.get(
            "precision_report"
        ),
        applied_count=3,
        shadow_count=0,
        membrane_prefix="v130_nf270_",
    )

    print("NF270 API default raw PASS")
    print("NF270 API precision runtime 3/3 PASS")

    return {
        "raw": raw_values,
        "precision": precision_values,
        "precision_report": report_summary,
    }


def run_nf90(
    helper: Any,
    client: Any,
    route_path: str,
) -> dict[str, Any]:
    raw_payload = helper.build_payload(
        membrane_model="FilmTec NF90-400/34",
        precision_enabled=False,
        case_id="v132_api_nf90",
    )

    precision_payload = copy.deepcopy(
        raw_payload
    )

    precision_payload[
        "wave_correction_enabled"
    ] = True

    raw_body = post_json(
        client,
        route_path,
        raw_payload,
    )

    precision_body = post_json(
        client,
        route_path,
        precision_payload,
    )

    assert_default_api_raw(
        raw_payload,
        raw_body,
    )

    raw_values = response_values(
        raw_body
    )

    precision_values = response_values(
        precision_body
    )

    for metric in (
        "feed_pressure",
        "specific_energy",
    ):
        if close(
            raw_values[metric],
            precision_values[metric],
        ):
            raise AssertionError(
                f"NF90 API precision did not "
                f"change {metric}"
            )

    if not close(
        raw_values["product_tds"],
        precision_values["product_tds"],
    ):
        raise AssertionError(
            "NF90 API shadow model changed "
            "public product TDS"
        )

    report_summary = assert_precision_report(
        precision_body.get(
            "precision_report"
        ),
        applied_count=2,
        shadow_count=1,
        membrane_prefix="v130_nf90_",
    )

    print("NF90 API default raw PASS")
    print("NF90 API precision runtime 2/2 PASS")
    print("NF90 API product-TDS shadow PASS")

    return {
        "raw": raw_values,
        "precision": precision_values,
        "precision_report": report_summary,
    }


def run_missing_membrane(
    helper: Any,
    client: Any,
    route_path: str,
) -> dict[str, Any]:
    raw_payload = helper.build_payload(
        membrane_model=None,
        precision_enabled=False,
        case_id="v132_api_missing_membrane",
    )

    precision_payload = copy.deepcopy(
        raw_payload
    )

    precision_payload[
        "calibration_mode"
    ] = "precision"

    raw_body = post_json(
        client,
        route_path,
        raw_payload,
    )

    precision_body = post_json(
        client,
        route_path,
        precision_payload,
    )

    assert_default_api_raw(
        raw_payload,
        raw_body,
    )

    if comparable_output(
        raw_body
    ) != comparable_output(
        precision_body
    ):
        raise AssertionError(
            "Missing membrane API precision request "
            "changed simulation output"
        )

    report = precision_body.get(
        "precision_report"
    )

    if not isinstance(report, dict):
        raise AssertionError(
            "Missing membrane API response has no "
            "precision_report"
        )

    if report.get("status") != (
        "missing_membrane_context"
    ):
        raise AssertionError(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )

    print("Missing membrane API raw identity PASS")
    print("Missing membrane API safety guard PASS")

    return {
        "raw": response_values(raw_body),
        "precision": response_values(
            precision_body
        ),
        "status": report.get("status"),
    }


def main() -> int:
    from fastapi.testclient import TestClient

    helper = load_helper()

    runtime_state = (
        install_temporary_runtime_layer()
    )

    app = None
    client = None

    try:
        app = find_fastapi_app()

        simulation_endpoint = (
            importlib.import_module(
                "app.api.v1.endpoints.simulation"
            )
        )

        get_db = getattr(
            simulation_endpoint,
            "get_db",
            None,
        )

        if get_db is None:
            raise RuntimeError(
                "simulation.get_db dependency "
                "was not found"
            )

        def override_get_db():
            yield None

        app.dependency_overrides[
            get_db
        ] = override_get_db

        route_path, _ = find_run_route(
            app
        )

        client = TestClient(
            app,
            raise_server_exceptions=True,
        )

        print("=" * 100)
        print("V132 NF FASTAPI POST /run E2E")
        print("=" * 100)
        print(f"route={route_path}")
        print(
            f"runtime_layer={RUNTIME_LAYER_PATH}"
        )
        print(
            "runtime_global_enabled=False"
        )

        nf270 = run_nf270(
            helper,
            client,
            route_path,
        )

        nf90 = run_nf90(
            helper,
            client,
            route_path,
        )

        missing = run_missing_membrane(
            helper,
            client,
            route_path,
        )

        output = {
            "schema_version": (
                "aquanova.nf_fastapi_e2e.v132"
            ),
            "status": "PASS",
            "route": route_path,
            "runtime_global_enabled": False,
            "default_api_path": (
                "raw_simulation_engine"
            ),
            "nf270": nf270,
            "nf90": nf90,
            "missing_membrane": missing,
        }

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUTPUT_PATH.write_text(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"output={OUTPUT_PATH}")
        print("default_global_off=PASS")
        print("default_api_raw_identity=PASS")
        print("NF270_api_runtime=3")
        print("NF90_api_runtime=2")
        print("NF90_api_shadow=1")
        print("missing_membrane_api_guard=PASS")
        print(
            "\nV132 NF FastAPI POST /run E2E PASS"
        )

        return 0

    finally:
        if client is not None:
            client.close()

        if app is not None:
            try:
                app.dependency_overrides.clear()
            except Exception:
                pass

        restore_runtime_layer(
            runtime_state
        )


if __name__ == "__main__":
    raise SystemExit(main())
