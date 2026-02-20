# app/schemas/simulation.py
# =============================================================================
# AquaNova Simulation Schemas (Pydantic v2)
#
# Key Policies:
# - Recursively drop explicit "None" keys to ensure Pydantic defaults are applied.
# - Ensure membrane area parameters are always populated to prevent calculation errors.
# - Maintain backward compatibility with broad alias support.
# - [WAVE MATCHING] Expanded to hold detailed Chemistry, Mass Balance, and Warnings
# - [CLEANUP] Removed all Legacy Excel-engine parameters. Pure Python physics only.
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Literal
from uuid import UUID

from pydantic import Field, AliasChoices, model_validator

from .common import AppBaseModel, ModuleType, FeedWaterType


# =============================================================================
# Helpers: Treat explicit null as "missing"
# =============================================================================
def _drop_none_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if v is None:
                continue
            out[k] = _drop_none_recursive(v)
        return out
    if isinstance(obj, list):
        return [_drop_none_recursive(v) for v in obj]
    return obj


def _norm_upper(s: Any) -> Any:
    if isinstance(s, str):
        t = s.strip()
        return t.upper() if t else s
    return s


# =============================================================================
# Default Constants (Industry Standards)
# =============================================================================
# 🛑 WAVE와 완벽히 일치하는 40.9로 고정!
DEFAULT_AREA_M2_PER_ELEMENT_8IN = 40.9
DEFAULT_AREA_M2_PER_ELEMENT_4IN = 20.0


def _default_area_by_inch(element_inch: int) -> float:
    inch = int(element_inch or 8)
    if inch <= 4:
        return float(DEFAULT_AREA_M2_PER_ELEMENT_4IN)
    return float(DEFAULT_AREA_M2_PER_ELEMENT_8IN)


# =============================================================================
# Sub-Models: Physics & Geometry
# =============================================================================
class HRROMassTransferIn(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    crossflow_velocity_m_s: Optional[float] = None
    recirc_flow_m3h: Optional[float] = None

    feed_channel_area_m2: Optional[float] = Field(
        0.015, description="Cross-sectional flow area per element"
    )

    rho_kg_m3: float = 998.0
    mu_pa_s: float = 0.001

    diffusivity_m2_s: float = 1.5e-9
    cp_exp_max: float = 5.0
    cp_rel_tol: float = 1e-4
    cp_abs_tol_lmh: float = 1e-3
    cp_relax: float = 0.5
    cp_max_iter: int = 30

    k_mt_multiplier: Optional[float] = None
    k_mt_min_m_s: Optional[float] = None
    segments_total: Optional[int] = None


class HRROSpacerIn(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    thickness_mm: float = Field(0.76, description="Spacer thickness (mil converted)")
    filament_diameter_mm: float = Field(0.35, description="Mesh filament diameter")
    mesh_size_mm: Optional[float] = None

    voidage: Optional[float] = Field(0.85, description="Porosity (Void fraction)")
    voidage_fallback: float = 0.85
    hydraulic_diameter_m: Optional[float] = None


class IonCompositionInput(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    # Cations (WAVE Order)
    NH4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("NH4", "nh4")
    )
    K: Optional[float] = Field(default=None, validation_alias=AliasChoices("K", "k"))
    Na: Optional[float] = Field(default=None, validation_alias=AliasChoices("Na", "na"))
    Mg: Optional[float] = Field(default=None, validation_alias=AliasChoices("Mg", "mg"))
    Ca: Optional[float] = Field(default=None, validation_alias=AliasChoices("Ca", "ca"))
    Sr: Optional[float] = Field(default=None, validation_alias=AliasChoices("Sr", "sr"))
    Ba: Optional[float] = Field(default=None, validation_alias=AliasChoices("Ba", "ba"))

    # Non-WAVE default cations (Kept for compatibility)
    Fe: Optional[float] = Field(default=None, validation_alias=AliasChoices("Fe", "fe"))
    Mn: Optional[float] = Field(default=None, validation_alias=AliasChoices("Mn", "mn"))
    Al: Optional[float] = Field(default=None, validation_alias=AliasChoices("Al", "al"))

    # Anions (WAVE Order)
    CO3: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("CO3", "co3")
    )
    HCO3: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("HCO3", "hco3")
    )
    NO3: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("NO3", "no3")
    )
    Cl: Optional[float] = Field(default=None, validation_alias=AliasChoices("Cl", "cl"))
    F: Optional[float] = Field(default=None, validation_alias=AliasChoices("F", "f"))
    SO4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("SO4", "so4")
    )
    Br: Optional[float] = Field(default=None, validation_alias=AliasChoices("Br", "br"))
    PO4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("PO4", "po4")
    )

    # Neutrals (WAVE Order)
    SiO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("SiO2", "sio2")
    )
    B: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("B", "boron")
    )
    CO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("CO2", "co2")
    )

    # Legacy
    HCO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("HCO2", "hco2")
    )
    NO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("NO2", "no2")
    )


