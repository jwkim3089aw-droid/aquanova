# app/schemas/simulation.py
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Literal
from uuid import UUID
from pydantic import Field, AliasChoices, model_validator, ConfigDict
from .common import AppBaseModel, ModuleType


def _drop_none_recursive(obj: Any) -> Any:
    """Recursively remove None values"""
    if isinstance(obj, dict):
        return {k: _drop_none_recursive(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_none_recursive(v) for v in obj]
    return obj


def _norm_upper(s: Any) -> Any:
    """String normalization to uppercase"""
    return s.strip().upper() if isinstance(s, str) and s.strip() else s


class AcidType(str, Enum):
    HCL = "HCl"
    H2SO4 = "H2SO4"


class BaseType(str, Enum):
    NAOH = "NaOH"


DEFAULT_AREA_M2_PER_ELEMENT_8IN = 37.16
DEFAULT_AREA_M2_PER_ELEMENT_4IN = 20.0
DEFAULT_UF_AREA_M2 = 77.0


def _default_area_by_type(module_type: ModuleType, element_inch: int = 8) -> float:
    """Return default membrane area based on module type and inch"""
    if module_type == ModuleType.UF:
        return float(DEFAULT_UF_AREA_M2)
    if int(element_inch or 8) <= 4:
        return float(DEFAULT_AREA_M2_PER_ELEMENT_4IN)
    return float(DEFAULT_AREA_M2_PER_ELEMENT_8IN)


class DosingControl(AppBaseModel):
    """Chemical dosing control for pH and scaling."""

    model_config = ConfigDict(extra="allow")

    target_ph: Optional[float] = Field(None, ge=0, le=14)
    pass2_target_ph: Optional[float] = Field(
        None, ge=0, le=14, description="Optional downstream-pass pH target."
    )
    acid_type: AcidType = Field(AcidType.HCL)
    base_type: BaseType = Field(BaseType.NAOH)
    antiscalant_enabled: bool = Field(True)


class ChemicalDosingItem(AppBaseModel):
    """Dosing output item"""

    chemical_name: str
    purpose: str
    dose_mgL: float
    usage_kg_day: float


class ChemicalDosingOut(AppBaseModel):
    """Dosing calculation output schema"""

    dosing_items: List[ChemicalDosingItem] = Field(default_factory=list)
    initial_ph: float
    target_ph: Optional[float] = None
    actual_ph: float
    warnings: List[str] = Field(default_factory=list)


class EconomicsOut(AppBaseModel):
    """Economics and Opex output schema"""

    unit_cost: float = 0.0
    energy_cost_per_m3: float = 0.0
    chem_cost_per_m3: float = 0.0
    energy_portion_pct: float = 0.0
    chem_portion_pct: float = 0.0
    daily_total_cost: float = 0.0
    currency: str = "$"


class OpexConfig(AppBaseModel):
    """Opex configuration and unit prices"""

    electricity_price_kwh: float = Field(0.12)
    antiscalant_price_kg: float = Field(5.50)
    acid_base_price_kg: float = Field(0.85)


class HRROMassTransferIn(AppBaseModel):
    """HRRO mass transfer configuration"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    crossflow_velocity_m_s: Optional[float] = None
    recirc_flow_m3h: Optional[float] = None
    feed_channel_area_m2: Optional[float] = Field(0.015)
    rho_kg_m3: float = 998.0
    mu_pa_s: float = 0.001
    diffuser_m2_s: float = 1.5e-9
    cp_exp_max: float = 5.0
    cp_rel_tol: float = 1e-4
    cp_abs_tol_lmh: float = 1e-3
    cp_relax: float = 0.5
    cp_max_iter: int = 30
    k_mt_multiplier: Optional[float] = None
    k_mt_min_m_s: Optional[float] = None
    segments_total: Optional[int] = None


class HRROSpacerIn(AppBaseModel):
    """HRRO feed spacer geometry configuration"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    thickness_mm: float = Field(0.76)
    filament_diameter_mm: float = Field(0.35)
    mesh_size_mm: Optional[float] = None
    voidage: Optional[float] = Field(0.85)
    voidage_fallback: float = 0.85
    hydraulic_diameter_m: Optional[float] = None


class IonCompositionInput(AppBaseModel):
    """Feed water ionic composition schema (mg/L)"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    NH4: Optional[float] = Field(None, validation_alias=AliasChoices("NH4", "nh4"))
    K: Optional[float] = Field(None, validation_alias=AliasChoices("K", "k"))
    Na: Optional[float] = Field(None, validation_alias=AliasChoices("Na", "na"))
    Mg: Optional[float] = Field(None, validation_alias=AliasChoices("Mg", "mg"))
    Ca: Optional[float] = Field(None, validation_alias=AliasChoices("Ca", "ca"))
    Sr: Optional[float] = Field(None, validation_alias=AliasChoices("Sr", "sr"))
    Ba: Optional[float] = Field(None, validation_alias=AliasChoices("Ba", "ba"))
    Fe: Optional[float] = Field(None, validation_alias=AliasChoices("Fe", "fe"))
    Mn: Optional[float] = Field(None, validation_alias=AliasChoices("Mn", "mn"))
    Al: Optional[float] = Field(None, validation_alias=AliasChoices("Al", "al"))
    CO3: Optional[float] = Field(None, validation_alias=AliasChoices("CO3", "co3"))
    HCO3: Optional[float] = Field(None, validation_alias=AliasChoices("HCO3", "hco3"))
    NO3: Optional[float] = Field(None, validation_alias=AliasChoices("NO3", "no3"))
    Cl: Optional[float] = Field(None, validation_alias=AliasChoices("Cl", "cl"))
    F: Optional[float] = Field(None, validation_alias=AliasChoices("F", "f"))
    SO4: Optional[float] = Field(None, validation_alias=AliasChoices("SO4", "so4"))
    Br: Optional[float] = Field(None, validation_alias=AliasChoices("Br", "br"))
    PO4: Optional[float] = Field(None, validation_alias=AliasChoices("PO4", "po4"))
    SiO2: Optional[float] = Field(None, validation_alias=AliasChoices("SiO2", "sio2"))
    B: Optional[float] = Field(None, validation_alias=AliasChoices("B", "boron"))
    CO2: Optional[float] = Field(None, validation_alias=AliasChoices("CO2", "co2"))
    HCO2: Optional[float] = Field(None, validation_alias=AliasChoices("HCO2", "hco2"))
    NO2: Optional[float] = Field(None, validation_alias=AliasChoices("NO2", "no2"))


class UFMaintenanceConfig(AppBaseModel):
    """UF/MF process maintenance cycles and cleaning conditions"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    filtration_duration_min: float = Field(60.0, ge=1)
    acid_ceb_interval_h: float = Field(24.0, ge=0)
    alkali_ceb_interval_h: float = Field(24.0, ge=0)
    cip_interval_d: float = Field(30.0, ge=0)
    mini_cip_interval_d: float = Field(0.0, ge=0)

    # Backwash Sequence
    backwash_duration_sec: float = Field(60.0, ge=0)
    drain_duration_sec: float = Field(30.0, ge=0)
    top_backwash_duration_sec: float = Field(30.0, ge=0)
    bottom_backwash_duration_sec: float = Field(30.0, ge=0)
    air_scour_duration_sec: float = Field(20.0, ge=0)
    forward_flush_duration_sec: float = Field(40.0, ge=0)

    # Flux and Flows
    backwash_flux_lmh: float = Field(100.0, ge=0)
    ceb_flux_lmh: float = Field(80.0, ge=0)
    forward_flush_flow_m3h_per_mod: float = Field(2.83, ge=0)
    air_flow_nm3h_per_mod: float = Field(12.0, ge=0)

    # CEB/CIP Specifics
    ceb_soaking_min: float = Field(10.0, ge=0)
    cip_heating_min: float = Field(60.0, ge=0)

    # Power and System OPEX
    power_plc_kw: float = Field(0.10, ge=0)
    power_valve_kw: float = Field(0.00, ge=0)
    valves_per_train: int = Field(6, ge=1)
    valve_action_sec: float = Field(5.0, ge=0)

    # Pressures and Piping Drops
    air_scour_pressure_bar: float = Field(0.75, ge=0)
    filtrate_pressure_bar: float = Field(0.50, ge=0)
    filtration_piping_dp_bar: float = Field(0.40, ge=0)
    strainer_dp_bar: float = Field(0.10, ge=0)
    backwash_piping_dp_bar: float = Field(0.50, ge=0)
    cip_piping_dp_bar: float = Field(2.50, ge=0)

    integrity_test_min_day: float = Field(0.0, ge=0)


class WAVEWaterType(str, Enum):
    WELL_WATER = "RO/NF Well Water"
    SURFACE_WATER = "RO/NF Surface Water"
    SEAWATER_OPEN = "SD Seawater (Open Intake)"
    SEAWATER_WELL = "SD Seawater (Well)"
    WASTEWATER = "WW Wastewater"
    CITY_WATER = "City Water"


class FoulingIndicators(AppBaseModel):
    """Fouling indicator indices"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    tss_mgL: Optional[float] = Field(None, ge=0)
    turbidity_ntu: Optional[float] = Field(None, ge=0)
    sdi15: Optional[float] = Field(None, ge=0)
    toc_mgL: Optional[float] = Field(None, ge=0)
    cod_mgL: Optional[float] = Field(None, ge=0)
    bod_mgL: Optional[float] = Field(None, ge=0)


class FeedInput(AppBaseModel):
    """Simulation feed water conditions"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    water_type: WAVEWaterType = Field(WAVEWaterType.WELL_WATER)
    flow_m3h: float = Field(100.0, ge=0)
    temperature_C: float = Field(25.0, ge=0, le=100)
    temp_min_C: Optional[float] = Field(None, ge=0, le=100)
    temp_max_C: Optional[float] = Field(None, ge=0, le=100)
    ph: float = Field(7.0, ge=0, le=14)
    dosing: DosingControl = Field(default_factory=DosingControl)
    pressure_bar: Optional[float] = Field(0.0, ge=0)
    fouling: FoulingIndicators = Field(default_factory=FoulingIndicators)
    ions: Optional[IonCompositionInput] = Field(default_factory=IonCompositionInput)
    tds_mgL: float = Field(0.0, ge=0)
    tss_mgL: float = Field(0.0, ge=0)
    chemistry: Optional[Dict[str, Any]] = None


class StageConfig(AppBaseModel):
    """Unit process configuration and hydraulic setup"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

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
    stage_idx: Optional[int] = Field(1, ge=1)
    pass_idx: int = Field(1, ge=1)
    stage_label: Optional[str] = None
    module_type: ModuleType = Field(
        ModuleType.RO, validation_alias=AliasChoices("type", "module_type")
    )

    cfg: Dict[str, Any] = Field(
        default_factory=dict, description="Frontend dynamic configuration mapping"
    )

    element_inch: int = Field(8, ge=4, le=16)
    vessel_count: int = Field(10, ge=1)
    elements_per_vessel: int = Field(5, ge=1)
    elements: int = Field(
        50,
        ge=1,
        validation_alias=AliasChoices(
            "elements", "num_elements", "total_elements", "modules_count"
        ),
    )
    membrane_model: Optional[str] = Field(default=None)
    membrane_area_m2: Optional[float] = Field(None)
    membrane_area_m2_per_element: Optional[float] = Field(
        None,
        ge=0,
        validation_alias=AliasChoices(
            "membrane_area_m2_per_element", "area_m2_per_element"
        ),
    )

    membrane_A_lmh_bar: Optional[float] = None
    membrane_B_lmh: Optional[float] = None
    A_correction_factor: float = Field(1.0, ge=0.0)
    B_correction_factor: float = Field(1.0, ge=0.0)
    membrane_salt_rejection_pct: Optional[float] = Field(99.5)
    temp_corr_factor_A: Optional[float] = None
    temp_corr_factor_B: Optional[float] = None
    cp_tuning_factor: Optional[float] = Field(
        None, validation_alias=AliasChoices("cp_tuning_factor", "cp_adjustment_factor")
    )
    cp_adjustment_factor: Optional[float] = None
    fouling_factor: Optional[float] = Field(None, ge=0.01)
    B_fouling_factor: Optional[float] = Field(None, ge=0.01)
    b_salinity_slope: Optional[float] = Field(
        None,
        ge=0.0,
        le=20.0,
        description="Salt-permeability increase with membrane-wall salinity.",
    )
    tuning_locked: bool = Field(
        False,
        description="Preserve explicitly supplied calibration coefficients.",
    )
    tuning_regime: Optional[str] = None
    tuning_source: Optional[str] = None
    source_file: Optional[str] = None
    pump_efficiency: Optional[float] = Field(
        0.80, validation_alias=AliasChoices("pump_efficiency", "pump_eff")
    )
    flow_factor: float = Field(0.85, ge=0.1, le=2.0)

    recovery_target_pct: Optional[float] = Field(
        90.0,
        ge=0,
        le=100,
        validation_alias=AliasChoices("recovery_target_pct", "recovery_pct"),
    )
    feed_flow_m3h: Optional[float] = Field(
        None, ge=0, validation_alias=AliasChoices("feed_flow_m3h", "q_raw_m3h")
    )
    pressure_bar: Optional[float] = Field(None, ge=0)
    flux_lmh: Optional[float] = None
    design_flux_lmh: Optional[float] = Field(None, ge=0)

    spi: float = Field(1.0, ge=1.0)
    strainer_recovery_pct: float = Field(99.5, ge=0, le=100)
    strainer_size_micron: float = Field(150.0, ge=0)
    temp_mode: Literal["Minimum", "Design", "Maximum"] = Field("Design")
    bypass_flow_m3h: float = Field(0.0, ge=0)
    pre_stage_dp_bar: float = Field(0.31, ge=0)
    isbp_pressure_bar: float = Field(0.0, ge=0)
    isbp_eff_pct: float = Field(80.0, ge=0, le=100)
    permeate_back_pressure_bar: float = Field(0.0, ge=0)
    pass_feed_fraction: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of the upstream pass permeate routed into this pass.",
    )
    split_remainder_to_product: bool = Field(
        False,
        description="Treat the unrouted upstream permeate fraction as a product branch.",
    )

    dp_correlation_enabled: bool = Field(
        False,
        description="Use the flow/temperature/TDS pressure-drop correlation.",
    )
    dp_correlation_multiplier: Optional[float] = Field(None, ge=0.05, le=20.0)
    dp_per_elem_bar: Optional[float] = Field(None, ge=0)
    dp_module_bar: Optional[float] = Field(None, ge=0)
    burst_pressure_limit_bar: float = Field(83.0, ge=0)
    max_tmp_bar: Optional[float] = Field(None, ge=0)
    max_inverse_pressure_bar: Optional[float] = Field(None, ge=1)

    loop_volume_m3: Optional[float] = Field(1.36)
    recirc_flow_m3h: Optional[float] = Field(120.0, ge=0)
    max_minutes: float = Field(60.0)
    stop_recovery_pct: Optional[float] = Field(90.0)
    stop_permeate_tds_mgL: Optional[float] = None
    cc_recycle_m3h_per_pv: Optional[float] = Field(
        4.33,
        ge=0,
        validation_alias=AliasChoices("cc_recycle_m3h_per_pv", "cc_recycle_m3h"),
    )
    hrro_engine: str = Field("physics")
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
    pf_feed_ratio_pct: float = Field(110.0, ge=0)
    pf_recovery_pct: float = Field(10.0, ge=0)
    ccro_recovery_pct: Optional[float] = None
    pf_cp_assist_enabled: bool = Field(
        False,
        description="Run the concentrate recycle pump during PF as a design-study option.",
    )
    pf_cp_assist_flow_m3h_per_pv: Optional[float] = Field(
        None,
        ge=0,
        description="Optional P-3/CP assist flow during PF, per pressure vessel.",
    )
    pf_mode: str = Field(
        "wave_true_plug_flow",
        description=(
            "PF operating mode: wave_true_plug_flow keeps P-3 off and fully opens "
            "the brine valve; smart_partial_drain keeps P-3 on and uses a partial "
            "brine-valve PID drain setpoint; field_optimized_low_fr is the same "
            "smart logic intended for FR 120-150 design studies."
        ),
    )
    min_concentrate_flow_m3h_per_pv: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum membrane concentrate outlet/crossflow target during CC/PF, per pressure vessel.",
    )
    p3_recycle_capacity_m3h_per_pv: Optional[float] = Field(
        None,
        ge=0,
        description="P-3 circulation pump available recycle capacity during smart PF, per pressure vessel.",
    )
    drain_low_threshold_m3h_per_pv: Optional[float] = Field(
        None,
        ge=0,
        description="Warning threshold for too-small external drain setpoint in smart partial-drain PF.",
    )
    adaptive_recovery_enabled: bool = Field(
        False,
        description="Allow CCRO cycle to stop below target recovery when brine conductivity/TDS or pressure safety limits are reached.",
    )
    brine_conductivity_limit_mgL: Optional[float] = Field(
        None,
        ge=0,
        description="Approximate brine conductivity/TDS limit used as an adaptive CC stop condition.",
    )
    brine_tds_limit_mgL: Optional[float] = Field(
        None,
        ge=0,
        description="Alias/alternative to brine_conductivity_limit_mgL for adaptive recovery control.",
    )
    adaptive_min_recovery_pct: float = Field(
        50.0,
        ge=0,
        le=100,
        description="Lower bound for adaptive recovery fallback when water quality limits are reached early.",
    )
    hpp_sizing_mode: str = Field(
        "base",
        description="HPP selection class from ReFlex-style catalog interpretation: base, step1, or step2. HPP count remains one.",
    )
    hpp_count: int = Field(1, ge=1, description="HPP count. CCRO/HRRO design assumes one HPP selected from base/step options.")
    p3_generated_head_bar: Optional[float] = Field(
        0.6, ge=0, description="P-3 generated head; separate from casing pressure rating."
    )
    p3_casing_pressure_rating_bar: Optional[float] = Field(
        12.0, ge=0, description="P-3 casing/shell pressure rating for operation inside the high-pressure loop."
    )
    rinse_volume_m3: Optional[float] = Field(
        0.0,
        ge=0,
        description="Additional rinse volume per configured interval; diagnostic only unless rinse_uses_permeate is true.",
    )
    rinse_interval_cycles: int = Field(1, ge=1)
    rinse_uses_permeate: bool = Field(False)

    uf_maintenance: UFMaintenanceConfig = Field(default_factory=UFMaintenanceConfig)
    spacer: Optional[HRROSpacerIn] = None
    mass_transfer: Optional[HRROMassTransferIn] = None
    chemistry: Optional[Dict[str, Any]] = None
    filtration_cycle_min: Optional[float] = 30.0
    backwash_duration_sec: Optional[float] = 60.0
    backwash_flux_multiplier: Optional[float] = 1.5
    backwash_flux_lmh: Optional[float] = None
    fouling_rate_constant: float = Field(1.5e-7, ge=0)

    @model_validator(mode="after")
    def _apply_defaults_and_derive(self):
        fields_set = getattr(self, "model_fields_set", set())
        if "elements" not in fields_set:
            self.elements = int(getattr(self, "vessel_count", 10)) * int(
                getattr(self, "elements_per_vessel", 5)
            )
        if self.membrane_area_m2 is None or float(self.membrane_area_m2) <= 0.0:
            self.membrane_area_m2 = _default_area_by_type(
                self.module_type, self.element_inch
            )
        if getattr(self, "module_type", None) == ModuleType.HRRO:
            per_el = getattr(self, "membrane_area_m2_per_element", None)
            if per_el is None or float(per_el) <= 0.0:
                self.membrane_area_m2_per_element = self.membrane_area_m2
        if self.module_type == ModuleType.UF and self.design_flux_lmh is None:
            self.design_flux_lmh = 55.5
        return self


class WaterChemistryInput(AppBaseModel):
    """Detailed water chemistry input schema"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    alkali_mgL_as_CaCO3: Optional[float] = Field(
        None,
        validation_alias=AliasChoices("alkali_mgL_as_CaCO3", "alkalinity_mgL_as_CaCO3"),
    )
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None
    sulfate_mgL: Optional[float] = None
    barium_mgL: Optional[float] = None
    strontium_mgL: Optional[float] = None
    silica_mgL_SiO2: Optional[float] = None


