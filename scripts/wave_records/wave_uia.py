#!/usr/bin/env python3
"""Refactored WAVE automation module: uia."""
from __future__ import annotations

import tempfile

from wave_common import *
from wave_runtime import record_event

def uia_configure_flow_calculator(
    dialog_hwnd: int,
    recovery_pct: str,
    timeout: float = 20.0,
    target_automation_id: str | None = None,
    pf_feed_ratio_pct: float | str | None = None,
    pf_recovery_pct: float | str | None = None,
    pass_index: int = 1,
) -> dict[str, Any]:
    """Set Recovery and invoke OK using Windows UI Automation.

    WAVE is DPI-unaware on the secondary monitor in the observed setup.  The
    top-level dialog rectangle returned by GetWindowRect can therefore be in a
    different coordinate space from SetCursorPos.  UI Automation acts on the
    actual WPF controls and avoids that coordinate mismatch entirely.
    """
    target_ps = _ps_literal(str(recovery_pct))
    target_aid_ps = _ps_literal(str(target_automation_id or ""))
    pf_ratio_ps = _ps_literal("" if pf_feed_ratio_pct is None else str(pf_feed_ratio_pct))
    pf_recovery_ps = _ps_literal("" if pf_recovery_pct is None else str(pf_recovery_pct))
    pass_index_ps = _ps_literal(str(int(pass_index or 1)))
    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$target = {target_ps}
$targetAutomationId = {target_aid_ps}
$pfRatioTarget = {pf_ratio_ps}
$pfRecoveryTarget = {pf_recovery_ps}
$passIndexTarget = {pass_index_ps}
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(dialog_hwnd)})
if ($null -eq $window) {{ throw 'flow_window_not_found' }}

$editCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Edit)
$textCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Text)
$buttonCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button)

$edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCondition)
$texts = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $textCondition)
$buttons = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $buttonCondition)
$wr = $window.Current.BoundingRectangle
$recoveryLabels = @()
foreach ($t in $texts) {{
    $n = [string]$t.Current.Name
    if ($n -match '(?i)recovery|회수') {{ $recoveryLabels += $t }}
}}

