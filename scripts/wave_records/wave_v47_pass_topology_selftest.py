#!/usr/bin/env python3
"""Static/offline regression checks for V52 pass topology reconciliation."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
uia = (HERE / "wave_uia.py").read_text(encoding="utf-8")
engine = (HERE / "wave_ro_engine.py").read_text(encoding="utf-8")
batch = (HERE / "wave_batch.py").read_text(encoding="utf-8")

assert "def uia_reconcile_ro_pass_count" in uia
assert "delete_pass2_button_not_found" in uia
assert "pass_count_verify_failed_actual_" in uia
assert "uia_ro_pass_count_reconcile_v52" in uia
assert "def _reconcile_ro_pass_topology" in engine
assert "_reconcile_ro_pass_topology(" in engine
assert "RO Pass 상태 정규화 성공" in engine
assert "한 배치에서 Pass_Count 변경은 안전하게 초기화할 수 없어" not in batch
assert "def _pdf_detect_pass_count" in batch
assert '"pass_count_exact": pass_count_exact' in batch
assert '"pass_topology_validation"' in batch
print("V52 pass-topology reconciliation self-test OK")
