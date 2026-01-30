# ./app/services/units.py

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Units:
    flow: str = "m3/h"       # m3/h | gpm
    pressure: str = "bar"    # bar | psi
    temperature: str = "C"   # C | F
    flux: str = "LMH"        # LMH | gfd

def _lin(scale: float, offset: float = 0.0) -> dict:
    return {"scale": float(scale), "offset": float(offset)}

def compute_conversions(u: Units) -> dict:
    res = {
        "flow":       {"engine": "m3/h"},
        "pressure":   {"engine": "bar"},
        "temperature":{"engine": "C"},
        "flux":       {"engine": "LMH"},
    }
    if (u.flow or "").lower() == "gpm":
        res["flow"].update({"display":"gpm","to_display":_lin(4.402867),"from_display":_lin(1/4.402867)})
    else:
        res["flow"].update({"display":"m3/h","to_display":_lin(1.0),"from_display":_lin(1.0)})

    if (u.pressure or "").lower() == "psi":
        res["pressure"].update({"display":"psi","to_display":_lin(14.5037738),"from_display":_lin(1/14.5037738)})
    else:
        res["pressure"].update({"display":"bar","to_display":_lin(1.0),"from_display":_lin(1.0)})

    if (u.temperature or "").upper() == "F":
        res["temperature"].update({"display":"F","to_display":_lin(9/5,32),"from_display":_lin(5/9,-32*5/9)})
    else:
        res["temperature"].update({"display":"C","to_display":_lin(1.0),"from_display":_lin(1.0)})

    if (u.flux or "").lower() == "gfd":
        res["flux"].update({"display":"gfd","to_display":_lin(0.588579),"from_display":_lin(1/0.588579)})
    else:
        res["flux"].update({"display":"LMH","to_display":_lin(1.0),"from_display":_lin(1.0)})
    return res