$diagnostics = @()
$chosen = $null
$bestScore = -1000000.0
$exactTargetSeen = $false
foreach ($edit in $edits) {{
    $name = [string]$edit.Current.Name
    $aid = [string]$edit.Current.AutomationId
    $r = $edit.Current.BoundingRectangle
    $value = $null
    $readOnly = $true
    $hasValue = $false
    try {{
        $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $value = [string]$vp.Current.Value
        $readOnly = [bool]$vp.Current.IsReadOnly
        $hasValue = $true
    }} catch {{}}
    $enabled = [bool]$edit.Current.IsEnabled
    $offscreen = [bool]$edit.Current.IsOffscreen
    $score = 0.0
    if (-not $hasValue) {{ $score -= 1000 }}
    if ($readOnly) {{ $score -= 500 }} else {{ $score += 100 }}
    if ($enabled) {{ $score += 40 }} else {{ $score -= 500 }}
    if ($offscreen) {{ $score -= 500 }}
    if ($name -match '(?i)recovery|회수') {{ $score += 500 }}
    if ($aid -match '(?i)recovery|회수') {{ $score += 500 }}
    if ($targetAutomationId.Length -gt 0) {{
        if ($aid -eq $targetAutomationId) {{
            $score += 5000
            $exactTargetSeen = $true
        }} elseif ($aid -match '(?i)^txtRecovery\\d+$') {{
            # When a specific CCRO pass is requested, selecting another pass's
            # Recovery box is worse than failing safely.
            $score -= 1200
        }}
    }}
    if ($value -match '^\\s*\\d+(?:[\\.,]\\d+)?\\s*$') {{ $score += 25 }}
    $num = 0.0
    if ([double]::TryParse(($value -replace ',', '.'), [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$num)) {{
        if ($num -ge 1 -and $num -le 99.99) {{ $score += 35 }}
    }}
    $cx = ($r.Left + $r.Right) / 2.0
    $cy = ($r.Top + $r.Bottom) / 2.0
    # Pass-1 recovery is in the left half and upper half of the calculator.
    if ($cx -lt ($wr.Left + $wr.Width * 0.52)) {{ $score += 55 }}
    if ($cy -gt ($wr.Top + $wr.Height * 0.20) -and
        $cy -lt ($wr.Top + $wr.Height * 0.58)) {{ $score += 55 }}
    $nearest = 999999.0
    foreach ($label in $recoveryLabels) {{
        $lr = $label.Current.BoundingRectangle
        $lcx = ($lr.Left + $lr.Right) / 2.0
        $lcy = ($lr.Top + $lr.Bottom) / 2.0
        $distance = [Math]::Abs($cx - $lcx) + [Math]::Abs($cy - $lcy)
        if ($distance -lt $nearest) {{ $nearest = $distance }}
    }}
    if ($nearest -lt 40) {{ $score += 500 }}
    elseif ($nearest -lt 100) {{ $score += 250 }}
    elseif ($nearest -lt 180) {{ $score += 100 }}

    $diagnostics += [pscustomobject]@{{
        name=$name; automation_id=$aid; value=$value; read_only=$readOnly;
        enabled=$enabled; offscreen=$offscreen; score=$score;
        rect=[pscustomobject]@{{left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom}}
    }}
    if ($score -gt $bestScore) {{ $bestScore = $score; $chosen = $edit }}
}}
if ($targetAutomationId.Length -gt 0 -and -not $exactTargetSeen) {{
    [pscustomobject]@{{ok=$false; error='target_recovery_control_not_found';
        target_automation_id=$targetAutomationId; edits=$diagnostics}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}
if ($null -eq $chosen -or $bestScore -lt 100) {{
    [pscustomobject]@{{ok=$false; error='editable_recovery_not_found';
        target_automation_id=$targetAutomationId; edits=$diagnostics}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}

$chosenVp = $chosen.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
$chosenVp.SetValue($target)
Start-Sleep -Milliseconds 500
$actual = [string]$chosenVp.Current.Value
$targetNum = 0.0; $actualNum = 0.0
$targetOk = [double]::TryParse(($target -replace ',', '.'), [Globalization.NumberStyles]::Float,
    [Globalization.CultureInfo]::InvariantCulture, [ref]$targetNum)
$actualOk = [double]::TryParse(($actual -replace ',', '.'), [Globalization.NumberStyles]::Float,
    [Globalization.CultureInfo]::InvariantCulture, [ref]$actualNum)
if (-not $targetOk -or -not $actualOk -or [Math]::Abs($targetNum - $actualNum) -gt 0.01) {{
    [pscustomobject]@{{ok=$false; error='recovery_value_not_applied'; target=$target;
        actual=$actual; chosen_score=$bestScore; edits=$diagnostics}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}

# V111: set CCRO PF Cycle values by exact UIAutomation IDs.
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

$okButton = $null
foreach ($button in $buttons) {{
    $n = ([string]$button.Current.Name).Trim()
    $aid = ([string]$button.Current.AutomationId).Trim()
    if ($n -match '^(?i:OK|확인)$' -or $aid -match '(?i)^ok$|okbutton|buttonok') {{
        $okButton = $button
        break
    }}
}}
if ($null -eq $okButton) {{
    [pscustomobject]@{{ok=$false; error='ok_button_not_found'; target=$target;
        actual=$actual; chosen_score=$bestScore; edits=$diagnostics;
        buttons=@($buttons | ForEach-Object {{ [pscustomobject]@{{name=$_.Current.Name; automation_id=$_.Current.AutomationId}} }})}} |
        ConvertTo-Json -Compress -Depth 8
    exit 0
}}

$chosenName = [string]$chosen.Current.Name
$chosenAid = [string]$chosen.Current.AutomationId
$okName = [string]$okButton.Current.Name
$okAid = [string]$okButton.Current.AutomationId
$invoked = $false
try {{
    $invoke = $okButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $invoke.Invoke()
    $invoked = $true
}} catch {{
    try {{
        $okButton.SetFocus()
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
        $invoked = $true
    }} catch {{}}
}}
[pscustomobject]@{{
    ok=$invoked; target=$target; actual=$actual; chosen_score=$bestScore;
    target_automation_id=$targetAutomationId;
    chosen_name=$chosenName; chosen_automation_id=$chosenAid;
    ok_name=$okName; ok_automation_id=$okAid;
    edits=$diagnostics
}} | ConvertTo-Json -Compress -Depth 8
"""
    result = _run_powershell_json(script, timeout=timeout)
    record_event(
        "uia_flow_calculator",
        dialog_hwnd=dialog_hwnd,
        recovery_pct=recovery_pct,
        target_automation_id=target_automation_id,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
        pass_index=pass_index,
        result=result,
    )
    if STATE.RUN_DIR is not None:
        try:
            (STATE.RUN_DIR / "uia_flow_calculator.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    return result


def _run_powershell_json(script: str, timeout: float = 15.0) -> dict[str, Any]:
    """Run an STA PowerShell/UIAutomation script and parse its JSON result.

    The script is written to a temporary UTF-8-with-BOM ``.ps1`` file instead
    of being embedded as a UTF-16/base64 command-line argument.  The membrane
    selector is
    roughly 15K source characters and expands to about 40K command-line
    characters when UTF-16/base64 encoded, exceeding Windows' process command
    line limit.  ``-File`` keeps the command line short and also preserves
    Korean and trademark characters used by WAVE labels.

    UI Automation remains optional at runtime: callers receive a structured
    error and keep their deterministic recovery paths.
    """
    if os.name != "nt":
        return {"ok": False, "error": "not_windows", "transport": "temp_file"}

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    script_path = ""
    try:
        fd, script_path = tempfile.mkstemp(
            prefix="aquanova_wave_uia_", suffix=".ps1"
        )
        # Windows PowerShell 5.1 reliably detects UTF-8 only when a BOM is
        # present.  Close the descriptor before launching PowerShell so that
        # the child can open the file on every supported Windows build.
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\n") as handle:
            handle.write(script)

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", "replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return {
            "ok": False,
            "error": f"powershell_timeout_{timeout:g}s",
            "transport": "temp_file",
            "script_chars": len(script),
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"powershell_launch: {exc!r}",
            "transport": "temp_file",
            "script_chars": len(script),
        }
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    payload: dict[str, Any] = {}
    if lines:
        try:
            payload = json.loads(lines[-1])
        except Exception:
            payload = {
                "ok": False,
                "error": "invalid_json",
                "stdout": completed.stdout[-4000:],
            }
    else:
        payload = {"ok": False, "error": "empty_stdout"}
    if completed.returncode != 0:
        payload.setdefault("ok", False)
        payload.setdefault("error", f"powershell_exit_{completed.returncode}")
        payload["stderr"] = completed.stderr[-4000:]
    payload.setdefault("transport", "temp_file")
    payload.setdefault("script_chars", len(script))
    return payload


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def uia_probe_point(point: tuple[int, int], timeout: float = 10.0) -> dict[str, Any]:
    """Read the nearest UIA Value/Selection pattern at an absolute screen point."""
    x, y = point
    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
$point = New-Object System.Windows.Point({x}, {y})
$element = [System.Windows.Automation.AutomationElement]::FromPoint($point)
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$result = $null
for ($i = 0; $i -lt 10 -and $null -ne $element; $i++) {{
    $name = $element.Current.Name
    $aid = $element.Current.AutomationId
    $ctype = $element.Current.ControlType.ProgrammaticName
    $value = $null
    $selected = @()
    try {{
        $vp = $element.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $value = $vp.Current.Value
    }} catch {{}}
    try {{
        $sp = $element.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
        $selected = @($sp.GetCurrentSelection() | ForEach-Object {{ $_.Current.Name }})
    }} catch {{}}
    if (($null -ne $value -and $value -ne '') -or $selected.Count -gt 0 -or $ctype -eq 'ControlType.ComboBox' -or $ctype -eq 'ControlType.Edit') {{
        $result = [pscustomobject]@{{
            ok = $true; name = $name; automation_id = $aid; control_type = $ctype;
            value = $value; selected = $selected
        }}
        break
    }}
    $element = $walker.GetParent($element)
}}
if ($null -eq $result) {{ $result = [pscustomobject]@{{ok=$false; error='no_value_or_selection_pattern'}} }}
$result | ConvertTo-Json -Compress -Depth 5
"""
    result = _run_powershell_json(script, timeout=timeout)
    record_event("uia_probe", point=point, result=result)
    return result


def uia_snapshot_ro_state(
    hwnd: int,
    points: dict[str, tuple[int, int]],
    *,
    expected_stage_counts: Optional[dict[int, int]] = None,
    timeout: float = 18.0,
) -> dict[str, Any]:
    """Capture a machine-readable WPF state snapshot of the RO screen.

    Screenshots are excellent for human review but do not reveal which WPF
    control a coordinate actually resolved to.  This probe records all visible
    RO-related Edit/ComboBox/RadioButton controls, their bounding rectangles,
    pattern values, selection state, and an ancestor chain for every important
    calibrated/stage point.  It is intentionally diagnostic-only and never
    mutates WAVE.
    """
    point_payload = [
        {"key": str(key), "x": int(point[0]), "y": int(point[1])}
        for key, point in sorted(points.items())
    ]
    points_json = json.dumps(point_payload, ensure_ascii=False)
    stage_json = json.dumps(expected_stage_counts or {}, ensure_ascii=False)
    script = rf"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(hwnd)})
if ($null -eq $window) {{ throw 'wave_window_not_found' }}
$wavePid = $window.Current.ProcessId
$wr = $window.Current.BoundingRectangle
$points = ConvertFrom-Json -InputObject {_ps_literal(points_json)}
$expectedStages = ConvertFrom-Json -InputObject {_ps_literal(stage_json)}
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

function Rect-Obj($r) {{
    [pscustomobject]@{{left=[double]$r.Left;top=[double]$r.Top;right=[double]$r.Right;bottom=[double]$r.Bottom;width=[double]$r.Width;height=[double]$r.Height}}
}}
function Element-Obj($e) {{
    if ($null -eq $e) {{ return $null }}
    $value = $null; $readOnly = $null; $selected = $null; $expanded = $null
    try {{ $vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); $value=[string]$vp.Current.Value; $readOnly=[bool]$vp.Current.IsReadOnly }} catch {{}}
    try {{ $sp=$e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern); $selected=[bool]$sp.Current.IsSelected }} catch {{}}
    try {{ $tp=$e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern); $selected=([string]$tp.Current.ToggleState -eq 'On') }} catch {{}}
    try {{ $ep=$e.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern); $expanded=[string]$ep.Current.ExpandCollapseState }} catch {{}}
    $selection=@()
    try {{ $sel=$e.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern); $selection=@($sel.GetCurrentSelection() | ForEach-Object {{ [string]$_.Current.Name }}) }} catch {{}}
    $r=$e.Current.BoundingRectangle
    [pscustomobject]@{{
        name=[string]$e.Current.Name; automation_id=[string]$e.Current.AutomationId;
        control_type=[string]$e.Current.ControlType.ProgrammaticName;
        class_name=[string]$e.Current.ClassName; framework_id=[string]$e.Current.FrameworkId;
        enabled=[bool]$e.Current.IsEnabled; offscreen=[bool]$e.Current.IsOffscreen;
        keyboard_focus=[bool]$e.Current.HasKeyboardFocus; value=$value; read_only=$readOnly;
        selected=$selected; selection=$selection; expand_state=$expanded; rect=(Rect-Obj $r)
    }}
}}

$types = @(
    [System.Windows.Automation.ControlType]::Edit,
    [System.Windows.Automation.ControlType]::ComboBox,
    [System.Windows.Automation.ControlType]::RadioButton,
    [System.Windows.Automation.ControlType]::Button,
    [System.Windows.Automation.ControlType]::Text
)
$controls = @()
foreach ($type in $types) {{
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty, $type)
    $items = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    foreach ($item in $items) {{
        try {{
            $r=$item.Current.BoundingRectangle
            if ($item.Current.ProcessId -ne $wavePid -or $r.Width -le 0 -or $r.Height -le 0) {{ continue }}
            # Keep controls inside the WAVE window.  Text is restricted to the
            # RO body to prevent the diagnostic file from becoming enormous.
            if ($r.Right -lt $wr.Left -or $r.Left -gt $wr.Right -or $r.Bottom -lt $wr.Top -or $r.Top -gt $wr.Bottom) {{ continue }}
            if ($type -eq [System.Windows.Automation.ControlType]::Text -and $r.Top -lt ($wr.Top + 245)) {{ continue }}
            $controls += (Element-Obj $item)
        }} catch {{}}
    }}
}}

$pointProbes = @()
foreach ($point in $points) {{
    $chain=@(); $element=$null
    try {{ $element=[System.Windows.Automation.AutomationElement]::FromPoint((New-Object System.Windows.Point([double]$point.x,[double]$point.y))) }} catch {{}}
    for ($i=0; $i -lt 10 -and $null -ne $element; $i++) {{
        try {{ $chain += (Element-Obj $element) }} catch {{}}
        if ($element -eq $window) {{ break }}
        try {{ $element=$walker.GetParent($element) }} catch {{ $element=$null }}
    }}
    $pointProbes += [pscustomobject]@{{key=[string]$point.key;x=[int]$point.x;y=[int]$point.y;chain=$chain}}
}}

$focused=$null
try {{ $focused=Element-Obj ([System.Windows.Automation.AutomationElement]::FocusedElement) }} catch {{}}
[pscustomobject]@{{
    ok=$true; hwnd={int(hwnd)}; process_id=$wavePid; window_rect=(Rect-Obj $wr);
    expected_stage_counts=$expectedStages; focused=$focused;
    controls=$controls; point_probes=$pointProbes
}} | ConvertTo-Json -Compress -Depth 12
"""
    result = _run_powershell_json(script, timeout=timeout)
    record_event(
        "uia_ro_state_snapshot_v44",
        hwnd=hwnd,
        expected_stage_counts=expected_stage_counts or {},
        point_count=len(point_payload),
        result_summary={
            "ok": result.get("ok"),
            "error": result.get("error"),
            "control_count": len(result.get("controls") or []),
            "point_probe_count": len(result.get("point_probes") or []),
            "transport": result.get("transport"),
        },
    )
    return result


def uia_select_combo_exact(
    hwnd: int,
    point: tuple[int, int],
    target: str,
    timeout: float = 22.0,
) -> dict[str, Any]:
    """Select a WPF ComboBox item with exact-index and layered verification.

    WAVE's membrane ComboBox exposes its complete virtualized catalog through
    UI Automation, but the collapsed presenter often exposes neither ValuePattern
    nor SelectionPattern.  V52 uses three evidence levels:

    1. exact visible/ValuePattern readback;
    2. exact SelectionItemPattern state while the list is expanded;
    3. a deterministic HOME/DOWN/ENTER commit at an exact catalog index when the
       control exposes no readable state at all.

    Level 3 is explicitly provisional.  It is accepted only when there is no
    contradictory membrane value, and WAVE's Summary transition remains the
    authoritative validation.  A reported missing Element Type is repaired and
    retried by ``wave_ro_engine``.
    """
    x, y = point
    target_ps = _ps_literal(target)
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms
$target = __TARGET__
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]__HWND__)
if ($null -eq $window) { throw 'wave_window_not_found' }
$wavePid = $window.Current.ProcessId
$point = New-Object System.Windows.Point(__X__, __Y__)
$element = [System.Windows.Automation.AutomationElement]::FromPoint($point)
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$combo = $null
for ($i = 0; $i -lt 12 -and $null -ne $element; $i++) {
    if ($element.Current.ControlType -eq [System.Windows.Automation.ControlType]::ComboBox -and
        $element.Current.ProcessId -eq $wavePid) { $combo = $element; break }
    $element = $walker.GetParent($element)
}
if ($null -eq $combo) {
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::ComboBox)
    $combos = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    foreach ($candidate in $combos) {
        $r = $candidate.Current.BoundingRectangle
        if (__X__ -ge $r.Left -and __X__ -le $r.Right -and __Y__ -ge $r.Top -and __Y__ -le $r.Bottom) {
            $combo = $candidate; break
        }
    }
}
if ($null -eq $combo) { throw 'combo_not_found_at_point' }

function Add-Unique([System.Collections.Generic.List[string]]$list, [string]$value) {
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $v = $value.Trim()
        if (-not $list.Contains($v)) { $list.Add($v) }
    }
}
function Is-FiniteRect($r) {
    return -not (
        [double]::IsInfinity($r.Left) -or [double]::IsInfinity($r.Top) -or
        [double]::IsInfinity($r.Right) -or [double]::IsInfinity($r.Bottom) -or
        [double]::IsNaN($r.Left) -or [double]::IsNaN($r.Top) -or
        $r.Width -le 0 -or $r.Height -le 0)
}
function Collapse-Combo {
    try {
        $ep = $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($ep.Current.ExpandCollapseState -ne [System.Windows.Automation.ExpandCollapseState]::Collapsed) {
            $ep.Collapse(); Start-Sleep -Milliseconds 220
        }
    } catch {}
}
function Expand-Combo {
    $ep = $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    if ($ep.Current.ExpandCollapseState -ne [System.Windows.Automation.ExpandCollapseState]::Expanded) {
        $ep.Expand(); Start-Sleep -Milliseconds 420
    }
}
function Get-DisplayedState {
    Collapse-Combo
    $displayed = New-Object System.Collections.Generic.List[string]
    $selected = @()
    $value = ''
    try {
        $sp = $combo.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
        $selected = @($sp.GetCurrentSelection() | ForEach-Object { $_.Current.Name })
        foreach ($v in $selected) { Add-Unique $displayed ([string]$v) }
    } catch {}
    try {
        $vp = $combo.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $value = [string]$vp.Current.Value
        Add-Unique $displayed $value
    } catch {}

    # Hidden virtualized catalog descendants have Infinity rectangles.  Only
    # finite Text elements physically inside the collapsed ComboBox are readback.
    $cr = $combo.Current.BoundingRectangle
    try {
        $tc = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Text)
        $texts = $combo.FindAll([System.Windows.Automation.TreeScope]::Descendants, $tc)
        foreach ($t in $texts) {
            $r = $t.Current.BoundingRectangle
            if (-not (Is-FiniteRect $r)) { continue }
            $cx = ($r.Left + $r.Right) / 2.0
            $cy = ($r.Top + $r.Bottom) / 2.0
            if ($cx -ge $cr.Left -and $cx -le $cr.Right -and $cy -ge $cr.Top -and $cy -le $cr.Bottom) {
                Add-Unique $displayed ([string]$t.Current.Name)
            }
        }
    } catch {}

    $sampleX = @([int]($cr.Left + 12), [int](($cr.Left + $cr.Right) / 2.0), [int]($cr.Right - 28))
    $sampleY = [int](($cr.Top + $cr.Bottom) / 2.0)
    foreach ($sx in $sampleX) {
        try {
            $e = [System.Windows.Automation.AutomationElement]::FromPoint(
                (New-Object System.Windows.Point($sx, $sampleY)))
            for ($j = 0; $j -lt 8 -and $null -ne $e; $j++) {
                if ($e -eq $combo) { break }
                if ($e.Current.ProcessId -eq $wavePid) { Add-Unique $displayed ([string]$e.Current.Name) }
                $e = $walker.GetParent($e)
            }
        } catch {}
    }

    $clipboard = ''
    try {
        $combo.SetFocus(); Start-Sleep -Milliseconds 80
        [System.Windows.Forms.Clipboard]::Clear()
        [System.Windows.Forms.SendKeys]::SendWait('^c')
        Start-Sleep -Milliseconds 120
        if ([System.Windows.Forms.Clipboard]::ContainsText()) {
            $clipboard = [System.Windows.Forms.Clipboard]::GetText().Trim()
            Add-Unique $displayed $clipboard
        }
    } catch {}
    $exact = $false
    foreach ($v in $displayed) { if ($v -ceq $target) { $exact = $true; break } }
    return [pscustomobject]@{
        displayed=@($displayed); selected=@($selected); value=$value;
        clipboard=$clipboard; exact=$exact
    }
}
function Get-ExpandedSelectionState {
    Expand-Combo
    $selected = New-Object System.Collections.Generic.List[string]
    $targetFound = $false
    $targetIsSelected = $false
    $selectionPatternSupported = $false
    try {
        $sp = $combo.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
        $selectionPatternSupported = $true
        foreach ($item in @($sp.GetCurrentSelection())) {
            $name = [string]$item.Current.Name
            Add-Unique $selected $name
            if ($name -ceq $target) { $targetIsSelected = $true }
        }
    } catch {}
    try {
        $condition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::ListItem)
        $items = $combo.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        foreach ($item in $items) {
            $name = [string]$item.Current.Name
            if ($name -ceq $target) { $targetFound = $true }
            try {
                $sip = $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
                $selectionPatternSupported = $true
                if ($sip.Current.IsSelected) {
                    Add-Unique $selected $name
                    if ($name -ceq $target) { $targetIsSelected = $true }
                }
            } catch {}
        }
    } catch {}
    $exact = $targetIsSelected
    if (-not $exact) {
        foreach ($v in $selected) { if ($v -ceq $target) { $exact = $true; break } }
    }
    return [pscustomobject]@{
        selected=@($selected); exact=[bool]$exact; target_found=[bool]$targetFound;
        target_is_selected=[bool]$targetIsSelected;
        selection_pattern_supported=[bool]$selectionPatternSupported
    }
}
function Get-CatalogNames {
    Expand-Combo
    $listNames = New-Object System.Collections.Generic.List[string]
    $textNames = New-Object System.Collections.Generic.List[string]
    try {
        $all = $combo.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($item in $all) {
            $name = [string]$item.Current.Name
            if ($item.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem) {
                Add-Unique $listNames $name
            } elseif ($item.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text) {
                Add-Unique $textNames $name
            }
        }
    } catch {}
    $catalog = if ($listNames.Contains($target) -and $listNames.Count -gt 1) {
        @($listNames)
    } else {
        @($textNames)
    }
    $specifyIndex = [Array]::IndexOf([object[]]$catalog, [object]'Specify')
    if ($specifyIndex -ge 0 -and $specifyIndex -lt $catalog.Count) {
        $catalog = @($catalog[$specifyIndex..($catalog.Count - 1)])
    }
    return @($catalog)
}
function Get-Contradictions($displayState, $selectionState, $catalog) {
    $wrong = New-Object System.Collections.Generic.List[string]
    # Expanded SelectionItemPattern is useful as positive exact evidence, but a
    # negative/stale value is not authoritative in this virtualized WPF list.
    # Only concrete collapsed presenter evidence can contradict the target.
    if (-not [string]::IsNullOrWhiteSpace([string]$displayState.value) -and
        ([string]$displayState.value) -cne $target) {
        Add-Unique $wrong ('value=' + [string]$displayState.value)
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$displayState.clipboard) -and
        ([string]$displayState.clipboard) -cne $target) {
        Add-Unique $wrong ('clipboard=' + [string]$displayState.clipboard)
    }
    foreach ($v in @($displayState.displayed)) {
        if ($catalog -contains [string]$v -and ([string]$v) -cne $target) {
            Add-Unique $wrong ('displayed_catalog=' + [string]$v)
        }
    }
    return @($wrong)
}

$initial = Get-DisplayedState
if ($initial.exact) {
    [pscustomobject]@{
        ok=$true; committed=$true; verified_exact=$true; provisional=$false;
        readback_unavailable=$false; target=$target; method='AlreadySelected';
        displayed=@($initial.displayed); catalog=@(); selected=@($initial.selected);
        value=$initial.value; clipboard=$initial.clipboard; target_index=-1;
        selection_before=$null; selection_after=$null; contradictions=@(); pattern_errors=@()
    } | ConvertTo-Json -Compress -Depth 10
    exit 0
}

$errors = New-Object System.Collections.Generic.List[string]
$method = $null
$committed = $false
$verified = $false
$provisional = $false
$readbackUnavailable = $false
$catalog = @(Get-CatalogNames)
$targetIndex = [Array]::IndexOf([object[]]$catalog, [object]$target)
$state = $initial
$selectionBefore = $null
$selectionAfter = $null
$contradictions = @()

# Primary path: deterministic exact catalog index.  This avoids virtualized item
# rectangles and is the only path eligible for provisional unreadable acceptance.
if ($targetIndex -ge 0) {
    try {
        Expand-Combo
        $combo.SetFocus(); Start-Sleep -Milliseconds 100
        [System.Windows.Forms.SendKeys]::SendWait('{HOME}')
        Start-Sleep -Milliseconds 100
        if ($targetIndex -gt 0) {
            [System.Windows.Forms.SendKeys]::SendWait(('{DOWN ' + $targetIndex + '}'))
            Start-Sleep -Milliseconds 140
        }
        $selectionBefore = Get-ExpandedSelectionState
        [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
        Start-Sleep -Milliseconds 420
        $selectionAfter = Get-ExpandedSelectionState
        $state = Get-DisplayedState
        $verified = [bool]($state.exact -or $selectionBefore.exact -or $selectionAfter.exact)
        $contradictions = @(Get-Contradictions $state $selectionAfter $catalog)
        if ($verified) {
            $method = if ($state.exact) { 'CatalogKeyboardIndexVisible' } else { 'CatalogKeyboardIndexSelectionPattern' }
            $committed = $true
        } elseif ($contradictions.Count -eq 0) {
            # WAVE's WPF presenter can be entirely unreadable to UIA.  HOME/DOWN
            # still selected the correct item in the V31 failure screenshot.  Do
            # not disturb that correct state with a second focus-based method.
            $method = 'CatalogKeyboardIndexProvisional'
            $committed = $true
            $provisional = $true
            $readbackUnavailable = $true
        } else {
            throw ('contradictory_readback: ' + ($contradictions -join ' | '))
        }
    } catch { $errors.Add('CatalogKeyboardIndex: ' + $_.Exception.Message) }
} else {
    $errors.Add('CatalogKeyboardIndex: exact_target_not_found_in_catalog')
}

# Secondary path is never accepted provisionally.  It is used only when the
# deterministic path had an explicit failure and must prove exact selection.
if (-not $committed) {
    try {
        Expand-Combo
        $nameCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, $target)
        $typeCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::ListItem)
        $condition = New-Object System.Windows.Automation.AndCondition($nameCondition, $typeCondition)
        $items = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants, $condition)
        $chosen = $null
        foreach ($item in $items) {
            if ($item.Current.ProcessId -eq $wavePid) { $chosen = $item; break }
        }
        if ($null -eq $chosen) { throw 'exact_list_item_not_found' }
        $chosen.SetFocus(); Start-Sleep -Milliseconds 120
        [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
        Start-Sleep -Milliseconds 420
        $selectionAfter = Get-ExpandedSelectionState
        $state = Get-DisplayedState
        $verified = [bool]($state.exact -or $selectionAfter.exact)
        if (-not $verified) {
            $contradictions = @(Get-Contradictions $state $selectionAfter $catalog)
            throw ('exact_selection_not_verified: ' + ($contradictions -join ' | '))
        }
        $method = if ($state.exact) { 'ExactItemFocusEnterVisible' } else { 'ExactItemFocusEnterSelectionPattern' }
        $committed = $true
    } catch { $errors.Add('ExactItemFocusEnterVerified: ' + $_.Exception.Message) }
}

Collapse-Combo
$finalSelected = if ($null -ne $selectionAfter) { @($selectionAfter.selected) } else { @($state.selected) }
[pscustomobject]@{
    ok=$committed; committed=$committed; verified_exact=[bool]$verified;
    provisional=[bool]$provisional; readback_unavailable=[bool]$readbackUnavailable;
    target=$target; method=$method; displayed=@($state.displayed); catalog=@($catalog);
    selected=@($finalSelected);
    value=$state.value; clipboard=$state.clipboard; target_index=$targetIndex;
    selection_before=$selectionBefore; selection_after=$selectionAfter;
    contradictions=@($contradictions); pattern_errors=@($errors)
} | ConvertTo-Json -Compress -Depth 10
"""
    script = (
        script.replace("__TARGET__", target_ps)
        .replace("__HWND__", str(int(hwnd)))
        .replace("__X__", str(int(x)))
        .replace("__Y__", str(int(y)))
    )
    result = _run_powershell_json(script, timeout=timeout)
    if "candidates" not in result:
        merged: list[str] = []
        for value in [*(result.get("displayed") or []), *(result.get("selected") or [])]:
            item = str(value).strip()
            if item and item not in merged:
                merged.append(item)
        result["candidates"] = merged
    record_event("uia_combo_exact_v32", point=point, target=target, result=result)
    return result

def uia_set_edit_value_exact(
    hwnd: int,
    point: tuple[int, int],
    target: str,
    *,
    preferred_automation_id: str = "",
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Set a WPF Edit through UI Automation and read the committed value back.

    The RO temperature box is a WPF numeric edit (AutomationId=txtdifftemp).
    Mouse/keyboard replacement can appear to run while the numeric control keeps
    its old value.  This routine targets the exact AutomationId when available,
    uses ValuePattern.SetValue, commits with TAB, and only then reports success.
    """
    x, y = point
    target_ps = _ps_literal(str(target))
    aid_ps = _ps_literal(preferred_automation_id)
    script = rf"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms
$target = {target_ps}
$preferredAid = {aid_ps}
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(hwnd)})
$point = New-Object System.Windows.Point({x}, {y})
$editType = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Edit)
$edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editType)
$chosen = $null
$best = [double]::PositiveInfinity
foreach ($edit in $edits) {{
    $r = $edit.Current.BoundingRectangle
    if ($r.Width -le 0 -or $r.Height -le 0) {{ continue }}
    $aid = ([string]$edit.Current.AutomationId).Trim()
    $contains = ({x} -ge $r.Left -and {x} -le $r.Right -and {y} -ge $r.Top -and {y} -le $r.Bottom)
    $cx = ($r.Left + $r.Right) / 2.0
    $cy = ($r.Top + $r.Bottom) / 2.0
    $distance = [Math]::Abs($cx - {x}) + [Math]::Abs($cy - {y})
    $score = $distance
    if ($preferredAid -ne '' -and $aid -eq $preferredAid) {{ $score -= 100000 }}
    if ($contains) {{ $score -= 10000 }}
    if ($score -lt $best) {{ $best = $score; $chosen = $edit }}
}}
if ($null -eq $chosen) {{ throw 'edit_not_found' }}
$chosenAid = [string]$chosen.Current.AutomationId
$chosenName = [string]$chosen.Current.Name
$before = $null
$afterSet = $null
$afterCommit = $null
$readOnly = $null
$setMethod = ''
try {{
    $vp = $chosen.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $before = [string]$vp.Current.Value
    $readOnly = [bool]$vp.Current.IsReadOnly
    if (-not $readOnly) {{
        $vp.SetValue($target)
        $setMethod = 'ValuePattern.SetValue'
        Start-Sleep -Milliseconds 250
        $afterSet = [string]$vp.Current.Value
        try {{
            $chosen.SetFocus()
            [System.Windows.Forms.SendKeys]::SendWait('{{TAB}}')
            Start-Sleep -Milliseconds 300
        }} catch {{}}
        $afterCommit = [string]$vp.Current.Value
    }}
}} catch {{
    $valuePatternError = $_.Exception.Message
}}
if (($readOnly -eq $true) -or ($afterCommit -ne $target -and $afterSet -ne $target)) {{
    try {{
        $chosen.SetFocus()
        [System.Windows.Forms.SendKeys]::SendWait('^a')
        [System.Windows.Forms.SendKeys]::SendWait($target)
        [System.Windows.Forms.SendKeys]::SendWait('{{TAB}}')
        Start-Sleep -Milliseconds 350
        $vp2 = $chosen.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $afterCommit = [string]$vp2.Current.Value
        if ($setMethod -eq '') {{ $setMethod = 'SetFocus+SendKeys' }} else {{ $setMethod += '+SendKeysFallback' }}
    }} catch {{
        $sendKeysError = $_.Exception.Message
    }}
}}
$ok = ($afterCommit -eq $target -or $afterSet -eq $target)
[pscustomobject]@{{
    ok=$ok; target=$target; before=$before; after_set=$afterSet; after_commit=$afterCommit;
    automation_id=$chosenAid; name=$chosenName; read_only=$readOnly; method=$setMethod;
    value_pattern_error=$valuePatternError; sendkeys_error=$sendKeysError
}} | ConvertTo-Json -Compress -Depth 6
"""
    result = _run_powershell_json(script, timeout=timeout)
    record_event(
        "uia_set_edit_value",
        point=point,
        target=target,
        preferred_automation_id=preferred_automation_id,
        result=result,
    )
    return result


def uia_read_combo_candidates(
    hwnd: int, point: tuple[int, int], timeout: float = 12.0
) -> dict[str, Any]:
    """Read a WPF ComboBox through collapsed and expanded selection evidence.

    ``displayed`` contains only physical collapsed-presenter values. ``selected``
    contains SelectionPattern/SelectionItemPattern values observed while expanded.
    When both are empty, ``readback_unavailable`` is true and callers must defer to
    an authoritative WAVE validation step instead of rewriting a possibly correct
    membrane selection.
    """
    x, y = point
    script = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $OutputEncoding=[Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient; Add-Type -AssemblyName UIAutomationTypes; Add-Type -AssemblyName WindowsBase; Add-Type -AssemblyName System.Windows.Forms
$w=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]__HWND__)
if($null -eq $w){throw 'wave_window_not_found'}
$wavePid=$w.Current.ProcessId
$p=New-Object System.Windows.Point(__X__,__Y__)
$e=[System.Windows.Automation.AutomationElement]::FromPoint($p)
$walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
$c=$null
for($i=0;$i -lt 12 -and $null -ne $e;$i++){
    if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::ComboBox -and $e.Current.ProcessId -eq $wavePid){$c=$e;break}
    $e=$walker.GetParent($e)
}
if($null -eq $c){throw 'combo_not_found'}
function Add-U($list,[string]$v){if(-not [string]::IsNullOrWhiteSpace($v)){$v=$v.Trim();if(-not $list.Contains($v)){$list.Add($v)}}}
function Collapse-C {try{$ep=$c.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern);if($ep.Current.ExpandCollapseState -ne [System.Windows.Automation.ExpandCollapseState]::Collapsed){$ep.Collapse();Start-Sleep -Milliseconds 180}}catch{}}
function Expand-C {try{$ep=$c.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern);if($ep.Current.ExpandCollapseState -ne [System.Windows.Automation.ExpandCollapseState]::Expanded){$ep.Expand();Start-Sleep -Milliseconds 300}}catch{}}
Collapse-C
$displayed=New-Object System.Collections.Generic.List[string]
$selectedCollapsed=@()
$value=''
try{$sp=$c.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern);$selectedCollapsed=@($sp.GetCurrentSelection()|ForEach-Object{$_.Current.Name});foreach($v in $selectedCollapsed){Add-U $displayed ([string]$v)}}catch{}
try{$vp=$c.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);$value=[string]$vp.Current.Value;Add-U $displayed $value}catch{}
$cr=$c.Current.BoundingRectangle
try{
    $tc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Text)
    $ts=$c.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tc)
    foreach($t in $ts){
        $r=$t.Current.BoundingRectangle
        $finite=-not([double]::IsInfinity($r.Left)-or[double]::IsInfinity($r.Top)-or[double]::IsInfinity($r.Right)-or[double]::IsInfinity($r.Bottom)-or[double]::IsNaN($r.Left)-or[double]::IsNaN($r.Top))
        if(-not $finite -or $r.Width -le 0 -or $r.Height -le 0){continue}
        $cx=($r.Left+$r.Right)/2.0;$cy=($r.Top+$r.Bottom)/2.0
        if($cx -ge $cr.Left -and $cx -le $cr.Right -and $cy -ge $cr.Top -and $cy -le $cr.Bottom){Add-U $displayed ([string]$t.Current.Name)}
    }
}catch{}
$sy=[int](($cr.Top+$cr.Bottom)/2.0)
foreach($sx in @([int]($cr.Left+12),[int](($cr.Left+$cr.Right)/2.0),[int]($cr.Right-28))){
    try{$z=[System.Windows.Automation.AutomationElement]::FromPoint((New-Object System.Windows.Point($sx,$sy)));for($j=0;$j -lt 8 -and $null -ne $z;$j++){if($z -eq $c){break};if($z.Current.ProcessId -eq $wavePid){Add-U $displayed ([string]$z.Current.Name)};$z=$walker.GetParent($z)}}catch{}
}
$clipboard=''
try{$c.SetFocus();Start-Sleep -Milliseconds 60;[System.Windows.Forms.Clipboard]::Clear();[System.Windows.Forms.SendKeys]::SendWait('^c');Start-Sleep -Milliseconds 100;if([System.Windows.Forms.Clipboard]::ContainsText()){$clipboard=[System.Windows.Forms.Clipboard]::GetText().Trim();Add-U $displayed $clipboard}}catch{}

