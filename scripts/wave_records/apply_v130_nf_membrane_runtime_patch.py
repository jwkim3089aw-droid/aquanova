from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RUNTIME_PATH = (
    ROOT
    / "app/services/simulation/calibration"
    / "wave_runtime_correction.py"
)

ENGINE_PATH = (
    ROOT
    / "app/services/simulation"
    / "wave_corrected_engine.py"
)

RUNTIME_MARKER = (
    "# --- V130 NF membrane-aware runtime selector BEGIN ---"
)

ENGINE_MARKER = (
    "# --- V130 request membrane propagation BEGIN ---"
)


RUNTIME_APPEND = r'''

# --- V130 NF membrane-aware runtime selector BEGIN ---
#
# V92 and V118 identify models primarily by process/metric/regime.
# NF270 and NF90 require an additional membrane scope because their
# pressure and product-quality response differs substantially.
#
# This wrapper only intercepts layers that explicitly carry:
#
#     applicability.mem­brane_models
#
# All existing non-NF and non-membrane-scoped layers continue through
# the previously active V118B/V118/V97 compatibility path.

_V130_PREVIOUS_APPLY = apply_wave_runtime_corrections_to_output


def _v130_norm_token(value):
    return "".join(
        char
        for char in str(value or "").lower()
        if char.isalnum()
    )


def _v130_membrane_from_options(options):
    opts = dict(options or {})

    for key in (
        "wave_membrane_model",
        "membrane_model",
        "membrane_model_hint",
        "element_model",
    ):
        value = opts.get(key)

        if value not in (None, ""):
            return str(value)

    return ""


def _v130_model_membrane_aliases(model):
    applicability = model.get("applicability") or {}

    values = applicability.get("membrane_models")

    if values in (None, ""):
        values = applicability.get("membrane_model")

    if values in (None, ""):
        values = applicability.get("membrane_family")

    if values in (None, ""):
        return []

    if isinstance(values, str):
        values = [values]

    aliases = []

    for value in values:
        normalized = _v130_norm_token(value)

        if normalized:
            aliases.append(normalized)

    return aliases


def _v130_has_membrane_scope(layer):
    for model in layer.get("models") or []:
        if not isinstance(model, dict):
            continue

        if _v130_model_membrane_aliases(model):
            return True

    return False


def _v130_membrane_matches(actual_membrane, aliases):
    actual = _v130_norm_token(actual_membrane)

    if not actual:
        return False

    for alias in aliases:
        if not alias:
            continue

        if actual == alias:
            return True

        # Handles forms such as:
        # FilmTec NF270-400/34
        # NF270-400
        # NF270
        if len(alias) >= 4 and alias in actual:
            return True

        if len(actual) >= 4 and actual in alias:
            return True

    return False


def _v130_model_for(
    layer,
    process_type,
    metric,
    regime,
    membrane_model,
):
    process = str(process_type or "").lower()
    metric_name = str(metric or "").lower()
    regime_name = str(regime or "")

    for model in layer.get("models") or []:
        if not isinstance(model, dict):
            continue

        if str(model.get("process_type", "")).lower() != process:
            continue

        if str(model.get("metric", "")).lower() != metric_name:
            continue

        model_regime = str(model.get("regime") or "")

        if model_regime and model_regime != regime_name:
            continue

        aliases = _v130_model_membrane_aliases(model)

        if not aliases:
            continue

        if _v130_membrane_matches(
            membrane_model,
            aliases,
        ):
            return model

    return None


def _v130_report_row(
    *,
    metric,
    model,
    raw_value,
    corrected_value,
    path,
    status,
    **extra,
):
    row = {
        "metric": metric,
        "model_id": (
            model.get("model_id", "")
            if isinstance(model, dict)
            else ""
        ),
        "raw_value": raw_value,
        "corrected_value": corrected_value,
        "path": path,
        "status": status,
    }

    row.update(extra)
    return row


def apply_wave_runtime_corrections_to_output(
    result,
    correction_layer,
    *,
    options=None,
    config=None,
):
    options = dict(options or {})
    config = dict(config or {})
    layer = dict(correction_layer or {})

    # Preserve all existing behavior when this is not a V130-style
    # membrane-scoped layer.
    if not _v130_has_membrane_scope(layer):
        return _V130_PREVIOUS_APPLY(
            result,
            correction_layer,
            options=options,
            config=config,
        )

    # Preserve the existing runtime opt-in gate.
    if _v118b_disabled(options, config):
        return _V130_PREVIOUS_APPLY(
            result,
            correction_layer,
            options=options,
            config=config,
        )

    process_type = str(
        options.get("wave_process_type")
        or _v118_infer_process(result, layer)
        or ""
    ).lower()

    # Only NF is intercepted by V130.
    if process_type != "nf":
        return _V130_PREVIOUS_APPLY(
            result,
            correction_layer,
            options=options,
            config=config,
        )

    membrane_model = _v130_membrane_from_options(options)

    report = {
        "schema_version": (
            "aquanova.wave_runtime_correction.v130"
        ),
        "runtime_bridge": (
            "v130_nf_membrane_aware_runtime_selector"
        ),
        "enabled": True,
        "process_type": process_type,
        "membrane_model": membrane_model,
        "applied_count": 0,
        "skipped_count": 0,
        "shadow_count": 0,
        "corrections": [],
        "options": options,
    }

    # Never fall back to an unscoped NF model when membrane identity
    # is missing. Returning raw values is safer than cross-applying
    # an NF270 model to NF90 or vice versa.
    if not membrane_model:
        report["status"] = "missing_membrane_context"
        return result, report

    corrected_result = _v118_copy.deepcopy(result)
    regime = _v118_infer_regime(
        corrected_result,
        process_type,
    )

    report["regime"] = regime

    metrics = [
        "feed_pressure",
        "product_tds",
        "final_concentrate_tds",
        "specific_energy",
    ]

    for metric in metrics:
        slot = _v118_find_metric_slot(
            corrected_result,
            metric,
        )

        model = _v130_model_for(
            layer,
            process_type,
            metric,
            regime,
            membrane_model,
        )

        if slot is None:
            report["skipped_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=model,
                    raw_value=None,
                    corrected_value=None,
                    path="",
                    status="no_output_path",
                )
            )
            continue

        parent, key, raw, path = slot

        if model is None:
            report["skipped_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=None,
                    raw_value=raw,
                    corrected_value=raw,
                    path=path,
                    status="no_membrane_scoped_model",
                )
            )
            continue

        # Use the established V92 evaluator. A one-model temporary
        # layer prevents the old process+metric selector from seeing
        # another membrane's model.
        prediction = apply_correction(
            {"models": [model]},
            process_type,
            metric,
            raw,
            {
                "membrane_model": membrane_model,
                "regime": regime,
            },
            force=True,
        )

        prediction_status = str(
            prediction.get("status") or ""
        )

        proposed = _v118_float(
            prediction.get("corrected_value")
        )

        if proposed is None:
            report["skipped_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=model,
                    raw_value=raw,
                    corrected_value=raw,
                    path=path,
                    status="prediction_failed",
                    prediction_status=prediction_status,
                )
            )
            continue

        # Shadow models are evaluated and reported, but never written
        # into the simulation output.
        if not bool(model.get("runtime_enabled")):
            report["shadow_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=model,
                    raw_value=raw,
                    corrected_value=raw,
                    path=path,
                    status="shadow_only",
                    shadow_corrected_value=proposed,
                    prediction_status=prediction_status,
                )
            )
            continue

        guard_reason = _v118_runtime_guard(
            metric,
            raw,
            proposed,
            model,
            regime,
        )

        if guard_reason:
            report["skipped_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=model,
                    raw_value=raw,
                    corrected_value=raw,
                    path=path,
                    status="blocked_runtime_guard",
                    blocked_corrected_value=proposed,
                    guard_reason=guard_reason,
                )
            )
            continue

        if not _v118_set(parent, key, proposed):
            report["skipped_count"] += 1
            report["corrections"].append(
                _v130_report_row(
                    metric=metric,
                    model=model,
                    raw_value=raw,
                    corrected_value=raw,
                    path=path,
                    status="set_failed",
                    blocked_corrected_value=proposed,
                )
            )
            continue

        report["applied_count"] += 1
        report["corrections"].append(
            _v130_report_row(
                metric=metric,
                model=model,
                raw_value=raw,
                corrected_value=proposed,
                path=path,
                status="applied",
                model_type=model.get("model_type"),
            )
        )

    if report["applied_count"] > 0:
        report["status"] = "corrected"
    elif report["shadow_count"] > 0:
        report["status"] = "shadow_only"
    else:
        report["status"] = (
            "guarded_no_runtime_corrections_applied"
        )

    return corrected_result, report

# --- V130 NF membrane-aware runtime selector END ---
'''


