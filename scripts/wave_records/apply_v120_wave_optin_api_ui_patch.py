#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


def _backup(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".v119_before_v120.bak")
    if path.exists() and not backup.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_typing(text: str) -> str:
    needed = ["Optional", "Dict", "Any"]
    m = re.search(r"from\s+typing\s+import\s+([^\n]+)", text)
    if not m:
        return "from typing import Optional, Dict, Any\n" + text
    names = [x.strip() for x in m.group(1).split(",")]
    changed = False
    for n in needed:
        if n not in names:
            names.append(n)
            changed = True
    return text if not changed else text[:m.start(1)] + ", ".join(names) + text[m.end(1):]


def patch_schema(root: Path) -> str:
    path = root / "app" / "schemas" / "simulation.py"
    if not path.exists():
        return "SKIP schema missing"
    _backup(path)
    text = path.read_text(encoding="utf-8")
    original = text
    text = _ensure_typing(text)

    if "wave_correction_enabled:" not in text:
        m = re.search(r"class\s+SimulationRequest\s*\([^)]*\):\n", text)
        if not m:
            raise SystemExit("SimulationRequest class not found")
        start = m.end()
        next_cls = text.find("\nclass ", start)
        end = next_cls if next_cls >= 0 else len(text)
        body = text[start:end]
        insert = (
            "    # V120: explicit opt-in only WAVE residual correction controls.\n"
            "    # Default path remains raw AquaNova physics.\n"
            "    wave_correction_enabled: bool = False\n"
            "    calibration_mode: Optional[str] = None\n"
        )
        pos = body.find("\n    scenario_name:")
        if pos >= 0:
            line_end = body.find("\n", pos + 1)
            ipos = start + line_end + 1
        else:
            ipos = start
        text = text[:ipos] + insert + text[ipos:]

    if "wave_correction_report:" not in text:
        m = re.search(r"class\s+ScenarioOutput\s*\([^)]*\):\n", text)
        if not m:
            raise SystemExit("ScenarioOutput class not found")
        start = m.end()
        next_cls = text.find("\nclass ", start)
        end = next_cls if next_cls >= 0 else len(text)
        body = text[start:end]
        field = (
            "    # V120: populated only when WAVE correction opt-in mode is explicitly enabled.\n"
            "    wave_correction_report: Optional[Dict[str, Any]] = None\n"
        )
        pos = body.find("\n    warnings:")
        if pos >= 0:
            line_end = body.find("\n", pos + 1)
            ipos = start + line_end + 1
        else:
            ipos = end
        text = text[:ipos] + field + text[ipos:]

    if text != original:
        path.write_text(text, encoding="utf-8")
        return "PATCHED app/schemas/simulation.py"
    return "UNCHANGED app/schemas/simulation.py"


def patch_endpoint(root: Path) -> str:
    path = root / "app" / "api" / "v1" / "endpoints" / "simulation.py"
    if not path.exists():
        return "SKIP endpoint missing"
    _backup(path)
    text = path.read_text(encoding="utf-8")
    original = text

    imp = "from app.services.simulation.wave_corrected_engine import run_simulation_with_optional_wave_correction\n"
    if "run_simulation_with_optional_wave_correction" not in text:
        anchor = "from app.services.simulation.engine import SimulationEngine\n"
        text = text.replace(anchor, anchor + imp) if anchor in text else imp + text

    if "V120: explicit WAVE correction opt-in" not in text:
        pat = re.compile(
            r"(?P<indent>\s*)engine\s*=\s*SimulationEngine\(\)\s*\n"
            r"(?P=indent)result(?:\s*:\s*ScenarioOutput)?\s*=\s*engine\.run\(request\)"
        )
        m = pat.search(text)
        if not m:
            raise SystemExit("Could not find SimulationEngine run block in simulation.py")
        ind = m.group("indent")
        block = (
            f"{ind}# V120: explicit WAVE correction opt-in. Default path stays raw SimulationEngine.\n"
            f"{ind}wave_correction_enabled = bool(getattr(request, 'wave_correction_enabled', False))\n"
            f"{ind}calibration_mode = str(getattr(request, 'calibration_mode', '') or '').strip().lower()\n"
            f"{ind}wave_correction_enabled = wave_correction_enabled or calibration_mode in {{\n"
            f"{ind}    'wave', 'wave_opt_in', 'wave_correction', 'wave_calibrated'\n"
            f"{ind}}}\n"
            f"{ind}if wave_correction_enabled:\n"
            f"{ind}    result, correction_report = run_simulation_with_optional_wave_correction(\n"
            f"{ind}        request,\n"
            f"{ind}        options={{'enable_wave_correction': True}},\n"
            f"{ind}    )\n"
            f"{ind}    try:\n"
            f"{ind}        if hasattr(result, 'model_copy'):\n"
            f"{ind}            result = result.model_copy(update={{'wave_correction_report': correction_report}})\n"
            f"{ind}        elif hasattr(result, 'copy'):\n"
            f"{ind}            result = result.copy(update={{'wave_correction_report': correction_report}})\n"
            f"{ind}        else:\n"
            f"{ind}            setattr(result, 'wave_correction_report', correction_report)\n"
            f"{ind}    except Exception:\n"
            f"{ind}        logger.warning('WAVE correction report could not be attached to response', exc_info=True)\n"
            f"{ind}else:\n"
            f"{ind}    engine = SimulationEngine()\n"
            f"{ind}    result = engine.run(request)"
        )
        text = text[:m.start()] + block + text[m.end():]

    if text != original:
        path.write_text(text, encoding="utf-8")
        return "PATCHED app/api/v1/endpoints/simulation.py"
    return "UNCHANGED app/api/v1/endpoints/simulation.py"