# =============================================================================
# Main Input Models
# =============================================================================
class StageConfig(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = _drop_none_recursive(data)

        mt = d.get("module_type", None) or d.get("type", None)
        if isinstance(mt, str):
            d["module_type"] = _norm_upper(mt)
        return d

    stage_id: Optional[str] = None
    module_type: ModuleType = Field(
        default=ModuleType.RO, validation_alias=AliasChoices("type", "module_type")
    )

    element_inch: int = Field(default=8, ge=4, le=16)

    # 🛑 [WAVE 일치화] 하드웨어 그릇 크기 동기화
    vessel_count: int = Field(default=10, ge=1)
    elements_per_vessel: int = Field(default=5, ge=1)
    elements: int = Field(
        default=50,
        ge=1,
        validation_alias=AliasChoices("elements", "num_elements", "total_elements"),
    )

    membrane_model: Optional[str] = Field(default="FilmTec SOAR 6000i")
    membrane_area_m2: Optional[float] = Field(default=40.9, ge=0)
    membrane_A_lmh_bar: Optional[float] = Field(default=6.35)
    membrane_B_lmh: Optional[float] = Field(default=0.058)
    membrane_salt_rejection_pct: Optional[float] = Field(default=99.5)

    flow_factor: float = Field(default=0.85, ge=0.1, le=2.0)

    # [WAVE 일치화] 새로 추가된 핵심 파라미터 3종
    temp_mode: Literal["Minimum", "Design", "Maximum"] = Field(
        default="Design", description="선택된 온도 시나리오"
    )
    bypass_flow_m3h: float = Field(
        default=0.0, ge=0, description="RO를 거치지 않는 바이패스 유량"
    )
    pre_stage_dp_bar: float = Field(
        default=0.31, ge=0, description="스테이지 진입 전 배관 압력 손실"
    )

    feed_flow_m3h: Optional[float] = Field(
        default=None, ge=0, validation_alias=AliasChoices("feed_flow_m3h", "q_raw_m3h")
    )
    recovery_target_pct: Optional[float] = Field(default=90.0, ge=0, le=100)
    pressure_bar: Optional[float] = Field(default=None, ge=0)
    dp_module_bar: Optional[float] = Field(0.2, ge=0)
    permeate_back_pressure_bar: float = Field(default=0.0, ge=0)
    burst_pressure_limit_bar: float = Field(default=83.0, ge=0)
    flux_lmh: Optional[float] = None

    loop_volume_m3: Optional[float] = Field(default=2.0)
    recirc_flow_m3h: Optional[float] = Field(default=120.0, ge=0)

    max_minutes: float = Field(default=60.0)
    stop_recovery_pct: Optional[float] = Field(default=90.0)
    stop_permeate_tds_mgL: Optional[float] = None

    # 🛑 [WAVE 일치화] 농축수 순환 유량 기본값(4.33) 세팅
    cc_recycle_m3h_per_pv: Optional[float] = Field(
        default=4.33,
        ge=0,
        validation_alias=AliasChoices("cc_recycle_m3h_per_pv", "cc_recycle_m3h"),
    )

    spacer: Optional[HRROSpacerIn] = None
    mass_transfer: Optional[HRROMassTransferIn] = None
    chemistry: Optional[Dict[str, Any]] = None

    hrro_pressure_limit_bar: Optional[float] = None
    hrro_elem_length_m: Optional[float] = 1.0
    hrro_spacer_friction_multiplier: Optional[float] = 5.0
    hrro_A_mu_exp: Optional[float] = 0.70
    hrro_B_mu_exp: Optional[float] = 0.30
    hrro_B_sal_slope: Optional[float] = 0.25
    hrro_A_compaction_k: Optional[float] = 0.003
    hrro_num_segments: int = 1
    hrro_k_mt_multiplier: Optional[float] = 0.5
    hrro_k_mt_min_m_s: Optional[float] = 0.0

    pump_eff: Optional[float] = Field(default=0.80, ge=0, le=1)
    filtration_cycle_min: Optional[float] = 30.0
    backwash_duration_sec: Optional[float] = 60.0
    backwash_flux_multiplier: Optional[float] = 1.5
    backwash_flux_lmh: Optional[float] = None

    membrane_area_m2_per_element: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices(
            "membrane_area_m2_per_element", "area_m2_per_element"
        ),
    )

    pf_feed_ratio_pct: float = Field(default=110.0, ge=0)
    pf_recovery_pct: float = Field(default=10.0, ge=0)
    ccro_recovery_pct: Optional[float] = None

    @model_validator(mode="after")
    def _apply_defaults_and_derive(self):
        fields_set = getattr(self, "model_fields_set", set())
        if "elements" not in fields_set:
            vc = getattr(self, "vessel_count", 10)
            epv = getattr(self, "elements_per_vessel", 5)
            self.elements = int(vc) * int(epv)

        inch = getattr(self, "element_inch", 8)
        default_area = _default_area_by_inch(inch)
        m_area = getattr(self, "membrane_area_m2", None)
        if m_area is None or float(m_area) <= 0.0:
            self.membrane_area_m2 = float(default_area)

        if getattr(self, "module_type", None) == ModuleType.HRRO:
            per_el = getattr(self, "membrane_area_m2_per_element", None)
            if per_el is None or float(per_el) <= 0.0:
                self.membrane_area_m2_per_element = self.membrane_area_m2
            if getattr(self, "membrane_area_m2", None) is None:
                self.membrane_area_m2 = float(self.membrane_area_m2_per_element)

        return self


