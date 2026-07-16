# scripts/wave_v83_ui_contract_selftest.py
from __future__ import annotations

from pathlib import Path

REQUIRED = {
    "ui/src/features/simulation/editors/UnitForms/HRROEditor.tsx": [
        "PF 운전 모드 / P-3 연동",
        "smart_partial_drain",
        "field_optimized_low_fr",
        "외부 배출 setpoint",
        "Adaptive Recovery / Pump Limits",
        "p3_casing_pressure_rating_bar",
    ],
    "ui/src/features/simulation/model/logic.ts": [
        "pf_mode:",
        "brine_valve_mode:",
        "p3_recycle_capacity_m3h_per_pv:",
        "adaptive_recovery_enabled:",
        "p3_casing_pressure_rating_bar:",
    ],
    "ui/src/api/types.ts": [
        "pf_mode?:",
        "brine_valve_mode?:",
        "adaptive_recovery_enabled?:",
        "p3_casing_pressure_rating_bar?:",
    ],
    "ui/src/components/common/DetailedResultModal/tabs/AuditTab.tsx": [
        "HRRO PF 제어 / Adaptive Recovery",
        "pf_p3_recycle_flow_m3h_per_pv",
        "Adaptive Recovery stop reason",
    ],
}


def find_project_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here.parent.parent, *here.parents]:
        if (candidate / "app").is_dir() and (candidate / "ui" / "src").is_dir():
            return candidate
    return Path.cwd()


def main() -> None:
    root = find_project_root()
    missing: list[str] = []
    for rel, needles in REQUIRED.items():
        text_path = root / rel
        if not text_path.exists():
            missing.append(f"missing file: {rel}")
            continue
        text = text_path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: missing {needle!r}")
    if missing:
        raise SystemExit("V83 UI contract selftest FAILED:\n" + "\n".join(missing))
    print("V83 UI contract selftest PASS")


if __name__ == "__main__":
    main()
