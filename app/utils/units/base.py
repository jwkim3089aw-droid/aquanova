# app/utils/units/base.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any

# ==========================================
# 1. 변환 계수 상수화 (유지보수 및 가독성 향상)
# ==========================================
FLOW_M3H_TO_GPM = 4.402867
PRESS_BAR_TO_PSI = 14.5037738
FLUX_LMH_TO_GFD = 0.588579


# ==========================================
# 2. 기본 데이터 클래스
# ==========================================
@dataclass
class Units:
    flow: str = "m3/h"  # m3/h | gpm
    pressure: str = "bar"  # bar | psi
    temperature: str = "C"  # C | F
    flux: str = "LMH"  # LMH | gfd


def _lin(scale: float, offset: float = 0.0) -> Dict[str, float]:
    """선형 변환 계수 딕셔너리 반환 헬퍼 함수"""
    return {"scale": float(scale), "offset": float(offset)}


# ==========================================
# 3. 변환 맵 생성 핵심 로직
# ==========================================
def compute_conversions(u: Units) -> Dict[str, Any]:
    res = {
        "flow": {"engine": "m3/h"},
        "pressure": {"engine": "bar"},
        "temperature": {"engine": "C"},
        "flux": {"engine": "LMH"},
    }

    # 1) Flow
    if (u.flow or "").strip().lower() == "gpm":
        res["flow"].update(
            {
                "display": "gpm",
                "to_display": _lin(FLOW_M3H_TO_GPM),
                "from_display": _lin(1 / FLOW_M3H_TO_GPM),
            }
        )
    else:
        res["flow"].update(
            {"display": "m3/h", "to_display": _lin(1.0), "from_display": _lin(1.0)}
        )

    # 2) Pressure
    if (u.pressure or "").strip().lower() == "psi":
        res["pressure"].update(
            {
                "display": "psi",
                "to_display": _lin(PRESS_BAR_TO_PSI),
                "from_display": _lin(1 / PRESS_BAR_TO_PSI),
            }
        )
    else:
        res["pressure"].update(
            {"display": "bar", "to_display": _lin(1.0), "from_display": _lin(1.0)}
        )

    # 3) Temperature
    if (u.temperature or "").strip().upper() == "F":
        res["temperature"].update(
            {
                "display": "F",
                "to_display": _lin(9 / 5, 32),
                "from_display": _lin(5 / 9, -32 * 5 / 9),
            }
        )
    else:
        res["temperature"].update(
            {"display": "C", "to_display": _lin(1.0), "from_display": _lin(1.0)}
        )

    # 4) Flux
    if (u.flux or "").strip().lower() == "gfd":
        res["flux"].update(
            {
                "display": "gfd",
                "to_display": _lin(FLUX_LMH_TO_GFD),
                "from_display": _lin(1 / FLUX_LMH_TO_GFD),
            }
        )
    else:
        res["flux"].update(
            {"display": "LMH", "to_display": _lin(1.0), "from_display": _lin(1.0)}
        )

    return res
