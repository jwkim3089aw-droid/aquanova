#!/usr/bin/env python3
"""Offline regression checks for V52 post-Flow stage restoration."""
from __future__ import annotations

from pathlib import Path

engine = Path(__file__).with_name("wave_ro_engine.py").read_text(encoding="utf-8")

assert "def _restore_stage_topologies_after_flow_commit(" in engine
assert "def _stabilize_after_flow_commit(" in engine
assert "ro_stage_topology_reassert_v44" in engine
assert "if pass_config.stage_count <= 1" in engine
assert "_configure_stage_grid(" in engine
assert 'context="post_recovery_v44"' in engine
assert "integrity_cycle_{integrity_cycle}_v44" in engine

# The stabilizer must restore topology before coordinate-based temperature and
# operating-input verification.  This order prevents expected two-stage points
# from aliasing onto a one-stage table after Flow Calculator closes.
start = engine.index("def _stabilize_after_flow_commit(")
end = engine.index("def configure_schema_ro_case(", start)
body = engine[start:end]
assert body.index("_restore_stage_topologies_after_flow_commit(") < body.index("_reassert_global_temperature_after_flow_commit(")
assert body.index("_reassert_global_temperature_after_flow_commit(") < body.index("_verify_case_operating_inputs(")

print("V52 stage-topology reassert self-test OK")
