#!/usr/bin/env python3
"""Schema and validation for extended WAVE RO automation cases.

V25 keeps the dependency-free XLSX/JSON workflow and expands the schema to
cover the controls observed in the user's RO inventory video: feed temperature
envelopes, pass temperature modes, 1-2 passes, 1-5 stages, stage-specific
membranes/PV/elements, pressure controls, flow factors, and Chemical Adjustment, anti-scalant/dechlorinator, and RO special features.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional
import math
import re


def _clean_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _lookup(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    normalized = {_clean_key(k): v for k, v in row.items()}
    for name in names:
        key = _clean_key(name)
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "y", "yes", "true", "on", "run", "실행"}


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = str(value).strip().replace(",", "")
        text = re.sub(
            r"\s*(%|°?c|bar|m3/h|m³/h|lmh|mg/l|uatm|µatm)\s*$",
            "",
            text,
            flags=re.I,
        )
        result = float(text)
    if not math.isfinite(result):
        raise ValueError(f"finite number required, got {value!r}")
    return result


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    number = _as_float(value, None)
    if number is None:
        return default
    rounded = int(round(number))
    if abs(number - rounded) > 1e-7:
        raise ValueError(f"integer required, got {value!r}")
    return rounded


def _as_text(value: Any, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value).strip()


@dataclass
class ROStageConfig:
    pv: int = 10
    elements_per_pv: int = 6
    membrane: str = "BW30-400"
    stage_back_pressure_bar: Optional[float] = None
    boost_pressure_bar: Optional[float] = None
    flow_factor: Optional[float] = None

    def validate(self, label: str) -> None:
        if not (1 <= self.pv <= 500):
            raise ValueError(f"{label}.pv must be 1..500, got {self.pv}")
        if not (1 <= self.elements_per_pv <= 12):
            raise ValueError(
                f"{label}.elements_per_pv must be 1..12, got {self.elements_per_pv}"
            )
        if not self.membrane:
            raise ValueError(f"{label}.membrane is required")
        restricted_tokens = ("obsolete", "to be discontinued", "china only")
        if any(token in self.membrane.strip().lower() for token in restricted_tokens):
            raise ValueError(
                f"{label}.membrane is restricted by WAVE list metadata: {self.membrane!r}"
            )
        if self.stage_back_pressure_bar is not None and self.stage_back_pressure_bar < 0:
            raise ValueError(f"{label}.stage_back_pressure_bar must be >= 0")
        if self.boost_pressure_bar is not None and self.boost_pressure_bar < 0:
            raise ValueError(f"{label}.boost_pressure_bar must be >= 0")
        if self.flow_factor is not None and not (0.1 <= self.flow_factor <= 1.5):
            raise ValueError(f"{label}.flow_factor must be 0.1..1.5")


@dataclass
class ROPassConfig:
    recovery_pct: float = 75.0
    stage_count: int = 1
    flow_factor: float = 0.85
    temperature_mode: str = "Specify"
    temperature_c: float = 25.0
    permeate_back_pressure_bar: float = 0.0
    stages: list[ROStageConfig] = field(default_factory=lambda: [ROStageConfig()])

    # Controls observed in Reverse Osmosis Flow Calculator.  They remain
    # fail-closed until a dedicated UIA inventory run proves their identifiers.
    recycle_target_pass: Optional[int] = None
    recycle_pct: Optional[float] = None
    bypass_pct: Optional[float] = None
    permeate_split_pct: Optional[float] = None
    recycle_split_pass1_pct: Optional[float] = None
    recycle_split_pass2_pct: Optional[float] = None

    def validate(self, label: str) -> None:
        if not (1 <= self.stage_count <= 5):
            raise ValueError(f"{label}.stage_count must be 1..5")
        if len(self.stages) != self.stage_count:
            raise ValueError(
                f"{label}.stages length {len(self.stages)} != stage_count {self.stage_count}"
            )
        if not (0.1 <= self.recovery_pct < 100):
            raise ValueError(f"{label}.recovery_pct must be 0.1..<100")
        if not (0.1 <= self.flow_factor <= 1.5):
            raise ValueError(f"{label}.flow_factor must be 0.1..1.5")
        if self.permeate_back_pressure_bar < 0:
            raise ValueError(f"{label}.permeate_back_pressure_bar must be >= 0")
        mode = self.temperature_mode.strip().lower()
        if mode not in {"minimum", "design", "maximum", "specify"}:
            raise ValueError(
                f"{label}.temperature_mode must be Minimum/Design/Maximum/Specify"
            )
        if not (-5 <= self.temperature_c <= 60):
            raise ValueError(f"{label}.temperature_c must be -5..60")
        for i, stage in enumerate(self.stages, start=1):
            stage.validate(f"{label}.stage{i}")
        for name in (
            "recycle_pct",
            "bypass_pct",
            "permeate_split_pct",
            "recycle_split_pass1_pct",
            "recycle_split_pass2_pct",
        ):
            value = getattr(self, name)
            if value is not None and not (0 <= value <= 100):
                raise ValueError(f"{label}.{name} must be 0..100")
        if self.recycle_target_pass is not None and self.recycle_target_pass not in (1, 2):
            raise ValueError(f"{label}.recycle_target_pass must be 1 or 2")


@dataclass
class ROChemicalConfig:
    acid_enabled: bool = False
    acid_type: Optional[str] = None
    acid_target_ph: Optional[float] = None
    degas_enabled: bool = False
    degas_mode: Optional[str] = None
    degas_value: Optional[float] = None
    base_enabled: bool = False
    base_type: Optional[str] = None
    base_target_ph: Optional[float] = None
    antiscalant_enabled: bool = False
    antiscalant_type: Optional[str] = None
    antiscalant_dose_mg_l: Optional[float] = None
    dechlorinator_enabled: bool = False
    dechlorinator_type: Optional[str] = None
    dechlorinator_dose_mg_l: Optional[float] = None
    temperature_mode: Optional[str] = None
    temperature_c: Optional[float] = None
    recovery_mode: Optional[str] = None
    recovery_value_pct: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return any(
            (
                self.acid_enabled,
                self.degas_enabled,
                self.base_enabled,
                self.antiscalant_enabled,
                self.dechlorinator_enabled,
                bool(self.temperature_mode),
                bool(self.recovery_mode),
            )
        )

    def validate(self) -> None:
        if self.acid_enabled and self.base_enabled:
            raise ValueError(
                "Acid and Base cannot be enabled together in one Chemical Adjustment case; "
                "use separate cases or combine either one with Degas/Anti-Scalant/Dechlorinator."
            )
        if self.acid_enabled:
            if self.acid_type not in {"HCl (32)", "H2SO4 (98)"}:
                raise ValueError("acid_type must be 'HCl (32)' or 'H2SO4 (98)'")
            if self.acid_target_ph is None or not (0 <= self.acid_target_ph <= 14):
                raise ValueError("acid_target_ph must be 0..14")
        if self.base_enabled:
            if self.base_type not in {"NaOH (30)", "NaOH (50)"}:
                raise ValueError("base_type must be 'NaOH (30)' or 'NaOH (50)'")
            if self.base_target_ph is None or not (0 <= self.base_target_ph <= 14):
                raise ValueError("base_target_ph must be 0..14")
        if self.degas_enabled:
            if self.degas_mode not in {
                "CO2 Removal",
                "CO2 Partial Pressure",
                "CO2 Concentration",
            }:
                raise ValueError("invalid degas_mode")
            if self.degas_value is None or self.degas_value < 0:
                raise ValueError("degas_value must be >= 0")
            if self.degas_mode == "CO2 Removal" and self.degas_value > 100:
                raise ValueError("CO2 Removal must be 0..100%")
        if self.antiscalant_enabled:
            if not str(self.antiscalant_type or "").strip():
                raise ValueError("antiscalant_type is required when enabled")
            if self.antiscalant_dose_mg_l is None or self.antiscalant_dose_mg_l < 0:
                raise ValueError("antiscalant_dose_mg_l must be >= 0")
        if self.dechlorinator_enabled:
            if not str(self.dechlorinator_type or "").strip():
                raise ValueError("dechlorinator_type is required when enabled")
            if self.dechlorinator_dose_mg_l is None or self.dechlorinator_dose_mg_l < 0:
                raise ValueError("dechlorinator_dose_mg_l must be >= 0")
        if self.temperature_mode:
            mode = self.temperature_mode.strip().casefold()
            if mode not in {"minimum", "design", "maximum", "specify"}:
                raise ValueError(
                    "chemical temperature_mode must be Minimum/Design/Maximum/Specify"
                )
            if mode == "specify" and self.temperature_c is None:
                raise ValueError("chemical temperature_c is required for Specify")
            if self.temperature_c is not None and not (-5 <= self.temperature_c <= 60):
                raise ValueError("chemical temperature_c must be -5..60")
        elif self.temperature_c is not None:
            raise ValueError("chemical temperature_mode is required when temperature_c is set")
        if self.recovery_mode:
            mode = self.recovery_mode.strip().casefold()
            if mode not in {"basic default", "specify", "based on ro config"}:
                raise ValueError(
                    "chemical recovery_mode must be Basic default/Specify/Based on RO config"
                )
            if mode == "specify":
                if self.recovery_value_pct is None or not (0.1 <= self.recovery_value_pct < 100):
                    raise ValueError("chemical recovery_value_pct must be 0.1..<100 for Specify")
            elif self.recovery_value_pct is not None and not (0 <= self.recovery_value_pct < 100):
                raise ValueError("chemical recovery_value_pct must be 0..<100")
        elif self.recovery_value_pct is not None:
            raise ValueError("chemical recovery_mode is required when recovery_value_pct is set")


@dataclass
class ROSpecialFeaturesConfig:
    compaction_enabled: bool = False
    compaction_mode: Optional[str] = None
    compaction_value: Optional[float] = None
    toc_rejection_enabled: bool = False
    toc_rejection_pct: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return self.compaction_enabled or self.toc_rejection_enabled

    def validate(self) -> None:
        if self.compaction_enabled:
            if self.compaction_value is not None and self.compaction_value < 0:
                raise ValueError("compaction_value must be >= 0")
        if self.toc_rejection_enabled:
            if self.toc_rejection_pct is None or not (0 <= self.toc_rejection_pct <= 100):
                raise ValueError("toc_rejection_pct must be 0..100")


@dataclass
class ROCaseConfig:
    case_id: str
    pdf_name: str
    water_profile: str
    feed_flow_m3h: float
    feed_temperature_c: float  # Design temperature; kept for V19-V21 compatibility.
    passes: list[ROPassConfig]
    feed_temperature_min_c: Optional[float] = None
    feed_temperature_max_c: Optional[float] = None
    chemical: ROChemicalConfig = field(default_factory=ROChemicalConfig)
    special_features: ROSpecialFeaturesConfig = field(default_factory=ROSpecialFeaturesConfig)
    run_enabled: bool = True
    batch_order: int = 0
    batch_group: str = ""
    notes: str = ""
    source_row: int = 0

    @property
    def pass_count(self) -> int:
        return len(self.passes)

    @property
    def feed_temperature_design_c(self) -> float:
        return self.feed_temperature_c

    @property
    def resolved_feed_temperature_min_c(self) -> float:
        return (
            self.feed_temperature_c
            if self.feed_temperature_min_c is None
            else self.feed_temperature_min_c
        )

    @property
    def resolved_feed_temperature_max_c(self) -> float:
        return (
            self.feed_temperature_c
            if self.feed_temperature_max_c is None
            else self.feed_temperature_max_c
        )

    @property
    def automation_tier(self) -> str:
        complex_flow = any(
            any(
                value is not None
                for value in (
                    p.recycle_target_pass,
                    p.recycle_pct,
                    p.bypass_pct,
                    p.permeate_split_pct,
                    p.recycle_split_pass1_pct,
                    p.recycle_split_pass2_pct,
                )
            )
            for p in self.passes
        )
        has_chemistry = self.chemical.enabled
        has_special_features = self.special_features.enabled
        has_boost = any(
            s.boost_pressure_bar is not None for p in self.passes for s in p.stages
        )
        # Two-pass, boost pressure, and chemistry paths are video-derived but not
        # yet validated in a full unattended batch, so require explicit opt-in.
        if complex_flow or has_chemistry or has_special_features or has_boost or self.pass_count == 2:
            return "experimental"
        p = self.passes[0]
        s = p.stages[0]
        simple = (
            p.stage_count == 1
            and abs(p.flow_factor - 0.85) < 1e-9
            and abs(p.permeate_back_pressure_bar) < 1e-9
            and s.stage_back_pressure_bar is None
            and s.flow_factor is None
            and p.temperature_mode.strip().lower() == "specify"
        )
        return "stable" if simple else "new"

    def validate(self) -> None:
        if not self.case_id:
            raise ValueError("case_id is required")
        if not self.pdf_name:
            raise ValueError("pdf_name is required")
        if Path(self.pdf_name).suffix.lower() != ".pdf":
            raise ValueError("pdf_name must end with .pdf")
        if not self.water_profile:
            raise ValueError("water_profile is required")
        if self.feed_flow_m3h <= 0:
            raise ValueError("feed_flow_m3h must be > 0")
        tmin = self.resolved_feed_temperature_min_c
        tdesign = self.feed_temperature_design_c
        tmax = self.resolved_feed_temperature_max_c
        if not all(-5 <= value <= 60 for value in (tmin, tdesign, tmax)):
            raise ValueError("feed temperatures must be -5..60")
        if not (tmin <= tdesign <= tmax):
            raise ValueError(
                "feed temperature envelope must satisfy Minimum <= Design <= Maximum; "
                f"got {tmin}/{tdesign}/{tmax}"
            )
        if not (1 <= self.pass_count <= 2):
            raise ValueError("pass_count must be 1 or 2")
        for i, pass_config in enumerate(self.passes, start=1):
            pass_config.validate(f"pass{i}")
            expected = {
                "minimum": tmin,
                "design": tdesign,
                "maximum": tmax,
            }.get(pass_config.temperature_mode.strip().lower())
            if expected is not None and abs(pass_config.temperature_c - expected) > 0.06:
                raise ValueError(
                    f"pass{i}.temperature_c={pass_config.temperature_c} does not match "
                    f"{pass_config.temperature_mode} feed temperature {expected}"
                )
        self.chemical.validate()
        self.special_features.validate()

    def to_flat_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "case_id": self.case_id,
            "pdf_name": self.pdf_name,
            "water_profile": self.water_profile,
            "feed_flow_m3h": self.feed_flow_m3h,
            "feed_temperature_min_c": self.resolved_feed_temperature_min_c,
            "feed_temperature_design_c": self.feed_temperature_design_c,
            "feed_temperature_max_c": self.resolved_feed_temperature_max_c,
            "pass_count": self.pass_count,
            "automation_tier": self.automation_tier,
            "run_enabled": self.run_enabled,
            "batch_order": self.batch_order,
            "batch_group": self.batch_group,
            "notes": self.notes,
            "source_row": self.source_row,
        }
        for p_idx, p in enumerate(self.passes, start=1):
            prefix = f"pass{p_idx}_"
            result.update(
                {
                    prefix + "recovery_pct": p.recovery_pct,
                    prefix + "stage_count": p.stage_count,
                    prefix + "flow_factor": p.flow_factor,
                    prefix + "temperature_mode": p.temperature_mode,
                    prefix + "temperature_c": p.temperature_c,
                    prefix + "permeate_back_pressure_bar": p.permeate_back_pressure_bar,
                }
            )
            for s_idx, s in enumerate(p.stages, start=1):
                sp = f"p{p_idx}s{s_idx}_"
                result.update(
                    {
                        sp + "pv": s.pv,
                        sp + "elements_per_pv": s.elements_per_pv,
                        sp + "membrane": s.membrane,
                        sp + "stage_back_pressure_bar": s.stage_back_pressure_bar,
                        sp + "boost_pressure_bar": s.boost_pressure_bar,
                        sp + "flow_factor": s.flow_factor,
                    }
                )
        result.update(
            {
                "acid_enabled": self.chemical.acid_enabled,
                "acid_type": self.chemical.acid_type,
                "acid_target_ph": self.chemical.acid_target_ph,
                "degas_enabled": self.chemical.degas_enabled,
                "degas_mode": self.chemical.degas_mode,
                "degas_value": self.chemical.degas_value,
                "base_enabled": self.chemical.base_enabled,
                "base_type": self.chemical.base_type,
                "base_target_ph": self.chemical.base_target_ph,
                "antiscalant_enabled": self.chemical.antiscalant_enabled,
                "antiscalant_type": self.chemical.antiscalant_type,
                "antiscalant_dose_mg_l": self.chemical.antiscalant_dose_mg_l,
                "dechlorinator_enabled": self.chemical.dechlorinator_enabled,
                "dechlorinator_type": self.chemical.dechlorinator_type,
                "dechlorinator_dose_mg_l": self.chemical.dechlorinator_dose_mg_l,
                "chemical_temperature_mode": self.chemical.temperature_mode,
                "chemical_temperature_c": self.chemical.temperature_c,
                "chemical_recovery_mode": self.chemical.recovery_mode,
                "chemical_recovery_value_pct": self.chemical.recovery_value_pct,
                "compaction_enabled": self.special_features.compaction_enabled,
                "compaction_mode": self.special_features.compaction_mode,
                "compaction_value": self.special_features.compaction_value,
                "toc_rejection_enabled": self.special_features.toc_rejection_enabled,
                "toc_rejection_pct": self.special_features.toc_rejection_pct,
            }
        )
        return result

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any], source_row: int = 0) -> "ROCaseConfig":
        case_id = _as_text(_lookup(row, "Case_ID", "case_id", default=f"RO_ROW_{source_row:03d}"))
        pdf_name = _as_text(
            _lookup(row, "Recommended_PDF_Name", "pdf_name", default=f"{case_id}.pdf")
        )
        water_profile = _as_text(
            _lookup(row, "WAVE_Library_Selection", "water_profile", "feedwater_profile")
        )
        feed_flow = _as_float(
            _lookup(row, "Feed_Flow_m3h", "Flow_m3h", "feed_flow_m3h"), 100.0
        )
        legacy_temp = _as_float(_lookup(row, "Temperature_C", "temperature_c"), 25.0)
        feed_design = _as_float(
            _lookup(
                row,
                "Temperature_Design_C",
                "Feed_Temperature_Design_C",
                "feed_temperature_design_c",
            ),
            legacy_temp,
        )
        feed_min = _as_float(
            _lookup(
                row,
                "Temperature_Min_C",
                "Feed_Temperature_Min_C",
                "feed_temperature_min_c",
            ),
            feed_design,
        )
        feed_max = _as_float(
            _lookup(
                row,
                "Temperature_Max_C",
                "Feed_Temperature_Max_C",
                "feed_temperature_max_c",
            ),
            feed_design,
        )
        run_enabled = _as_bool(_lookup(row, "Run_Enabled", "run_enabled", default="Y"), True)
        order = _as_int(_lookup(row, "Batch_Order", "batch_order"), source_row) or source_row
        batch_group = _as_text(_lookup(row, "Batch_Group", "batch_group"))
        notes = _as_text(_lookup(row, "Notes", "notes"))

        pass_count = _as_int(_lookup(row, "Pass_Count", "pass_count"), None)
        if pass_count is None:
            pass_stage = _as_text(_lookup(row, "Pass_Stage", "pass_stage", default="1P/1S"))
            match = re.search(r"(\d+)\s*p", pass_stage, re.I)
            pass_count = int(match.group(1)) if match else 1
        pass_count = max(1, min(2, int(pass_count)))

        global_recovery = _as_float(_lookup(row, "Recovery_pct", "recovery_pct"), 75.0)
        global_pv = _as_int(_lookup(row, "PV", "pv_per_stage"), 10) or 10
        global_elements = _as_int(_lookup(row, "Elements_per_PV", "elements_per_pv"), 6) or 6
        global_membrane = _as_text(
            _lookup(row, "Membrane_Model", "membrane", default="BW30-400")
        )

        passes: list[ROPassConfig] = []
        for p_idx in range(1, pass_count + 1):
            p_recovery = _as_float(
                _lookup(row, f"Pass{p_idx}_Recovery_pct", f"P{p_idx}_Recovery_pct"),
                global_recovery if p_idx == 1 else 80.0,
            )
            stage_count = _as_int(
                _lookup(row, f"Pass{p_idx}_Stage_Count", f"P{p_idx}_Stage_Count"),
                1,
            ) or 1
            flow_factor = _as_float(
                _lookup(row, f"Pass{p_idx}_Flow_Factor", f"P{p_idx}_Flow_Factor"),
                0.85 if p_idx == 1 else 1.0,
            ) or (0.85 if p_idx == 1 else 1.0)
            temp_mode = _as_text(
                _lookup(row, f"Pass{p_idx}_Temperature_Mode", f"P{p_idx}_Temperature_Mode"),
                "Specify",
            )
            mode_default = {
                "minimum": feed_min,
                "design": feed_design,
                "maximum": feed_max,
            }.get(temp_mode.strip().lower(), feed_design)
            pass_temp = _as_float(
                _lookup(row, f"Pass{p_idx}_Temperature_C", f"P{p_idx}_Temperature_C"),
                mode_default,
            )
            back_pressure = _as_float(
                _lookup(
                    row,
                    f"Pass{p_idx}_Permeate_Back_Pressure_bar",
                    f"P{p_idx}_Permeate_Back_Pressure_bar",
                ),
                0.0,
            ) or 0.0

            stages: list[ROStageConfig] = []
            for s_idx in range(1, stage_count + 1):
                prefixes = (f"P{p_idx}S{s_idx}", f"Pass{p_idx}_Stage{s_idx}")

                def stage_lookup(*suffixes: str, default: Any = None) -> Any:
                    names: list[str] = []
                    for prefix in prefixes:
                        names.extend(f"{prefix}_{suffix}" for suffix in suffixes)
                    return _lookup(row, *names, default=default)

                stages.append(
                    ROStageConfig(
                        pv=_as_int(stage_lookup("PV"), global_pv) or global_pv,
                        elements_per_pv=_as_int(
                            stage_lookup("Elements_per_PV", "Elements"), global_elements
                        ) or global_elements,
                        membrane=_as_text(
                            stage_lookup("Membrane", "Membrane_Model"), global_membrane
                        ),
                        stage_back_pressure_bar=_as_float(
                            stage_lookup("Stage_Back_Pressure_bar"), None
                        ),
                        boost_pressure_bar=_as_float(
                            stage_lookup("Boost_Pressure_bar"), None
                        ),
                        flow_factor=_as_float(stage_lookup("Flow_Factor"), None),
                    )
                )

            passes.append(
                ROPassConfig(
                    recovery_pct=float(p_recovery),
                    stage_count=stage_count,
                    flow_factor=float(flow_factor),
                    temperature_mode=temp_mode,
                    temperature_c=float(pass_temp),
                    permeate_back_pressure_bar=float(back_pressure),
                    stages=stages,
                    recycle_target_pass=_as_int(
                        _lookup(row, f"Pass{p_idx}_Recycle_Target_Pass"), None
                    ),
                    recycle_pct=_as_float(_lookup(row, f"Pass{p_idx}_Recycle_pct"), None),
                    bypass_pct=_as_float(_lookup(row, f"Pass{p_idx}_Bypass_pct"), None),
                    permeate_split_pct=_as_float(
                        _lookup(row, f"Pass{p_idx}_Permeate_Split_pct"), None
                    ),
                    recycle_split_pass1_pct=_as_float(
                        _lookup(row, f"Pass{p_idx}_Recycle_Split_Pass1_pct"), None
                    ),
                    recycle_split_pass2_pct=_as_float(
                        _lookup(row, f"Pass{p_idx}_Recycle_Split_Pass2_pct"), None
                    ),
                )
            )

        acid_type_raw = _as_text(_lookup(row, "Acid_Type", "acid_type"))
        base_type_raw = _as_text(_lookup(row, "Base_Type", "base_type"))
        degas_mode_raw = _as_text(_lookup(row, "Degas_Mode", "degas_mode"))
        acid_alias = {
            "hcl32": "HCl (32)",
            "hcl(32)": "HCl (32)",
            "hcl (32)": "HCl (32)",
            "h2so498": "H2SO4 (98)",
            "h2so4(98)": "H2SO4 (98)",
            "h2so4 (98)": "H2SO4 (98)",
        }
        base_alias = {
            "naoh30": "NaOH (30)",
            "naoh(30)": "NaOH (30)",
            "naoh (30)": "NaOH (30)",
            "naoh50": "NaOH (50)",
            "naoh(50)": "NaOH (50)",
            "naoh (50)": "NaOH (50)",
        }
        degas_alias = {
            "co2removal": "CO2 Removal",
            "co2removalpct": "CO2 Removal",
            "co2partialpressure": "CO2 Partial Pressure",
            "co2concentration": "CO2 Concentration",
        }
        temp_mode_alias = {
            "minimum": "Minimum",
            "min": "Minimum",
            "design": "Design",
            "maximum": "Maximum",
            "max": "Maximum",
            "specify": "Specify",
            "specified": "Specify",
        }
        recovery_mode_alias = {
            "basicdefault": "Basic default",
            "default": "Basic default",
            "specify": "Specify",
            "specified": "Specify",
            "basedonroconfig": "Based on RO config",
            "roconfig": "Based on RO config",
        }
        acid_type = acid_alias.get(_clean_key(acid_type_raw), acid_type_raw or None)
        base_type = base_alias.get(_clean_key(base_type_raw), base_type_raw or None)
        degas_mode = degas_alias.get(_clean_key(degas_mode_raw), degas_mode_raw or None)
        antiscalant_type = _as_text(
            _lookup(row, "Antiscalant_Type", "AntiScalant_Type", "anti_scalant_type")
        ) or None
        dechlorinator_type = _as_text(
            _lookup(row, "Dechlorinator_Type", "dechlorinator_type")
        ) or None
        chemical_temp_raw = _as_text(
            _lookup(
                row,
                "Chemical_Temperature_Mode",
                "Chemical_Adjustment_Temperature_Mode",
                "chemical_temperature_mode",
            )
        )
        chemical_recovery_raw = _as_text(
            _lookup(
                row,
                "Chemical_Recovery_Mode",
                "Chemical_Adjustment_Recovery_Mode",
                "chemical_recovery_mode",
            )
        )
        chemical_temp_mode = temp_mode_alias.get(
            _clean_key(chemical_temp_raw), chemical_temp_raw or None
        )
        chemical_recovery_mode = recovery_mode_alias.get(
            _clean_key(chemical_recovery_raw), chemical_recovery_raw or None
        )

        chemical = ROChemicalConfig(
            acid_enabled=_as_bool(_lookup(row, "Acid_Enabled"), bool(acid_type)),
            acid_type=acid_type,
            acid_target_ph=_as_float(_lookup(row, "Acid_Target_pH"), None),
            degas_enabled=_as_bool(_lookup(row, "Degas_Enabled"), bool(degas_mode)),
            degas_mode=degas_mode,
            degas_value=_as_float(_lookup(row, "Degas_Value"), None),
            base_enabled=_as_bool(_lookup(row, "Base_Enabled"), bool(base_type)),
            base_type=base_type,
            base_target_ph=_as_float(_lookup(row, "Base_Target_pH"), None),
            antiscalant_enabled=_as_bool(
                _lookup(row, "Antiscalant_Enabled", "AntiScalant_Enabled"),
                bool(antiscalant_type),
            ),
            antiscalant_type=antiscalant_type,
            antiscalant_dose_mg_l=_as_float(
                _lookup(
                    row,
                    "Antiscalant_Dose_mgL",
                    "Antiscalant_Dose_mg_L",
                    "AntiScalant_Dose_mgL",
                ),
                None,
            ),
            dechlorinator_enabled=_as_bool(
                _lookup(row, "Dechlorinator_Enabled"), bool(dechlorinator_type)
            ),
            dechlorinator_type=dechlorinator_type,
            dechlorinator_dose_mg_l=_as_float(
                _lookup(
                    row,
                    "Dechlorinator_Dose_mgL",
                    "Dechlorinator_Dose_mg_L",
                ),
                None,
            ),
            temperature_mode=chemical_temp_mode,
            temperature_c=_as_float(
                _lookup(
                    row,
                    "Chemical_Temperature_C",
                    "Chemical_Adjustment_Temperature_C",
                ),
                None,
            ),
            recovery_mode=chemical_recovery_mode,
            recovery_value_pct=_as_float(
                _lookup(
                    row,
                    "Chemical_Recovery_pct",
                    "Chemical_Recovery_Value",
                    "Chemical_Adjustment_Recovery_pct",
                ),
                None,
            ),
        )
        special_features = ROSpecialFeaturesConfig(
            compaction_enabled=_as_bool(_lookup(row, "Compaction_Enabled"), False),
            compaction_mode=_as_text(_lookup(row, "Compaction_Mode")) or None,
            compaction_value=_as_float(_lookup(row, "Compaction_Value"), None),
            toc_rejection_enabled=_as_bool(
                _lookup(
                    row,
                    "RO_TOC_Rejection_Enabled",
                    "TOC_Rejection_Enabled",
                ),
                _lookup(
                    row,
                    "RO_TOC_Rejection_pct",
                    "TOC_Rejection_pct",
                    default=None,
                ) not in (None, ""),
            ),
            toc_rejection_pct=_as_float(
                _lookup(
                    row,
                    "RO_TOC_Rejection_pct",
                    "TOC_Rejection_pct",
                ),
                None,
            ),
        )

        case = cls(
            case_id=case_id,
            pdf_name=pdf_name,
            water_profile=water_profile,
            feed_flow_m3h=float(feed_flow),
            feed_temperature_c=float(feed_design),
            feed_temperature_min_c=float(feed_min),
            feed_temperature_max_c=float(feed_max),
            passes=passes,
            chemical=chemical,
            special_features=special_features,
            run_enabled=run_enabled,
            batch_order=order,
            batch_group=batch_group,
            notes=notes,
            source_row=source_row,
        )
        case.validate()
        return case


__all__ = [
    "ROStageConfig",
    "ROPassConfig",
    "ROChemicalConfig",
    "ROSpecialFeaturesConfig",
    "ROCaseConfig",
]
