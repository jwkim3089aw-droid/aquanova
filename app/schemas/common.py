# app/schemas/common.py
from enum import Enum
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """모든 모델의 부모 클래스: V2 설정 적용"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        from_attributes=True,
    )


class ModuleType(str, Enum):
    RO = "RO"
    HRRO = "HRRO"
    PRO = "PRO"
    NF = "NF"
    MF = "MF"
    UF = "UF"


class FeedWaterType(str, Enum):
    SEAWATER = "Seawater"
    BRACKISH = "Brackish"
    SURFACE = "Surface"
    GROUNDWATER = "Groundwater"
    WASTEWATER = "Wastewater"
    OTHER = "Other"


class UnitsSettingsIn(AppBaseModel):
    flow: Literal["m3/h", "gpm"] = "m3/h"
    pressure: Literal["bar", "psi"] = "bar"
    temperature: Literal["C", "F"] = "C"
    flux: Literal["LMH", "gfd"] = "LMH"


class UnitsSettingsOut(UnitsSettingsIn):
    id: str
    # 💡 [핵심 수정] float 대신 Any를 사용하여 복잡한 변환 객체 파싱 에러(500) 원천 차단
    conversions: dict[str, Any] = {}
