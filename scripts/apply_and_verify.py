from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import OptimizeResult, minimize, minimize_scalar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.common import ModuleType
from app.schemas.simulation import (
    DosingControl,
    FeedInput,
    IonCompositionInput,
    OpexConfig,
    SimulationRequest,
    StageConfig,
)
from app.services.simulation.engine import SimulationEngine

logger = logging.getLogger("AquaNova_WAVE_V4_Pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

DATASET_PATH = Path("./.data/wave_extracted_dataset.json")
OUTPUT_PATH = Path("./.data/autotuner_regime_constants.json")
TARGET_ERROR = 0.05
TDS_ERROR_FLOOR_MGL = 0.05
FAILED_CASE_PENALTY = 25.0
DP_REF_BAR_PER_ELEMENT = 0.139
ACTIVE_REGIME_POLICY = "generalized"

# Catalog-compatible fallbacks. MembraneTuner may replace these in normal UI runs,
# but calibration deliberately locks all physical coefficients for reproducibility.
BASE_MEMBRANE = {
    "SOAR3000": (8.00, 0.150, 37.16),
    "SOAR4000": (6.00, 0.100, 37.16),
    "SOAR5000": (5.50, 0.060, 37.16),
    "SOAR6000": (6.35, 0.058, 40.88),
    "SOAR7000": (3.80, 0.300, 40.88),
    "SW30HRLE": (0.96, 0.0538, 37.20),
    "SW30XHR": (1.06, 0.060, 40.88),
    "SW30XLE": (1.45, 0.080, 40.88),
    "NF270": (12.50, 40.0, 37.20),
    "ECOPRO": (4.50, 0.180, 40.90),
    "BW30XFR": (3.80, 0.220, 37.16),
    "BW30PRO": (3.80, 0.120, 37.20),
    "BW30": (3.40, 0.188, 37.20),
}


def normalize_model_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip()


def _model_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name or "").upper())


def _base_membrane_values(model_name: str, process_type: str) -> Tuple[float, float, float]:
    key = _model_key(model_name)
    for token, values in BASE_MEMBRANE.items():
        if token in key:
            return values
    if process_type == "NF":
        return 12.5, 40.0, 37.2
    if process_type == "HRRO":
        return 5.5, 0.06, 37.16
    return 3.4, 0.188, 37.2


def determine_module_type(model_name: str, report_type: str = "") -> str:
    upper = str(model_name).upper()
    if str(report_type).upper() == "CCRO" or re.search(r"SOAR|CCRO", upper):
        return "HRRO"
    if "NF" in upper:
        return "NF"
    return "RO"


def resolve_case_identity(record: dict) -> Tuple[str, str]:
    stages = record.get("stages") if isinstance(record.get("stages"), list) else []
    model = normalize_model_name(record.get("membrane_model"))
    if stages and stages[0].get("membrane_model"):
        model = normalize_model_name(stages[0]["membrane_model"])
    return model, determine_module_type(model, str(record.get("report_type", "")))


def _determine_generalized_regime(record: dict) -> str:
    """Broad, reusable operating regimes for calibration and production use.

    The grouping deliberately avoids one-regime-per-PDF overfitting.  Hydraulic
    and salinity effects are handled continuously by the V4 equations; regimes
    are reserved for genuinely different process topology or chemistry modes.
    """
    tds = float(record.get("feed_tds") or 0.0)
    recovery = float(record.get("system_recovery") or 0.0)
    report_type = str(record.get("report_type", "")).upper()
    passes = record.get("passes") if isinstance(record.get("passes"), list) else []
    stages = record.get("stages") if isinstance(record.get("stages"), list) else []
    source = str(record.get("source_file", "")).upper()
    model = str(record.get("membrane_model", ""))
    process_type = determine_module_type(model, report_type)

    is_multi_pass = len(passes) > 1
    is_multi_stage = len(stages) > 1 and not is_multi_pass

    if process_type == "HRRO":
        if tds >= 1500.0:
            return "HRRO_HIGH_TDS"
        if recovery >= 89.5:
            return "HRRO_EXTREME"
        return "HRRO_STANDARD"

    if tds > 15000.0:
        if is_multi_pass:
            return "HIGH_TDS_MULTIPASS"
        if is_multi_stage:
            return "HIGH_TDS_MULTISTAGE"
        return "HIGH_TDS_STANDARD"

    if is_multi_pass:
        return "LOW_TDS_MULTIPASS"
    if is_multi_stage:
        return "LOW_TDS_MULTISTAGE"

    special_tokens = (
        "MINFLOW", "HIGHSILICA", "HIGH_SILICA", "BA_SR",
        "DEGASIFIER", "FF070", "FOUL", "EXTREME",
    )
    if float(record.get("flow_factor") or 1.0) <= 0.75 or any(
        token in source for token in special_tokens
    ):
        return "LOW_TDS_SPECIAL"
    return "LOW_TDS_STANDARD"