ENGINE_APPEND = r'''

# --- V130 request membrane propagation BEGIN ---
#
# Preserve the existing option extraction behavior, then attach the first
# configured membrane model to runtime options. The current NF calibration
# campaign uses one pressure-membrane stage per request.

_V130_PREVIOUS_EXTRACT_OPTIONS = extract_wave_correction_options


def _v130_request_membrane_model(request):
    payload = _as_mapping(request)

    for key in (
        "wave_membrane_model",
        "membrane_model",
        "membrane_model_hint",
    ):
        value = payload.get(key)

        if value not in (None, ""):
            return str(value)

    for section_name in (
        "options",
        "settings",
        "calibration",
        "runtime",
        "advanced_options",
    ):
        section = _as_mapping(payload.get(section_name))

        for key in (
            "wave_membrane_model",
            "membrane_model",
            "membrane_model_hint",
        ):
            value = section.get(key)

            if value not in (None, ""):
                return str(value)

    stages = payload.get("stages")

    if stages is None and request is not None:
        stages = getattr(request, "stages", None)

    if not isinstance(stages, (list, tuple)):
        return ""

    for stage in stages:
        stage_payload = _as_mapping(stage)

        value = (
            stage_payload.get("membrane_model")
            or stage_payload.get("element_model")
            or stage_payload.get("module_model")
        )

        if value not in (None, ""):
            return str(value)

    return ""


def extract_wave_correction_options(
    request=None,
    explicit_options=None,
):
    out = _V130_PREVIOUS_EXTRACT_OPTIONS(
        request,
        explicit_options,
    )

    membrane_model = _v130_request_membrane_model(
        request
    )

    if membrane_model:
        out.setdefault(
            "wave_membrane_model",
            membrane_model,
        )

    return out

# --- V130 request membrane propagation END ---
'''


def append_once(
    path: Path,
    marker: str,
    block: str,
) -> bool:
    text = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    if marker in text:
        print(f"SKIP already patched: {path}")
        return False

    if not text.endswith("\n"):
        text += "\n"

    path.write_text(
        text + block.lstrip("\n"),
        encoding="utf-8",
    )

    print(f"PATCHED: {path}")
    return True


def main() -> int:
    for path in (RUNTIME_PATH, ENGINE_PATH):
        if not path.exists():
            print(f"FAIL missing source: {path}")
            return 1

    append_once(
        RUNTIME_PATH,
        RUNTIME_MARKER,
        RUNTIME_APPEND,
    )

    append_once(
        ENGINE_PATH,
        ENGINE_MARKER,
        ENGINE_APPEND,
    )

    print("V130 NF membrane runtime patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
