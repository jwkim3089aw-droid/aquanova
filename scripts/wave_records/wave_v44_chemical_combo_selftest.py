"""Offline regression checks for V52 WAVE Chemical combo selection."""
from pathlib import Path

text = (Path(__file__).with_name("wave_uia.py")).read_text(encoding="utf-8")
required = [
    "AquaNovaMouseV52",
    "NormComboText",
    "NormalizationForm]::FormKC",
    "$script:comboSelectionDiagnostics",
    "active_combo_context",
    "foreach($item in $matching)",
    "SelectionItemPattern]::Pattern",
    "click_list_item",
    "keyboard_focus_target",
    "mouse_combo_keyboard",
    "combo_selection_failed_",
    "attempts=@($attempts)",
]
for marker in required:
    assert marker in text, marker
# The old unconditional focus call was the exact V43 failure on ShowB.
assert "$strategy='keyboard';$combo.SetFocus()" not in text
# Per-item pattern failures must be caught inside the candidate loop.
fragment = text[text.index("function SelectCombo"):text.index("function FindWritableEditNear")]
assert "foreach($item in $matching)" in fragment
assert "catch {" in fragment
print("V52 Chemical combo selection self-test OK")
