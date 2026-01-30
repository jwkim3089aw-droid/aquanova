# app\schemas\simulation.py
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from pydantic import Field, AliasChoices
from .common import AppBaseModel, ModuleType, FeedWaterType

# --- Input Models ---


class HRROMassTransferIn(AppBaseModel):
    crossflow_velocity_m_s: Optional[float] = None
    recirc_flow_m3h: Optional[float] = None
    feed_channel_area_m2: Optional[float] = None
    rho_kg_m3: float = 998.0
    mu_pa_s: float = 0.001
    diffusivity_m2_s: float = 1.5e-9
    cp_exp_max: float = 5.0
    cp_rel_tol: float = 1e-4
    cp_abs_tol_lmh: float = 1e-3
    cp_relax: float = 0.5
    cp_max_iter: int = 30


class HRROSpacerIn(AppBaseModel):
    thickness_mm: float = 0.76
    filament_diameter_mm: float = 0.35
    mesh_size_mm: Optional[float] = None
    voidage: Optional[float] = None
    voidage_fallback: float = 0.85
    hydraulic_diameter_m: Optional[float] = None


class StageConfig(AppBaseModel):
    stage_id: Optional[str] = None
    module_type: ModuleType = Field(
        default=ModuleType.RO,
        validation_alias=AliasChoices("type", "module_type"),
    )
    elements: int = Field(default=6, ge=1, alias="num_elements")
    pressure_bar: Optional[float] = Field(None, ge=0)
    recovery_target_pct: Optional[float] = Field(None, ge=0, le=100)

    # Membrane
    membrane_model: Optional[str] = None
    membrane_area_m2: Optional[float] = None
    membrane_A_lmh_bar: Optional[float] = None
    membrane_B_lmh: Optional[float] = None
    membrane_salt_rejection_pct: Optional[float] = None

    # HRRO Specific
    loop_volume_m3: Optional[float] = 2.0
    recirc_flow_m3h: Optional[float] = 12.0
    bleed_m3h: Optional[float] = 0.0
    timestep_s: int = 5
    max_minutes: float = 60.0
    stop_permeate_tds_mgL: Optional[float] = None
    stop_recovery_pct: Optional[float] = None
    mass_transfer: Optional[HRROMassTransferIn] = None
    spacer: Optional[HRROSpacerIn] = None

    # UF/MF Specific
    filtration_cycle_min: Optional[float] = 30.0
    backwash_duration_sec: Optional[float] = 60.0
    backwash_flux_multiplier: Optional[float] = 1.5
    flux_lmh: Optional[float] = None
    backwash_flux_lmh: Optional[float] = None


class FeedInput(AppBaseModel):
    flow_m3h: float = Field(gt=0)
    tds_mgL: float = Field(ge=0)
    temperature_C: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    water_type: Optional[FeedWaterType] = None
    water_subtype: Optional[str] = None
    turbidity_ntu: Optional[float] = None
    tss_mgL: Optional[float] = None
    sdi15: Optional[float] = None
    toc_mgL: Optional[float] = None


class WaterChemistryInput(AppBaseModel):
    alkalinity_mgL_as_CaCO3: Optional[float] = None
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None
    sulfate_mgL: Optional[float] = None
    barium_mgL: Optional[float] = None
    strontium_mgL: Optional[float] = None
    silica_mgL_SiO2: Optional[float] = None


class SimulationRequest(AppBaseModel):
    simulation_id: str = Field(default_factory=lambda: str(UUID(int=0)))
    project_id: Union[UUID, str] = "default"
    scenario_name: str = "Simulation"
    feed: FeedInput
    stages: List[StageConfig]
    options: Dict[str, Any] = {}
    chemistry: Optional[WaterChemistryInput] = None


# Legacy alias
ScenarioInput = SimulationRequest

# --- Output Models ---


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


class StageMetric(AppBaseModel):
    stage: int = Field(validation_alias=AliasChoices("stage", "idx", "stage_index"))
    module_type: str = Field(validation_alias=AliasChoices("module_type", "type"))
    recovery_pct: Optional[float] = None
    flux_lmh: Optional[float] = Field(
        None, validation_alias=AliasChoices("flux_lmh", "jw_avg_lmh")
    )
    sec_kwhm3: Optional[float] = Field(
        None, validation_alias=AliasChoices("sec_kwhm3", "sec_kwh_m3")
    )
    ndp_bar: Optional[float] = None
    delta_pi_bar: Optional[float] = None
    p_in_bar: Optional[float] = Field(
        None, validation_alias=AliasChoices("p_in_bar", "pin")
    )
    p_out_bar: Optional[float] = Field(
        None, validation_alias=AliasChoices("p_out_bar", "pout")
    )
    Qf: Optional[float] = None
    Qp: Optional[float] = None
    Qc: Optional[float] = None
    Cf: Optional[float] = None
    Cp: Optional[float] = None
    Cc: Optional[float] = None
    gross_flow_m3h: Optional[float] = None
    net_flow_m3h: Optional[float] = None
    backwash_loss_m3h: Optional[float] = None
    net_recovery_pct: Optional[float] = None
    time_history: Optional[List[TimeSeriesPoint]] = None
    chemistry: Optional[Dict[str, Any]] = None


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
    prod_tds: Optional[float] = None
    feed_m3h: Optional[float] = None
    permeate_m3h: Optional[float] = None


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


class ScenarioOutput(AppBaseModel):
    scenario_id: Union[UUID, str]
    streams: List[StreamOut]
    kpi: KPIOut
    stage_metrics: Optional[List[StageMetric]] = None
    unit_labels: Optional[Dict[str, str]] = None
    chemistry: Optional[WaterChemistryOut] = None
    time_history: Optional[List[TimeSeriesPoint]] = None
    schema_version: int = 2