class SimulationRequest(AppBaseModel):
    """Main simulation request payload schema"""

    @model_validator(mode="before")
    @classmethod
    def _strip_nulls(cls, data: Any) -> Any:
        return _drop_none_recursive(data)

    simulation_id: str = Field(default_factory=lambda: str(UUID(int=0)))
    project_id: Union[UUID, str] = "default"
    scenario_name: str = "Simulation"
    # V120: explicit opt-in only WAVE residual correction controls.
    # Default path remains raw AquaNova physics.
    wave_correction_enabled: bool = False
    precision_mode_enabled: bool = False
    calibration_mode: Optional[str] = None
    engine_mode: Optional[str] = None
    feed: FeedInput
    stages: List[StageConfig]
    options: Dict[str, Any] = Field(default_factory=dict)
    chemistry: Optional[WaterChemistryInput] = None
    opex_config: Optional[OpexConfig] = Field(default_factory=OpexConfig)


ScenarioInput = SimulationRequest


class SimulationWarning(AppBaseModel):
    """Simulation limit warning schema"""

    stage: Optional[str] = None
    module_type: Optional[str] = None
    key: str
    message: str
    value: Optional[float] = None
    limit: Any = None
    unit: str = ""
    level: str = "WARN"


class TimeSeriesPoint(AppBaseModel):
    """Time series point for dynamic systems"""

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
    phase: Optional[str] = None
    feed_flow_m3h: Optional[float] = None
    recirc_flow_m3h: Optional[float] = None
    concentrate_flow_m3h: Optional[float] = None


