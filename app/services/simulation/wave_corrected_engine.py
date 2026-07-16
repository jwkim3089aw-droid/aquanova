"""V95 opt-in SimulationEngine integration for WAVE calibration correction.

V94 added a low-level correction helper that can apply a reviewed V92 correction
layer to a ScenarioOutput-like object.  V95 is the runtime-facing bridge: it can
wrap the real ``SimulationEngine`` and apply that correction only when the
request/config explicitly opts in.

Safety rules:

* default behavior is unchanged/off;
* the original base engine is still responsible for the physical simulation;
* WAVE correction is applied only after the raw result is produced;
* layer/config loading is lazy, so missing .data files do not affect normal runs;
* the wrapper stores a machine-readable report on ``last_wave_correction_report``.

This file deliberately does not replace ``app.services.simulation.engine``.  It
is an opt-in adapter that API/UI code can call first, then V96 can run benchmark
regression with the flag enabled.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from app.services.simulation.calibration.wave_runtime_correction import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_LAYER_PATH,
    ENABLE_OPTION_KEYS,
    apply_wave_runtime_corrections_to_output,
    load_correction_layer,
    load_runtime_config,
    runtime_enabled,
)

SCHEMA_VERSION = "aquanova.wave_corrected_engine.v95"


def _as_mapping(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        try:
            return dict(obj.model_dump(mode="python"))
        except TypeError:
            return dict(obj.model_dump())
    if hasattr(obj, "dict"):
        return dict(obj.dict())
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {}


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def extract_wave_correction_options(request: Any = None, explicit_options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Collect opt-in flags from a request-like object and explicit options.

    AquaNova request shapes have changed during development, so this function is
    intentionally tolerant.  It checks common locations such as ``options``,
    ``settings``, ``calibration``, Pydantic extras, and top-level request fields.
    Explicit options win last.
    """
    out: dict[str, Any] = {}
    payload = _as_mapping(request)

    # Top-level flags.
    for key in ENABLE_OPTION_KEYS:
        if key in payload:
            out[key] = payload[key]

    # Nested request sections that often carry UI/API feature flags.
    for section_name in ("options", "settings", "calibration", "runtime", "advanced_options"):
        nested = _as_mapping(payload.get(section_name)) or _as_mapping(getattr(request, section_name, None) if request is not None else None)
        for key in ENABLE_OPTION_KEYS:
            if key in nested:
                out[key] = nested[key]

    # Pydantic v2 extras are not always included in model_dump depending on config.
    extra = getattr(request, "model_extra", None) if request is not None else None
    if isinstance(extra, Mapping):
        for key in ENABLE_OPTION_KEYS:
            if key in extra:
                out[key] = extra[key]
        for section_name in ("options", "settings", "calibration", "runtime", "advanced_options"):
            nested = _as_mapping(extra.get(section_name))
            for key in ENABLE_OPTION_KEYS:
                if key in nested:
                    out[key] = nested[key]

    # Environment override is useful for local benchmark runs, but explicit
    # request options can still override it.
    env_value = os.getenv("AQUANOVA_ENABLE_WAVE_CORRECTION")
    if env_value is not None:
        out.setdefault("enable_wave_correction", _boolish(env_value))

    if explicit_options:
        out.update(dict(explicit_options))
    return out


def build_disabled_report(reason: str = "disabled", *, options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": reason,
        "enabled": False,
        "applied_count": 0,
        "skipped_count": 0,
        "corrections": [],
        "options": dict(options or {}),
    }


def maybe_apply_wave_correction(
    result: Any,
    *,
    request: Any = None,
    options: Mapping[str, Any] | None = None,
    correction_layer: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    layer_path: str | Path | None = None,
    config_path: str | Path | None = None,
    strict_layer: bool = False,
) -> tuple[Any, dict[str, Any]]:
    """Apply installed WAVE correction to an engine result when explicitly enabled.

    The function is safe to call on every simulation result.  If the runtime flag
    is off, or if no reviewed layer is installed, the original result is returned
    unchanged with a report explaining why.
    """
    cfg = dict(config or load_runtime_config(config_path or DEFAULT_CONFIG_PATH, missing_ok=True))
    opts = extract_wave_correction_options(request, options)
    enabled = runtime_enabled(opts, cfg)
    if not enabled:
        return result, build_disabled_report("disabled", options=opts)

    try:
        layer = dict(correction_layer or load_correction_layer(layer_path or cfg.get("correction_layer_path") or DEFAULT_LAYER_PATH))
    except Exception as exc:
        if strict_layer:
            raise
        report = build_disabled_report("layer_missing_or_invalid", options=opts)
        report.update({"enabled": True, "error": f"{exc.__class__.__name__}: {exc}"})
        return result, report

    corrected, report = apply_wave_runtime_corrections_to_output(
        result,
        layer,
        options=opts,
        config=cfg,
    )
    report = dict(report)
    report.setdefault("schema_version", SCHEMA_VERSION)
    report["engine_integration_schema_version"] = SCHEMA_VERSION
    report["runtime_bridge"] = "v95_opt_in_simulation_engine"
    report["options"] = opts
    return corrected, report


class WaveCorrectedSimulationEngine:
    """Opt-in wrapper around the real AquaNova ``SimulationEngine``.

    Example:
        engine = WaveCorrectedSimulationEngine()
        result = engine.run(request)  # unchanged unless request/options enable correction
        report = engine.last_wave_correction_report
    """

    def __init__(
        self,
        base_engine: Any | None = None,
        *,
        correction_layer: Mapping[str, Any] | None = None,
        config: Mapping[str, Any] | None = None,
        layer_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        if base_engine is None:
            from app.services.simulation.engine import SimulationEngine  # imported lazily to avoid circular imports

            base_engine = SimulationEngine()
        self.base_engine = base_engine
        self.correction_layer = correction_layer
        self.config = config
        self.layer_path = layer_path
        self.config_path = config_path
        self.last_wave_correction_report: dict[str, Any] = build_disabled_report("not_run")

    def run_raw(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        return self.base_engine.run(request, *args, **kwargs)

    def run(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        result = self.run_raw(request, *args, **kwargs)
        corrected, report = maybe_apply_wave_correction(
            result,
            request=request,
            correction_layer=self.correction_layer,
            config=self.config,
            layer_path=self.layer_path,
            config_path=self.config_path,
        )
        self.last_wave_correction_report = report
        return corrected


def run_simulation_with_optional_wave_correction(
    request: Any,
    *,
    engine: Any | None = None,
    options: Mapping[str, Any] | None = None,
    correction_layer: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    layer_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Run the real engine and return ``(result, correction_report)``.

    This is the preferred integration point for API routes or benchmark scripts
    that want an explicit report in addition to the ScenarioOutput.
    """
    if engine is None:
        from app.services.simulation.engine import SimulationEngine

        engine = SimulationEngine()
    raw = engine.run(request)
    return maybe_apply_wave_correction(
        raw,
        request=request,
        options=options,
        correction_layer=correction_layer,
        config=config,
        layer_path=layer_path,
        config_path=config_path,
    )
