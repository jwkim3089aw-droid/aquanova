"""Batch plan/case schema helpers extracted by V131A.

The legacy module imports these names back for compatibility.
"""
from __future__ import annotations

# V134E WaveAutomationError bridge
class WaveAutomationError(RuntimeError):
    pass

try:
    from wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]
except Exception:
    try:
        from ..wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]
    except Exception:
        pass

import copy

import csv
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple, Union

try:
    from wave_ro_schema import ROCaseConfig
except ImportError:
    try:
        from ..wave_ro_schema import ROCaseConfig
    except ImportError:
        ROCaseConfig = None  # type: ignore

def _choose_stable_global_temperature_mode(
    case: ROCaseConfig,
    group: dict[str, Any],
) -> tuple[str, str]:
    """Choose a physically equivalent WAVE mode that survives topology edits.

    In this WAVE build, committing ``Specify`` at the feed Design temperature
    can collapse a multi-stage pass to one stage, while re-selecting the stage
    count restores the source-profile temperature.  When the numerical target
    exactly equals an envelope point, use that native envelope mode instead of
    Specify.  The operating temperature is unchanged; only the unstable UI path
    is avoided.  The decision is recorded in the expansion manifest.
    """
    temperature = float(group["temperature_c"])
    unique_modes = list(dict.fromkeys(group["modes"]))
    has_multistage = any(p.stage_count > 1 for p in case.passes)
    envelope = [
        ("Design", float(case.feed_temperature_design_c)),
        ("Minimum", float(case.resolved_feed_temperature_min_c)),
        ("Maximum", float(case.resolved_feed_temperature_max_c)),
    ]
    for native_mode, native_value in envelope:
        if abs(temperature - native_value) <= 0.06 and (
            len(unique_modes) > 1 or (has_multistage and "Specify" in unique_modes)
        ):
            return (
                native_mode,
                f"V52 stable-mode normalization: {temperature:g}C matches feed {native_mode}; "
                "avoids WAVE Specify/multi-stage topology reset",
            )
    if len(unique_modes) == 1:
        return unique_modes[0], "single requested global mode"
    return "Specify", "mixed labels at one numerical temperature"

def _settings_from_case(
    case: dict[str, str],
    *,
    add_ro: bool,
    pause: float,
    long_wait: float,
    validate_pdf: bool,
) -> Settings:
    return Settings(
        water_profile=case["water_profile"],
        temperature_c=case["temperature_c"],
        feed_flow_m3h=case["feed_flow_m3h"],
        recovery_pct=case["recovery_pct"],
        pv_per_stage=case["pv_per_stage"],
        elements_per_pv=case["elements_per_pv"],
        membrane=case["membrane"],
        add_ro=add_ro,
        pause=pause,
        long_wait=long_wait,
        validate_pdf=validate_pdf,
    )

# V134D_PLAN_SCHEMA_SELF_CONTAINED_APPLIED

def _canonical_temperature_mode(mode: str) -> str:
    mapping = {
        "minimum": "Minimum",
        "design": "Design",
        "maximum": "Maximum",
        "specify": "Specify",
    }
    key = str(mode or "").strip().casefold()
    if key not in mapping:
        raise WaveAutomationError(f"지원하지 않는 RO 온도 모드입니다: {mode!r}")
    return mapping[key]

def _temperature_variant_suffix(mode: str, temperature_c: float) -> str:
    mode_token = {
        "Minimum": "MIN",
        "Design": "DESIGN",
        "Maximum": "MAX",
        "Specify": "SPEC",
    }[_canonical_temperature_mode(mode)]
    number = f"{float(temperature_c):g}".replace("-", "M").replace(".", "p")
    return f"{mode_token}_{number}C"

