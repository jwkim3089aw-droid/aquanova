# app/services/physics/solver.py
from __future__ import annotations
from typing import Callable
from loguru import logger
import math


def secant(
    func: Callable[[float], float],
    x0: float,
    x1: float,
    tol: float = 1e-4,
    maxit: int = 30,
) -> float:
    """
    할선법(Secant Method)을 이용하여 비선형 방정식의 해(Root)를 찾습니다.
    막 여과 시뮬레이션(RO/NF 등)에서 플럭스와 삼투압의 수렴 계산에 주로 사용됩니다.
    """
    f0, f1 = func(x0), func(x1)

    for i in range(maxit):
        denom = f1 - f0
        if abs(denom) < 1e-12:
            return x1
        x2 = x1 - f1 * (x1 - x0) / denom
        if abs(x2 - x1) < tol:
            return x2
        x0, x1, f0, f1 = x1, x2, f1, func(x2)

    logger.warning(
        f"Secant method failed to converge within {maxit} iterations. Returning best guess: {x1}"
    )
    return x1


def calc_spacer_k_mt(velocity_m_s: float, temperature_C: float) -> float:
    """
    [WAVE/ROSA Standard] 나선형 멤브레인 스페이서 물질 전달 계수 (k_mt)
    정석 상관식: Sh = 0.065 * Re^0.875 * Sc^0.25
    """
    T_K = temperature_C + 273.15

    # 1. 물의 동점성 계수 (nu, m^2/s) - 온도 보정
    nu = 1.0e-6 * math.exp(1500.0 * (1.0 / T_K - 1.0 / 298.15))

    # 2. 염(NaCl) 확산 계수 (D, m^2/s)
    # WAVE 해수 표준 확산계수(1.6e-9 @ 25°C) 및 Stokes-Einstein 보정
    D_298 = 1.6e-9
    nu_298 = 1.0e-6
    D = D_298 * (T_K / 298.15) * (nu_298 / nu)

    # 3. 스페이서 기하학 (Hydraulic Diameter)
    d_h = 0.00085  # 표준 34mil 스페이서 두께 (0.85 mm)

    # 4. 무차원 수 (Re, Sc)
    Re = max(1e-3, (velocity_m_s * d_h) / nu)
    Sc = max(1.0, nu / D)

    # 5. Sherwood Number (난류 촉진 효과 적용)
    Sh = 0.065 * (Re**0.875) * (Sc**0.25)

    # 6. 질량 전달 계수
    k_mt = (Sh * D) / d_h
    return max(k_mt, 1e-6)
