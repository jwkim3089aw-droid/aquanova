# app/services/simulation/engine.py
from __future__ import annotations

import json
import os
import re
import uuid
import math
from pathlib import Path
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.schemas.simulation import (
    FeedInput,
    KPIOut,
    ModuleType,
    ScenarioOutput,
    SimulationRequest,
    StageMetric,
    StreamOut,
    WaterChemistryOut,
    MassBalanceOut,
    SimulationWarning,
    ChemicalDosingOut,
    ChemicalDosingItem,
    IonCompositionInput,
)
from app.services.simulation.utils import inject_global_chemistry_into_stages
from app.services.simulation.modules.hrro import HRROModule
from app.services.simulation.modules.mf import MFModule
from app.services.simulation.modules.nf import NFModule
from app.services.simulation.modules.ro import ROModule
from app.services.simulation.modules.uf import UFModule
from app.data.membranes import MEMBRANES

try:
    from app.services.chemistry import (
        calc_scaling_indices,
        ChemistryProfile,
        scale_profile_for_tds,
        apply_balance_makeup,
        calculate_ph_adjustment,
        calculate_antiscalant_dosing,
    )
    from app.services.chemistry.dosing import calculate_borate_fraction
    from app.services.simulation.economics import calculate_opex

    HAS_EXTENSIONS = True
except ImportError:
    HAS_EXTENSIONS = False

PRESSURE_MEMBRANE_TYPES = frozenset({ModuleType.RO, ModuleType.NF, ModuleType.HRRO})
NEXT_FEED_STREAM_KIND = {
    ModuleType.UF: "permeate",
    ModuleType.MF: "permeate",
    ModuleType.RO: "concentrate",
    ModuleType.NF: "concentrate",
    ModuleType.HRRO: "concentrate",
}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (ValueError, TypeError):
        return float(default)


def _r(v: Any, ndigits: int, default: float = 0.0) -> float:
    return round(_f(v, default), ndigits)


def safe_arr(v: Any) -> List:
    return v if isinstance(v, list) else []


@dataclass(frozen=True)
class _ResolvedStream:
    flow_m3h: float
    tds_mgL: float
    pressure_bar: float = 0.0
    ions: Optional[Dict[str, float]] = None
    ph: float = 7.0


@dataclass
class EngineContext:
    request: SimulationRequest
    initial_ph: float = 7.0
    current_feed: Optional[FeedInput] = None
    current_chem_prof: Optional["ChemistryProfile"] = None
    dosing_items: List[ChemicalDosingItem] = field(default_factory=list)
    dosing_warnings: List[str] = field(default_factory=list)
    stage_metrics: List[StageMetric] = field(default_factory=list)
    stage_types: List[ModuleType] = field(default_factory=list)
    stage_passes: List[int] = field(default_factory=list)
    resolved_streams: List[Dict[str, _ResolvedStream]] = field(default_factory=list)
    # Product-side branches that leave an upstream pass instead of feeding the
    # next pass (for example a 50% permeate split).  Each item carries the
    # stream plus representative flux/NDP for system KPI weighting.
    product_branches: List[Dict[str, Any]] = field(default_factory=list)
    total_power_kw: float = 0.0
    feed_flow: float = 0.0
    feed_tds: float = 0.0
    prod_flow: float = 0.0
    prod_tds: float = 0.0
    avg_flux: float = 0.0
    avg_ndp: float = 0.0
    sys_waste_flow: float = 0.0
    sys_waste_salt: float = 0.0
    brine_tds: float = 0.0
    sys_recovery: float = 0.0
    sys_sec: float = 0.0
    sys_chemistry: Optional[WaterChemistryOut] = None


