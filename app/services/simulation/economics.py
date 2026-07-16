# app/services/simulation/economics.py
from __future__ import annotations
from typing import List, Dict, Any
from app.schemas.simulation import ChemicalDosingItem, OpexConfig


def calculate_opex(
    sec_kwhm3: float,
    dosing_items: List[ChemicalDosingItem],
    product_flow_m3h: float,
    config: OpexConfig,  # 🟢 [NEW] 프론트엔드에서 보낸 설정 객체 수신
) -> Dict[str, Any]:
    """
    [경제성 분석 엔진]
    시스템의 비에너지(SEC)와 약품 소모량을 기반으로 톤당 생산 원가(OPEX)를 산출합니다.
    """
    CURRENCY_SYMBOL = "$"

    if product_flow_m3h <= 1e-9:
        return {
            "unit_cost": 0.0,
            "energy_cost_per_m3": 0.0,
            "chem_cost_per_m3": 0.0,
            "energy_portion_pct": 0.0,
            "chem_portion_pct": 0.0,
            "daily_total_cost": 0.0,
            "currency": CURRENCY_SYMBOL,
        }

    # 1. 전력 비용 산출 ($/m³)
    # 🟢 [PATCH] 사용자가 입력한 전력 단가 적용
    energy_cost_per_m3 = sec_kwhm3 * config.electricity_price_kwh

    # 2. 약품 비용 산출 ($/일 -> $/m³)
    total_chem_daily_cost = 0.0
    for item in dosing_items:
        # 🟢 [PATCH] 약품 종류에 따른 커스텀 단가 적용
        if "스케일" in item.purpose or "Antiscalant" in item.purpose:
            unit_price = config.antiscalant_price_kg
        else:
            unit_price = config.acid_base_price_kg

        total_chem_daily_cost += item.usage_kg_day * unit_price

    daily_production_m3 = product_flow_m3h * 24.0
    chem_cost_per_m3 = (
        total_chem_daily_cost / daily_production_m3 if daily_production_m3 > 0 else 0.0
    )

    # 3. 총합 및 비중 분석
    unit_cost = energy_cost_per_m3 + chem_cost_per_m3
    daily_total_cost = unit_cost * daily_production_m3

    energy_pct = (energy_cost_per_m3 / unit_cost * 100.0) if unit_cost > 0 else 0.0
    chem_pct = (chem_cost_per_m3 / unit_cost * 100.0) if unit_cost > 0 else 0.0

    return {
        "unit_cost": round(unit_cost, 3),
        "energy_cost_per_m3": round(energy_cost_per_m3, 3),
        "chem_cost_per_m3": round(chem_cost_per_m3, 3),
        "energy_portion_pct": round(energy_pct, 1),
        "chem_portion_pct": round(chem_pct, 1),
        "daily_total_cost": round(daily_total_cost, 2),
        "currency": CURRENCY_SYMBOL,
    }