def patch_ui_types(root: Path) -> str:
    path = root / "ui" / "src" / "api" / "types.ts"
    if not path.exists():
        return "SKIP ui/src/api/types.ts missing"
    _backup(path)
    text = path.read_text(encoding="utf-8")
    original = text

    if "wave_correction_enabled" not in text:
        fields = (
            "  /** V120: explicit opt-in only. Default/raw mode is false. */\n"
            "  wave_correction_enabled?: boolean;\n"
            "  calibration_mode?: 'raw' | 'wave_opt_in' | string;\n"
        )
        m = re.search(r"(export\s+(?:interface|type)\s+SimulationRequest\s*(?:=)?\s*\{\n)", text)
        if m:
            text = text[:m.end()] + fields + text[m.end():]
        else:
            text += "\n\nexport type WaveCorrectionOptInFields = { wave_correction_enabled?: boolean; calibration_mode?: 'raw' | 'wave_opt_in' | string };\n"

    if text != original:
        path.write_text(text, encoding="utf-8")
        return "PATCHED ui/src/api/types.ts"
    return "UNCHANGED ui/src/api/types.ts"


def patch_flow_runner(root: Path) -> str:
    path = root / "ui" / "src" / "features" / "simulation" / "hooks" / "flow" / "useFlowRunner.ts"
    if not path.exists():
        return "SKIP useFlowRunner.ts missing"
    _backup(path)
    text = path.read_text(encoding="utf-8")
    original = text

    helper = """
function isWaveCorrectionOptIn(): boolean {
  try {
    if (typeof window === 'undefined') return false;
    const url = new URL(window.location.href);
    const queryValue =
      url.searchParams.get('wave_correction') ??
      url.searchParams.get('waveCorrection') ??
      url.searchParams.get('wave_calibration');
    if (['1', 'true', 'yes', 'on', 'wave'].includes(String(queryValue || '').toLowerCase())) return true;
    const stored =
      window.localStorage.getItem('aquanova.waveCorrectionEnabled') ??
      window.localStorage.getItem('aquanova.wave_correction_enabled');
    return ['1', 'true', 'yes', 'on', 'wave'].includes(String(stored || '').toLowerCase());
  } catch {
    return false;
  }
}

"""
    if "function isWaveCorrectionOptIn" not in text:
        m = re.search(r"\n(export\s+function\s+useFlowRunner|export\s+const\s+useFlowRunner|function\s+useFlowRunner|const\s+useFlowRunner)", text)
        pos = m.start() if m else 0
        text = text[:pos] + "\n" + helper + text[pos:]

    if "const waveCorrectionEnabled = isWaveCorrectionOptIn();" not in text:
        marker = "const payload: SimulationRequest = {"
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit("Could not find const payload: SimulationRequest = { in useFlowRunner.ts")
        line_start = text.rfind("\n", 0, idx) + 1
        indent = text[line_start:idx]
        text = text[:line_start] + indent + "const waveCorrectionEnabled = isWaveCorrectionOptIn();\n" + text[line_start:]

    if "wave_correction_enabled:" not in text:
        m = re.search(r"(\n\s*project_id:\s*resolveProjectId\(\),\n)", text)
        if m:
            add = m.group(1) + "        wave_correction_enabled: waveCorrectionEnabled,\n        calibration_mode: waveCorrectionEnabled ? 'wave_opt_in' : 'raw',\n"
            text = text[:m.start(1)] + add + text[m.end(1):]
        else:
            m = re.search(r"(const\s+payload:\s+SimulationRequest\s*=\s*\{\n)", text)
            if not m:
                raise SystemExit("Could not find payload insertion point in useFlowRunner.ts")
            text = text[:m.end()] + "        wave_correction_enabled: waveCorrectionEnabled,\n        calibration_mode: waveCorrectionEnabled ? 'wave_opt_in' : 'raw',\n" + text[m.end():]

    if text != original:
        path.write_text(text, encoding="utf-8")
        return "PATCHED ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
    return "UNCHANGED ui/src/features/simulation/hooks/flow/useFlowRunner.ts"


def main() -> int:
    root = Path.cwd().resolve()
    msgs = [
        patch_schema(root),
        patch_endpoint(root),
        patch_ui_types(root),
        patch_flow_runner(root),
    ]
    print("V120 WAVE opt-in API/UI payload patch complete")
    for msg in msgs:
        print(msg)
    print("Enable UI opt-in for test:")
    print("  localStorage.setItem('aquanova.waveCorrectionEnabled', 'true')")
    print("or append ?wave_correction=1 to the UI URL")
    print("Disable:")
    print("  localStorage.removeItem('aquanova.waveCorrectionEnabled')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
