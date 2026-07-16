"""Offline structural regression checks for V52 idempotent case-state reconciliation."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent
uia = (ROOT / "wave_uia.py").read_text(encoding="utf-8")
engine = (ROOT / "wave_ro_engine.py").read_text(encoding="utf-8")
batch = (ROOT / "wave_batch.py").read_text(encoding="utf-8")
for token in ("function ModeActive($label)", "function SetModeState", "chemical_state_reconciliation", "mode_state_before", "mode_state_after_reset", "Based on RO config", "already_selected"):
    assert token in uia, token
assert "_force_chemical_reconcile" in engine
assert "chemical_case_state_reconciliation_v45" in batch
assert 'setattr(case, "_force_chemical_reconcile", True)' in batch
print("V52 idempotent Chemical state reconciliation self-test OK")
