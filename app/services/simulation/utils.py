# app/services/simulation/utils.py
# ✅ Simulation Utilities (Clean + Safe)
# - 기본 단위/보정 유틸
# - Global chemistry -> stage.chemistry injection (Pydantic v2-safe)
# - "utils.py" 파일이 이미 있으므로, utils/ 디렉토리 만들지 않음(이 파일이 정답 위치)

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.transport import viscosity_water_pa_s

# ============================================================
# Constants
# ============================================================
R_BAR_L_PER_MOL_K = 0.08314
P_PERM_BAR = 0.0  # permeate side backpressure (assumption)
DEFAULT_REF_TEMP_C = 25.0  # standard reference temperature


# ============================================================
# Basic helpers
# ============================================================
def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x to [lo, hi]."""
    return max(lo, min(hi, x))


def mps_to_lmh(J_mps: float) -> float:
    """Convert flux from m/s to LMH."""
    return (float(J_mps) * 1000.0) * 3600.0


def lmh_to_mps(J_lmh: float) -> float:
    """Convert flux from LMH to m/s."""
    return (float(J_lmh) / 1000.0) / 3600.0


def temp_correct_A(
    A_ref: float, temp_C: float, ref_C: float = DEFAULT_REF_TEMP_C
) -> float:
    """
    Temperature correction for A using viscosity ratio.
    - Higher temperature -> lower viscosity -> higher permeability (A increases).
    """
    mu = viscosity_water_pa_s(float(temp_C))
    mu_ref = viscosity_water_pa_s(float(ref_C))
    return float(A_ref) * (mu_ref / max(mu, 1e-12))


# ============================================================
# ✅ Global chemistry -> stage.chemistry injection
# ============================================================
def _to_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Convert chemistry object into a serializable dict payload.
    Accepts:
      - dict
      - Pydantic v2 model (model_dump)
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        return obj

    # Pydantic v2 model
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            return None

    return None


def inject_global_chemistry_into_stages(request: Any) -> Any:
    """
    Inject request.chemistry into each stage.chemistry if stage.chemistry is None.
    - stage-level chemistry overrides global chemistry
    - Works with Pydantic v2 models (model_copy/update)
    - Safe no-op if fields don't exist

    Expected shape:
      request.chemistry: Optional[WaterChemistryInput]
      request.stages: List[StageConfig]
      stage.chemistry: Optional[Dict[str, Any]]   (added to StageConfig)
    """
    payload = _to_payload(getattr(request, "chemistry", None))
    if payload is None:
        return request

    stages = getattr(request, "stages", None)
    if not stages:
        return request

    new_stages = []
    for s in stages:
        # If StageConfig has no "chemistry" field (old schema), skip safely.
        if not hasattr(s, "chemistry"):
            new_stages.append(s)
            continue

        if getattr(s, "chemistry", None) is None:
            mc = getattr(s, "model_copy", None)
            if callable(mc):
                new_stages.append(mc(update={"chemistry": payload}))
            else:
                # best-effort fallback: mutate (rare path)
                try:
                    setattr(s, "chemistry", payload)
                except Exception:
                    pass
                new_stages.append(s)
        else:
            new_stages.append(s)

    # return updated request
    mc_req = getattr(request, "model_copy", None)
    if callable(mc_req):
        return mc_req(update={"stages": new_stages})

    # best-effort fallback: mutate
    try:
        request.stages = new_stages
    except Exception:
        pass
    return request
