# app/schemas/membrane.py
from typing import Optional, Literal, Dict
from pydantic import Field
from .common import AppBaseModel


class MembraneSpec(AppBaseModel):
    id: str
    name: Optional[str] = None
    vendor: Optional[str] = None
    family: Optional[str] = None
    size: Optional[str] = None

    # Membrane Type (BWRO, SWRO 추가)
    type: Optional[Literal["RO", "BWRO", "SWRO", "HRRO", "NF", "UF", "MF"]] = "RO"

    # Physical Dimensions
    area_m2: Optional[float] = Field(
        None, description="Active surface area per element"
    )

    # Performance Parameters
    A_lmh_bar: Optional[float] = Field(
        None, description="Water permeability coefficient"
    )

    # Salt Permeability: Support both units
    B_lmh: Optional[float] = Field(
        None, description="Salt permeability (L/m²/h) - Primary"
    )
    B_mps: Optional[float] = Field(
        None, description="Salt permeability (m/s) - Legacy/Scientific"
    )

    salt_rejection_pct: Optional[float] = Field(
        None, description="Nominal salt rejection (%)"
    )

    ion_rejections: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Specific ion rejection rates (e.g., {'na': 0.992, 'ca': 0.998})",
    )


class MembraneOut(MembraneSpec):
    pass