class FeedInput(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    # 🛑 [WAVE 일치화] 유입 유량 기본값 세팅
    flow_m3h: float = Field(default=100.0, ge=0, description="Feed Flow Rate")
    tds_mgL: float = Field(default=0.0, ge=0, description="Total Dissolved Solids")

    # WAVE Temperature Model
    temperature_C: float = Field(
        default=25.0, ge=0, le=100, description="Design Temperature"
    )
    temp_min_C: Optional[float] = Field(
        default=None, ge=0, le=100, description="Minimum Temperature"
    )
    temp_max_C: Optional[float] = Field(
        default=None, ge=0, le=100, description="Maximum Temperature"
    )

    ph: float = Field(default=7.0, ge=0, le=14)
    pressure_bar: Optional[float] = Field(default=0.0, ge=0)

    # WAVE Solid & Organic Content
    water_type: Optional[FeedWaterType] = None
    water_subtype: Optional[str] = None
    turbidity_ntu: Optional[float] = None
    tss_mgL: Optional[float] = None
    sdi15: Optional[float] = None
    toc_mgL: Optional[float] = None

    chemistry: Optional[Dict[str, Any]] = None


class WaterChemistryInput(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    alkalinity_mgL_as_CaCO3: Optional[float] = None
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None
    sulfate_mgL: Optional[float] = None
    barium_mgL: Optional[float] = None
    strontium_mgL: Optional[float] = None
    silica_mgL_SiO2: Optional[float] = None


class SimulationRequest(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    simulation_id: str = Field(default_factory=lambda: str(UUID(int=0)))
    project_id: Union[UUID, str] = "default"
    scenario_name: str = "Simulation"

    feed: FeedInput
    stages: List[StageConfig]
    options: Dict[str, Any] = Field(default_factory=dict)

    chemistry: Optional[WaterChemistryInput] = None
    ions: Optional[IonCompositionInput] = Field(
        default=None,
        validation_alias=AliasChoices("ions", "ion_composition", "ionComposition"),
    )


ScenarioInput = SimulationRequest


# =============================================================================
# Output Models: Expanded for WAVE Reporting Parity
# =============================================================================
class SimulationWarning(AppBaseModel):
    stage: Optional[str] = None
    module_type: Optional[str] = None
    key: str
    message: str
    value: Optional[float] = None
    limit: Any = None
    unit: str = ""
    level: str = "WARN"


class TimeSeriesPoint(AppBaseModel):
    time_min: float
    recovery_pct: float
    pressure_bar: float = Field(
        validation_alias=AliasChoices("pressure_bar", "feed_pressure_bar")
    )
    tds_mgL: float = Field(validation_alias=AliasChoices("tds_mgL", "loop_tds_mgL"))
    flux_lmh: Optional[float] = None
    ndp_bar: Optional[float] = None
    permeate_flow_m3h: Optional[float] = None
    permeate_tds_mgL: Optional[float] = None
    specific_energy_kwh_m3: Optional[float] = None


class ScalingIndexOut(AppBaseModel):
    lsi: Optional[float] = None
    rsi: Optional[float] = None
    s_dsi: Optional[float] = None
    caco3_si: Optional[float] = None
    caso4_si: Optional[float] = None
    baso4_si: Optional[float] = None
    srso4_si: Optional[float] = None
    caf2_si: Optional[float] = None
    sio2_si: Optional[float] = None
    caso4_sat_pct: Optional[float] = None
    baso4_sat_pct: Optional[float] = None
    sio2_sat_pct: Optional[float] = None


class WaterChemistryOut(AppBaseModel):
    feed: Optional[ScalingIndexOut] = None
    final_brine: Optional[ScalingIndexOut] = None


class StageMetric(AppBaseModel):
    stage: int = Field(validation_alias=AliasChoices("stage", "idx", "stage_index"))
    module_type: str = Field(validation_alias=AliasChoices("module_type", "type"))

    recovery_pct: Optional[float] = None
    flux_lmh: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("flux_lmh", "jw_avg_lmh", "avg_flux_lmh"),
    )
    sec_kwhm3: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("sec_kwhm3", "sec_kwh_m3")
    )
    ndp_bar: Optional[float] = None

    p_in_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("p_in_bar", "pin", "pin_bar", "pressure_in"),
    )
    p_out_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("p_out_bar", "pout", "pout_bar", "pressure_out"),
    )
    dp_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("dp_bar", "delta_p_bar", "deltaP_bar"),
    )
    tmp_bar: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("tmp_bar", "TMP_bar", "tmp")
    )
    delta_pi_bar: Optional[float] = None

    Qf: Optional[float] = None
    Qp: Optional[float] = None
    Qc: Optional[float] = None
    gross_flow_m3h: Optional[float] = None
    net_flow_m3h: Optional[float] = None
    backwash_loss_m3h: Optional[float] = None
    net_recovery_pct: Optional[float] = None

    Cf: Optional[float] = None
    Cp: Optional[float] = None
    Cc: Optional[float] = None

    time_history: Optional[List[TimeSeriesPoint]] = None

    chemistry: Optional[Union[Dict[str, Any], ScalingIndexOut]] = None
    guidelines: Optional[Dict[str, Any]] = None
    warnings: Optional[List[SimulationWarning]] = None