class ScalingIndexOut(AppBaseModel):
    """Scaling indicators output schema"""

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
    """Comprehensive water chemistry indexing"""

    feed: Optional[ScalingIndexOut] = None
    final_brine: Optional[ScalingIndexOut] = None


class StageMetric(AppBaseModel):
    """Stage-level performance metrics"""

    stage: int = Field(validation_alias=AliasChoices("stage", "idx", "stage_index"))
    module_type: str = Field(validation_alias=AliasChoices("module_type", "type"))
    recovery_pct: Optional[float] = None
    flux_lmh: Optional[float] = Field(
        None, validation_alias=AliasChoices("flux_lmh", "jw_avg_lmh", "avg_flux_lmh")
    )
    design_flux_lmh: Optional[float] = None
    instantaneous_flux_lmh: Optional[float] = None
    average_flux_lmh: Optional[float] = None
    sec_kwhm3: Optional[float] = Field(
        None, validation_alias=AliasChoices("sec_kwhm3", "sec_kwh_m3")
    )
    ndp_bar: Optional[float] = None
    p_in_bar: Optional[float] = Field(
        None, validation_alias=AliasChoices("p_in_bar", "pin", "pin_bar", "pressure_in")
    )
    p_out_bar: Optional[float] = Field(
        None,
        validation_alias=AliasChoices("p_out_bar", "pout", "pout_bar", "pressure_out"),
    )
    dp_bar: Optional[float] = Field(
        None, validation_alias=AliasChoices("dp_bar", "delta_p_bar", "deltaP_bar")
    )
    tmp_bar: Optional[float] = Field(
        None, validation_alias=AliasChoices("tmp_bar", "TMP_bar", "tmp")
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
    """Process stream properties"""

    label: str
    flow_m3h: float
    tds_mgL: float
    ph: float
    pressure_bar: float
    temperature_C: Optional[float] = None
    ions: Optional[Dict[str, float]] = None


class MassBalanceOut(AppBaseModel):
    """Mass balance checking parameters"""

    flow_error_m3h: float = 0.0
    flow_error_pct: float = 0.0
    salt_error_kgh: float = 0.0
    salt_error_pct: float = 0.0
    system_rejection_pct: Optional[float] = None
    is_balanced: bool = True


class KPIOut(AppBaseModel):
    """Top-level Key Performance Indicators"""

    recovery_pct: float
    flux_lmh: float
    ndp_bar: float
    sec_kwhm3: float
    batchcycle: Optional[float] = Field(
        None,
        validation_alias=AliasChoices(
            "batchcycle", "batch_cycle", "batchcycle_min", "filtration_cycle_min"
        ),
    )
    prod_tds: Optional[float] = None
    feed_m3h: Optional[float] = None
    permeate_m3h: Optional[float] = None
    mass_balance: Optional[MassBalanceOut] = None
    unit_cost: float = Field(0.0)
    currency: str = Field("$")


class ScenarioOutput(AppBaseModel):
    """Master simulation output schema"""

    scenario_id: Union[UUID, str]
    streams: List[StreamOut]
    kpi: KPIOut
    stage_metrics: Optional[List[StageMetric]] = None
    unit_labels: Optional[Dict[str, str]] = None
    chemistry: Optional[WaterChemistryOut] = None
    dosing: Optional[ChemicalDosingOut] = None
    economics: Optional[EconomicsOut] = None
    time_history: Optional[List[TimeSeriesPoint]] = None
    warnings: Optional[List[SimulationWarning]] = None
    # V120: populated only when WAVE correction opt-in mode is explicitly enabled.
    precision_report: Optional[Dict[str, Any]] = None
    schema_version: int = 2