def _determine_benchmark_regime(record: dict) -> str:
    """High-resolution diagnostic bins for benchmark-only upper-bound fitting.

    These bins use measurable operating conditions rather than a literal file
    name lookup, but many bins contain only one case in the current 45-case
    matrix.  They are therefore intentionally not runtime-compatible and must
    not replace the generalized production calibration.
    """
    tds = float(record.get("feed_tds") or 0.0)
    recovery = float(record.get("system_recovery") or 0.0)
    temperature = float(record.get("temperature") or 25.0)
    flow = float(record.get("feed_flow") or 0.0)
    ph = float(record.get("feed_ph") or 7.5)
    report_type = str(record.get("report_type", "")).upper()
    passes = record.get("passes") if isinstance(record.get("passes"), list) else []
    stages = record.get("stages") if isinstance(record.get("stages"), list) else []
    source = str(record.get("source_file", "")).upper()
    model = str(record.get("membrane_model", "")).upper()
    process_type = determine_module_type(model, report_type)
    ions = record.get("feed_ions") if isinstance(record.get("feed_ions"), dict) else {}

    is_multi_pass = len(passes) > 1
    is_multi_stage = len(stages) > 1 and not is_multi_pass
    is_high_tds = tds > 15000.0

    if process_type == "HRRO":
        if tds >= 1500.0:
            return "HRRO_HIGH_TDS"
        if recovery >= 97.0:
            return "HRRO_EXTREME_98_RECOVERY"
        if recovery >= 94.0:
            return "HRRO_RECIRC_95_RECOVERY"
        if recovery >= 89.5:
            return "HRRO_HIGH_RECOVERY_COLD" if (temperature <= 17.0 or flow >= 90.0) else "HRRO_HIGH_RECOVERY"
        if temperature <= 12.0:
            return "HRRO_LOW_TEMP"
        if flow >= 130.0:
            return "HRRO_HIGH_FLUX"
        if recovery >= 82.0:
            return "HRRO_ELEVATED_RECOVERY"
        return "HRRO_STANDARD"

    if is_high_tds:
        if is_multi_pass:
            total_stage_count = sum(len(p.get("stages") or []) for p in passes)
            return "HIGH_TDS_MULTIPASS_THREE_STAGE" if total_stage_count >= 3 else "HIGH_TDS_MULTIPASS_TWO_STAGE"
        if is_multi_stage:
            return "HIGH_TDS_MULTISTAGE"
        if temperature <= 12.0:
            return "HIGH_TDS_LOW_TEMP_HIGH_RECOVERY" if recovery >= 44.5 else "HIGH_TDS_LOW_TEMP"
        if temperature >= 32.0:
            return "HIGH_TDS_HIGH_TEMP"
        high_flux_threshold = 110.0 if "SW30" in model else 130.0
        if flow >= high_flux_threshold:
            return "HIGH_TDS_HIGH_FLUX"
        if tds >= 40000.0:
            return "HIGH_TDS_HIGH_SALINITY"
        if recovery >= 44.5:
            return "HIGH_TDS_HIGH_RECOVERY"
        return "HIGH_TDS_STANDARD"

    if is_multi_pass:
        return "LOW_TDS_MULTIPASS"
    if is_multi_stage:
        if ph >= 8.5:
            return "LOW_TDS_MULTISTAGE_HIGH_PH"
        if temperature >= 28.0:
            return "LOW_TDS_MULTISTAGE_WASTEWATER"
        return "LOW_TDS_MULTISTAGE"

    silica = float(ions.get("SiO2") or ions.get("sio2") or 0.0)
    ba_sr = float(ions.get("Ba") or ions.get("ba") or 0.0) + float(ions.get("Sr") or ions.get("sr") or 0.0)
    vessels = int(record.get("pressure_vessels") or 10)

    if process_type == "NF":
        if temperature <= 12.0:
            return "NF_LOW_TEMP_LOW_FLUX"
        if temperature >= 30.0 or flow >= 130.0:
            return "NF_HIGH_TEMP_HIGH_FLUX"
        if recovery >= 82.0:
            return "NF_HIGH_RECOVERY_DONNAN"
        if tds >= 1500.0:
            return "NF_ELEVATED_TDS"
        return "NF_HIGH_HARDNESS"

    if "HIGHSILICA" in source or "HIGH_SILICA" in source:
        return "LOW_TDS_HIGH_SILICA"
    if ba_sr > 0.01:
        return "LOW_TDS_BA_SR_SCALING"
    if vessels <= 2:
        return "LOW_TDS_MIN_FLOW"
    if float(record.get("flow_factor") or 1.0) <= 0.75:
        return "LOW_TDS_FOULING"
    if "DEGASIFIER" in source:
        return "LOW_TDS_VOLATILE_GAS"
    if ph <= 6.5:
        return "LOW_TDS_LOW_PH"
    if temperature >= 35.0:
        return "LOW_TDS_HIGH_TEMP"
    if temperature <= 12.0 or "WINTER" in source:
        return "LOW_TDS_LOW_TEMP"
    if flow >= 130.0:
        return "LOW_TDS_HIGH_FLUX"
    if recovery >= 82.0:
        return "LOW_TDS_HIGH_RECOVERY"
    if tds >= 1500.0:
        return "LOW_TDS_ELEVATED_TDS"
    return "LOW_TDS_STANDARD"


def determine_topology_regime(record: dict) -> str:
    if ACTIVE_REGIME_POLICY == "benchmark":
        return _determine_benchmark_regime(record)
    return _determine_generalized_regime(record)


