#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
audit = ROOT / "scripts" / "wave_records" / "aquanova_v144_ro_refactor_integrity_audit.py"
out = ROOT / ".refactor_blueprint" / "v144_ro_integrity"

assert audit.exists(), audit

proc = subprocess.run([sys.executable, str(audit)], cwd=str(ROOT), text=True, capture_output=True)
print(proc.stdout, end="")
if proc.returncode != 0:
    print(proc.stderr, end="")
    raise SystemExit(proc.returncode)

summary = out / "RO_REFACTOR_INTEGRITY_AUDIT.md"
assert summary.exists(), summary
text = summary.read_text(encoding="utf-8", errors="ignore")
assert "V144 RO refactor integrity audit" in text
assert "Import failures: `0`" in text
assert "Expected export failures: `0`" in text
assert "Unresolved function rows: `0`" in text
assert "PASS" in text

print("V144 RO refactor integrity audit selftest PASS")
