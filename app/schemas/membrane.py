# app/schemas/membrane.py
from typing import Optional, Literal
from pydantic import Field
from .common import AppBaseModel


class MembraneSpec(AppBaseModel):
    id: str
    name: Optional[str] = None
    vendor: Optional[str] = None

    # Membrane Type (RO, NF, HRRO, etc.)
    type: Optional[Literal["RO", "NF", "UF", "MF", "HRRO"]] = "RO"

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


class MembraneOut(MembraneSpec):
    pass
