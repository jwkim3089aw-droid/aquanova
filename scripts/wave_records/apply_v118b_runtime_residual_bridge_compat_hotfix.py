#!/usr/bin/env python3
from __future__ import annotations

import py_compile
from pathlib import Path

MARK_BEGIN = "# --- V118B residual runtime compatibility hotfix BEGIN ---"
MARK_END = "# --- V118B residual runtime compatibility hotfix END ---"
COMPAT_BLOCK = '\n# --- V118B residual runtime compatibility hotfix BEGIN ---\nimport importlib.machinery as _v118b_machinery\nimport importlib.util as _v118b_util\nfrom pathlib import Path as _V118BPath\n\n_V118B_RESIDUAL_APPLY = apply_wave_runtime_corrections_to_output\n\ndef _v118b_bool(value):\n    if isinstance(value, str):\n        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}\n    return bool(value)\n\ndef _v118b_option_enabled(options):\n    opts = dict(options or {})\n    for key in ("enable_wave_correction", "wave_correction_enabled", "enable_correction", "use_wave_correction", "apply_wave_correction"):\n        if key in opts and _v118b_bool(opts.get(key)):\n            return True\n    return False\n\ndef _v118b_disabled(options, config):\n    if _v118b_option_enabled(options):\n        return False\n    cfg = dict(config or {})\n    if "enabled" in cfg and not _v118b_bool(cfg.get("enabled")):\n        return True\n    return False\n\ndef _v118b_is_residual_layer(correction_layer):\n    layer = dict(correction_layer or {})\n    for model in layer.get("models") or []:\n        if not isinstance(model, dict):\n            continue\n        payload = model.get("model_payload") or {}\n        if str(payload.get("prediction_mode", "")).lower() == "bounded_residual_delta":\n            return True\n        if "delta_ratio" in payload:\n            return True\n    return False\n\ndef _v118b_legacy_apply():\n    helper_path = _V118BPath(__file__).resolve()\n    for suffix in (".v117_before_v118.bak", ".v118_syntax_error.bak", ".v118a_before_v118b.bak"):\n        backup = helper_path.with_suffix(helper_path.suffix + suffix)\n        if backup.exists():\n            loader = _v118b_machinery.SourceFileLoader("_aquanova_v118b_legacy_wave_runtime_correction", str(backup))\n            spec = _v118b_util.spec_from_loader(loader.name, loader)\n            if spec is None:\n                continue\n            module = _v118b_util.module_from_spec(spec)\n            loader.exec_module(module)\n            return getattr(module, "apply_wave_runtime_corrections_to_output", None)\n    return None\n\ndef apply_wave_runtime_corrections_to_output(\n    result,\n    correction_layer,\n    *,\n    options=None,\n    config=None,\n):\n    """V118B compatibility wrapper for legacy V94/V95 tests and V98/V117 residual layers."""\n    if _v118b_disabled(options, config):\n        return result, {\n            "schema_version": "aquanova.wave_runtime_correction.v118b",\n            "runtime_bridge": "v118b_compatibility_wrapper",\n            "enabled": False,\n            "status": "disabled",\n            "applied_count": 0,\n            "skipped_count": 0,\n            "corrections": [],\n        }\n\n    if _v118b_is_residual_layer(correction_layer):\n        corrected, report = _V118B_RESIDUAL_APPLY(result, correction_layer, options=options, config=config)\n        report = dict(report or {})\n        report["compatibility_wrapper"] = "v118b"\n        return corrected, report\n\n    legacy = _v118b_legacy_apply()\n    if legacy is not None:\n        return legacy(result, correction_layer, options=options, config=config)\n\n    return result, {\n        "schema_version": "aquanova.wave_runtime_correction.v118b",\n        "runtime_bridge": "v118b_compatibility_wrapper",\n        "enabled": True,\n        "status": "no_legacy_apply_available",\n        "applied_count": 0,\n        "skipped_count": 0,\n        "corrections": [],\n    }\n# --- V118B residual runtime compatibility hotfix END ---\n'

def strip_existing(text: str) -> str:
    if MARK_BEGIN not in text:
        return text
    start = text.index(MARK_BEGIN)
    end = text.index(MARK_END, start) + len(MARK_END)
    return text[:start].rstrip() + "\n" + text[end:].lstrip()

def main() -> int:
    root = Path.cwd().resolve()
    helper = root / "app" / "services" / "simulation" / "calibration" / "wave_runtime_correction.py"
    if not helper.exists():
        raise SystemExit(f"not found: {helper}")
    text = helper.read_text(encoding="utf-8")
    backup = helper.with_suffix(helper.suffix + ".v118a_before_v118b.bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    patched = strip_existing(text).rstrip() + "\n\n" + COMPAT_BLOCK.strip() + "\n"
    helper.write_text(patched, encoding="utf-8")
    py_compile.compile(str(helper), doraise=True)
    print("V118B compatibility hotfix applied")
    print(f"helper: {helper}")
    print(f"backup: {backup}")
    print("compile: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
