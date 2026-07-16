"""Batch retry/recovery classification helpers.

V132 extracted low-risk retry/recovery helpers from ``wave_batch_legacy.py``.
The legacy module imports these names back for compatibility.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

def _classify_constraint_adjusted_recovery(
    errors: list[str],
    recovery_details: dict[str, Any],
    constraint_warnings: dict[str, Any],
) -> dict[str, Any]:
    """Identify a valid WAVE result whose achieved recovery differs by constraint.

    This is intentionally fail-closed.  A case is classified as
    ``constraint_adjusted`` only when every non-recovery PDF check passed,
    WAVE printed at least one design or solubility warning, and the printed/flow-derived
    recovery evidence is physically valid and mutually consistent.
    """
    recovery_errors = [key for key in errors if re.fullmatch(r"pass\d+_recovery", key)]
    other_errors = [key for key in errors if key not in recovery_errors]
    result: dict[str, Any] = {
        "eligible": False,
        "recovery_errors": recovery_errors,
        "other_errors": other_errors,
        "warning_count": int(constraint_warnings.get("count", 0) or 0),
        "passes": {},
    }
    if not recovery_errors or other_errors or result["warning_count"] <= 0:
        return result

    all_consistent = True
    for key in recovery_errors:
        pass_info = dict((recovery_details.get("passes") or {}).get(key) or {})
        observed = list(pass_info.get("observed") or [])
        values = [float(item["value"]) for item in observed if item.get("value") is not None]
        physical = bool(values) and all(0.0 < value < 100.0 for value in values)
        spread = (max(values) - min(values)) if values else None
        consistent = physical and (spread is not None) and spread <= 0.35 + 1e-9
        preferred = next(
            (float(item["value"]) for item in observed if item.get("source") == "Pass Recovery"),
            values[0] if values else None,
        )
        expected = float(pass_info.get("expected_input_target", 0.0))
        result["passes"][key] = {
            "requested_recovery_pct": expected,
            "achieved_recovery_pct": preferred,
            "deviation_pct_points": (preferred - expected) if preferred is not None else None,
            "evidence_values": values,
            "evidence_spread_pct_points": spread,
            "physical": physical,
            "consistent": consistent,
        }
        all_consistent = all_consistent and consistent

    result["eligible"] = all_consistent
    result["reason"] = (
        "WAVE report is internally consistent, all configured topology/input checks passed, "
        "and WAVE design/solubility warnings explain why achieved recovery differs from the requested target."
        if all_consistent
        else "Recovery evidence was missing, nonphysical, or internally inconsistent."
    )
    return result
