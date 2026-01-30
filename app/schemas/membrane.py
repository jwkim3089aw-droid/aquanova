# app\schemas\membrane.py
from typing import Optional
from .common import AppBaseModel


class MembraneSpec(AppBaseModel):
    id: str
    name: Optional[str] = None
    vendor: Optional[str] = None
    area_m2: Optional[float] = None
    A_lmh_bar: Optional[float] = None
    B_mps: Optional[float] = None
    salt_rejection_pct: Optional[float] = None


class MembraneOut(MembraneSpec):
    pass