$selected=New-Object System.Collections.Generic.List[string]
$selectionPatternSupported=$false
Expand-C
try{$sp=$c.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern);$selectionPatternSupported=$true;foreach($item in @($sp.GetCurrentSelection())){Add-U $selected ([string]$item.Current.Name)}}catch{}
try{
    $lc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ListItem)
    $items=$c.FindAll([System.Windows.Automation.TreeScope]::Descendants,$lc)
    foreach($item in $items){
        try{$sip=$item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern);$selectionPatternSupported=$true;if($sip.Current.IsSelected){Add-U $selected ([string]$item.Current.Name)}}catch{}
    }
}catch{}
Collapse-C
$candidates=New-Object System.Collections.Generic.List[string]
foreach($v in $displayed){Add-U $candidates $v};foreach($v in $selected){Add-U $candidates $v}
$unavailable=($displayed.Count -eq 0 -and $selected.Count -eq 0 -and [string]::IsNullOrWhiteSpace($value) -and [string]::IsNullOrWhiteSpace($clipboard))
[pscustomobject]@{ok=$true;displayed=@($displayed);selected=@($selected);candidates=@($candidates);value=$value;clipboard=$clipboard;selection_pattern_supported=[bool]$selectionPatternSupported;readback_unavailable=[bool]$unavailable}|ConvertTo-Json -Compress -Depth 6
"""
    script = (
        script.replace("__HWND__", str(int(hwnd)))
        .replace("__X__", str(int(x)))
        .replace("__Y__", str(int(y)))
    )
    result = _run_powershell_json(script, timeout=timeout)
    record_event("uia_combo_readback_v32", point=point, result=result)
    return result

def uia_configure_flow_calculator_recoveries(
    dialog_hwnd: int, recoveries: list[float], timeout: float = 25.0
) -> dict[str, Any]:
    targets_json = json.dumps([_fmt_value(value) for value in recoveries])
    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$targets = ConvertFrom-Json {_ps_literal(targets_json)}
$window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{int(dialog_hwnd)})
if ($null -eq $window) {{ throw 'flow_window_not_found' }}
$editCondition = New-Object System.Windows.Automation.PropertyCondition(
 [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
 [System.Windows.Automation.ControlType]::Edit)
$buttonCondition = New-Object System.Windows.Automation.PropertyCondition(
 [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
 [System.Windows.Automation.ControlType]::Button)
$edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCondition)
$buttons = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $buttonCondition)
$inventory = @()
$editable = @()
foreach ($edit in $edits) {{
  $name=[string]$edit.Current.Name; $aid=[string]$edit.Current.AutomationId
  $r=$edit.Current.BoundingRectangle; $vp=$null; $value=$null; $ro=$true
  try {{ $vp=$edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); $value=[string]$vp.Current.Value; $ro=[bool]$vp.Current.IsReadOnly }} catch {{}}
  $row=[pscustomobject]@{{element=$edit; name=$name; aid=$aid; value=$value; read_only=$ro; top=$r.Top; left=$r.Left}}
  $inventory += [pscustomobject]@{{name=$name;automation_id=$aid;value=$value;read_only=$ro;top=$r.Top;left=$r.Left}}
  if ($null -ne $vp -and -not $ro -and $edit.Current.IsEnabled) {{ $editable += $row }}
}}
$applied=@()
for ($i=0; $i -lt $targets.Count; $i++) {{
  $passNo=$i+1; $chosen=$null
  foreach ($candidate in $editable) {{
    if ($candidate.aid -match ("(?i)^txtRecovery"+$passNo+"$") -or $candidate.name -match ("(?i)recovery.*"+$passNo+"$")) {{ $chosen=$candidate; break }}
  }}
  if ($null -eq $chosen) {{
    $recoveryCandidates=@($editable | Where-Object {{ $_.aid -match '(?i)recovery' -or $_.name -match '(?i)recovery' }} | Sort-Object top,left)
    if ($i -lt $recoveryCandidates.Count) {{ $chosen=$recoveryCandidates[$i] }}
  }}
  if ($null -eq $chosen) {{
    [pscustomobject]@{{ok=$false;error=('recovery_control_not_found_pass_'+$passNo);inventory=$inventory;applied=$applied}} | ConvertTo-Json -Compress -Depth 8
    exit 0
  }}
  $vp=$chosen.element.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  $vp.SetValue([string]$targets[$i]); Start-Sleep -Milliseconds 350
  $actual=[string]$vp.Current.Value
  $applied += [pscustomobject]@{{pass=$passNo;target=[string]$targets[$i];actual=$actual;name=$chosen.name;automation_id=$chosen.aid}}
}}
$ok=$null
foreach ($button in $buttons) {{
  $n=([string]$button.Current.Name).Trim(); $aid=([string]$button.Current.AutomationId).Trim()
  if ($n -match '^(?i:OK|확인)$' -or $aid -match '(?i)^ok$|okbutton|buttonok') {{ $ok=$button; break }}
}}
if ($null -eq $ok) {{ [pscustomobject]@{{ok=$false;error='ok_button_not_found';inventory=$inventory;applied=$applied}} | ConvertTo-Json -Compress -Depth 8; exit 0 }}
$invoke=$ok.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $invoke.Invoke()
[pscustomobject]@{{ok=$true;applied=$applied;inventory=$inventory}} | ConvertTo-Json -Compress -Depth 8
"""
    result = _run_powershell_json(script, timeout=timeout)
    record_event("uia_flow_calculator_multi", recoveries=recoveries, result=result)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "uia_flow_calculator_multi.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def uia_configure_chemical_adjustment(
    dialog_hwnd: int, case: ROCaseConfig
) -> dict[str, Any]:
    """Configure the complete RO Chemical Adjustment dialog.

    V52 covers all five chemistry panels observed in the user's video
    (acid, degas, base, anti-scalant and dechlorinator), plus the dialog-level
    Temperature and RO Recovery controls.  It also captures the calculation
    table and full WPF inventory before/after input so later failures can be
    diagnosed without replaying the video by hand.
    """
    cfg = case.chemical
    payload = {
        "acid_enabled": cfg.acid_enabled,
        "acid_type": cfg.acid_type,
        "acid_target_ph": cfg.acid_target_ph,
        "degas_enabled": cfg.degas_enabled,
        "degas_mode": cfg.degas_mode,
        "degas_value": cfg.degas_value,
        "base_enabled": cfg.base_enabled,
        "base_type": cfg.base_type,
        "base_target_ph": cfg.base_target_ph,
        "antiscalant_enabled": cfg.antiscalant_enabled,
        "antiscalant_type": cfg.antiscalant_type,
        "antiscalant_dose_mg_l": cfg.antiscalant_dose_mg_l,
        "dechlorinator_enabled": cfg.dechlorinator_enabled,
        "dechlorinator_type": cfg.dechlorinator_type,
        "dechlorinator_dose_mg_l": cfg.dechlorinator_dose_mg_l,
        "temperature_mode": cfg.temperature_mode,
        "temperature_c": cfg.temperature_c,
        "recovery_mode": cfg.recovery_mode,
        "recovery_value_pct": cfg.recovery_value_pct,
        # Whenever the Chemical dialog is opened, reconcile all five panels
        # and dialog-level defaults instead of assuming a fresh project.
        "reconcile_all_modes": True,
    }
    template = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $OutputEncoding=[Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AquaNovaMouseV52 {
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
}
'@
$cfg=ConvertFrom-Json __PAYLOAD__
$root=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]__HWND__)
if ($null -eq $root) { throw 'chemical_host_window_not_found' }
$rootRect=$root.Current.BoundingRectangle
$chemicalModePattern='(?i)(↓|down|lower).*pH|^\s*↓\s*pH|degas|(↑|up|raise).*pH|^\s*↑\s*pH|anti.?scal|dechlor'
function AllRoot($type) {
  $c=New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,$type)
  return @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$c))
}
function RectObject([double]$left,[double]$top,[double]$right,[double]$bottom) {
  return [pscustomobject]@{Left=$left;Top=$top;Right=$right;Bottom=$bottom;Width=($right-$left);Height=($bottom-$top)}
}
function RawCX($e) { $r=$e.Current.BoundingRectangle; return ($r.Left+$r.Right)/2 }
function RawCY($e) { $r=$e.Current.BoundingRectangle; return ($r.Top+$r.Bottom)/2 }
function ParentPath($e) {
  $items=@();$walker=[System.Windows.Automation.TreeWalker]::RawViewWalker;$node=$e
  for($depth=0;$depth -lt 8;$depth++) {
    try{$node=$walker.GetParent($node)}catch{$node=$null}
    if($null -eq $node){break}
    $items += [pscustomobject]@{
      depth=($depth+1);name=[string]$node.Current.Name;automation_id=[string]$node.Current.AutomationId;
      type=[string]$node.Current.ControlType.ProgrammaticName;class_name=[string]$node.Current.ClassName;
      framework_id=[string]$node.Current.FrameworkId
    }
  }
  return @($items)
}
function ElementDiag($e) {
  if($null -eq $e){return $null}
  $r=$e.Current.BoundingRectangle;$patterns=@();$value=$null;$readOnly=$null;$selected=$null;$toggle=$null
  try{$patterns=@($e.GetSupportedPatterns() | ForEach-Object {[string]$_.ProgrammaticName})}catch{}
  try{$vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);$value=[string]$vp.Current.Value;$readOnly=[bool]$vp.Current.IsReadOnly}catch{}
  try{$sp=$e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern);$selected=[bool]$sp.Current.IsSelected}catch{}
  try{$tp=$e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern);$toggle=[string]$tp.Current.ToggleState}catch{}
  return [pscustomobject]@{
    type=[string]$e.Current.ControlType.ProgrammaticName;localized_type=[string]$e.Current.LocalizedControlType;
    name=[string]$e.Current.Name;automation_id=[string]$e.Current.AutomationId;class_name=[string]$e.Current.ClassName;
    framework_id=[string]$e.Current.FrameworkId;enabled=[bool]$e.Current.IsEnabled;offscreen=[bool]$e.Current.IsOffscreen;
    focusable=[bool]$e.Current.IsKeyboardFocusable;has_focus=[bool]$e.Current.HasKeyboardFocus;
    left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom;width=$r.Width;height=$r.Height;
    center_x=(RawCX $e);center_y=(RawCY $e);value=$value;read_only=$readOnly;selected=$selected;
    toggle_state=$toggle;supported_patterns=$patterns;parent_path=(ParentPath $e)
  }
}
function DiagElements($type) {
  $items=@();foreach($e in (AllRoot $type)){$items += ElementDiag $e};return @($items | Sort-Object top,left)
}
$hostKind='top_level_window'
$modeButtonSource='root_named'
$w=$root
$wr=$rootRect
$rootName=([string]$root.Current.Name).Trim()
$titleCandidates=@(AllRoot ([System.Windows.Automation.ControlType]::Text) | Where-Object {
  ([string]$_.Current.Name).Trim() -match '^(?i:Chemical Adjustment)$'
})
$allRootButtons=@(AllRoot ([System.Windows.Automation.ControlType]::Button))
$namedModeButtons=@($allRootButtons | Where-Object {([string]$_.Current.Name) -match $chemicalModePattern})
$modeButtons=@($namedModeButtons)
if($rootName -notmatch '(?i)chemical adjustment') {
  if($modeButtons.Count -lt 2 -and $titleCandidates.Count -gt 0) {
    # Some WPF skins expose the large chemistry selectors as unnamed Buttons;
    # recover them by geometry only when the Chemical Adjustment title is also
    # present in the same HWND, preventing the main ribbon from being mistaken
    # for the panel.
    $geometryButtons=@($allRootButtons | Where-Object {
      $r=$_.Current.BoundingRectangle;$n=([string]$_.Current.Name).Trim()
      $_.Current.IsEnabled -and $r.Width -ge 95 -and $r.Height -ge 28 -and
      (RawCY $_) -ge ($rootRect.Top+$rootRect.Height*0.03) -and
      (RawCY $_) -le ($rootRect.Top+$rootRect.Height*0.30) -and
      $n -notmatch '^(?i:OK|확인|Cancel|취소)$'
    } | Sort-Object {RawCX $_})
    if($geometryButtons.Count -ge 2){$modeButtons=$geometryButtons;$modeButtonSource='title_plus_geometry'}
  }
  if($modeButtons.Count -lt 2) {
    [pscustomobject]@{
      ok=$false;error=('chemical_embedded_panel_not_found_mode_buttons_'+$modeButtons.Count);
      phase='host_detection';host_kind=$hostKind;mode_button_source=$modeButtonSource;
      root=(ElementDiag $root);root_rect=$rootRect;root_name=$rootName;
      title_candidates=@($titleCandidates | ForEach-Object {ElementDiag $_});
      named_mode_buttons=@($namedModeButtons | ForEach-Object {ElementDiag $_});
      all_buttons=(DiagElements ([System.Windows.Automation.ControlType]::Button));
      all_texts=(DiagElements ([System.Windows.Automation.ControlType]::Text));
      all_combos=(DiagElements ([System.Windows.Automation.ControlType]::ComboBox));
      all_edits=(DiagElements ([System.Windows.Automation.ControlType]::Edit));
      all_radios=(DiagElements ([System.Windows.Automation.ControlType]::RadioButton))
    } | ConvertTo-Json -Compress -Depth 16
    exit 0
  }
  $hostKind='embedded_wpf_overlay'
  $minButtonLeft=($modeButtons | ForEach-Object {$_.Current.BoundingRectangle.Left} | Measure-Object -Minimum).Minimum
  $minButtonTop=($modeButtons | ForEach-Object {$_.Current.BoundingRectangle.Top} | Measure-Object -Minimum).Minimum
  $maxButtonRight=($modeButtons | ForEach-Object {$_.Current.BoundingRectangle.Right} | Measure-Object -Maximum).Maximum
  $left=if($titleCandidates.Count -gt 0){$titleCandidates[0].Current.BoundingRectangle.Left}else{[Math]::Max($rootRect.Left,$minButtonLeft-$rootRect.Width*0.13)}
  $top=if($titleCandidates.Count -gt 0){$titleCandidates[0].Current.BoundingRectangle.Top}else{[Math]::Max($rootRect.Top,$minButtonTop-$rootRect.Height*0.07)}
  # The rightmost Anti-Scalant/Dechlorinator and Temperature/Recovery controls
  # may be logically outside the clipped viewport. Keep the geometry wide and
  # use UIA patterns even when IsOffscreen=True.
  $right=[Math]::Max($rootRect.Right,$maxButtonRight+$rootRect.Width*0.24)
  $bottom=$rootRect.Bottom-$rootRect.Height*0.08
  $wr=RectObject $left $top $right $bottom
}
$hostDiagnostics=[pscustomobject]@{
  root=(ElementDiag $root);host_kind=$hostKind;mode_button_source=$modeButtonSource;
  title_candidates=@($titleCandidates | ForEach-Object {ElementDiag $_});
  mode_buttons=@($modeButtons | ForEach-Object {ElementDiag $_})
}
function All($type) { return @(AllRoot $type) }
function CX($e) { $r=$e.Current.BoundingRectangle; return ($r.Left+$r.Right)/2 }
function CY($e) { $r=$e.Current.BoundingRectangle; return ($r.Top+$r.Bottom)/2 }
function ReadValue($e) {
  try { return [string]$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value } catch {}
  try {
    $sp=$e.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
    $sel=@($sp.Current.GetSelection())
    if($sel.Count -gt 0){ return [string]$sel[0].Current.Name }
  } catch {}
  return [string]$e.Current.Name
}
function Inventory() {
  $out=@()
  foreach($type in @(
    [System.Windows.Automation.ControlType]::Button,
    [System.Windows.Automation.ControlType]::ComboBox,
    [System.Windows.Automation.ControlType]::Edit,
    [System.Windows.Automation.ControlType]::RadioButton,
    [System.Windows.Automation.ControlType]::ListItem,
    [System.Windows.Automation.ControlType]::Text
  )) {
    foreach($e in (All $type)) {
      $r=$e.Current.BoundingRectangle; $value=$null; $readOnly=$null; $selected=$null; $toggle=$null
      try{$vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);$value=[string]$vp.Current.Value;$readOnly=[bool]$vp.Current.IsReadOnly}catch{}
      try{$sp=$e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern);$selected=[bool]$sp.Current.IsSelected}catch{}
      try{$tp=$e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern);$toggle=[string]$tp.Current.ToggleState}catch{}
      $patterns=@();try{$patterns=@($e.GetSupportedPatterns() | ForEach-Object {[string]$_.ProgrammaticName})}catch{}
      $out += [pscustomobject]@{
        type=[string]$e.Current.ControlType.ProgrammaticName;localized_type=[string]$e.Current.LocalizedControlType;
        name=[string]$e.Current.Name;automation_id=[string]$e.Current.AutomationId;class_name=[string]$e.Current.ClassName;
        framework_id=[string]$e.Current.FrameworkId;enabled=[bool]$e.Current.IsEnabled;offscreen=[bool]$e.Current.IsOffscreen;
        focusable=[bool]$e.Current.IsKeyboardFocusable;has_focus=[bool]$e.Current.HasKeyboardFocus;
        left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom;width=$r.Width;height=$r.Height;
        center_x=(CX $e);center_y=(CY $e);value=$value;read_only=$readOnly;selected=$selected;toggle_state=$toggle;
        supported_patterns=$patterns;parent_path=(ParentPath $e)
      }
    }
  }
  return @($out | Sort-Object top,left)
}
$phase='initial_inventory'
$script:comboSelectionDiagnostics=@()
$script:activeComboContext=$null
trap {
  $message=[string]$_.Exception.Message
  $position=[string]$_.InvocationInfo.PositionMessage
  $stack=[string]$_.ScriptStackTrace
  $diagInventory=@();try{$diagInventory=Inventory}catch{}
  $diagTable=@();try{$diagTable=TableSnapshot}catch{}
  [pscustomobject]@{
    ok=$false;error=$message;phase=$phase;position=$position;script_stack=$stack;
    host_kind=$hostKind;host_rect=$wr;host_diagnostics=$hostDiagnostics;config=$cfg;
    active_combo_context=$script:activeComboContext;
    combo_selection_diagnostics=@($script:comboSelectionDiagnostics);
    inventory=$diagInventory;table_snapshot=$diagTable
  } | ConvertTo-Json -Compress -Depth 16
  exit 0
}
function TopModeButtons() {
  $b=@($modeButtons | Where-Object {
    $y=(CY $_); $x=(CX $_)
    $y -ge ($wr.Top-$wr.Height*0.02) -and $y -lt ($wr.Top+$wr.Height*0.34) -and
    $x -ge ($wr.Left-$wr.Width*0.02) -and $x -le ($wr.Right+$wr.Width*0.05)
  } | Sort-Object {(CX $_)})
  return $b
}
function FindModeButton($regex,[int]$fallbackIndex) {
  $buttons=TopModeButtons
  foreach($b in $buttons){ if(([string]$b.Current.Name) -match $regex){ return $b } }
  if($fallbackIndex -ge 0 -and $fallbackIndex -lt $buttons.Count){ return $buttons[$fallbackIndex] }
  return $null
}
function FindAnyComboNear([double]$x,[double]$preferY,[double]$minY,[double]$maxY) {
  $best=$null;$bestD=1e99
  foreach($e in (All ([System.Windows.Automation.ControlType]::ComboBox))) {
    $r=$e.Current.BoundingRectangle;if($r.Width -le 0 -or $r.Height -le 0){continue}
    $y=(CY $e);if($y -lt $minY -or $y -gt $maxY){continue}
    $d=[Math]::Abs((CX $e)-$x)+0.35*[Math]::Abs($y-$preferY)
    if($d -lt $bestD){$best=$e;$bestD=$d}
  }
  return $best
}
function FindAnyEditNear([double]$x,[double]$preferY,[double]$minY,[double]$maxY) {
  $best=$null;$bestD=1e99
  foreach($e in (All ([System.Windows.Automation.ControlType]::Edit))) {
    $r=$e.Current.BoundingRectangle;if($r.Width -le 0 -or $r.Height -le 0){continue}
    $y=(CY $e);if($y -lt $minY -or $y -gt $maxY){continue}
    $d=[Math]::Abs((CX $e)-$x)+0.35*[Math]::Abs($y-$preferY)
    if($d -lt $bestD){$best=$e;$bestD=$d}
  }
  return $best
}
function ModeActive($label) {
  $x=[double]$panelCenters[$label]
  if($label -eq 'degas') {
    $radios=@(All ([System.Windows.Automation.ControlType]::RadioButton) | Where-Object {
      [Math]::Abs((CX $_)-$x) -lt $wr.Width*0.13 -and
      (CY $_) -ge $topMin -and (CY $_) -le $topMax
    })
    return [bool](@($radios | Where-Object {$_.Current.IsEnabled}).Count -gt 0)
  }
  $combo=FindAnyComboNear $x $comboY $topMin $topMax
  if($null -ne $combo){return [bool]$combo.Current.IsEnabled}
  $edit=FindAnyEditNear $x $editY $topMin $topMax
  if($null -ne $edit){return [bool]$edit.Current.IsEnabled}
  return $false
}
function WaitModeState($label,[bool]$desired) {
  for($i=0;$i -lt 12;$i++) {
    $actual=[bool](ModeActive $label)
    if($actual -eq $desired){return $true}
    Start-Sleep -Milliseconds 150
  }
  return $false
}
function SetModeState($regex,[int]$fallbackIndex,$label,[bool]$desired) {
  $b=FindModeButton $regex $fallbackIndex
  if($null -eq $b){throw ('mode_button_not_found_'+$label)}
  $before=[bool](ModeActive $label);$attempts=@();$strategy='already_correct'
  if($before -ne $desired) {
    $attempt=[ordered]@{strategy='uia_pattern';before=$before;desired=$desired;error=$null;after=$before}
    try {
      try {
        $tp=$b.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
        $tp.Toggle();$strategy='toggle_pattern'
      } catch {
        $ip=$b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        $ip.Invoke();$strategy='invoke_pattern'
      }
      $attempt.after=[bool](ModeActive $label)
    } catch {$attempt.error=[string]$_.Exception.Message}
    $attempts += [pscustomobject]$attempt
    $ok=WaitModeState $label $desired
    if(-not $ok) {
      $attempt=[ordered]@{strategy='mouse_click';before=[bool](ModeActive $label);desired=$desired;error=$null;after=$null}
      try {
        if(-not (ClickElement $b)){throw 'mode_button_click_point_unavailable'}
        $strategy='mouse_click';$attempt.after=[bool](ModeActive $label)
      } catch {$attempt.error=[string]$_.Exception.Message}
      $attempts += [pscustomobject]$attempt
      $ok=WaitModeState $label $desired
    }
    if(-not $ok) {
      throw ('mode_state_verify_failed_'+$label+'_target_'+$desired+'_actual_'+(ModeActive $label))
    }
  }
  $after=[bool](ModeActive $label)
  return [pscustomobject]@{
    field=($label+'_enabled');target=$desired;actual=$after;before=$before;strategy=$strategy;
    name=[string]$b.Current.Name;automation_id=[string]$b.Current.AutomationId;
    x=(CX $b);y=(CY $b);attempts=@($attempts)
  }
}
function FindComboNear([double]$x,[double]$preferY,[double]$minY,[double]$maxY) {
  $best=$null;$bestD=1e99
  foreach($e in (All ([System.Windows.Automation.ControlType]::ComboBox))) {
    if(-not $e.Current.IsEnabled){continue}
    $r=$e.Current.BoundingRectangle;if($r.Width -le 0 -or $r.Height -le 0){continue}
    $y=(CY $e); if($y -lt $minY -or $y -gt $maxY){continue}
    $d=[Math]::Abs((CX $e)-$x)+0.35*[Math]::Abs($y-$preferY)
    if($d -lt $bestD){$best=$e;$bestD=$d}
  }
  return $best
}
function ComboActual($combo) {
  try {
    $sp=$combo.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
    $sel=@($sp.Current.GetSelection());if($sel.Count -gt 0){return [string]$sel[0].Current.Name}
  } catch {}
  try {return [string]$combo.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value} catch {}
  return [string]$combo.Current.Name
}
function NormComboText($text) {
  if($null -eq $text){return ''}
  $s=([string]$text).Normalize([Text.NormalizationForm]::FormKC).Trim().ToLowerInvariant()
  # WAVE labels differ from workbook labels in harmless typography such as
  # H₂SO₄(98) vs H2SO4 (98). Preserve semantic punctuation but ignore spacing.
  return [regex]::Replace($s,'\s+','')
}
function ClickElement($e) {
  if($null -eq $e){return $false}
  $pt=$null
  try{$pt=$e.GetClickablePoint()}catch{}
  if($null -eq $pt){
    try{$r=$e.Current.BoundingRectangle;if($r.Width -gt 0 -and $r.Height -gt 0){$pt=[pscustomobject]@{X=(($r.Left+$r.Right)/2);Y=(($r.Top+$r.Bottom)/2)}}}catch{}
  }
  if($null -eq $pt){return $false}
  [System.Windows.Forms.Cursor]::Position=New-Object System.Drawing.Point([int][Math]::Round($pt.X),[int][Math]::Round($pt.Y))
  [AquaNovaMouseV52]::mouse_event(0x0002,0,0,0,[UIntPtr]::Zero)
  [AquaNovaMouseV52]::mouse_event(0x0004,0,0,0,[UIntPtr]::Zero)
  Start-Sleep -Milliseconds 180
  return $true
}
function SelectCombo($combo,$value,$label) {
  if($null -eq $combo){throw ('combo_not_found_'+$label)}
  $target=([string]$value).Trim();$targetKey=NormComboText $target
  $selected=$false;$strategy='selection_item';$attempts=@();$ep=$null
  $script:activeComboContext=[pscustomobject]@{
    field=$label;target=$target;combo=(ElementDiag $combo);stage='begin';attempts=@()
  }
  $initialActual=ComboActual $combo
  if((NormComboText ([string]$initialActual)) -eq $targetKey) {
    $diag=[pscustomobject]@{field=$label;target=$target;actual=$initialActual;selected=$true;strategy='already_selected';combo=(ElementDiag $combo);attempts=@()}
    $script:comboSelectionDiagnostics += $diag;$script:activeComboContext=$diag
    return [pscustomobject]@{field=$label;target=$target;actual=$initialActual;strategy='already_selected';selected=$true;name=[string]$combo.Current.Name;automation_id=[string]$combo.Current.AutomationId;x=(CX $combo);y=(CY $combo);attempts=@()}
  }
  try {
    $ep=$combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $ep.Expand();Start-Sleep -Milliseconds 350
    $matching=@(All ([System.Windows.Automation.ControlType]::ListItem) | Where-Object {
      (NormComboText ([string]$_.Current.Name)) -eq $targetKey
    })
    # WAVE exposes each visible combo item twice in some builds: a raw text/list
    # proxy without SelectionItemPattern followed by the selectable peer. Never
    # let the first proxy abort the entire candidate search.
    foreach($item in $matching) {
      $attempt=[ordered]@{strategy='selection_item';item=(ElementDiag $item);selected=$false;error=$null;actual_before=(ComboActual $combo);actual_after=$null}
      try {
        $sip=$item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
        $sip.Select();Start-Sleep -Milliseconds 300
        $attempt.selected=[bool]$sip.Current.IsSelected
        $attempt.actual_after=(ComboActual $combo)
        if($attempt.selected -or ((NormComboText ([string]$attempt.actual_after)) -eq $targetKey)) {
          $selected=$true;$strategy='selection_item';$attempts += [pscustomobject]$attempt;break
        }
      } catch {
        $attempt.error=[string]$_.Exception.Message
      }
      $attempts += [pscustomobject]$attempt
    }
    if(-not $selected) {
      foreach($item in $matching) {
        $attempt=[ordered]@{strategy='click_list_item';item=(ElementDiag $item);selected=$false;error=$null;actual_before=(ComboActual $combo);actual_after=$null}
        try {
          if(ClickElement $item){
            Start-Sleep -Milliseconds 300;$attempt.actual_after=(ComboActual $combo)
            if((NormComboText ([string]$attempt.actual_after)) -eq $targetKey){$selected=$true;$strategy='click_list_item';$attempt.selected=$true}
          }
        } catch {$attempt.error=[string]$_.Exception.Message}
        $attempts += [pscustomobject]$attempt
        if($selected){break}
      }
    }
  } catch {
    $attempts += [pscustomobject]@{strategy='expand_or_enumerate';selected=$false;error=[string]$_.Exception.Message;combo=(ElementDiag $combo)}
  }
  if(-not $selected) {
    # Editable ComboBox children can accept focus even when the ComboBox itself
    # reports IsKeyboardFocusable=False (the exact WAVE Acid selector behavior).
    $focusTargets=@()
    try {
      $editCondition=New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit)
      $focusTargets=@($combo.FindAll([System.Windows.Automation.TreeScope]::Descendants,$editCondition) | Where-Object {$_.Current.IsEnabled -and $_.Current.IsKeyboardFocusable})
    } catch {}
    if($combo.Current.IsKeyboardFocusable){$focusTargets=@($combo)+$focusTargets}
    foreach($focusTarget in $focusTargets) {
      $attempt=[ordered]@{strategy='keyboard_focus_target';focus_target=(ElementDiag $focusTarget);selected=$false;error=$null;actual_before=(ComboActual $combo);actual_after=$null}
      try {
        $focusTarget.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('^a');
        [System.Windows.Forms.SendKeys]::SendWait($target);[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 450
        $attempt.actual_after=(ComboActual $combo)
        if((NormComboText ([string]$attempt.actual_after)) -eq $targetKey){$selected=$true;$strategy='keyboard_focus_target';$attempt.selected=$true}
      } catch {$attempt.error=[string]$_.Exception.Message}
      $attempts += [pscustomobject]$attempt
      if($selected){break}
    }
  }
  if(-not $selected) {
    $attempt=[ordered]@{strategy='mouse_combo_keyboard';combo=(ElementDiag $combo);selected=$false;error=$null;actual_before=(ComboActual $combo);actual_after=$null}
    try {
      if(ClickElement $combo){
        [System.Windows.Forms.SendKeys]::SendWait($target);[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 500
        $attempt.actual_after=(ComboActual $combo)
        if((NormComboText ([string]$attempt.actual_after)) -eq $targetKey){$selected=$true;$strategy='mouse_combo_keyboard';$attempt.selected=$true}
      }
    } catch {$attempt.error=[string]$_.Exception.Message}
    $attempts += [pscustomobject]$attempt
  }
  try{if($null -ne $ep){$ep.Collapse()}}catch{}
  $actual=ComboActual $combo
  $diag=[pscustomobject]@{field=$label;target=$target;actual=$actual;selected=$selected;strategy=$strategy;combo=(ElementDiag $combo);attempts=@($attempts)}
  $script:comboSelectionDiagnostics += $diag
  $script:activeComboContext=$diag
  if(-not $selected -and -not ([string]$actual).Trim()) {
    throw ('combo_selection_failed_'+$label+'_target_'+$target+'_attempts_'+$attempts.Count)
  }
  if(([string]$actual).Trim() -and (NormComboText ([string]$actual)) -ne $targetKey) {
    throw ('combo_verify_failed_'+$label+'_target_'+$target+'_actual_'+$actual)
  }
  return [pscustomobject]@{field=$label;target=$target;actual=$actual;strategy=$strategy;selected=$selected;name=[string]$combo.Current.Name;automation_id=[string]$combo.Current.AutomationId;x=(CX $combo);y=(CY $combo);attempts=@($attempts)}
}
function FindWritableEditNear([double]$x,[double]$preferY,[double]$minY,[double]$maxY) {
  $best=$null;$bestD=1e99
  foreach($e in (All ([System.Windows.Automation.ControlType]::Edit))) {
    if(-not $e.Current.IsEnabled){continue}
    $r=$e.Current.BoundingRectangle;if($r.Width -le 0 -or $r.Height -le 0){continue}
    $y=(CY $e);if($y -lt $minY -or $y -gt $maxY){continue}
    try{$vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);if($vp.Current.IsReadOnly){continue}}catch{continue}
    $d=[Math]::Abs((CX $e)-$x)+0.4*[Math]::Abs($y-$preferY)
    if($d -lt $bestD){$best=$e;$bestD=$d}
  }
  return $best
}
function SetNumeric($edit,$value,$label) {
  if($null -eq $edit){throw ('editable_field_not_found_'+$label)}
  $vp=$edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  $vp.SetValue([string]$value);$edit.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 450
  $actual=[string]$vp.Current.Value;$targetNum=[double]$value;$actualNum=0.0
  if(-not [double]::TryParse($actual,[Globalization.NumberStyles]::Any,[Globalization.CultureInfo]::InvariantCulture,[ref]$actualNum)){
    if(-not [double]::TryParse($actual,[ref]$actualNum)){throw ('numeric_readback_failed_'+$label+'_'+$actual)}
  }
  if([Math]::Abs($actualNum-$targetNum) -gt 0.011){throw ('numeric_verify_failed_'+$label+'_target_'+$targetNum+'_actual_'+$actualNum)}
  return [pscustomobject]@{field=$label;target=$targetNum;actual=$actualNum;name=[string]$edit.Current.Name;automation_id=[string]$edit.Current.AutomationId;x=(CX $edit);y=(CY $edit)}
}
function TableSnapshot() {
  $cells=@()
  foreach($type in @([System.Windows.Automation.ControlType]::Text,[System.Windows.Automation.ControlType]::Edit)) {
    foreach($e in (All $type)) {
      $x=(CX $e);$y=(CY $e)
      if($x -ge ($wr.Left+$wr.Width*0.08) -and $x -le ($wr.Left+$wr.Width*0.68) -and $y -ge ($wr.Top+$wr.Height*0.36) -and $y -le ($wr.Bottom-$wr.Height*0.08)) {
        $cells += [pscustomobject]@{type=[string]$e.Current.ControlType.ProgrammaticName;name=[string]$e.Current.Name;value=(ReadValue $e);automation_id=[string]$e.Current.AutomationId;x=$x;y=$y}
      }
    }
  }
  return @($cells | Sort-Object y,x)
}
$phase='capture_before';$before=Inventory;$tableBefore=TableSnapshot;$applied=@();$panelCenters=@{}
$defs=@(
  @{label='acid';regex='(?i)(↓|down|lower).*pH|^\s*↓\s*pH';idx=0;fraction=0.18},
  @{label='degas';regex='(?i)degas';idx=1;fraction=0.38},
  @{label='base';regex='(?i)(↑|up|raise).*pH|^\s*↑\s*pH';idx=2;fraction=0.53},
  @{label='antiscalant';regex='(?i)anti.?scal';idx=3;fraction=0.66},
  @{label='dechlorinator';regex='(?i)dechlor';idx=4;fraction=0.79}
)
foreach($d in $defs){$b=FindModeButton $d.regex $d.idx;$panelCenters[$d.label]=if($null -ne $b){(CX $b)}else{$wr.Left+$wr.Width*$d.fraction}}
$topMin=$wr.Top+$wr.Height*0.08;$topMax=$wr.Top+$wr.Height*0.38;$comboY=$wr.Top+$wr.Height*0.18;$editY=$wr.Top+$wr.Height*0.26
$desiredModes=@{
  acid=[bool]$cfg.acid_enabled;degas=[bool]$cfg.degas_enabled;base=[bool]$cfg.base_enabled;
  antiscalant=[bool]$cfg.antiscalant_enabled;dechlorinator=[bool]$cfg.dechlorinator_enabled
}
$modeStateBefore=[ordered]@{}
foreach($label in @('acid','degas','base','antiscalant','dechlorinator')){$modeStateBefore[$label]=[bool](ModeActive $label)}
$phase='chemical_state_reconciliation';$reconciliation=@()
# Disable stale modes first. Base is deliberately disabled before Acid is
# enabled because WAVE prevents simultaneous down-pH and up-pH adjustment.
foreach($label in @('base','acid','degas','antiscalant','dechlorinator')) {
  if(-not [bool]$desiredModes[$label]) {
    $d=@($defs | Where-Object {$_.label -eq $label})[0]
    $item=SetModeState $d.regex $d.idx $label $false
    $reconciliation += $item;$applied += $item
  }
}
foreach($label in @('acid','degas','base','antiscalant','dechlorinator')) {
  if([bool]$desiredModes[$label]) {
    $d=@($defs | Where-Object {$_.label -eq $label})[0]
    $item=SetModeState $d.regex $d.idx $label $true
    $reconciliation += $item;$applied += $item
  }
}
$modeStateAfterReset=[ordered]@{}
foreach($label in @('acid','degas','base','antiscalant','dechlorinator')){$modeStateAfterReset[$label]=[bool](ModeActive $label)}
if($cfg.acid_enabled){$phase='acid_configuration'
  $applied += SelectCombo (FindComboNear $panelCenters.acid $comboY $topMin $topMax) $cfg.acid_type 'acid_type'
  $applied += SetNumeric (FindWritableEditNear $panelCenters.acid $editY $topMin $topMax) $cfg.acid_target_ph 'acid_target_ph'
}
if($cfg.degas_enabled){$phase='degas_configuration'
  $rs=@(All ([System.Windows.Automation.ControlType]::RadioButton) | Where-Object {
    $_.Current.IsEnabled -and [Math]::Abs((CX $_)-$panelCenters.degas) -lt $wr.Width*0.13 -and (CY $_) -lt ($wr.Top+$wr.Height*0.39)
  } | Sort-Object {(CY $_)})
  $wanted=if($cfg.degas_mode -eq 'CO2 Removal'){0}elseif($cfg.degas_mode -eq 'CO2 Partial Pressure'){1}else{2}
  if($wanted -ge $rs.Count){throw 'degas_radio_not_found'}
  $sp=$rs[$wanted].GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern);$sp.Select();Start-Sleep -Milliseconds 350
  if(-not $sp.Current.IsSelected){throw 'degas_radio_selection_failed'}
  $applied += [pscustomobject]@{field='degas_mode';target=[string]$cfg.degas_mode;actual=[string]$rs[$wanted].Current.Name;selected=$true;automation_id=[string]$rs[$wanted].Current.AutomationId;x=(CX $rs[$wanted]);y=(CY $rs[$wanted])}
  $applied += SetNumeric (FindWritableEditNear ($panelCenters.degas+$wr.Width*0.055) (CY $rs[$wanted]) $topMin $topMax) $cfg.degas_value 'degas_value'
}
if($cfg.base_enabled){$phase='base_configuration'
  $applied += SelectCombo (FindComboNear $panelCenters.base $comboY $topMin $topMax) $cfg.base_type 'base_type'
  $applied += SetNumeric (FindWritableEditNear $panelCenters.base $editY $topMin $topMax) $cfg.base_target_ph 'base_target_ph'
}
if($cfg.antiscalant_enabled){$phase='antiscalant_configuration'
  $applied += SelectCombo (FindComboNear $panelCenters.antiscalant $comboY $topMin $topMax) $cfg.antiscalant_type 'antiscalant_type'
  $applied += SetNumeric (FindWritableEditNear $panelCenters.antiscalant $editY $topMin $topMax) $cfg.antiscalant_dose_mg_l 'antiscalant_dose_mg_l'
}
if($cfg.dechlorinator_enabled){$phase='dechlorinator_configuration'
  $applied += SelectCombo (FindComboNear $panelCenters.dechlorinator $comboY $topMin $topMax) $cfg.dechlorinator_type 'dechlorinator_type'
  $applied += SetNumeric (FindWritableEditNear $panelCenters.dechlorinator $editY $topMin $topMax) $cfg.dechlorinator_dose_mg_l 'dechlorinator_dose_mg_l'
}
$rightCombos=@(All ([System.Windows.Automation.ControlType]::ComboBox) | Where-Object {(CX $_) -gt ($wr.Left+$wr.Width*0.69) -and (CY $_) -gt ($wr.Top+$wr.Height*0.40)} | Sort-Object {(CY $_)})
$effectiveTemperatureMode=if($cfg.temperature_mode){[string]$cfg.temperature_mode}elseif($cfg.reconcile_all_modes){'Design'}else{$null}
$effectiveRecoveryMode=if($cfg.recovery_mode){[string]$cfg.recovery_mode}elseif($cfg.reconcile_all_modes){'Based on RO config'}else{$null}
if($effectiveTemperatureMode){$phase='chemical_temperature_configuration'
  if($rightCombos.Count -lt 1){throw 'chemical_temperature_combo_not_found'}
  $tc=$rightCombos[0];$applied += SelectCombo $tc $effectiveTemperatureMode 'chemical_temperature_mode'
  if($effectiveTemperatureMode -eq 'Specify'){
    $applied += SetNumeric (FindWritableEditNear (CX $tc) ((CY $tc)+$wr.Height*0.055) ($wr.Top+$wr.Height*0.40) ($wr.Bottom-$wr.Height*0.08)) $cfg.temperature_c 'chemical_temperature_c'
  }
}
if($effectiveRecoveryMode){$phase='chemical_recovery_configuration'
  if($rightCombos.Count -lt 2){throw 'chemical_recovery_combo_not_found'}
  $rc=$rightCombos[$rightCombos.Count-1];$applied += SelectCombo $rc $effectiveRecoveryMode 'chemical_recovery_mode'
  if($effectiveRecoveryMode -eq 'Specify'){
    $applied += SetNumeric (FindWritableEditNear (CX $rc) ((CY $rc)+$wr.Height*0.055) ($wr.Top+$wr.Height*0.48) ($wr.Bottom-$wr.Height*0.05)) $cfg.recovery_value_pct 'chemical_recovery_value_pct'
  }
}
$phase='capture_after';Start-Sleep -Milliseconds 500
$after=Inventory;$tableAfter=TableSnapshot
$phase='ok_button_resolution';$buttons=All ([System.Windows.Automation.ControlType]::Button);$ok=$null
foreach($b in $buttons){if(([string]$b.Current.Name).Trim() -match '^(?i:OK|확인)$'){$ok=$b;break}}
if($null -eq $ok){throw 'ok_button_not_found'}
$phase='ok_invoke';$ok.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
$phase='close_verification';$closeVerified=$false
for($attempt=1;$attempt -le 60;$attempt++) {
  Start-Sleep -Milliseconds 200
  try {
    $visibleModes=@(AllRoot ([System.Windows.Automation.ControlType]::Button) | Where-Object {
      ([string]$_.Current.Name) -match $chemicalModePattern -and
      -not $_.Current.IsOffscreen -and
      $_.Current.BoundingRectangle.Width -gt 0 -and $_.Current.BoundingRectangle.Height -gt 0
    })
    if($visibleModes.Count -lt 2) {$closeVerified=$true;break}
  } catch {
    $closeVerified=$true;break
  }
}
if(-not $closeVerified){throw 'chemical_adjustment_not_closed_after_ok'}
$modeStateAfter=[ordered]@{}
foreach($label in @('acid','degas','base','antiscalant','dechlorinator')){$modeStateAfter[$label]=[bool]$desiredModes[$label]}
[pscustomobject]@{ok=$true;phase='completed';host_kind=$hostKind;host_name=$rootName;host_rect=$wr;host_diagnostics=$hostDiagnostics;mode_button_source=$modeButtonSource;close_verified=$closeVerified;config=$cfg;reconcile_all_modes=[bool]$cfg.reconcile_all_modes;mode_state_before=$modeStateBefore;mode_state_after_reset=$modeStateAfterReset;mode_state_after=$modeStateAfter;reconciliation=$reconciliation;applied=$applied;panel_centers=$panelCenters;inventory_before=$before;inventory_after=$after;table_before=$tableBefore;table_after=$tableAfter} | ConvertTo-Json -Compress -Depth 12
"""
    script = template.replace("__PAYLOAD__", _ps_literal(json.dumps(payload))).replace(
        "__HWND__", str(int(dialog_hwnd))
    )
    result = _run_powershell_json(script, timeout=70.0)
    record_event("uia_chemical_adjustment_v44", case_id=case.case_id, result=result)
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / f"chemical_{case.case_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (STATE.RUN_DIR / f"chemical_table_{case.case_id}.json").write_text(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "requested": payload,
                    "table_before": result.get("table_before", []),
                    "table_after": result.get("table_after", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return result



def uia_reconcile_ro_pass_count(
    hwnd: int,
    expected_pass_count: int,
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Make the visible RO pass topology match one or two passes.

    WAVE keeps Pass 2 when a later case requests only one pass.  That stale
    topology silently changes the exported system recovery even when every
    Pass 1 field is correct.  Reconcile the pass buttons through WPF UIA before
    any recovery/stage input is written, and verify the resulting count.
    """
    if expected_pass_count not in (1, 2):
        raise ValueError(f"expected_pass_count must be 1 or 2, got {expected_pass_count}")
    template = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();$OutputEncoding=[Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]__HWND__)
