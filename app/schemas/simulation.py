# app/schemas/simulation.py
# =============================================================================
# AquaNova Simulation Schemas (Pydantic v2)
#
# 핵심 정책:
# - 클라이언트가 null을 보내더라도(default가 있는 필드라면) 기본값이 적용되도록
#   "None key drop"을 재귀적으로 수행한다.
# - HRRO는 membrane_area_m2_per_element를 항상 채워서 모듈에서 float(None) 방지한다.
# - 가능한 한 기존 동작/호환을 유지한다 (alias/키 후보를 넓게 유지).
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Literal, Tuple
from uuid import UUID

from pydantic import Field, AliasChoices, model_validator

from .common import AppBaseModel, ModuleType, FeedWaterType


# =============================================================================
# helpers: treat explicit null as "missing" to let Field defaults apply
# =============================================================================
def _drop_none_recursive(obj: Any) -> Any:
    """
    Recursively remove dict keys where value is None.
    - This makes Field(default=...) kick in even if client sends null.
    - Also helps nested sub-models apply their defaults.
    """
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


def _as_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _as_float(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _norm_upper(s: Any) -> Any:
    if isinstance(s, str):
        t = s.strip()
        return t.upper() if t else s
    return s


def _norm_lower(s: Any) -> Any:
    if isinstance(s, str):
        t = s.strip()
        return t.lower() if t else s
    return s


# =============================================================================
# HRRO defaults (industry-typical / conservative)
# - 8-inch element area is commonly ~37 m2 (several vendor baselines)
# - 4-inch element area is commonly ~20 m2 (rough baseline)
# =============================================================================
DEFAULT_AREA_M2_PER_ELEMENT_8IN = 37.0
DEFAULT_AREA_M2_PER_ELEMENT_4IN = 20.0


def _default_area_by_inch(element_inch: int) -> float:
    inch = int(element_inch or 8)
    if inch <= 4:
        return float(DEFAULT_AREA_M2_PER_ELEMENT_4IN)
    return float(DEFAULT_AREA_M2_PER_ELEMENT_8IN)


# =============================================================================
# Sub-Models
# =============================================================================
class HRROMassTransferIn(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    crossflow_velocity_m_s: Optional[float] = None
    recirc_flow_m3h: Optional[float] = None

    feed_channel_area_m2: Optional[float] = Field(
        0.015, description="Cross-sectional flow area"
    )

    rho_kg_m3: float = 998.0
    mu_pa_s: float = 0.001

    diffusivity_m2_s: float = 1.5e-9
    cp_exp_max: float = 5.0
    cp_rel_tol: float = 1e-4
    cp_abs_tol_lmh: float = 1e-3
    cp_relax: float = 0.5
    cp_max_iter: int = 30

    # (optional extensions used by hrro.py if present)
    k_mt_multiplier: Optional[float] = None
    k_mt_min_m_s: Optional[float] = None
    segments_total: Optional[int] = None


class HRROSpacerIn(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    thickness_mm: float = Field(0.76, description="Spacer thickness")
    filament_diameter_mm: float = Field(0.35, description="Mesh filament diameter")
    mesh_size_mm: Optional[float] = None

    voidage: Optional[float] = Field(0.85, description="Porosity")
    voidage_fallback: float = 0.85
    hydraulic_diameter_m: Optional[float] = None


class IonCompositionInput(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    # Cations (mg/L)
    NH4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("NH4", "nh4")
    )
    K: Optional[float] = Field(default=None, validation_alias=AliasChoices("K", "k"))
    Na: Optional[float] = Field(default=None, validation_alias=AliasChoices("Na", "na"))
    Mg: Optional[float] = Field(default=None, validation_alias=AliasChoices("Mg", "mg"))
    Ca: Optional[float] = Field(default=None, validation_alias=AliasChoices("Ca", "ca"))
    Sr: Optional[float] = Field(default=None, validation_alias=AliasChoices("Sr", "sr"))
    Ba: Optional[float] = Field(default=None, validation_alias=AliasChoices("Ba", "ba"))

    # Anions (mg/L)
    CO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("CO2", "co2")
    )
    HCO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("HCO2", "hco2")
    )
    HCO3: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("HCO3", "hco3")
    )
    NO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("NO2", "no2")
    )
    Cl: Optional[float] = Field(default=None, validation_alias=AliasChoices("Cl", "cl"))
    F: Optional[float] = Field(default=None, validation_alias=AliasChoices("F", "f"))
    SO4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("SO4", "so4")
    )
    PO4: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("PO4", "po4")
    )
    Br: Optional[float] = Field(default=None, validation_alias=AliasChoices("Br", "br"))

    # Neutrals (mg/L)
    SiO2: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("SiO2", "sio2")
    )
    B: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("B", "boron")
    )


