#!/usr/bin/env python3
"""V86 selftest: CCRO must select element before opening Flow Calculator."""
from __future__ import annotations

import inspect
from pathlib import Path


def main() -> None:
    import wave_ccro

    source = inspect.getsource(wave_ccro._configure_ccro_selected_pass_fields)
    required_tokens = [
        'element_before_flow_calculator_v86',
        'ccro_pass{pass_index}_element_ready_before_flow_v86',
        'Please specify Element Type in Pass 1 Stage 1',
    ]
    missing = [token for token in required_tokens if token not in source]
    if missing:
        raise AssertionError(f"V86 markers missing from wave_ccro.py: {missing}")

    element_idx = source.index('"element_type_combo"')
    flow_idx = source.index('_configure_ccro_flow_calculator(')
    if not element_idx < flow_idx:
        raise AssertionError(
            "CCRO Flow Calculator is still opened before Stage 1 element selection"
        )

    module_path = Path(wave_ccro.__file__).resolve()
    print(f"V86 CCRO element-before-flow selftest PASS: {module_path}")


if __name__ == "__main__":
    main()
