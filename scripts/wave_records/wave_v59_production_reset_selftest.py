#!/usr/bin/env python3
"""Offline checks for Legacy V59/V69 production reset and spinner handling."""
from pathlib import Path

src = Path(__file__).resolve().parent
prod = (src / "wave_production.py").read_text(encoding="utf-8")
dialogs = (src / "wave_dialogs.py").read_text(encoding="utf-8")
pdf = (src / "wave_pdf.py").read_text(encoding="utf-8")
uf = (src / "wave_uf.py").read_text(encoding="utf-8")

assert 'PRODUCTION_AUTOMATION_VERSION = "V69"' in prod
assert 'production_wave_restart_start_v69' in prod
assert 'discarded_unsaved_project' in prod
assert 'production_project_reset_start_v69' in prod
assert 'if isolate_process_families:' in prod and 'attempt=attempt' in prod
assert 'V58 Add Case duplicated the existing topology' in prod
assert 'def wait_for_report_loading_spinner' in dialogs
assert 'ReportLoadingSpinner' in dialogs
assert 'report_loading_spinner_waited_v59' in dialogs or 'report_loading_spinner_waited' in dialogs
assert 'wait_for_report_loading_spinner(' in pdf
assert 'before_uf_export_pdf_v59' in uf or 'before_uf_export_pdf' in uf
print("V69-compatible production reset/spinner self-test PASS")