# =============================================================================
# Main Input Models
# =============================================================================
class StageConfig(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls_and_normalize(cls, data: Any) -> Any:
        """
        1) Recursively drop None keys so Field defaults apply even if client sends null.
        2) Normalize module_type/type strings (HRRO, RO, etc.) to improve robustness.
        3) Normalize hrro_engine / hrro_excel_only_cp_mode if provided.
        """
        if not isinstance(data, dict):
            return data

        d = _drop_none_recursive(data)

        # normalize module_type / type strings
        mt = d.get("module_type", None) or d.get("type", None)
        if isinstance(mt, str):
            d["module_type"] = _norm_upper(mt)

        # normalize hrro_engine if provided
        if "hrro_engine" in d:
            d["hrro_engine"] = _norm_lower(d.get("hrro_engine"))

        # normalize hrro_excel_only_cp_mode if provided
        if "hrro_excel_only_cp_mode" in d:
            d["hrro_excel_only_cp_mode"] = _norm_lower(d.get("hrro_excel_only_cp_mode"))

        return d

    # --------------------------
    # Common stage identifiers
    # --------------------------
    stage_id: Optional[str] = None

    module_type: ModuleType = Field(
        default=ModuleType.RO,
        validation_alias=AliasChoices("type", "module_type"),
    )

    # ✅ 기존 호환: num_elements -> elements
    elements: int = Field(
        default=6,
        ge=1,
        validation_alias=AliasChoices("elements", "num_elements"),
    )

    pressure_bar: Optional[float] = Field(default=None, ge=0)
    dp_module_bar: Optional[float] = Field(
        0.2, ge=0, description="RO: pressure drop per element (bar/element)"
    )

    recovery_target_pct: Optional[float] = Field(default=None, ge=0, le=100)
    flux_lmh: Optional[float] = None

    membrane_model: Optional[str] = None

    # ✅ 기존 의미 유지: element 1개당 면적(m2) - default 37.0
    # NOTE: client가 null을 보내도 before-validator가 key를 제거하므로 default가 적용됨.
    membrane_area_m2: Optional[float] = Field(default=37.0, ge=0)

    membrane_A_lmh_bar: Optional[float] = None
    membrane_B_lmh: Optional[float] = None
    membrane_salt_rejection_pct: Optional[float] = None

    # --------------------------
    # HRRO batch / loop params
    # --------------------------
    loop_volume_m3: Optional[float] = 2.0
    recirc_flow_m3h: Optional[float] = 12.0
    bleed_m3h: Optional[float] = 0.0
    timestep_s: int = 5
    max_minutes: float = 60.0
    stop_permeate_tds_mgL: Optional[float] = None
    stop_recovery_pct: Optional[float] = None

    mass_transfer: Optional[HRROMassTransferIn] = None
    spacer: Optional[HRROSpacerIn] = None

    # ✅ 전역 chemistry를 stage로 내려받는 통로
    chemistry: Optional[Dict[str, Any]] = None

    # --------------------------
    # UF/MF filtration defaults
    # --------------------------
    filtration_cycle_min: Optional[float] = 30.0
    backwash_duration_sec: Optional[float] = 60.0
    backwash_flux_multiplier: Optional[float] = 1.5
    backwash_flux_lmh: Optional[float] = None

    # ==========================
    # ✅ HRRO Excel Design Inputs
    # ==========================
    hrro_engine: Literal["excel_only", "excel_physics"] = Field(
        default="excel_only",
        description="HRRO 계산 모드: excel_only(엑셀식) / excel_physics(엑셀+물리)",
    )

    hrro_excel_only_cp_mode: Literal["min_model", "none", "fixed_rejection"] = Field(
        default="min_model",
        description="excel_only에서 Cp/Cc 계산 방식: min_model / none / fixed_rejection",
    )

    hrro_excel_only_fixed_rejection_pct: float = Field(
        default=99.5,
        ge=0,
        le=100,
        description="excel_only + fixed_rejection에서 적용할 고정 염제거율(%)",
    )

    hrro_excel_only_min_model_rejection_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="excel_only + min_model rejection(%) override",
    )

    element_inch: int = Field(default=8, ge=4, le=8)
    vessel_count: int = Field(default=1, ge=1)
    elements_per_vessel: int = Field(default=6, ge=1)

    feed_flow_m3h: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("feed_flow_m3h", "q_raw_m3h", "raw_feed_m3h"),
    )

    ccro_recovery_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        validation_alias=AliasChoices(
            "ccro_recovery_pct", "ccro_recovery", "ccro_rec_pct"
        ),
    )

    pf_feed_ratio_pct: float = Field(
        default=110.0,
        ge=0,
        le=300,
        validation_alias=AliasChoices(
            "pf_feed_ratio_pct", "pf_feed_ratio", "pf_feed_ratio_percent"
        ),
    )

    pf_recovery_pct: float = Field(
        default=10.0,
        ge=0,
        le=100,
        validation_alias=AliasChoices("pf_recovery_pct", "pf_recovery", "pf_rec_pct"),
    )

    cc_recycle_m3h_per_pv: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices(
            "cc_recycle_m3h_per_pv", "cc_recycle_m3h", "recycle_m3h_per_pv"
        ),
    )

    membrane_area_m2_per_element: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices(
            "membrane_area_m2_per_element", "area_m2_per_element"
        ),
    )

    pump_eff: Optional[float] = Field(default=0.80, ge=0, le=1)

    # ==========================
    # ✅ HRRO Physics/Knobs (optional, safe defaults)
    # ==========================
    hrro_pressure_limit_bar: Optional[float] = Field(
        default=None,
        ge=0,
        description="excel_physics: inlet pressure upper bound (if None uses pressure_bar or 60bar)",
    )
    hrro_elem_length_m: Optional[float] = Field(
        default=1.0,
        ge=0,
        description="Element length for ΔP calculation (m)",
    )
    hrro_spacer_friction_multiplier: Optional[float] = Field(
        default=5.0,
        ge=0,
        description="Spacer friction multiplier for ΔP (>=1 typical)",
    )
    hrro_A_mu_exp: Optional[float] = Field(
        default=0.70,
        ge=0,
        description="Viscosity exponent for A (A~(mu_ref/mu)^exp)",
    )
    hrro_B_mu_exp: Optional[float] = Field(
        default=0.30,
        ge=0,
        description="Viscosity exponent for B (B~(mu_ref/mu)^exp)",
    )
    hrro_B_sal_slope: Optional[float] = Field(
        default=0.25,
        ge=0,
        description="Salinity slope factor applied to B",
    )
    hrro_A_compaction_k: Optional[float] = Field(
        default=0.003,
        ge=0,
        description="Compaction coefficient for A per bar above 25bar",
    )
    hrro_num_segments: int = Field(
        default=1,
        ge=1,
        le=200,
        description="excel_physics: axial segments for CP/ΔP (>=1)",
    )
    hrro_k_mt_multiplier: Optional[float] = Field(
        default=0.5,
        ge=0,
        description="Mass transfer coefficient multiplier",
    )
    hrro_k_mt_min_m_s: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Minimum mass transfer coefficient (m/s), 0 disables",
    )

    @model_validator(mode="after")
    def _apply_defaults_and_derive(self):
        """
        ✅ 핵심 보장:
        - client가 null을 보내도(default가 있는 필드면) 기본값 적용
        - HRRO: membrane_area_m2_per_element 반드시 값 존재하도록 채움
        - vessel_count/elements_per_vessel가 주어지고 elements가 명시되지 않았다면 elements 자동 파생
        """
        fields_set = getattr(self, "model_fields_set", set())

        # 1) elements 파생: elements를 명시하지 않았다면 vessel_count * elements_per_vessel
        if "elements" not in fields_set:
            vc = getattr(self, "vessel_count", None)
            epv = getattr(self, "elements_per_vessel", None)
            if vc is not None and epv is not None:
                self.elements = int(vc) * int(epv)

        # 2) area defaults (robust)
        default_area = _default_area_by_inch(getattr(self, "element_inch", 8))

        # membrane_area_m2: None/0/음수면 default로 보정
        m_area = getattr(self, "membrane_area_m2", None)
        if m_area is None or _as_float(m_area, 0.0) <= 0.0:
            self.membrane_area_m2 = float(default_area)

        # HRRO는 element area를 강제 보장
        if getattr(self, "module_type", None) == ModuleType.HRRO:
            per_el = getattr(self, "membrane_area_m2_per_element", None)
            if per_el is None or _as_float(per_el, 0.0) <= 0.0:
                base = getattr(self, "membrane_area_m2", None)
                base = float(base) if base is not None else float(default_area)
                self.membrane_area_m2_per_element = float(base)

            # legacy 일관성: membrane_area_m2가 비어있으면 per_element로 채움
            if getattr(self, "membrane_area_m2", None) is None:
                self.membrane_area_m2 = float(self.membrane_area_m2_per_element)

        # normalize strings again (defensive)
        # (module_type is enum, but others are literal strings)
        self.hrro_engine = _norm_lower(self.hrro_engine)
        self.hrro_excel_only_cp_mode = _norm_lower(self.hrro_excel_only_cp_mode)

        return self


