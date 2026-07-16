#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def resolve_project_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "scripts" / "wave_records").exists():
        return here
    if (here / "wave_records").exists():
        return here.parent
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records").exists():
        return cwd
    raise SystemExit("Cannot find AquaNova project root. Run this from C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code")


ROOT = resolve_project_root()
WR = ROOT / "scripts" / "wave_records"
WAVE_CCRO = WR / "wave_ccro.py"
WAVE_PRODUCTION = WR / "wave_production.py"
WAVE_DIALOGS = WR / "wave_dialogs.py"
WAVE_UIA = WR / "wave_uia.py"


def replace_required(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if old in text:
        return text.replace(old, new, 1), True
    if new in text:
        print(f"already_patched: {label}")
        return text, False
    raise SystemExit(f"pattern_not_found: {label}")


def patch_wave_ccro() -> None:
    path = WAVE_CCRO
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    text = path.read_text(encoding="utf-8")
    changed = False

    if "pf_feed_ratio_pct: float = 120.0" not in text:
        old = """    recovery_pct: float = 75.0
    feed_temperature_min_c: float = 10.0
"""
        new = """    recovery_pct: float = 75.0
    # V111: CCRO PF Cycle fields in Flow Calculator
    pf_feed_ratio_pct: float = 120.0
    pf_recovery_pct: float = 20.0
    feed_temperature_min_c: float = 10.0
"""
        text, c = replace_required(text, old, new, "wave_ccro dataclass PF fields")
        changed |= c

    if "pf_feed_ratio_pct: float | None = None" not in text:
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
        text, c = replace_required(text, old, new, "wave_ccro flow calculator signature")
        changed |= c

    if "pass_index=2 if pass_label == \"pass2\" else 1" not in text:
        old = """        target_automation_id=target_automation_id,
    )
"""
        new = """        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=2 if pass_label == "pass2" else 1,
    )
"""
        text, c = replace_required(text, old, new, "wave_ccro pass PF values to dialog")
        changed |= c

    if "target_pf_feed_ratio_pct" not in text:
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
        text, c = replace_required(text, old, new, "wave_ccro flow calculator return PF summary")
        changed |= c

    if "pf_feed_ratio_pct: float | None = None," not in text:
        old = """    stage_flow_factor: float,
) -> dict[str, Any]:
"""
        new = """    stage_flow_factor: float,
    pf_feed_ratio_pct: float | None = None,
    pf_recovery_pct: float | None = None,
) -> dict[str, Any]:
"""
        text, c = replace_required(text, old, new, "wave_ccro selected pass signature PF fields")
        changed |= c

    if "pf_feed_ratio_pct=pf_feed_ratio_pct" not in text:
        old = """    flow_result = _configure_ccro_flow_calculator(
        hwnd, monitor, points, recovery_pct, settings, pass_label
    )
"""
        new = """    flow_result = _configure_ccro_flow_calculator(
        hwnd,
        monitor,
        points,
        recovery_pct,
        settings,
        pass_label,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
    )
"""
        text, c = replace_required(text, old, new, "wave_ccro selected pass call PF fields")
        changed |= c

    if "pf_feed_ratio_pct=case.pf_feed_ratio_pct" not in text:
        old = """            stage_back_pressure_bar=0.0,
            stage_flow_factor=case.flow_factor,
        )
"""
        new = """            stage_back_pressure_bar=0.0,
            stage_flow_factor=case.flow_factor,
            pf_feed_ratio_pct=case.pf_feed_ratio_pct,
            pf_recovery_pct=case.pf_recovery_pct,
        )
"""
        text, c = replace_required(text, old, new, "wave_ccro pass1 call PF fields")
        changed |= c

    if "pf_feed_ratio_pct=case.pf_feed_ratio_pct" in text and "case.pass2_stage_flow_factor,\n                pf_feed_ratio_pct=case.pf_feed_ratio_pct" not in text:
        old = """                stage_back_pressure_bar=case.pass2_stage_back_pressure_bar,
                stage_flow_factor=case.pass2_stage_flow_factor,
            )
"""
        new = """                stage_back_pressure_bar=case.pass2_stage_back_pressure_bar,
                stage_flow_factor=case.pass2_stage_flow_factor,
                pf_feed_ratio_pct=case.pf_feed_ratio_pct,
                pf_recovery_pct=case.pf_recovery_pct,
            )
"""
        text, c = replace_required(text, old, new, "wave_ccro pass2 call PF fields")
        changed |= c

    if "pf_feed_ratio_pct: float | str | None = None" not in text:
        old = """    pass2_recovery_pct: float | None = None,
    pv_per_stage: int | float | str | None = None,
"""
        new = """    pass2_recovery_pct: float | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pv_per_stage: int | float | str | None = None,
"""
        text, c = replace_required(text, old, new, "wave_ccro run_ccro_video_case signature PF fields")
        changed |= c

    if "case.pf_feed_ratio_pct = float(pf_feed_ratio_pct)" not in text:
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
        text, c = replace_required(text, old, new, "wave_ccro run_ccro_video_case assign PF fields")
        changed |= c

    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def patch_wave_dialogs() -> None:
    path = WAVE_DIALOGS
    text = path.read_text(encoding="utf-8")
    changed = False

    if "pf_feed_ratio_pct: float | str | None = None" not in text:
        old = """    *,
    target_automation_id: str | None = None,
) -> None:
"""
        new = """    *,
    target_automation_id: str | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pass_index: int = 1,
) -> None:
"""
        text, c = replace_required(text, old, new, "wave_dialogs signature PF fields")
        changed |= c

    if "pf_feed_ratio_pct=pf_feed_ratio_pct" not in text:
        old = """        target_automation_id=target_automation_id,
    )
"""
        new = """        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=pass_index,
    )
"""
        text, c = replace_required(text, old, new, "wave_dialogs call UIA PF fields")
        changed |= c

    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def patch_wave_production() -> None:
    path = WAVE_PRODUCTION
    text = path.read_text(encoding="utf-8")
    if "pf_feed_ratio_pct=(" in text:
        print(f"already ok: {path}")
        return

    old = """            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
            # V101 PLAN FIELD PASSTHROUGH
"""
    new = """            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
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
    text, _ = replace_required(text, old, new, "wave_production pass PF fields")
    path.write_text(text, encoding="utf-8")
    print(f"patched: {path}")


def patch_wave_uia() -> None:
    path = WAVE_UIA
    text = path.read_text(encoding="utf-8")
    changed = False

    if "pf_feed_ratio_pct: float | str | None = None" not in text:
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
        text, c = replace_required(text, old, new, "wave_uia signature PF fields")
        changed |= c

    if "pf_ratio_ps = _ps_literal" not in text:
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
        text, c = replace_required(text, old, new, "wave_uia Python literals PF fields")
        changed |= c

    if "$pfRatioTarget = {pf_ratio_ps}" not in text:
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
        text, c = replace_required(text, old, new, "wave_uia PowerShell variables PF fields")
        changed |= c

    if "V111: set CCRO PF Cycle values" not in text:
        old = """if (-not $targetOk -or -not $actualOk -or [Math]::Abs($targetNum - $actualNum) -gt 0.01) {{
    [pscustomobject]@{{ok=$false; error='recovery_value_not_applied'; target=$target;
        actual=$actual; chosen_score=$bestScore; edits=$diagnostics}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}

"""
        new = old + """# V111: set CCRO PF Cycle values by exact UIAutomation IDs.
$pfSetResults = @()
function Set-ExactEditValue([string]$aid, [string]$targetValue, [string]$fieldName) {{
    if ([string]::IsNullOrWhiteSpace($targetValue)) {{ return }}
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $aid)
    $el = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if ($null -eq $el) {{
        $script:pfSetResults += [pscustomobject]@{{field=$fieldName; automation_id=$aid; ok=$false; error='control_not_found'}}
        return
    }}
    try {{
        $vp = $el.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $vp.SetValue($targetValue)
        Start-Sleep -Milliseconds 250
        $actualValue = [string]$vp.Current.Value
        $targetNum2 = 0.0; $actualNum2 = 0.0
        $targetOk2 = [double]::TryParse(($targetValue -replace ',', '.'), [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$targetNum2)
        $actualOk2 = [double]::TryParse(($actualValue -replace ',', '.'), [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$actualNum2)
        $ok2 = $targetOk2 -and $actualOk2 -and ([Math]::Abs($targetNum2 - $actualNum2) -le 0.01)
        $script:pfSetResults += [pscustomobject]@{{field=$fieldName; automation_id=$aid; ok=$ok2; target=$targetValue; actual=$actualValue}}
    }} catch {{
        $script:pfSetResults += [pscustomobject]@{{field=$fieldName; automation_id=$aid; ok=$false; target=$targetValue; error=[string]$_.Exception.Message}}
    }}
}}
$pfPass = if ($passIndexTarget -eq '2') {{ '2' }} else {{ '1' }}
Set-ExactEditValue ("txtFeedRatio" + $pfPass) $pfRatioTarget "pf_feed_ratio_pct"
Set-ExactEditValue ("txtPFRecovery" + $pfPass) $pfRecoveryTarget "pf_recovery_pct"
$pfFailed = @($pfSetResults | Where-Object {{ $_.ok -eq $false }})
if ($pfFailed.Count -gt 0) {{
    [pscustomobject]@{{ok=$false; error='pf_cycle_value_not_applied'; target=$target;
        actual=$actual; pf_results=$pfSetResults; chosen_score=$bestScore; edits=$diagnostics}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}

"""
        text, c = replace_required(text, old, new, "wave_uia PowerShell set exact PF controls")
        changed |= c

    if "pf_results=$pfSetResults" not in text:
        old = """    target_automation_id=$targetAutomationId;
    chosen_name=$chosenName; chosen_automation_id=$chosenAid;
"""
        new = """    target_automation_id=$targetAutomationId;
    pf_results=$pfSetResults;
    chosen_name=$chosenName; chosen_automation_id=$chosenAid;
"""
        text, c = replace_required(text, old, new, "wave_uia JSON include PF results")
        changed |= c

    if "pf_feed_ratio_pct=pf_feed_ratio_pct" not in text:
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
        text, c = replace_required(text, old, new, "wave_uia record event PF fields")
        changed |= c

    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path}")
    else:
        print(f"already ok: {path}")


def main() -> int:
    patch_wave_ccro()
    patch_wave_production()
    patch_wave_dialogs()
    patch_wave_uia()

    # Syntax check without importing project-specific modules.
    import py_compile
    for target in (WAVE_CCRO, WAVE_PRODUCTION, WAVE_DIALOGS, WAVE_UIA):
        py_compile.compile(str(target), doraise=True)

    print("V111 CCRO PF Feed Ratio force patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