class MembraneTuner:
    """Resolve membrane properties without overwriting explicit user/tuner values.

    Precedence is:
      explicit StageConfig values > generated regime calibration > membrane catalog > safe defaults.
    """

    CALIBRATION_PATH = Path(
        os.getenv(
            "AQUANOVA_CALIBRATION_PATH",
            ".data/autotuner_regime_constants.json",
        )
    )
    _calibration_cache: Optional[Dict[str, Any]] = None
    _calibration_mtime_ns: Optional[int] = None

    _TUNING_KEYS = frozenset(
        {
            "membrane_A_lmh_bar",
            "membrane_B_lmh",
            "A_correction_factor",
            "A_corr",
            "B_correction_factor",
            "B_corr",
            "cp_tuning_factor",
            "cp_adjustment_factor",
            "dp_per_elem_bar",
            "dp_module_bar",
            "dp_correlation_enabled",
            "dp_correlation_multiplier",
            "b_salinity_slope",
            "fouling_factor",
            "B_fouling_factor",
            "temp_corr_factor_A",
            "temp_corr_factor_B",
        }
    )

    _ALIASES = {
        "A_correction_factor": {"A_correction_factor", "A_corr"},
        "B_correction_factor": {"B_correction_factor", "B_corr"},
        "cp_tuning_factor": {"cp_tuning_factor", "cp_adjustment_factor"},
        "cp_adjustment_factor": {"cp_tuning_factor", "cp_adjustment_factor"},
        "dp_per_elem_bar": {"dp_per_elem_bar", "dp_module_bar"},
        "dp_module_bar": {"dp_per_elem_bar", "dp_module_bar"},
        "dp_correlation_multiplier": {"dp_correlation_multiplier"},
        "b_salinity_slope": {"b_salinity_slope", "hrro_B_sal_slope"},
    }

    @classmethod
    def apply_tuning(cls, stage_conf: Any, feed: Optional[FeedInput] = None) -> None:
        raw_m_id = cls._get_value(stage_conf, "membrane_model")
        if not raw_m_id:
            return

        explicit_keys = cls._explicit_keys(stage_conf)
        regime = cls._determine_regime(stage_conf, feed)
        m_type = cls._get_value(stage_conf, "module_type", ModuleType.RO)
        process_type = cls._process_type(m_type)

        mem_spec = cls._resolve_catalog_spec(str(raw_m_id), regime)
        if mem_spec:
            cls._inject_physical_properties(stage_conf, mem_spec, explicit_keys)
            cls._inject_catalog_values(stage_conf, mem_spec, explicit_keys)
            cls._inject_chemistry_rejections(stage_conf, mem_spec)

        calibrated = cls._find_external_calibration(
            str(raw_m_id), process_type, regime
        )
        if calibrated:
            cls._inject_calibrated_values(stage_conf, calibrated, explicit_keys)
            cls._set_value(stage_conf, "tuning_source", "regime_calibration")
        elif mem_spec:
            cls._set_value(stage_conf, "tuning_source", "membrane_catalog")
        else:
            cls._set_value(stage_conf, "tuning_source", "stage_defaults")

        cls._set_value(stage_conf, "tuning_regime", regime)

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    @classmethod
    def _get_value(cls, conf: Any, key: str, default: Any = None) -> Any:
        if isinstance(conf, dict):
            return conf.get(key, default)

        extras = getattr(conf, "model_extra", None)
        if isinstance(extras, dict) and key in extras:
            return extras[key]

        pydantic_extras = getattr(conf, "__pydantic_extra__", None)
        if isinstance(pydantic_extras, dict) and key in pydantic_extras:
            return pydantic_extras[key]

        value = getattr(conf, key, None)
        if value is not None:
            return value

        cfg = getattr(conf, "cfg", None)
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        if cfg is not None:
            value = getattr(cfg, key, None)
            if value is not None:
                return value
        return default

    @classmethod
    def _set_value(cls, conf: Any, key: str, value: Any) -> None:
        if isinstance(conf, dict):
            conf[key] = value
            injected = conf.setdefault("_tuner_injected_values", {})
            if isinstance(injected, dict):
                injected[key] = value
            return

        try:
            setattr(conf, key, value)
        except Exception:
            pass

        cfg = getattr(conf, "cfg", None)
        if isinstance(cfg, dict):
            cfg[key] = value
            injected = cfg.setdefault("_tuner_injected_values", {})
            if isinstance(injected, dict):
                injected[key] = value
        elif cfg is not None:
            try:
                setattr(cfg, key, value)
            except Exception:
                pass

        # For unknown extra fields, Pydantic may store the value here after setattr.
        # Known schema fields must not be duplicated into model_extra because that
        # would make a later engine pass look like new user input.
        if not hasattr(type(conf), key):
            extras = getattr(conf, "model_extra", None)
            if isinstance(extras, dict):
                extras[key] = value

    @staticmethod
    def _values_equal(left: Any, right: Any) -> bool:
        try:
            return abs(float(left) - float(right)) <= 1e-12
        except (TypeError, ValueError):
            return left == right

    @classmethod
    def _explicit_keys(cls, conf: Any) -> set[str]:
        keys: set[str] = set()
        injected_values: Dict[str, Any] = {}

        if isinstance(conf, dict):
            raw_injected = conf.get("_tuner_injected_values", {})
            if isinstance(raw_injected, dict):
                injected_values = raw_injected
            for key, value in conf.items():
                if key == "_tuner_injected_values":
                    continue
                if key in injected_values and cls._values_equal(
                    value, injected_values[key]
                ):
                    continue
                keys.add(key)
        else:
            cfg = getattr(conf, "cfg", None)
            if isinstance(cfg, dict):
                raw_injected = cfg.get("_tuner_injected_values", {})
                if isinstance(raw_injected, dict):
                    injected_values = raw_injected

            # Pydantic's field set is the strongest signal of constructor input.
            # Engine-injected fields are removed only when their current value still
            # matches the value recorded by the tuner.
            for key in (getattr(conf, "model_fields_set", set()) or set()):
                current = getattr(conf, key, None)
                if key in injected_values and cls._values_equal(
                    current, injected_values[key]
                ):
                    continue
                keys.add(key)

            for attr_name in ("model_extra", "__pydantic_extra__"):
                container = getattr(conf, attr_name, None)
                if not isinstance(container, dict):
                    continue
                for key, value in container.items():
                    if key in injected_values and cls._values_equal(
                        value, injected_values[key]
                    ):
                        continue
                    keys.add(key)

            if isinstance(cfg, dict):
                for key, value in cfg.items():
                    if key == "_tuner_injected_values":
                        continue
                    if key in injected_values and cls._values_equal(
                        value, injected_values[key]
                    ):
                        continue
                    keys.add(key)

            # Also recognize values injected by external code after construction.
            non_default_values = {
                "membrane_A_lmh_bar": None,
                "membrane_B_lmh": None,
                "A_correction_factor": 1.0,
                "B_correction_factor": 1.0,
                "cp_tuning_factor": None,
                "cp_adjustment_factor": None,
                "dp_per_elem_bar": None,
                "dp_module_bar": None,
                "fouling_factor": None,
                "B_fouling_factor": None,
            }
            for key, default in non_default_values.items():
                value = getattr(conf, key, None)
                if key in injected_values and cls._values_equal(
                    value, injected_values[key]
                ):
                    continue
                if value is not None and (default is None or value != default):
                    keys.add(key)

        if bool(cls._get_value(conf, "tuning_locked", False)):
            keys.update(cls._TUNING_KEYS)
        return keys

    @classmethod
    def _is_explicit(cls, explicit_keys: set[str], key: str) -> bool:
        aliases = cls._ALIASES.get(key, {key})
        return bool(aliases.intersection(explicit_keys))

    @staticmethod
    def _process_type(module_type: Any) -> str:
        value = getattr(module_type, "value", module_type)
        return str(value).split(".")[-1].upper()

    @classmethod
    def _determine_regime(
        cls, stage_conf: Any, feed: Optional[FeedInput]
    ) -> str:
        explicit_regime = str(
            cls._get_value(stage_conf, "tuning_regime") or ""
        ).strip().upper()
        # Calibration and optimization requests lock an explicit regime.  Do
        # not reject newly introduced, physically named V4 regimes.
        if bool(cls._get_value(stage_conf, "tuning_locked", False)) and explicit_regime:
            return explicit_regime

        tds = _f(getattr(feed, "tds_mgL", None), 0.0) if feed is not None else 0.0
        recovery = _f(cls._get_value(stage_conf, "recovery_target_pct", 0.0), 0.0)
        pass_idx = int(_f(cls._get_value(stage_conf, "pass_idx", 1), 1))
        source_name = str(cls._get_value(stage_conf, "source_file", "")).upper()
        process_type = cls._process_type(
            cls._get_value(stage_conf, "module_type", ModuleType.RO)
        )
        system_pass_count = int(
            _f(cls._get_value(stage_conf, "system_pass_count", pass_idx), pass_idx)
        )
        system_stage_count = int(
            _f(cls._get_value(stage_conf, "system_stage_count", 1), 1)
        )
        is_multi_pass = system_pass_count > 1 or pass_idx > 1 or "2PASS" in source_name
        is_multi_stage = system_stage_count > system_pass_count and not is_multi_pass

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
        if _f(cls._get_value(stage_conf, "flow_factor", 1.0), 1.0) <= 0.75 or any(
            token in source_name for token in special_tokens
        ):
            return "LOW_TDS_SPECIAL"
        return "LOW_TDS_STANDARD"

    @classmethod
    def _resolve_catalog_spec(cls, raw_id: str, regime: str) -> Optional[Dict]:
        spec = cls._find_membrane_spec(f"{raw_id} [{regime}]")
        return spec or cls._find_membrane_spec(raw_id)

    @classmethod
    def _find_membrane_spec(cls, raw_id: str) -> Optional[Dict]:
        search_key = cls._normalize(raw_id)
        if not search_key:
            return None

        candidates = []
        for membrane in MEMBRANES:
            keys = {
                cls._normalize(membrane.get("id")),
                cls._normalize(membrane.get("name")),
            }
            for alias in membrane.get("aliases", []) or []:
                keys.add(cls._normalize(alias))
            keys.discard("")
            candidates.append((membrane, keys))
            if search_key in keys:
                return membrane

        # WAVE reports often omit catalog descriptors such as '(Standard)' or
        # trademarks. Accept a unique containment match after exact matching.
        fuzzy = []
        for membrane, keys in candidates:
            if any(
                min(len(search_key), len(key)) >= 8
                and (search_key in key or key in search_key)
                for key in keys
            ):
                fuzzy.append(membrane)
        return fuzzy[0] if len(fuzzy) == 1 else None

    @classmethod
    def _load_calibration(cls) -> Dict[str, Any]:
        path = cls.CALIBRATION_PATH
        try:
            stat = path.stat()
        except OSError:
            cls._calibration_cache = {}
            cls._calibration_mtime_ns = None
            return {}

        if (
            cls._calibration_cache is not None
            and cls._calibration_mtime_ns == stat.st_mtime_ns
        ):
            return cls._calibration_cache

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
        except Exception as exc:
            logger.warning(f"Failed to load membrane calibration {path}: {exc}")
            payload = {}

        cls._calibration_cache = payload
        cls._calibration_mtime_ns = stat.st_mtime_ns
        return payload

    @classmethod
    def _find_external_calibration(
        cls, model_name: str, process_type: str, regime: str
    ) -> Optional[Dict[str, float]]:
        groups = cls._load_calibration().get("groups", {})
        if not isinstance(groups, dict):
            return None

        normalized_model = cls._normalize(model_name)
        for group in groups.values():
            if not isinstance(group, dict):
                continue
            if cls._normalize(group.get("model_name")) != normalized_model:
                continue
            if str(group.get("process_type", "")).upper() != process_type:
                continue
            if str(group.get("regime", "")).upper() != regime:
                continue
            params = group.get("parameters")
            return params if isinstance(params, dict) else None
        return None

    @classmethod
    def _inject_physical_properties(
        cls, conf: Any, spec: Dict, explicit_keys: set[str]
    ) -> None:
        base_area = _f(spec.get("area_m2"), 0.0)
        current_area = _f(cls._get_value(conf, "membrane_area_m2", 0.0), 0.0)
        # StageConfig derives a generic area in an after-validator and may add it
        # to model_fields_set. Treat known generic defaults as non-explicit.
        generic_defaults = (20.0, 37.16, 77.0)
        is_generic_default = any(abs(current_area - value) <= 1e-9 for value in generic_defaults)
        if base_area > 0.0 and (
            not cls._is_explicit(explicit_keys, "membrane_area_m2")
            or is_generic_default
        ):
            cls._set_value(conf, "membrane_area_m2", base_area)

    @classmethod
    def _inject_catalog_values(
        cls, conf: Any, spec: Dict, explicit_keys: set[str]
    ) -> None:
        if not cls._is_explicit(explicit_keys, "membrane_A_lmh_bar"):
            catalog_a = _f(spec.get("A_lmh_bar"), 0.0)
            if catalog_a > 0.0:
                cls._set_value(conf, "membrane_A_lmh_bar", catalog_a)
        if not cls._is_explicit(explicit_keys, "membrane_B_lmh"):
            catalog_b = _f(spec.get("B_lmh"), 0.0)
            if catalog_b <= 0.0:
                catalog_b = _f(spec.get("B_mps"), 0.0) * 3.6e6
            if catalog_b > 0.0:
                cls._set_value(conf, "membrane_B_lmh", catalog_b)

        safe_defaults = {
            "temp_corr_factor_A": 2640.0,
            "temp_corr_factor_B": 4860.0,
            "cp_tuning_factor": 1.0,
            "fouling_factor": 1.0,
            "B_fouling_factor": 1.0,
            "dp_per_elem_bar": 0.15,
        }
        for key, default_value in safe_defaults.items():
            if cls._is_explicit(explicit_keys, key):
                continue
            value = spec.get(key, default_value)
            if key == "dp_per_elem_bar":
                cls._set_value(conf, "dp_per_elem_bar", _f(value, default_value))
                cls._set_value(conf, "dp_module_bar", _f(value, default_value))
            elif key == "cp_tuning_factor":
                cls._set_value(conf, "cp_tuning_factor", _f(value, default_value))
                cls._set_value(conf, "cp_adjustment_factor", _f(value, default_value))
            else:
                cls._set_value(conf, key, _f(value, default_value))

        correction_mapping = {
            "A_correction_factor": ("A_correction_factor",),
            "B_correction_factor": ("B_correction_factor",),
            "cp_adjustment_factor": (
                "cp_adjustment_factor",
                "cp_tuning_factor",
            ),
            "dp_per_elem_bar": ("dp_per_elem_bar", "dp_module_bar"),
            "dp_correlation_multiplier": ("dp_correlation_multiplier",),
            "b_salinity_slope": ("b_salinity_slope", "hrro_B_sal_slope"),
        }
        for spec_key, target_keys in correction_mapping.items():
            if spec_key not in spec or cls._is_explicit(explicit_keys, spec_key):
                continue
            value = _f(spec[spec_key], 1.0)
            for target_key in target_keys:
                cls._set_value(conf, target_key, value)

    @classmethod
    def _inject_calibrated_values(
        cls, conf: Any, params: Dict[str, Any], explicit_keys: set[str]
    ) -> None:
        mapping = {
            "A_correction_factor": ("A_correction_factor",),
            "B_correction_factor": ("B_correction_factor",),
            "cp_adjustment_factor": (
                "cp_adjustment_factor",
                "cp_tuning_factor",
            ),
            "dp_per_elem_bar": ("dp_per_elem_bar", "dp_module_bar"),
            "dp_correlation_multiplier": ("dp_correlation_multiplier",),
            "b_salinity_slope": ("b_salinity_slope", "hrro_B_sal_slope"),
        }
        for source_key, target_keys in mapping.items():
            if source_key not in params or cls._is_explicit(explicit_keys, source_key):
                continue
            value = float(params[source_key])
            for target_key in target_keys:
                cls._set_value(conf, target_key, value)

        if (
            "dp_correlation_multiplier" in params
            and not cls._is_explicit(explicit_keys, "dp_correlation_enabled")
        ):
            cls._set_value(conf, "dp_correlation_enabled", True)

    @classmethod
    def _inject_chemistry_rejections(cls, conf: Any, spec: Dict) -> None:
        ion_rejections = spec.get("ion_rejections")
        if not isinstance(ion_rejections, dict):
            return

        calib_ions = spec.get("calib_ion_multipliers", {})
        current = cls._get_value(conf, "chemistry", {})
        chemistry = dict(current) if isinstance(current, dict) else {}
        rejections = dict(chemistry.get("rejections", {}))
        for ion, base_value in ion_rejections.items():
            rejections.setdefault(
                ion,
                min(0.9999, float(base_value) * float(calib_ions.get(ion, 1.0))),
            )
        chemistry["rejections"] = rejections
        cls._set_value(conf, "chemistry", chemistry)


