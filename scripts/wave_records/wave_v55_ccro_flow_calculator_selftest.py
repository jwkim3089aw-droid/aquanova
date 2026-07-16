#!/usr/bin/env python3
"""V55 CCRO Flow Calculator pass-targeting self-test.

This is an offline source-level test because the WAVE UI is only available on
Windows.  It verifies that the patch cannot silently choose Pass 1 recovery
when the CCRO caller requests Pass 2.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
uia = (ROOT / "wave_uia.py").read_text(encoding="utf-8")
dialogs = (ROOT / "wave_dialogs.py").read_text(encoding="utf-8")
ccro = (ROOT / "wave_ccro.py").read_text(encoding="utf-8")
cli = (ROOT / "wave_cli.py").read_text(encoding="utf-8")

assert "target_automation_id: str | None = None" in uia
assert "$targetAutomationId" in uia
assert "target_recovery_control_not_found" in uia
assert "$score += 5000" in uia
assert "$score -= 1200" in uia
assert "target_automation_id=target_automation_id" in dialogs
assert '"txtRecovery2" if pass_label == "pass2" else "txtRecovery1"' in ccro
assert "ccro_total_cycles_error_acknowledged_v55" in ccro
assert "_dismiss_ccro_startup_total_cycles_error" in cli
assert "_dismiss_ccro_startup_flow_calculator" in cli
print("V55 CCRO pass-targeting self-test PASS")