def _module_enum(process_type: str) -> ModuleType:
    if process_type == "NF":
        return ModuleType.NF
    if process_type == "HRRO":
        return getattr(ModuleType, "HRRO", ModuleType.RO)
    return ModuleType.RO


def _canonical_ions(record: dict) -> Dict[str, float]:
    raw = record.get("feed_ions") if isinstance(record.get("feed_ions"), dict) else {}
    cleaned: Dict[str, float] = {}
    aliases = {
        "NH4": "NH4", "K": "K", "NA": "Na", "MG": "Mg", "CA": "Ca", "SR": "Sr",
        "BA": "Ba", "CO3": "CO3", "HCO3": "HCO3", "NO3": "NO3", "CL": "Cl",
        "F": "F", "SO4": "SO4", "BR": "Br", "PO4": "PO4", "SIO2": "SiO2",
        "B": "B", "BORON": "B", "CO2": "CO2",
    }
    for key, value in raw.items():
        canonical = aliases.get(re.sub(r"[^A-Z0-9]", "", str(key).upper()))
        if not canonical:
            continue
        try:
            cleaned[canonical] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    if cleaned:
        return cleaned

    # Compatibility fallback for old schema-v1/v2 datasets.
    tds = max(float(record.get("feed_tds") or 1.0), 1.0)
    return {
        "Na": tds * 0.35,
        "Cl": tds * 0.55,
        "Ca": tds * 0.03,
        "Mg": tds * 0.02,
        "SO4": tds * 0.04,
        "HCO3": tds * 0.01,
    }


def _stage_process_type(model_name: str, system_process_type: str) -> str:
    if system_process_type == "HRRO":
        return "HRRO"
    return determine_module_type(model_name)


def _flow_factor_for_stage(pass_record: dict, stage_index: int, record: dict) -> float:
    factors = pass_record.get("flow_factors") if isinstance(pass_record.get("flow_factors"), list) else []
    if factors:
        return float(factors[min(stage_index, len(factors) - 1)])
    return float(record.get("flow_factor") or 0.85)


def _temperature_factors(model_name: str) -> Tuple[float, float]:
    key = _model_key(model_name)
    if "SW30" in key:
        return 2350.0, 4905.0
    if "NF270" in key:
        return 2640.0, 3500.0
    return 2640.0, 3500.0


def _system_targets(record: dict) -> Dict[str, Any]:
    """Return physically consistent system-level targets.

    WAVE's permeate-split report has no single system-product row.  In that
    special case, derive the product from the pass-1 branch that bypasses pass
    2 plus the pass-2 permeate.
    """
    target = {
        "pressure_bar": float(record.get("feed_pressure") or 0.0),
        "tds_mgL": float(record.get("permeate_tds") or 0.0),
        "recovery_pct": float(record.get("system_recovery") or 0.0),
        "product_flow_m3h": None,
        "scope": "reported_system_product",
    }
    summary = record.get("summary_streams") if isinstance(record.get("summary_streams"), dict) else {}
    for label, stream in summary.items():
        if "NET PRODUCT" in str(label).upper() and isinstance(stream, dict):
            target["tds_mgL"] = float(stream.get("tds_mgL") or target["tds_mgL"])
            target["product_flow_m3h"] = float(stream.get("flow_m3h") or 0.0)
            break

    passes = record.get("passes") if isinstance(record.get("passes"), list) else []
    has_system_product = bool((record.get("data_quality") or {}).get("has_system_product", True))
    if len(passes) >= 2 and not has_system_product:
        p1, p2 = passes[0], passes[1]
        p1_perm = max(float(p1.get("permeate_flow_m3h") or 0.0), 0.0)
        p2_feed = max(float(p2.get("feed_flow_m3h") or 0.0), 0.0)
        p2_perm = max(float(p2.get("permeate_flow_m3h") or 0.0), 0.0)
        branch_flow = max(p1_perm - p2_feed, 0.0)
        product_flow = branch_flow + p2_perm
        if product_flow > 1e-12:
            p1_tds = float(p1.get("permeate_tds_mgL") or 0.0)
            p2_tds = float(p2.get("permeate_tds_mgL") or 0.0)
            target["tds_mgL"] = (branch_flow * p1_tds + p2_perm * p2_tds) / product_flow
            target["product_flow_m3h"] = product_flow
            raw_feed = float(record.get("raw_feed_flow") or record.get("feed_flow") or 0.0)
            if raw_feed > 1e-12:
                target["recovery_pct"] = product_flow / raw_feed * 100.0
            target["scope"] = "derived_permeate_split_product"
    return target


def _pass_feed_fraction(passes: List[dict], pass_position: int) -> float:
    if pass_position <= 0 or pass_position >= len(passes):
        return 1.0
    upstream_perm = float(passes[pass_position - 1].get("permeate_flow_m3h") or 0.0)
    downstream_feed = float(passes[pass_position].get("feed_flow_m3h") or 0.0)
    if upstream_perm <= 1e-12:
        return 1.0
    return min(1.0, max(0.0, downstream_feed / upstream_perm))