def _clone_case_for_global_temperature(
    case: ROCaseConfig,
    *,
    mode: str,
    temperature_c: float,
    suffix: str | None,
) -> ROCaseConfig:
    clone = copy.deepcopy(case)
    canonical = _canonical_temperature_mode(mode)
    for pass_config in clone.passes:
        pass_config.temperature_mode = canonical
        pass_config.temperature_c = float(temperature_c)
    source_case_id = case.case_id
    if suffix:
        clone.case_id = f"{source_case_id}__{suffix}"
        pdf = Path(case.pdf_name)
        clone.pdf_name = f"{pdf.stem}__{suffix}{pdf.suffix}"
    clone.notes = (
        (case.notes + " | ") if case.notes else ""
    ) + (
        f"V52 WAVE 전역 온도 변형: source={source_case_id}, "
        f"mode={canonical}, temperature={float(temperature_c):g}C"
    )
    setattr(clone, "_source_case_id", source_case_id)
    setattr(clone, "_temperature_variant_mode", canonical)
    setattr(clone, "_temperature_variant_c", float(temperature_c))
    setattr(clone, "_temperature_expanded", bool(suffix))
    clone.validate()
    return clone

def expand_cases_for_wave_global_temperature(
    cases: list[ROCaseConfig],
) -> tuple[list[ROCaseConfig], list[dict[str, Any]]]:
    """Normalize/expand pass temperatures because WAVE exposes one global mode.

    WAVE visually repeats the Temperature control on each Pass tab, but changing
    it on Pass 2 also changes Pass 1.  Cases whose passes request the same
    numerical temperature are normalized to one global setting.  Cases that
    request different temperatures are expanded into one deterministic run per
    distinct temperature, preserving every requested operating point without
    silently overwriting another pass.
    """
    expanded: list[ROCaseConfig] = []
    manifest: list[dict[str, Any]] = []
    for case in cases:
        groups: list[dict[str, Any]] = []
        for pass_index, pass_config in enumerate(case.passes, start=1):
            temp = float(pass_config.temperature_c)
            mode = _canonical_temperature_mode(pass_config.temperature_mode)
            group = next(
                (item for item in groups if abs(float(item["temperature_c"]) - temp) <= 0.06),
                None,
            )
            if group is None:
                group = {"temperature_c": temp, "modes": [], "passes": []}
                groups.append(group)
            group["modes"].append(mode)
            group["passes"].append(pass_index)

        variants: list[ROCaseConfig] = []
        mode_decisions: list[dict[str, Any]] = []
        if len(groups) == 1:
            group = groups[0]
            mode, reason = _choose_stable_global_temperature_mode(case, group)
            variant = _clone_case_for_global_temperature(
                case, mode=mode, temperature_c=group["temperature_c"], suffix=None
            )
            setattr(variant, "_temperature_mode_reason", reason)
            variants.append(variant)
            mode_decisions.append(
                {
                    "temperature_c": float(group["temperature_c"]),
                    "requested_modes": list(dict.fromkeys(group["modes"])),
                    "selected_mode": mode,
                    "reason": reason,
                }
            )
        else:
            for group in groups:
                mode, reason = _choose_stable_global_temperature_mode(case, group)
                suffix = _temperature_variant_suffix(mode, group["temperature_c"])
                variant = _clone_case_for_global_temperature(
                    case,
                    mode=mode,
                    temperature_c=group["temperature_c"],
                    suffix=suffix,
                )
                setattr(variant, "_temperature_mode_reason", reason)
                variants.append(variant)
                mode_decisions.append(
                    {
                        "temperature_c": float(group["temperature_c"]),
                        "requested_modes": list(dict.fromkeys(group["modes"])),
                        "selected_mode": mode,
                        "reason": reason,
                    }
                )

        expanded.extend(variants)
        manifest.append(
            {
                "source_case_id": case.case_id,
                "requested": [
                    {
                        "pass": index,
                        "mode": _canonical_temperature_mode(pass_config.temperature_mode),
                        "temperature_c": float(pass_config.temperature_c),
                    }
                    for index, pass_config in enumerate(case.passes, start=1)
                ],
                "expanded_case_ids": [variant.case_id for variant in variants],
                "expanded_pdf_names": [variant.pdf_name for variant in variants],
                "mode_decisions": mode_decisions,
                "reason": (
                    "WAVE temperature is global across Pass tabs"
                    if len(groups) > 1
                    else "single effective global temperature"
                ),
            }
        )
    return expanded, manifest
