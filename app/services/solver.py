# app/services/solver.py
from __future__ import annotations
from typing import Callable

def secant(func: Callable[[float], float], x0: float, x1: float, tol: float = 1e-4, maxit: int = 30) -> float:
    f0, f1 = func(x0), func(x1)
    for _ in range(maxit):
        denom = (f1 - f0)
        if abs(denom) < 1e-12:
            return x1
        x2 = x1 - f1 * (x1 - x0) / denom
        if abs(x2 - x1) < tol:
            return x2
        x0, x1, f0, f1 = x1, x2, f1, func(x2)
    return x1