def _build_hrro_stage(
    model_name: str,
    record: dict,
    params: Sequence[float],
    regime: str,
) -> StageConfig:
    a_corr, b_corr, dp_multiplier, cp_adj, b_salinity_slope = [float(value) for value in params]
    a_base, b_base, area = _base_membrane_values(model_name, "HRRO")
    temp_a, temp_b = _temperature_factors(model_name)
    ccro = record.get("ccro") if isinstance(record.get("ccro"), dict) else {}
    vessels = int(record.get("pressure_vessels") or 10)
    cc_net_per_pv = float(ccro.get("cc_net_feed_flow_m3h_per_pv") or 0.0)
    recirc_flow = cc_net_per_pv * vessels if cc_net_per_pv > 0.0 else float(record.get("recirc_flow_m3h") or 120.0)
    return StageConfig(
        stage_idx=1,
        pass_idx=1,
        stage_label="CCRO",
        module_type=_module_enum("HRRO"),
        membrane_model=model_name,
        vessel_count=vessels,
        elements_per_vessel=int(record.get("elements_per_vessel") or 6),
        elements=int(record.get("number_of_elements") or 60),
        membrane_area_m2=area,
        membrane_A_lmh_bar=a_base,
        membrane_B_lmh=b_base,
        temp_corr_factor_A=temp_a,
        temp_corr_factor_B=temp_b,
        flow_factor=float(record.get("flow_factor") or 0.85),
        fouling_factor=1.0,
        B_fouling_factor=float(record.get("B_fouling_factor") or 1.0),
        recovery_target_pct=float(record.get("system_recovery") or 90.0),
        feed_flow_m3h=float(record.get("feed_flow") or 100.0),
        recirc_flow_m3h=recirc_flow,
        loop_volume_m3=float(ccro.get("cc_system_volume_m3") or record.get("loop_volume_m3") or 1.36),
        max_minutes=float(ccro.get("complete_cycle_duration_min") or record.get("max_minutes") or 60.0),
        pf_feed_ratio_pct=float(ccro.get("pf_feed_ratio_pct") or 110.0),
        pf_recovery_pct=float(ccro.get("pf_recovery_pct") or 10.0),
        ccro_recovery_pct=float(ccro.get("cc_recovery_pct") or 0.0),
        max_tmp_bar=max(30.0, float(record.get("feed_pressure_max") or record.get("feed_pressure") or 120.0) * 1.5),
        A_correction_factor=a_corr,
        B_correction_factor=b_corr,
        b_salinity_slope=b_salinity_slope,
        hrro_B_sal_slope=b_salinity_slope,
        dp_per_elem_bar=DP_REF_BAR_PER_ELEMENT * dp_multiplier,
        dp_module_bar=DP_REF_BAR_PER_ELEMENT * dp_multiplier,
        dp_correlation_multiplier=dp_multiplier,
        cp_tuning_factor=cp_adj,
        cp_adjustment_factor=cp_adj,
        source_file=str(record.get("source_file", "")),
        tuning_regime=regime,
        tuning_locked=True,
        wave_target_pressure_bar=float(record.get("feed_pressure") or 0.0),
        wave_target_permeate_tds=float(record.get("permeate_tds") or 0.0),
        wave_target_permeate_flow=float(record.get("feed_flow") or 0.0) * float(record.get("system_recovery") or 0.0) / 100.0,
    )