class SimulationEngine:
    def __init__(self) -> None:
        self.modules = {
            ModuleType.RO: ROModule(),
            ModuleType.HRRO: HRROModule(),
            ModuleType.NF: NFModule(),
            ModuleType.UF: UFModule(),
            ModuleType.MF: MFModule(),
        }

    def run(self, request: SimulationRequest) -> ScenarioOutput:
        request = inject_global_chemistry_into_stages(request)
        if not request.stages:
            return self._empty_result(request)
        ctx = self._initialize_context(request)
        self._apply_ph_dosing(ctx)
        self._execute_stages(ctx)
        self._aggregate_system_kpis(ctx)
        self._apply_antiscalant_dosing(ctx)
        opex = self._calculate_economics(ctx) if HAS_EXTENSIONS else {}
        return self._build_final_output(ctx, opex)

    def _initialize_context(self, request: SimulationRequest) -> EngineContext:
        ctx = EngineContext(
            request=request,
            initial_ph=_f(request.feed.ph, 7.0),
            current_feed=request.feed,
        )
        ctx.feed_flow = _f(request.feed.flow_m3h)
        ctx.feed_tds = _f(request.feed.tds_mgL)
        if HAS_EXTENSIONS:
            ctx.current_chem_prof = self._build_base_chem_profile(ctx.current_feed)
        return ctx

    @staticmethod
    def _blend_streams(streams: List[_ResolvedStream]) -> _ResolvedStream:
        if not streams:
            return _ResolvedStream(flow_m3h=0.0, tds_mgL=0.0)
        total_flow = sum(max(0.0, _f(stream.flow_m3h)) for stream in streams)
        if total_flow <= 1e-12:
            return streams[-1]
        tds = sum(_f(stream.flow_m3h) * _f(stream.tds_mgL) for stream in streams) / total_flow
        ion_mass: Dict[str, float] = {}
        for stream in streams:
            if not isinstance(stream.ions, dict):
                continue
            for key, value in stream.ions.items():
                ion_mass[key] = ion_mass.get(key, 0.0) + _f(stream.flow_m3h) * _f(value)
        ions = {key: mass / total_flow for key, mass in ion_mass.items()} if ion_mass else None
        return _ResolvedStream(
            flow_m3h=total_flow,
            tds_mgL=tds,
            pressure_bar=0.0,
            ions=ions,
            ph=streams[-1].ph,
        )

    @staticmethod
    def _scale_stream_flow(stream: _ResolvedStream, fraction: float) -> _ResolvedStream:
        fraction = max(0.0, min(float(fraction), 1.0))
        return replace(stream, flow_m3h=max(0.0, _f(stream.flow_m3h) * fraction))

    def _execute_stages(self, ctx: EngineContext) -> None:
        pass_permeates: List[_ResolvedStream] = []
        system_pass_count = max(
            [int(_f(getattr(stage, "pass_idx", 1), 1)) for stage in ctx.request.stages]
            or [1]
        )
        system_stage_count = len(ctx.request.stages)

        for idx, stage_conf in enumerate(ctx.request.stages):
            MembraneTuner._set_value(stage_conf, "system_pass_count", system_pass_count)
            MembraneTuner._set_value(stage_conf, "system_stage_count", system_stage_count)
            handler = self.modules.get(stage_conf.module_type)
            if not handler:
                continue

            current_pass = max(1, int(_f(getattr(stage_conf, "pass_idx", 1), 1)))
            MembraneTuner.apply_tuning(stage_conf, ctx.current_feed)

            if (
                ctx.current_chem_prof
                and stage_conf.module_type in PRESSURE_MEMBRANE_TYPES
            ):
                current_ph, current_temp = _f(ctx.current_feed.ph, 7.5), _f(
                    ctx.current_feed.temperature_C, 25.0
                )
                borate_frac = calculate_borate_fraction(current_ph, current_temp)
                if not hasattr(stage_conf, "chemistry") or not stage_conf.chemistry:
                    stage_conf.chemistry = {"rejections": {}}
                if (
                    isinstance(stage_conf.chemistry, dict)
                    and "rejections" in stage_conf.chemistry
                ):
                    stage_conf.chemistry["rejections"]["b"] = (borate_frac * 0.995) + (
                        (1.0 - borate_frac) * 0.40
                    )
                ctx.current_feed.chemistry = self._prof_to_dict(ctx.current_chem_prof)

            metric = handler.compute(stage_conf, ctx.current_feed)
            if metric is None:
                continue

            metric.stage = idx + 1
            ctx.stage_metrics.append(metric)
            ctx.stage_types.append(stage_conf.module_type)
            ctx.stage_passes.append(current_pass)

            if metric.sec_kwhm3 and metric.Qp:
                ctx.total_power_kw += metric.sec_kwhm3 * metric.Qp
            cache = {
                "feed": self._stream_from_metric(metric, "feed"),
                "permeate": self._stream_from_metric(metric, "permeate"),
                "concentrate": self._stream_from_metric(metric, "concentrate"),
            }
            cache["permeate"] = replace(
                cache["permeate"], ph=_f(ctx.current_feed.ph, 7.0)
            )
            ctx.resolved_streams.append(cache)

            if stage_conf.module_type in PRESSURE_MEMBRANE_TYPES:
                pass_permeates.append(cache["permeate"])

            if idx + 1 >= len(ctx.request.stages):
                continue

            next_conf = ctx.request.stages[idx + 1]
            next_pass = max(1, int(_f(getattr(next_conf, "pass_idx", current_pass), current_pass)))
            if next_pass > current_pass:
                upstream_product = self._blend_streams(pass_permeates)
                pass_permeates = []

                route_fraction = max(
                    0.0,
                    min(
                        _f(getattr(next_conf, "pass_feed_fraction", 1.0), 1.0),
                        1.0,
                    ),
                )
                target_stream = self._scale_stream_flow(upstream_product, route_fraction)

                if (
                    route_fraction < 1.0 - 1e-12
                    and bool(getattr(next_conf, "split_remainder_to_product", False))
                ):
                    branch = self._scale_stream_flow(upstream_product, 1.0 - route_fraction)
                    if branch.flow_m3h > 1e-12:
                        ctx.product_branches.append(
                            {
                                "stream": branch,
                                "flux_lmh": _f(metric.flux_lmh),
                                "ndp_bar": _f(metric.ndp_bar),
                                "source_pass": current_pass,
                            }
                        )

                target_ph = (
                    getattr(ctx.request.feed.dosing, "pass2_target_ph", None)
                    if next_pass == 2 and getattr(ctx.request.feed, "dosing", None)
                    else None
                )
                self._relay_ions_to_next_stage(ctx, target_stream, target_ph=target_ph)
            else:
                next_kind = NEXT_FEED_STREAM_KIND.get(stage_conf.module_type, "concentrate")
                self._relay_ions_to_next_stage(ctx, cache[next_kind])

    def _relay_ions_to_next_stage(
        self,
        ctx: EngineContext,
        target_stream: _ResolvedStream,
        target_ph: Optional[float] = None,
    ) -> None:
        if ctx.current_chem_prof:
            if target_stream.ions:
                for ion_key, ion_val in target_stream.ions.items():
                    if hasattr(ctx.current_chem_prof, f"{ion_key.lower()}_mgL"):
                        setattr(
                            ctx.current_chem_prof, f"{ion_key.lower()}_mgL", _f(ion_val)
                        )
                ctx.current_chem_prof.tds_mgL = _f(target_stream.tds_mgL)
            else:
                ctx.current_chem_prof = scale_profile_for_tds(
                    ctx.current_chem_prof, _f(target_stream.tds_mgL)
                )

            ctx.current_chem_prof.ph = (
                _f(target_ph) if target_ph is not None else target_stream.ph
            )
            next_ions_input = IonCompositionInput(
                **{
                    k.replace("_mgL", "").capitalize(): v
                    for k, v in vars(ctx.current_chem_prof).items()
                    if k.endswith("_mgL") and v is not None
                }
            )
        else:
            next_ions_input = None

        ctx.current_feed = FeedInput(
            flow_m3h=_f(target_stream.flow_m3h),
            tds_mgL=_f(target_stream.tds_mgL),
            temperature_C=ctx.current_feed.temperature_C,
            ph=(
                ctx.current_chem_prof.ph
                if ctx.current_chem_prof
                else (_f(target_ph) if target_ph is not None else target_stream.ph)
            ),
            pressure_bar=_f(target_stream.pressure_bar),
            chemistry=ctx.current_feed.chemistry,
            ions=next_ions_input,
        )

    def _stream_from_metric(self, metric: StageMetric, kind: str) -> _ResolvedStream:
        k = str(kind or "").strip().lower()
        chem_streams = (
            getattr(metric, "chemistry", {}).get("streams", {})
            if getattr(metric, "chemistry", None)
            else {}
        )
        for tk in (
            ("permeate", "product")
            if k == "permeate"
            else (("concentrate", "brine") if k == "concentrate" else ("feed",))
        ):
            if tk in chem_streams:
                node = chem_streams[tk]
                return _ResolvedStream(
                    flow_m3h=_f(node.get("flow_m3h")),
                    tds_mgL=_f(node.get("tds_mgL")),
                    pressure_bar=_f(node.get("pressure_bar", 0.0)),
                    ions=node.get("ions"),
                )
        return _ResolvedStream(
            flow_m3h=_f(
                metric.Qp
                if k == "permeate"
                else (metric.Qf if k == "feed" else metric.Qc)
            ),
            tds_mgL=_f(
                metric.Cp
                if k == "permeate"
                else (metric.Cf if k == "feed" else metric.Cc)
            ),
            pressure_bar=_f(
                0.0
                if k == "permeate"
                else (metric.p_in_bar if k == "feed" else metric.p_out_bar)
            ),
        )

    def _apply_ph_dosing(self, ctx: EngineContext) -> None:
        if not HAS_EXTENSIONS or not ctx.current_chem_prof:
            return
        ctx.current_chem_prof = apply_balance_makeup(ctx.current_chem_prof)
        dosing = getattr(ctx.request.feed, "dosing", None)
        target_ph = getattr(dosing, "target_ph", None)
        if target_ph is not None and abs(ctx.initial_ph - target_ph) > 0.01:
            ph_res = calculate_ph_adjustment(
                ctx.current_chem_prof,
                target_ph,
                acid_type=getattr(dosing, "acid_type", "H2SO4"),
                base_type=getattr(dosing, "base_type", "NaOH"),
            )
            dose = float(ph_res.get("dose_mgL", 0))
            if dose > 0:
                ctx.dosing_items.append(
                    ChemicalDosingItem(
                        chemical_name=ph_res["chemical"],
                        purpose="pH Adjustment",
                        dose_mgL=dose,
                        usage_kg_day=round(
                            (ctx.current_feed.flow_m3h * dose * 24.0) / 1e3, 3
                        ),
                    )
                )
                ctx.current_chem_prof.ph = target_ph
        ctx.current_feed.tds_mgL, ctx.current_feed.ph = (
            ctx.current_chem_prof.tds_mgL,
            ctx.current_chem_prof.ph,
        )

    def _apply_antiscalant_dosing(self, ctx: EngineContext) -> None:
        if (
            not HAS_EXTENSIONS
            or not getattr(ctx, "sys_chemistry", None)
            or not ctx.sys_chemistry.final_brine
        ):
            return
        if not getattr(
            getattr(ctx.request.feed, "dosing", None), "antiscalant_enabled", False
        ):
            return
        indices = (
            ctx.sys_chemistry.final_brine.model_dump()
            if hasattr(ctx.sys_chemistry.final_brine, "model_dump")
            else vars(ctx.sys_chemistry.final_brine)
        )
        anti_res = calculate_antiscalant_dosing(indices)
        if anti_res.get("required"):
            ctx.dosing_items.append(
                ChemicalDosingItem(
                    chemical_name=anti_res.get("chemical", "Antiscalant"),
                    purpose="Scaling Control",
                    dose_mgL=float(anti_res["dose_mgL"]),
                    usage_kg_day=round(
                        (ctx.feed_flow * float(anti_res["dose_mgL"]) * 24.0) / 1e3, 3
                    ),
                )
            )
            ctx.dosing_warnings.extend(anti_res.get("warnings", []))

    def _aggregate_system_kpis(self, ctx: EngineContext) -> None:
        ctx.prod_flow, ctx.prod_tds, ctx.avg_flux, ctx.avg_ndp = (
            self._aggregate_system_product(
                ctx.stage_types,
                ctx.stage_passes,
                ctx.stage_metrics,
                ctx.resolved_streams,
                ctx.request.feed,
                ctx.product_branches,
            )
        )
        for i, res in enumerate(ctx.resolved_streams):
            current_pass = ctx.stage_passes[i] if i < len(ctx.stage_passes) else 1
            next_pass = (
                ctx.stage_passes[i + 1]
                if i + 1 < len(ctx.stage_passes)
                else current_pass + 1
            )
            is_pass_end = i == len(ctx.resolved_streams) - 1 or next_pass > current_pass
            concentrate_is_waste = (
                is_pass_end
                or NEXT_FEED_STREAM_KIND.get(ctx.stage_types[i], "concentrate")
                == "permeate"
            )
            if concentrate_is_waste:
                ctx.sys_waste_flow += _f(res["concentrate"].flow_m3h)
                ctx.sys_waste_salt += _f(res["concentrate"].flow_m3h) * _f(
                    res["concentrate"].tds_mgL
                )
        ctx.brine_tds = (
            (ctx.sys_waste_salt / ctx.sys_waste_flow)
            if ctx.sys_waste_flow > 1e-9
            else 0.0
        )
        ctx.sys_recovery = (
            (ctx.prod_flow / ctx.feed_flow * 100.0) if ctx.feed_flow > 0 else 0.0
        )
        ctx.sys_sec = (
            (ctx.total_power_kw / ctx.prod_flow) if ctx.prod_flow > 1e-9 else 0.0
        )
        if HAS_EXTENSIONS:
            try:
                feed_prof = self._build_base_chem_profile(ctx.request.feed)
                ctx.sys_chemistry = WaterChemistryOut(
                    feed=calc_scaling_indices(feed_prof),
                    final_brine=calc_scaling_indices(
                        scale_profile_for_tds(feed_prof, ctx.brine_tds)
                    ),
                )
            except Exception:
                pass

    def _aggregate_system_product(
        self,
        stage_types,
        stage_passes,
        stage_metrics,
        resolved_streams,
        feed,
        product_branches=None,
    ) -> Tuple[float, float, float, float]:
        p_idxs = [i for i, t in enumerate(stage_types) if t in PRESSURE_MEMBRANE_TYPES]
        if p_idxs:
            final_pass = max(stage_passes[i] if i < len(stage_passes) else 1 for i in p_idxs)
            if final_pass > 1:
                p_idxs = [
                    i for i in p_idxs
                    if (stage_passes[i] if i < len(stage_passes) else 1) == final_pass
                ]
        if not p_idxs:
            return (
                _f(resolved_streams[-1]["permeate"].flow_m3h),
                _f(resolved_streams[-1]["permeate"].tds_mgL, feed.tds_mgL),
                0.0,
                0.0,
            )
        q_p, tds_sum, flux_sum, ndp_sum, weight_sum = 0.0, 0.0, 0.0, 0.0, 0.0
        for i in p_idxs:
            m, stream = stage_metrics[i], resolved_streams[i]["permeate"]
            q = _f(stream.flow_m3h)
            q_p += q
            weight_sum += q
            tds_sum += q * _f(stream.tds_mgL)
            flux_sum += q * _f(m.flux_lmh)
            ndp_sum += q * _f(m.ndp_bar)

        for item in product_branches or []:
            stream = item.get("stream") if isinstance(item, dict) else None
            if not isinstance(stream, _ResolvedStream):
                continue
            q = _f(stream.flow_m3h)
            q_p += q
            weight_sum += q
            tds_sum += q * _f(stream.tds_mgL)
            flux_sum += q * _f(item.get("flux_lmh"))
            ndp_sum += q * _f(item.get("ndp_bar"))

        w = max(weight_sum, 1e-9)
        return q_p, tds_sum / w, flux_sum / w, ndp_sum / w

    def _calculate_economics(self, ctx: EngineContext) -> Dict:
        from app.schemas.simulation import OpexConfig

        opex_raw = ctx.request.opex_config
        return calculate_opex(
            ctx.sys_sec,
            ctx.dosing_items,
            ctx.prod_flow,
            (
                OpexConfig(**opex_raw)
                if isinstance(opex_raw, dict)
                else (opex_raw or OpexConfig())
            ),
        )

    def _build_final_output(self, ctx: EngineContext, opex: Dict) -> ScenarioOutput:
        return ScenarioOutput(
            scenario_id=ctx.request.simulation_id or str(uuid.uuid4()),
            streams=[
                StreamOut(
                    label="Feed",
                    flow_m3h=ctx.feed_flow,
                    tds_mgL=ctx.feed_tds,
                    ph=ctx.initial_ph,
                    pressure_bar=_f(ctx.request.feed.pressure_bar),
                    temperature_C=ctx.request.feed.temperature_C,
                ),
                StreamOut(
                    label="Product",
                    flow_m3h=_r(ctx.prod_flow, 2),
                    tds_mgL=_r(ctx.prod_tds, 2),
                    ph=ctx.current_feed.ph,
                    pressure_bar=0.0,
                    temperature_C=ctx.request.feed.temperature_C,
                ),
                StreamOut(
                    label="Brine",
                    flow_m3h=_r(ctx.sys_waste_flow, 2),
                    tds_mgL=_r(ctx.brine_tds, 2),
                    ph=ctx.current_feed.ph,
                    pressure_bar=0.0,
                    temperature_C=ctx.request.feed.temperature_C,
                ),
            ],
            kpi=KPIOut(
                recovery_pct=_r(ctx.sys_recovery, 2),
                flux_lmh=_r(ctx.avg_flux, 1),
                ndp_bar=_r(ctx.avg_ndp, 2),
                sec_kwhm3=_r(ctx.sys_sec, 3),
                prod_tds=_r(ctx.prod_tds, 2),
                feed_m3h=ctx.feed_flow,
                permeate_m3h=_r(ctx.prod_flow, 6),
                mass_balance=self._calc_mass_balance(
                    ctx.feed_flow,
                    ctx.feed_tds,
                    ctx.prod_flow,
                    ctx.prod_tds,
                    ctx.sys_waste_flow,
                    ctx.brine_tds,
                ),
                unit_cost=opex.get("unit_cost", 0.0),
                currency=opex.get("currency", "$"),
            ),
            stage_metrics=ctx.stage_metrics,
            chemistry=ctx.sys_chemistry,
            economics=opex,
            dosing=ChemicalDosingOut(
                dosing_items=ctx.dosing_items,
                initial_ph=ctx.initial_ph,
                actual_ph=ctx.current_feed.ph,
                target_ph=getattr(
                    getattr(ctx.request.feed, "dosing", None), "target_ph", None
                ),
                warnings=ctx.dosing_warnings,
            ),
            warnings=self._extract_warnings(ctx.stage_metrics),
        )

    def _calc_mass_balance(self, qf, cf, qp, cp, qb, cb) -> MassBalanceOut:
        f_err = qf - (qp + qb)
        s_err_g = (qf * cf) - ((qp * cp) + (qb * cb))
        return MassBalanceOut(
            flow_error_m3h=round(f_err, 4),
            flow_error_pct=round((f_err / max(1e-9, qf)) * 100, 2),
            salt_error_kgh=round(s_err_g / 1000.0, 4),
            salt_error_pct=round((s_err_g / max(1e-9, qf * cf)) * 100, 2),
            system_rejection_pct=round((1.0 - cp / max(1e-9, cf)) * 100.0, 2),
            is_balanced=abs(f_err) < 0.01,
        )

    def _build_base_chem_profile(self, feed: FeedInput) -> ChemistryProfile:
        prof = ChemistryProfile(
            tds_mgL=_f(feed.tds_mgL),
            temperature_C=_f(feed.temperature_C),
            ph=_f(feed.ph),
        )
        if feed.ions:
            for ion in [
                "Na",
                "K",
                "Ca",
                "Mg",
                "NH4",
                "Ba",
                "Sr",
                "Fe",
                "Mn",
                "Al",
                "Cl",
                "SO4",
                "HCO3",
                "NO3",
                "F",
                "SiO2",
                "B",
            ]:
                setattr(
                    prof, f"{ion.lower()}_mgL", _f(getattr(feed.ions, ion, None), 0.0)
                )
        return prof

    def _prof_to_dict(self, p: ChemistryProfile) -> Dict[str, float]:
        return {
            k.replace("_mgL", ""): _f(v)
            for k, v in vars(p).items()
            if k.endswith("_mgL")
        }

    def _extract_warnings(self, metrics: List[StageMetric]) -> List[SimulationWarning]:
        warnings = []
        for m in metrics:
            for v in safe_arr(
                (getattr(m, "chemistry", {}) or {}).get("violations", [])
            ):
                warnings.append(
                    SimulationWarning(
                        stage=f"Stage {m.stage}",
                        module_type=m.module_type,
                        key=v.get("key", "unknown"),
                        message=v.get("message", ""),
                        value=v.get("value"),
                        limit=v.get("limit"),
                        unit=v.get("unit", ""),
                    )
                )
            if getattr(m, "warnings", None):
                warnings.extend(m.warnings)
        return warnings

    def _empty_result(self, request: SimulationRequest) -> ScenarioOutput:
        return ScenarioOutput(
            scenario_id=request.simulation_id or str(uuid.uuid4()),
            streams=[],
            kpi=KPIOut(
                recovery_pct=0.0,
                flux_lmh=0.0,
                ndp_bar=0.0,
                sec_kwhm3=0.0,
                feed_m3h=_f(request.feed.flow_m3h),
                permeate_m3h=0.0,
                prod_tds=0.0,
            ),
        )