if($null -eq $root){throw 'wave_window_not_found'}
$expected=__EXPECTED__
function Buttons(){
  $c=New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button)
  return @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$c))
}
function Obj($e){
  $r=$e.Current.BoundingRectangle
  [pscustomobject]@{name=[string]$e.Current.Name;automation_id=[string]$e.Current.AutomationId;
    enabled=[bool]$e.Current.IsEnabled;offscreen=[bool]$e.Current.IsOffscreen;
    left=[double]$r.Left;top=[double]$r.Top;right=[double]$r.Right;bottom=[double]$r.Bottom;
    width=[double]$r.Width;height=[double]$r.Height}
}
function PassButtons(){
  $o=@()
  foreach($b in (Buttons)){
    $n=([string]$b.Current.Name).Trim()
    if($b.Current.AutomationId -eq 'btnPass' -and $n -match '^Pass [12]$' -and -not $b.Current.IsOffscreen){$o += ,$b}
  }
  return @($o | Sort-Object { $_.Current.BoundingRectangle.Top })
}
$beforeButtons=PassButtons
$before=@($beforeButtons | ForEach-Object {Obj $_})
$action='none';$candidate=$null
if($beforeButtons.Count -ne $expected){
  if($expected -eq 2 -and $beforeButtons.Count -eq 1){
    foreach($b in (Buttons)){
      if(([string]$b.Current.Name).Trim() -eq 'Add Pass' -and $b.Current.IsEnabled -and -not $b.Current.IsOffscreen){$candidate=$b;break}
    }
    if($null -eq $candidate){throw 'add_pass_button_not_found'}
    $candidate.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    $action='add_pass'
  } elseif($expected -eq 1 -and $beforeButtons.Count -eq 2){
    $pass2=@($beforeButtons | Where-Object {([string]$_.Current.Name).Trim() -eq 'Pass 2'})[0]
    if($null -eq $pass2){throw 'pass2_button_not_found'}
    $pr=$pass2.Current.BoundingRectangle
    $best=$null;$bestScore=1.0e9
    foreach($b in (Buttons)){
      if(-not $b.Current.IsEnabled -or $b.Current.IsOffscreen){continue}
      if(([string]$b.Current.Name).Trim()){continue}
      $r=$b.Current.BoundingRectangle
      $overlap=[Math]::Min($r.Bottom,$pr.Bottom)-[Math]::Max($r.Top,$pr.Top)
      $gap=$pr.Left-$r.Right
      if($overlap -le 4 -or $gap -lt -3 -or $gap -gt 35 -or $r.Width -gt 36 -or $r.Height -gt 48){continue}
      $score=[Math]::Abs(($r.Top+$r.Bottom)-($pr.Top+$pr.Bottom))+[Math]::Abs($gap)
      if($score -lt $bestScore){$best=$b;$bestScore=$score}
    }
    if($null -eq $best){throw 'delete_pass2_button_not_found'}
    $candidate=$best
    $best.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    $action='delete_pass2'
  } else {
    throw ('unexpected_pass_topology_before_'+$beforeButtons.Count+'_expected_'+$expected)
  }
  Start-Sleep -Milliseconds 1200
}
$afterButtons=PassButtons
$after=@($afterButtons | ForEach-Object {Obj $_})
if($afterButtons.Count -ne $expected){throw ('pass_count_verify_failed_actual_'+$afterButtons.Count+'_expected_'+$expected)}
[pscustomobject]@{ok=$true;expected=$expected;actual=$afterButtons.Count;action=$action;
  candidate=$(if($null -ne $candidate){Obj $candidate}else{$null});before=$before;after=$after} |
  ConvertTo-Json -Compress -Depth 8