def _build_stage_sequence(
    system_model: str,
    system_process_type: str,
    record: dict,
    params: Sequence[float],
    regime: str,
) -> List[StageConfig]:
    if system_process_type == "HRRO" or str(record.get("report_type", "")).upper() == "CCRO":
        return [_build_hrro_stage(system_model, record, params, regime)]

    a_corr, b_corr, dp_multiplier, cp_adj, b_salinity_slope = [float(value) for value in params]
    passes = record.get("passes") if isinstance(record.get("passes"), list) else []
    if not passes:
        passes = [{"pass_idx": 1, "stages": record.get("stages") or []}]

    sequence: List[StageConfig] = []
    global_stage_idx = 0
    source_upper = str(record.get("source_file", "")).upper()
    has_system_product = bool((record.get("data_quality") or {}).get("has_system_product", True))

    for pass_position, pass_record in enumerate(passes):
        pass_idx = int(pass_record.get("pass_idx") or pass_position + 1)
        stages = pass_record.get("stages") if isinstance(pass_record.get("stages"), list) else []
        if not stages:
            pass_feed = float(pass_record.get("feed_flow_m3h") or record.get("feed_flow") or 100.0)
            pass_perm = float(pass_record.get("permeate_flow_m3h") or pass_feed * float(pass_record.get("recovery_pct") or record.get("system_recovery") or 75.0) / 100.0)
            stages = [{
                "stage_idx": 1,
                "stage_label": "1",
                "membrane_model": system_model,
                "pressure_vessels": int(record.get("pressure_vessels") or 10),
                "elements_per_vessel": int(record.get("elements_per_vessel") or 6),
                "feed_flow_m3h": pass_feed,
                "permeate_flow_m3h": pass_perm,
                "feed_pressure_bar": float(pass_record.get("feed_pressure_bar") or record.get("feed_pressure") or 0.0),
                "permeate_tds_mgL": float(pass_record.get("permeate_tds_mgL") or 0.0),
                "pressure_drop_bar": 0.0,
                "boost_pressure_bar": 0.0,
            }]

        route_fraction = _pass_feed_fraction(passes, pass_position)
        split_remainder = (
            pass_position > 0
            and route_fraction < 1.0 - 1e-9
            and (not has_system_product or "PERMEATESPLIT" in source_upper)
        )

        for local_index, stage in enumerate(stages):
            global_stage_idx += 1
            stage_model = normalize_model_name(stage.get("membrane_model") or system_model)
            stage_type = _stage_process_type(stage_model, system_process_type)
            a_base, b_base, area = _base_membrane_values(stage_model, stage_type)
            temp_a, temp_b = _temperature_factors(stage_model)
            stage_feed = max(float(stage.get("feed_flow_m3h") or pass_record.get("feed_flow_m3h") or 0.0), 1e-9)
            stage_perm = max(float(stage.get("permeate_flow_m3h") or 0.0), 0.0)
            stage_recovery = min(99.5, max(0.0, stage_perm / stage_feed * 100.0))
            vessel_count = int(stage.get("pressure_vessels") or record.get("pressure_vessels") or 10)
            epv = int(stage.get("elements_per_vessel") or record.get("elements_per_vessel") or 6)
            flow_factor = _flow_factor_for_stage(pass_record, local_index, record)

            sequence.append(StageConfig(
                stage_idx=global_stage_idx,
                pass_idx=pass_idx,
                stage_label=str(stage.get("stage_label") or stage.get("stage_idx") or local_index + 1),
                module_type=_module_enum(stage_type),
                membrane_model=stage_model,
                vessel_count=vessel_count,
                elements_per_vessel=epv,
                elements=vessel_count * epv,
                membrane_area_m2=area,
                membrane_A_lmh_bar=a_base,
                membrane_B_lmh=b_base,
                temp_corr_factor_A=temp_a,
                temp_corr_factor_B=temp_b,
                flow_factor=flow_factor,
                fouling_factor=1.0,
                B_fouling_factor=float(record.get("B_fouling_factor") or 1.0),
                recovery_target_pct=stage_recovery,
                feed_flow_m3h=stage_feed,
                isbp_pressure_bar=float(stage.get("boost_pressure_bar") or 0.0),
                pass_feed_fraction=(route_fraction if local_index == 0 else 1.0),
                split_remainder_to_product=(split_remainder if local_index == 0 else False),
                A_correction_factor=a_corr,
                B_correction_factor=b_corr,
                b_salinity_slope=b_salinity_slope,
                dp_correlation_enabled=True,
                dp_correlation_multiplier=dp_multiplier,
                dp_per_elem_bar=DP_REF_BAR_PER_ELEMENT * dp_multiplier,
                dp_module_bar=DP_REF_BAR_PER_ELEMENT * dp_multiplier,
                cp_tuning_factor=cp_adj,
                cp_adjustment_factor=cp_adj,
                source_file=str(record.get("source_file", "")),
                tuning_regime=regime,
                tuning_locked=True,
                wave_target_pressure_bar=float(stage.get("feed_pressure_bar") or 0.0),
                wave_target_pressure_drop_bar=float(stage.get("pressure_drop_bar") or 0.0),
                wave_target_permeate_tds=float(stage.get("permeate_tds_mgL") or 0.0),
                wave_target_permeate_flow=float(stage.get("permeate_flow_m3h") or 0.0),
            ))
    return sequence


def _build_request(
    model_name: str,
    process_type: str,
    record: dict,
    params: Sequence[float],
    simulation_id: str,
) -> SimulationRequest:
    feed_tds = max(float(record.get("feed_tds") or 1.0), 1.0)
    feed = FeedInput(
        flow_m3h=float(record.get("feed_flow") or 100.0),
        tds_mgL=feed_tds,
        ions=IonCompositionInput(**_canonical_ions(record)),
        temperature_C=float(record.get("temperature") or 25.0),
        ph=float(record.get("feed_ph") or 7.5),
        dosing=DosingControl(
            pass2_target_ph=(
                float(record["pass2_target_ph"])
                if record.get("pass2_target_ph") is not None
                else None
            )
        ),
    )
    regime = determine_topology_regime(record)
    stages = _build_stage_sequence(model_name, process_type, record, params, regime)
    return SimulationRequest(
        simulation_id=simulation_id,
        feed=feed,
        stages=stages,
        opex_config=OpexConfig(),
    )


def _relative_error(predicted: float, target: float, floor: float) -> float:
    return abs(float(predicted) - float(target)) / max(abs(float(target)), floor)


def _threshold_loss(error: float, threshold: float = TARGET_ERROR) -> float:
    excess = max(0.0, error - threshold)
    return error + 20.0 * excess * excess


