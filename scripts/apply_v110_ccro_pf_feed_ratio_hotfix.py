#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WR = ROOT / "scripts" / "wave_records"
WAVE_CCRO = WR / "wave_ccro.py"
WAVE_PRODUCTION = WR / "wave_production.py"
WAVE_DIALOGS = WR / "wave_dialogs.py"
WAVE_UIA = WR / "wave_uia.py"


def replace_once(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if old in text:
        return text.replace(old, new, 1), True
    if new in text:
        print(f"already_patched: {label}")
        return text, False
    raise SystemExit(f"pattern_not_found: {label}")


def patch_wave_ccro() -> None:
    path = WAVE_CCRO
    text = path.read_text(encoding="utf-8")
    changed = False

    old = """    recovery_pct: float = 75.0
    feed_temperature_min_c: float = 10.0
"""
    new = """    recovery_pct: float = 75.0
    # V110: CCRO Flow Calculator PF Cycle fields.
    # WAVE defaults these to Feed Ratio 120% and PF Recovery 20%.
    # Meeting tests need FR120/150/270/300 to be real, not just in filenames.
    pf_feed_ratio_pct: float = 120.0
    pf_recovery_pct: float = 20.0
    feed_temperature_min_c: float = 10.0
"""
    text, c = replace_once(text, old, new, "wave_ccro dataclass pf fields")
    changed |= c

    old = """    recovery_pct: float,
    settings: Settings,
    pass_label: str,
) -> dict[str, Any] | None:
"""
    new = """    recovery_pct: float,
    settings: Settings,
    pass_label: str,
    pf_feed_ratio_pct: float | None = None,
    pf_recovery_pct: float | None = None,
) -> dict[str, Any] | None:
"""
    text, c = replace_once(text, old, new, "wave_ccro flow calculator signature")
    changed |= c

    old = """        context,
        target_automation_id=target_automation_id,
    )
"""
    new = """        context,
        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=2 if pass_label == "pass2" else 1,
    )
"""
    text, c = replace_once(text, old, new, "wave_ccro pass pf values to dialog")
    changed |= c

    old = """    record_event("ccro_flow_calculator_configured_v55", pass_label=pass_label, recovery_pct=recovery_pct)
    return {"configured": True, "pass_label": pass_label, "target_recovery_pct": recovery_pct}
"""
    new = """    record_event(
        "ccro_flow_calculator_configured_v55",
        pass_label=pass_label,
        recovery_pct=recovery_pct,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
    )
    return {
        "configured": True,
        "pass_label": pass_label,
        "target_recovery_pct": recovery_pct,
        "target_pf_feed_ratio_pct": pf_feed_ratio_pct,
        "target_pf_recovery_pct": pf_recovery_pct,
    }
"""
    text, c = replace_once(text, old, new, "wave_ccro return pf summary")
    changed |= c

    old = """            settings,
            pass_label,
        )
    )
"""
    new = """            settings,
            pass_label,
            pf_feed_ratio_pct=case.pf_feed_ratio_pct,
            pf_recovery_pct=case.pf_recovery_pct,
        )
    )
"""
    text, c = replace_once(text, old, new, "wave_ccro selected pass pf call")
    changed |= c

    old = """    pass2_recovery_pct: float | None = None,
    pv_per_stage: int | float | str | None = None,
"""
    new = """    pass2_recovery_pct: float | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pv_per_stage: int | float | str | None = None,
"""
    text, c = replace_once(text, old, new, "wave_ccro runner pf signature")
    changed |= c

    old = """    if pass2_recovery_pct is not None:
        case.pass2_recovery_pct = float(pass2_recovery_pct)


    # V101 PLAN FIELD PASSTHROUGH
"""
    new = """    if pass2_recovery_pct is not None:
        case.pass2_recovery_pct = float(pass2_recovery_pct)
    if pf_feed_ratio_pct is not None:
        case.pf_feed_ratio_pct = float(pf_feed_ratio_pct)
    if pf_recovery_pct is not None:
        case.pf_recovery_pct = float(pf_recovery_pct)


    # V101 PLAN FIELD PASSTHROUGH
"""
    text, c = replace_once(text, old, new, "wave_ccro runner set pf fields")
    changed |= c

    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def patch_wave_production() -> None:
    path = WAVE_PRODUCTION
    text = path.read_text(encoding="utf-8")
    old = """            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
            # V101 PLAN FIELD PASSTHROUGH
"""
    new = """            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
            # V110 CCRO Flow Calculator PF Cycle fields
            pf_feed_ratio_pct=(
                raw.get("pf_feed_ratio_pct")
                or raw.get("ccro_pf_feed_ratio_pct")
                or raw.get("target_pf_feed_ratio_pct")
            ),
            pf_recovery_pct=(
                raw.get("pf_recovery_pct")
                or raw.get("ccro_pf_recovery_pct")
                or raw.get("target_pf_recovery_pct")
            ),
            # V101 PLAN FIELD PASSTHROUGH
"""
    text, c = replace_once(text, old, new, "wave_production pass pf fields")
    if c:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def patch_wave_dialogs() -> None:
    path = WAVE_DIALOGS
    text = path.read_text(encoding="utf-8")

    old = """    target_automation_id: str | None = None,
) -> None:
"""
    new = """    target_automation_id: str | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pass_index: int = 1,
) -> None:
"""
    text, c1 = replace_once(text, old, new, "wave_dialogs signature pf fields")

    old = """        target_automation_id=target_automation_id,
    )
"""
    new = """        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=pass_index,
    )
"""
    text, c2 = replace_once(text, old, new, "wave_dialogs pass pf fields to uia")

    if c1 or c2:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def patch_wave_uia() -> None:
    path = WAVE_UIA
    text = path.read_text(encoding="utf-8")

    old = """def uia_configure_flow_calculator(
    dialog_hwnd: int,
    recovery_pct: str,
    timeout: float = 20.0,
    target_automation_id: str | None = None,
) -> dict[str, Any]:
"""
    new = """def uia_configure_flow_calculator(
    dialog_hwnd: int,
    recovery_pct: str,
    timeout: float = 20.0,
    target_automation_id: str | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pass_index: int = 1,
) -> dict[str, Any]:
"""
    text, c1 = replace_once(text, old, new, "wave_uia signature pf fields")

    old = """    target_ps = _ps_literal(str(recovery_pct))
    target_aid_ps = _ps_literal(str(target_automation_id or ""))
    script = f\"\"\"
"""
    new = """    target_ps = _ps_literal(str(recovery_pct))
    target_aid_ps = _ps_literal(str(target_automation_id or ""))
    pf_ratio_ps = _ps_literal("" if pf_feed_ratio_pct is None else str(pf_feed_ratio_pct))
    pf_recovery_ps = _ps_literal("" if pf_recovery_pct is None else str(pf_recovery_pct))
    pass_index_ps = _ps_literal(str(int(pass_index or 1)))
    script = f\"\"\"
"""
    text, c2 = replace_once(text, old, new, "wave_uia ps literals pf fields")

    old = """$target = {target_ps}
$targetAutomationId = {target_aid_ps}
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(dialog_hwnd)})
"""
    new = """$target = {target_ps}
$targetAutomationId = {target_aid_ps}
$pfRatioTarget = {pf_ratio_ps}
$pfRecoveryTarget = {pf_recovery_ps}
$passIndexTarget = {pass_index_ps}
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(dialog_hwnd)})
"""
    text, c3 = replace_once(text, old, new, "wave_uia ps variables pf fields")

    old = """$chosenVp.SetValue($target)
Start-Sleep -Milliseconds 500
$actual = [string]$chosenVp.Current.Value
"""
    new = """$chosenVp.SetValue($target)
Start-Sleep -Milliseconds 500
$actual = [string]$chosenVp.Current.Value

# V110: set CCRO PF Cycle values by exact WAVE UIAutomation IDs.
# Dialog screenshots and UIA inventory show:
#   txtFeedRatio1 / txtPFRecovery1 for Pass 1
#   txtFeedRatio2 / txtPFRecovery2 for Pass 2
$pfSetResults = @()
function Set-ExactEditValue([string]$aid, [string]$targetValue, [string]$fieldName) {
    if ([string]::IsNullOrWhiteSpace($targetValue)) { return }
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $aid)
    $el = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if ($null -eq $el) {
        $script:pfSetResults += [pscustomobject]@{field=$fieldName; automation_id=$aid; ok=$false; error='control_not_found'}
        return
    }
    try {
        $vp = $el.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $vp.SetValue($targetValue)
        Start-Sleep -Milliseconds 250
        $actualValue = [string]$vp.Current.Value
        $targetNum = 0.0; $actualNum = 0.0
        $targetOk = [double]::TryParse(($targetValue -replace ',', '.'), [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$targetNum)
        $actualOk = [double]::TryParse(($actualValue -replace ',', '.'), [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$actualNum)
        $ok = $targetOk -and $actualOk -and ([Math]::Abs($targetNum - $actualNum) -le 0.01)
        $script:pfSetResults += [pscustomobject]@{field=$fieldName; automation_id=$aid; ok=$ok; target=$targetValue; actual=$actualValue}
    } catch {
        $script:pfSetResults += [pscustomobject]@{field=$fieldName; automation_id=$aid; ok=$false; target=$targetValue; error=[string]$_.Exception.Message}
    }
}
$pfPass = if ($passIndexTarget -eq '2') { '2' } else { '1' }
Set-ExactEditValue ("txtFeedRatio" + $pfPass) $pfRatioTarget "pf_feed_ratio_pct"
Set-ExactEditValue ("txtPFRecovery" + $pfPass) $pfRecoveryTarget "pf_recovery_pct"
$pfFailed = @($pfSetResults | Where-Object { $_.ok -eq $false })
if ($pfFailed.Count -gt 0) {
    [pscustomobject]@{ok=$false; error='pf_cycle_value_not_applied'; target=$target;
        actual=$actual; pf_results=$pfSetResults; chosen_score=$bestScore; edits=$diagnostics} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}
"""
    text, c4 = replace_once(text, old, new, "wave_uia set pf fields before validation")

    old = """    ok=$invoked; target=$target; actual=$actual; chosen_score=$bestScore;
    target_automation_id=$targetAutomationId;
    chosen_name=$chosenName; chosen_automation_id=$chosenAid;
    ok_name=$okName; ok_automation_id=$okAid;
    edits=$diagnostics
"""
    new = """    ok=$invoked; target=$target; actual=$actual; chosen_score=$bestScore;
    target_automation_id=$targetAutomationId;
    pf_results=$pfSetResults;
    chosen_name=$chosenName; chosen_automation_id=$chosenAid;
    ok_name=$okName; ok_automation_id=$okAid;
    edits=$diagnostics
"""
    text, c5 = replace_once(text, old, new, "wave_uia result include pf fields")

    old = """        recovery_pct=recovery_pct,
        target_automation_id=target_automation_id,
        result=result,
"""
    new = """        recovery_pct=recovery_pct,
        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=pass_index,
        result=result,
"""
    text, c6 = replace_once(text, old, new, "wave_uia record pf fields")

    if c1 or c2 or c3 or c4 or c5 or c6:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def main() -> int:
    patch_wave_ccro()
    patch_wave_production()
    patch_wave_dialogs()
    patch_wave_uia()
    print("V110 CCRO PF Feed Ratio passthrough hotfix applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