class FeedInput(AppBaseModel):
    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data) if isinstance(data, dict) else data

    # ✅ UI 편의 + 안정성: 빠진 값은 안전 기본값
    flow_m3h: float = Field(default=0.0, ge=0, description="Feed Flow Rate")
    tds_mgL: float = Field(default=0.0, ge=0, description="TDS")
    temperature_C: float = Field(default=25.0, ge=0, le=100)
    ph: float = Field(default=7.0, ge=0, le=14)
    pressure_bar: Optional[float] = Field(default=0.0, ge=0)

    water_type: Optional[FeedWaterType] = None
    water_subtype: Optional[str] = None
    turbidity_ntu: Optional[float] = None
    tss_mgL: Optional[float] = None
    sdi15: Optional[float] = None
    toc_mgL: Optional[float] = None

    # ✅ feed-level chemistry passthrough
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

    # NOTE: 기존 코드 호환 유지 (의미상 placeholder)
    simulation_id: str = Field(default_factory=lambda: str(UUID(int=0)))
    project_id: Union[UUID, str] = "default"
    scenario_name: str = "Simulation"

    feed: FeedInput
    stages: List[StageConfig]

    # ✅ mutable default 방지
    options: Dict[str, Any] = Field(default_factory=dict)

    chemistry: Optional[WaterChemistryInput] = None

    ions: Optional[IonCompositionInput] = Field(
        default=None,
        validation_alias=AliasChoices("ions", "ion_composition", "ionComposition"),
    )


