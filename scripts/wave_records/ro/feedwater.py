from __future__ import annotations

"""Planned home for RO feedwater helpers. V135 scaffold only."""

# V138_RO_FEEDWATER_HAS_FLOW_OPTIMIZATION_APPLIED

def _has_flow_optimization(pass_config: ROPassConfig) -> bool:
    return any(
        value is not None
        for value in (
            pass_config.recycle_target_pass,
            pass_config.recycle_pct,
            pass_config.bypass_pct,
            pass_config.permeate_split_pct,
            pass_config.recycle_split_pass1_pct,
            pass_config.recycle_split_pass2_pct,
        )
    )