def _diagnostics(output: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for metric in getattr(output, "stage_metrics", None) or []:
        chemistry = getattr(metric, "chemistry", None)
        model = chemistry.get("model", {}) if isinstance(chemistry, dict) else {}
        if not isinstance(model, dict):
            continue
        result["pressure_limited"] = bool(result.get("pressure_limited", False) or model.get("pressure_limited", False))
        result["target_flow_achieved"] = bool(result.get("target_flow_achieved", True) and model.get("target_flow_achieved", True))
        result["flow_error_fraction"] = max(float(result.get("flow_error_fraction", 0.0)), float(model.get("flow_error_fraction") or 0.0))
    return result


def _simulate_case(
    engine: SimulationEngine,
    process_type: str,
    model_name: str,
    record: dict,
    params: Sequence[float],
    simulation_id: str,
):
    request = _build_request(model_name, process_type, record, params, simulation_id)
    output = engine.run(request)
    if not output or not output.stage_metrics:
        raise RuntimeError("Simulation returned no stage metrics")
    return output, request


def _case_errors(output: Any, record: dict) -> Tuple[float, float, float, Dict[str, Any]]:
    stage_metrics = output.stage_metrics or []
    sim_pressure = float(getattr(stage_metrics[0], "p_in_bar", 0.0))
    sim_tds = float(getattr(output.kpi, "prod_tds", 0.0) or 0.0)
    sim_recovery = float(getattr(output.kpi, "recovery_pct", 0.0) or 0.0)
    target = _system_targets(record)

    return (
        _relative_error(sim_pressure, target["pressure_bar"], 0.1),
        _relative_error(sim_tds, target["tds_mgL"], TDS_ERROR_FLOOR_MGL),
        _relative_error(sim_recovery, target["recovery_pct"], 1.0),
        {**_diagnostics(output), "targets": target},
    )


def _stage_supervision_loss(output: Any, request: SimulationRequest) -> float:
    losses: List[float] = []
    for metric, config in zip(output.stage_metrics or [], request.stages or []):
        target_p = float(getattr(config, "wave_target_pressure_bar", 0.0) or 0.0)
        target_dp = float(getattr(config, "wave_target_pressure_drop_bar", 0.0) or 0.0)
        target_cp = float(getattr(config, "wave_target_permeate_tds", 0.0) or 0.0)
        target_qp = float(getattr(config, "wave_target_permeate_flow", 0.0) or 0.0)
        if target_p > 0.0:
            losses.append(0.12 * _threshold_loss(_relative_error(metric.p_in_bar, target_p, 0.5)))
        if target_dp > 0.0:
            sim_dp = max(0.0, float(metric.p_in_bar) - float(metric.p_out_bar))
            losses.append(0.10 * _threshold_loss(_relative_error(sim_dp, target_dp, 0.1)))
        if target_cp > 0.0:
            losses.append(0.16 * _threshold_loss(_relative_error(metric.Cp, target_cp, TDS_ERROR_FLOOR_MGL)))
        if target_qp > 0.0:
            losses.append(0.08 * _threshold_loss(_relative_error(metric.Qp, target_qp, 0.1)))
    return float(np.mean(losses)) if losses else 0.0


def _regularization(x: Sequence[float]) -> float:
    a, b, dp_multiplier, cp, b_slope = [float(value) for value in x]
    return 0.01 * (
        math.log(max(a, 1e-9)) ** 2
        + 0.5 * math.log(max(b, 1e-9)) ** 2
        + 0.35 * math.log(max(dp_multiplier, 1e-9)) ** 2
        + 0.5 * math.log(max(cp, 1e-9)) ** 2
        + 0.04 * b_slope**2
    )


def optimize_group(
    engine: SimulationEngine,
    model_name: str,
    process_type: str,
    records: List[dict],
):
    bounds = [(0.1, 12.0), (0.01, 15.0), (0.10, 5.0), (0.2, 6.0), (0.0, 10.0)]
    starts = [
        [1.0, 1.0, 1.0, 1.0, 0.5],
        [0.7, 2.0, 0.8, 1.5, 1.5],
        [1.5, 0.5, 1.5, 0.7, 3.0],
    ]
    evaluations = 0

    def objective(x):
        nonlocal evaluations
        evaluations += 1
        losses = []
        for record in records:
            try:
                output, request = _simulate_case(
                    engine, process_type, model_name, record, x, f"opt-{evaluations}"
                )
                err_p, err_tds, err_rec, diag = _case_errors(output, record)
                loss = (
                    _threshold_loss(err_p)
                    + 1.7 * _threshold_loss(err_tds)
                    + 2.2 * _threshold_loss(err_rec)
                    + _stage_supervision_loss(output, request)
                    + 5.0 * float(diag.get("flow_error_fraction") or 0.0)
                    + (10.0 if diag.get("pressure_limited") else 0.0)
                )
            except Exception:
                loss = FAILED_CASE_PENALTY
            losses.append(loss)
        values = np.asarray(losses, dtype=float)
        if not len(values):
            return 1e9
        return float(
            np.mean(values)
            + 0.40 * np.percentile(values, 90)
            + 0.20 * np.max(values)
            + _regularization(x)
        )

    # Bounded coordinate refinement is substantially faster and more stable
    # than a five-dimensional Powell search for the rounded engine outputs.
    x = np.asarray(starts[0], dtype=float)
    best_x = x.copy()
    best_fun = objective(best_x)
    sweeps = 1 if process_type == "HRRO" else (2 if len(records) <= 2 else 3)
    order = [0, 2, 1, 4, 3]
    if process_type == "HRRO":
        order = [0, 1, 3, 4]

    for _ in range(sweeps):
        for coordinate in order:
            lo, hi = bounds[coordinate]

            def scalar_objective(value: float) -> float:
                candidate = x.copy()
                candidate[coordinate] = value
                return objective(candidate)

            scalar = minimize_scalar(
                scalar_objective,
                method="bounded",
                bounds=(lo, hi),
                options={"maxiter": 18, "xatol": 2e-3},
            )
            x[coordinate] = float(scalar.x)
            current_fun = objective(x)
            if current_fun < best_fun:
                best_fun = current_fun
                best_x = x.copy()

    # A short joint polish captures the remaining A/dP and B/CP interaction.
    polish_budget = 45 if process_type == "HRRO" else (90 if len(records) <= 1 else 120)
    polished = minimize(
        objective,
        x0=best_x,
        method="Powell",
        bounds=bounds,
        options={
            "maxiter": 30,
            "maxfev": polish_budget,
            "xtol": 5e-4,
            "ftol": 5e-5,
            "disp": False,
        },
    )
    if float(polished.fun) < best_fun:
        best_x = np.asarray(polished.x, dtype=float)
        best_fun = float(polished.fun)

    # The inverse-flow solvers make A primarily identifiable from feed pressure
    # and B primarily identifiable from product TDS.  A final one-dimensional
    # refinement prevents a stage-level secondary objective from pulling the
    # system pressure away from its WAVE target.
    for _ in range(2):
        def pressure_objective(a_value: float) -> float:
            candidate = best_x.copy()
            candidate[0] = a_value
            values = []
            for record in records:
                try:
                    output, _ = _simulate_case(
                        engine, process_type, model_name, record, candidate, "primary-pressure"
                    )
                    err_p, _, _, _ = _case_errors(output, record)
                    values.append(err_p * err_p)
                except Exception:
                    values.append(FAILED_CASE_PENALTY)
            return float(np.mean(values))

        p_refine = minimize_scalar(
            pressure_objective,
            method="bounded",
            bounds=bounds[0],
            options={"maxiter": 45, "xatol": 1e-4},
        )
        best_x[0] = float(p_refine.x)

        def quality_objective(b_value: float) -> float:
            candidate = best_x.copy()
            candidate[1] = b_value
            values = []
            for record in records:
                try:
                    output, _ = _simulate_case(
                        engine, process_type, model_name, record, candidate, "primary-quality"
                    )
                    _, err_tds, err_rec, _ = _case_errors(output, record)
                    values.append(err_tds * err_tds + 0.2 * err_rec * err_rec)
                except Exception:
                    values.append(FAILED_CASE_PENALTY)
            return float(np.mean(values))

        q_refine = minimize_scalar(
            quality_objective,
            method="bounded",
            bounds=bounds[1],
            options={"maxiter": 45, "xatol": 1e-4},
        )
        best_x[1] = float(q_refine.x)

    best_fun = objective(best_x)
    return OptimizeResult(
        x=best_x,
        fun=best_fun,
        success=True,
        message="Coordinate and primary-target refinement completed.",
    ), evaluations


def run_pipeline(
    dataset_path: Path = DATASET_PATH,
    output_path: Path = OUTPUT_PATH,
    regime_policy: str = "generalized",
) -> Dict[str, Any]:
    global ACTIVE_REGIME_POLICY
    normalized_policy = str(regime_policy or "generalized").strip().lower()
    if normalized_policy not in {"generalized", "benchmark"}:
        raise ValueError(f"Unsupported regime policy: {regime_policy}")
    ACTIVE_REGIME_POLICY = normalized_policy

    logger.info("=" * 100)
    logger.info(" AquaNova WAVE V4 split/dP/salinity-aware calibration [%s]", ACTIVE_REGIME_POLICY)
    if ACTIVE_REGIME_POLICY == "benchmark":
        logger.warning(" Benchmark policy is diagnostic only and may contain singleton groups.")
    logger.info("=" * 100)
    started = time.time()

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    grouped: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    skipped_legacy = 0
    for record in data:
        model_name, process_type = resolve_case_identity(record)
        if not model_name or re.search(r"SFP|INTEGRAFLUX|UF|MF", model_name.upper()):
            continue
        if int(record.get("schema_version") or 1) < 3:
            skipped_legacy += 1
        regime = determine_topology_regime(record)
        grouped[(model_name, process_type, regime)].append(record)

    engine = SimulationEngine()
    all_cases: List[Dict[str, Any]] = []
    groups_payload: Dict[str, Any] = {}

    for (model_name, process_type, regime), records in grouped.items():
        key = f"{model_name}|{process_type}|{regime}"
        logger.info("\n[%s] cases=%d", key, len(records))
        result, evaluations = optimize_group(engine, model_name, process_type, records)
        params = {
            "A_correction_factor": float(result.x[0]),
            "B_correction_factor": float(result.x[1]),
            "dp_correlation_multiplier": float(result.x[2]),
            "dp_per_elem_bar": float(DP_REF_BAR_PER_ELEMENT * result.x[2]),
            "cp_adjustment_factor": float(result.x[3]),
            "b_salinity_slope": float(result.x[4]),
        }
        logger.info(
            "  best: A=%.4f, B=%.4f, dP×=%.4f, CP=%.4f, Bsal=%.4f, objective=%.6f",
            params["A_correction_factor"], params["B_correction_factor"],
            params["dp_correlation_multiplier"], params["cp_adjustment_factor"],
            params["b_salinity_slope"], float(result.fun),
        )

        case_payload = []
        for index, record in enumerate(records, start=1):
            try:
                values = [params[key] for key in (
                    "A_correction_factor", "B_correction_factor",
                    "dp_correlation_multiplier", "cp_adjustment_factor",
                    "b_salinity_slope",
                )]
                output, request = _simulate_case(
                    engine, process_type, model_name, record, values, f"verify-{index}"
                )
                err_p, err_tds, err_rec, diag = _case_errors(output, record)
                targets = diag.get("targets") or _system_targets(record)
                first_metric = output.stage_metrics[0]
                case = {
                    "source_file": record.get("source_file", "Unknown"),
                    "schema_version": int(record.get("schema_version") or 1),
                    "pass_count": len(record.get("passes") or []) or 1,
                    "stage_count": len(request.stages),
                    "has_actual_ion_composition": bool(record.get("feed_ions")),
                    "target_scope": targets.get("scope"),
                    "target_pressure_bar": float(targets.get("pressure_bar") or 0.0),
                    "sim_pressure_bar": float(getattr(first_metric, "p_in_bar", 0.0)),
                    "pressure_error_pct": err_p * 100.0,
                    "target_tds_mgL": float(targets.get("tds_mgL") or 0.0),
                    "sim_tds_mgL": float(output.kpi.prod_tds or 0.0),
                    "tds_error_pct": err_tds * 100.0,
                    "target_recovery_pct": float(targets.get("recovery_pct") or 0.0),
                    "sim_recovery_pct": float(output.kpi.recovery_pct or 0.0),
                    "recovery_error_pct": err_rec * 100.0,
                    "target_flow_achieved": bool(diag.get("target_flow_achieved", True)),
                    "pressure_limited": bool(diag.get("pressure_limited", False)),
                    "flow_error_fraction": float(diag.get("flow_error_fraction") or 0.0),
                }
            except Exception as exc:
                case = {
                    "source_file": record.get("source_file", "Unknown"),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            case_payload.append(case)
            all_cases.append(case)
            if "error" in case:
                logger.info("  FAIL %-44s %s", case["source_file"], case["error"])
            else:
                logger.info(
                    "  %-44s P %7.2f%% | TDS %7.2f%% | Rec %7.2f%% | %dp/%ds",
                    str(case["source_file"])[:44], case["pressure_error_pct"],
                    case["tds_error_pct"], case["recovery_error_pct"],
                    case["pass_count"], case["stage_count"],
                )

        groups_payload[key] = {
            "model_name": model_name,
            "process_type": process_type,
            "regime": regime,
            "case_count": len(records),
            "optimizer_success": bool(result.success),
            "optimizer_message": str(result.message),
            "objective": float(result.fun),
            "evaluations": evaluations,
            "parameters": params,
            "calibration_warning": (
                "Insufficient cases for independent validation" if len(records) < 3 else None
            ),
            "cases": case_payload,
        }

    valid = [item for item in all_cases if "error" not in item]
    failed = [item for item in all_cases if "error" in item]
    group_sizes = [len(records) for records in grouped.values()]
    summary = {
        "total_cases": len(all_cases),
        "group_count": len(group_sizes),
        "singleton_group_count": sum(size == 1 for size in group_sizes),
        "multi_case_group_count": sum(size > 1 for size in group_sizes),
        "valid_cases": len(valid),
        "failed_cases": len(failed),
        "legacy_schema_cases": skipped_legacy,
        "schema_v3_cases": sum(item.get("schema_version") == 3 for item in valid),
        "mean_pressure_error_pct": float(np.mean([item["pressure_error_pct"] for item in valid])) if valid else None,
        "mean_tds_error_pct": float(np.mean([item["tds_error_pct"] for item in valid])) if valid else None,
        "mean_recovery_error_pct": float(np.mean([item["recovery_error_pct"] for item in valid])) if valid else None,
        "pressure_cases_under_5pct": sum(item["pressure_error_pct"] <= 5.0 for item in valid),
        "tds_cases_under_5pct": sum(item["tds_error_pct"] <= 5.0 for item in valid),
        "both_pressure_tds_under_5pct": sum(
            item["pressure_error_pct"] <= 5.0 and item["tds_error_pct"] <= 5.0 for item in valid
        ),
        "pressure_limited_cases": sum(bool(item["pressure_limited"]) for item in valid),
        "elapsed_seconds": time.time() - started,
    }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "target_error_pct": TARGET_ERROR * 100.0,
        "calibration_schema": 4,
        "regime_policy": ACTIVE_REGIME_POLICY,
        "runtime_compatible": ACTIVE_REGIME_POLICY == "generalized",
        "features": ["pass_split", "dynamic_dp", "salinity_dependent_B", "stage_supervision"],
        "summary": summary,
        "groups": groups_payload,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("\n%s", "=" * 100)
    logger.info(json.dumps(summary, ensure_ascii=False, indent=2))
    logger.info("Saved: %s", output_path)
    logger.info("=" * 100)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AquaNova WAVE V4 topology/chemistry-aware calibration"
    )
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--regime-policy",
        choices=("generalized", "benchmark"),
        default="generalized",
        help="generalized is production-safe; benchmark is diagnostic and may overfit",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to production or benchmark-specific filename.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    output = args.output
    if output is None:
        output = (
            OUTPUT_PATH
            if args.regime_policy == "generalized"
            else Path("./.data/autotuner_regime_constants.benchmark.json")
        )
    run_pipeline(args.dataset, output, args.regime_policy)