ScenarioInput = SimulationRequest


# =============================================================================
# Output Models
# =============================================================================
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


class ScalingIndexOut(AppBaseModel):
    lsi: Optional[float] = None
    rsi: Optional[float] = None
    s_dsi: Optional[float] = None
    caco3_si: Optional[float] = None
    caso4_si: Optional[float] = None
    sio2_si: Optional[float] = None


class WaterChemistryOut(AppBaseModel):
    feed: Optional[ScalingIndexOut] = None
    final_brine: Optional[ScalingIndexOut] = None


class StageMetric(AppBaseModel):
    # Stage identity
    stage: int = Field(validation_alias=AliasChoices("stage", "idx", "stage_index"))
    module_type: str = Field(validation_alias=AliasChoices("module_type", "type"))

    # Common KPIs
    recovery_pct: Optional[float] = None
    flux_lmh: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("flux_lmh", "jw_avg_lmh", "avg_flux_lmh"),
    )
    sec_kwhm3: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("sec_kwhm3", "sec_kwh_m3"),
    )
    ndp_bar: Optional[float] = None

    # Pressures
    p_in_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("p_in_bar", "pin", "pin_bar", "pressure_in"),
    )
    p_out_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("p_out_bar", "pout", "pout_bar", "pressure_out"),
    )

    # ✅ 추천 확장: UF/RO 등에서 유용 (엔진이 안 주면 None)
    dp_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("dp_bar", "delta_p_bar", "deltaP_bar"),
    )
    tmp_bar: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("tmp_bar", "TMP_bar", "tmp"),
    )

    delta_pi_bar: Optional[float] = None

    # Flows
    Qf: Optional[float] = None
    Qp: Optional[float] = None
    Qc: Optional[float] = None
    gross_flow_m3h: Optional[float] = None
    net_flow_m3h: Optional[float] = None
    backwash_loss_m3h: Optional[float] = None
    net_recovery_pct: Optional[float] = None

    # Concentrations / salinity
    Cf: Optional[float] = None
    Cp: Optional[float] = None
    Cc: Optional[float] = None

    # HRRO per-stage time history
    time_history: Optional[List[TimeSeriesPoint]] = None

    # chemistry can be dict (stage-local debug) or structured out
    chemistry: Optional[Union[Dict[str, Any], ScalingIndexOut]] = None


class StreamOut(AppBaseModel):
    label: str
    flow_m3h: float
    tds_mgL: float
    ph: float
    pressure_bar: float


class KPIOut(AppBaseModel):
    recovery_pct: float
    flux_lmh: float
    ndp_bar: float
    sec_kwhm3: float

    # ✅ UF/MF filtration cycle (min) 등을 UI에서 batchcycle로 쓰기 위한 KPI 키
    batchcycle: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices(
            "batchcycle",
            "batch_cycle",
            "batchcycle_min",
            "filtration_cycle_min",
        ),
    )

    prod_tds: Optional[float] = None
    feed_m3h: Optional[float] = None
    permeate_m3h: Optional[float] = None


class ScenarioOutput(AppBaseModel):
    scenario_id: Union[UUID, str]
    streams: List[StreamOut]
    kpi: KPIOut

    stage_metrics: Optional[List[StageMetric]] = None
    unit_labels: Optional[Dict[str, str]] = None
    chemistry: Optional[WaterChemistryOut] = None

    # legacy/system-level time history (optional)
    time_history: Optional[List[TimeSeriesPoint]] = None

    schema_version: int = 2