"""
    script = template.replace("__HWND__", str(int(hwnd))).replace(
        "__EXPECTED__", str(int(expected_pass_count))
    )
    result = _run_powershell_json(script, timeout=timeout)
    record_event(
        "uia_ro_pass_count_reconcile_v52",
        hwnd=hwnd,
        expected_pass_count=expected_pass_count,
        result=result,
    )
    if STATE.RUN_DIR is not None:
        (STATE.RUN_DIR / "ro_pass_count_reconcile.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result

def uia_configure_special_feature_dialog(
    dialog_hwnd: int,
    *,
    feature: str,
    mode: str | None = None,
    value: float | None = None,
) -> dict[str, Any]:
    """Configure a simple Compaction or RO TOC Rejection dialog fail-closed.

    These dialogs differ by WAVE build.  V52 inventories every control, selects
    an exact combo/radio label when supplied, writes the sole writable numeric
    field when supplied, verifies readback, and then invokes OK.  Ambiguous
    dialogs fail instead of guessing.
    """
    payload = {"feature": feature, "mode": mode, "value": value}
    template = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();$OutputEncoding=[Console]::OutputEncoding
Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes;Add-Type -AssemblyName System.Windows.Forms
$cfg=ConvertFrom-Json __PAYLOAD__
$w=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]__HWND__)
if($null -eq $w){throw 'feature_window_not_found'}
function All($type){$c=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,$type);return @($w.FindAll([System.Windows.Automation.TreeScope]::Descendants,$c))}
function Inv(){
 $o=@();foreach($type in @([System.Windows.Automation.ControlType]::Button,[System.Windows.Automation.ControlType]::ComboBox,[System.Windows.Automation.ControlType]::Edit,[System.Windows.Automation.ControlType]::RadioButton,[System.Windows.Automation.ControlType]::ListItem,[System.Windows.Automation.ControlType]::Text)){
  foreach($e in (All $type)){$r=$e.Current.BoundingRectangle;$v=$null;$ro=$null;$sel=$null
   try{$vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);$v=[string]$vp.Current.Value;$ro=[bool]$vp.Current.IsReadOnly}catch{}
   try{$sp=$e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern);$sel=[bool]$sp.Current.IsSelected}catch{}
   $o += [pscustomobject]@{type=[string]$e.Current.ControlType.ProgrammaticName;name=[string]$e.Current.Name;automation_id=[string]$e.Current.AutomationId;enabled=[bool]$e.Current.IsEnabled;left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom;value=$v;read_only=$ro;selected=$sel}
  }
 };return $o
}
$before=Inv;$applied=@()
if($cfg.mode){
 $done=$false
 foreach($combo in (All ([System.Windows.Automation.ControlType]::ComboBox))){
  if(-not $combo.Current.IsEnabled){continue}
  try{$ep=$combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern);$ep.Expand();Start-Sleep -Milliseconds 200
   foreach($item in (All ([System.Windows.Automation.ControlType]::ListItem))){if(([string]$item.Current.Name).Trim().ToLowerInvariant() -eq ([string]$cfg.mode).Trim().ToLowerInvariant()){$item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select();$done=$true;break}}
   try{$ep.Collapse()}catch{}
  }catch{}
  if($done){$applied += [pscustomobject]@{field='mode';target=$cfg.mode;automation_id=[string]$combo.Current.AutomationId};break}
 }
 if(-not $done){throw ('feature_mode_not_found_'+$cfg.mode)}
}
if($null -ne $cfg.value){
 $writable=@()
 foreach($e in (All ([System.Windows.Automation.ControlType]::Edit))){if(-not $e.Current.IsEnabled){continue};try{$vp=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern);if(-not $vp.Current.IsReadOnly){$writable += ,@($e,$vp)}}catch{}}
 if($writable.Count -ne 1){throw ('ambiguous_writable_numeric_fields_'+$writable.Count)}
 $edit=$writable[0][0];$vp=$writable[0][1];$vp.SetValue([string]$cfg.value);$edit.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 350
 $actual=[string]$vp.Current.Value;$num=0.0;if(-not [double]::TryParse($actual,[ref]$num)){throw ('feature_numeric_readback_failed_'+$actual)}
 if([Math]::Abs($num-[double]$cfg.value) -gt 0.011){throw ('feature_numeric_verify_failed_'+$num)}
 $applied += [pscustomobject]@{field='value';target=[double]$cfg.value;actual=$num;automation_id=[string]$edit.Current.AutomationId}
}
$after=Inv;$ok=$null
foreach($b in (All ([System.Windows.Automation.ControlType]::Button))){if(([string]$b.Current.Name).Trim() -match '^(?i:OK|확인)$'){$ok=$b;break}}
if($null -eq $ok){throw 'feature_ok_not_found'}
$phase='ok_invoke';$ok.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
[pscustomobject]@{ok=$true;config=$cfg;applied=$applied;inventory_before=$before;inventory_after=$after}|ConvertTo-Json -Compress -Depth 10
"""
    script = template.replace("__PAYLOAD__", _ps_literal(json.dumps(payload))).replace(
        "__HWND__", str(int(dialog_hwnd))
    )
    result = _run_powershell_json(script, timeout=35.0)
    record_event("uia_ro_special_feature_v44", feature=feature, result=result)
    if STATE.RUN_DIR is not None:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", feature)
        (STATE.RUN_DIR / f"special_feature_{safe}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result