class StreamOut(AppBaseModel):
    label: str
    flow_m3h: float
    tds_mgL: float
    ph: float
    pressure_bar: float
    temperature_C: Optional[float] = None
    ions: Optional[Dict[str, float]] = None


class MassBalanceOut(AppBaseModel):
    flow_error_m3h: float = 0.0
    flow_error_pct: float = 0.0
    salt_error_kgh: float = 0.0
    salt_error_pct: float = 0.0
    system_rejection_pct: Optional[float] = None
    is_balanced: bool = True


class KPIOut(AppBaseModel):
    recovery_pct: float
    flux_lmh: float
    ndp_bar: float
    sec_kwhm3: float

    batchcycle: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices(
            "batchcycle", "batch_cycle", "batchcycle_min", "filtration_cycle_min"
        ),
    )

    prod_tds: Optional[float] = None
    feed_m3h: Optional[float] = None
    permeate_m3h: Optional[float] = None

    mass_balance: Optional[MassBalanceOut] = None


class ScenarioOutput(AppBaseModel):
    scenario_id: Union[UUID, str]
    streams: List[StreamOut]
    kpi: KPIOut

    stage_metrics: Optional[List[StageMetric]] = None
    unit_labels: Optional[Dict[str, str]] = None
    chemistry: Optional[WaterChemistryOut] = None
    time_history: Optional[List[TimeSeriesPoint]] = None
    warnings: Optional[List[SimulationWarning]] = None

    schema_version: int = 2
