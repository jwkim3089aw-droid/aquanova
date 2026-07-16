from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (
    load_correction_layer,
)
from app.services.simulation.wave_corrected_engine import (
    maybe_apply_wave_correction,
)

SOURCE_LAYER = (
    ROOT
    / "scripts/wave_records/results/_report_corpus"
    / "v130_nf_membrane_correction_layer.json"
)

INSTALL_DIR = ROOT / ".data"

INSTALLED_LAYER = (
    INSTALL_DIR
    / "wave_correction_layer_v130_nf.json"
)

INSTALLED_CONFIG = (
    INSTALL_DIR
    / "wave_correction_runtime_config_v130_nf.json"
)

DEFAULT_LAYER = (
    INSTALL_DIR
    / "wave_correction_layer.json"
)

DEFAULT_CONFIG = (
    INSTALL_DIR
    / "wave_correction_runtime_config.json"
)


def close(
    actual: Any,
    expected: Any,
    tolerance: float = 1e-8,
) -> bool:
    return math.isclose(
        float(actual),
        float(expected),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def find_metric(report, metric: str) -> dict[str, Any]:
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return dict(row)

    raise AssertionError(
        f"Missing correction report metric: {metric}"
    )


def snapshot(path: Path) -> bytes | None:
    if not path.exists():
        return None

    return path.read_bytes()


def assert_unchanged(
    path: Path,
    before: bytes | None,
) -> None:
    after = snapshot(path)

    if after != before:
        raise AssertionError(
            f"Default runtime file was modified: {path}"
        )


def install_isolated() -> None:
    if not SOURCE_LAYER.exists():
        raise FileNotFoundError(SOURCE_LAYER)

    INSTALL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        SOURCE_LAYER,
        INSTALLED_LAYER,
    )

    config = {
        "schema_version": (
            "aquanova.wave_runtime_correction.v130"
        ),
        "enabled": False,
        "correction_layer_path": str(
            INSTALLED_LAYER
        ),
        "installation_mode": (
            "isolated_opt_in_only"
        ),
        "notes": (
            "V130 NF270/NF90 membrane-scoped layer. "
            "The normal AquaNova default config is unchanged."
        ),
    }

    INSTALLED_CONFIG.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_disabled_test(
    layer: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    request = {
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF270-400/34"
                ),
            },
        ],
    }

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=layer,
        config={
            "enabled": False,
            "correction_layer_path": str(
                INSTALLED_LAYER
            ),
        },
    )

    if report.get("status") != "disabled":
        raise AssertionError(report)

    if corrected != raw:
        raise AssertionError(
            "Disabled correction modified output"
        )

    print("Default-disabled behavior PASS")


def run_nf270_test(
    layer: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    request = {
        "enable_wave_correction": True,
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF270-400/34"
                ),
            },
        ],
    }

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=layer,
        config={
            "enabled": False,
            "correction_layer_path": str(
                INSTALLED_LAYER
            ),
        },
    )

    if report.get("status") != "corrected":
        raise AssertionError(report)

    if report.get("applied_count") != 3:
        raise AssertionError(report)

    if report.get("shadow_count") != 0:
        raise AssertionError(report)

    pressure = find_metric(
        report,
        "feed_pressure",
    )

    product = find_metric(
        report,
        "product_tds",
    )

    energy = find_metric(
        report,
        "specific_energy",
    )

    if not pressure["model_id"].startswith(
        "v130_nf270_"
    ):
        raise AssertionError(pressure)

    if not product["model_id"].startswith(
        "v130_nf270_"
    ):
        raise AssertionError(product)

    if not energy["model_id"].startswith(
        "v130_nf270_"
    ):
        raise AssertionError(energy)

    if close(
        corrected["system"]["feed_pressure_bar"],
        raw["system"]["feed_pressure_bar"],
    ):
        raise AssertionError(
            "NF270 pressure was not corrected"
        )

    print("Installed NF270 opt-in PASS")


def run_nf90_test(
    layer: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 434.5,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    request = {
        "enable_wave_correction": True,
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF90-400/34"
                ),
            },
        ],
    }

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=layer,
        config={
            "enabled": False,
            "correction_layer_path": str(
                INSTALLED_LAYER
            ),
        },
    )

    if report.get("status") != "corrected":
        raise AssertionError(report)

    if report.get("applied_count") != 2:
        raise AssertionError(report)

    if report.get("shadow_count") != 1:
        raise AssertionError(report)

    pressure = find_metric(
        report,
        "feed_pressure",
    )

    product = find_metric(
        report,
        "product_tds",
    )

    energy = find_metric(
        report,
        "specific_energy",
    )

    if not pressure["model_id"].startswith(
        "v130_nf90_"
    ):
        raise AssertionError(pressure)

    if not product["model_id"].startswith(
        "v130_nf90_"
    ):
        raise AssertionError(product)

    if not energy["model_id"].startswith(
        "v130_nf90_"
    ):
        raise AssertionError(energy)

    if product.get("status") != "shadow_only":
        raise AssertionError(product)

    if not close(
        corrected["system"]["product_tds_mgL"],
        raw["system"]["product_tds_mgL"],
    ):
        raise AssertionError(
            "NF90 product TDS shadow changed output"
        )

    if product.get(
        "shadow_corrected_value"
    ) is None:
        raise AssertionError(product)

    print("Installed NF90 opt-in/shadow PASS")


def main() -> int:
    default_layer_before = snapshot(
        DEFAULT_LAYER
    )

    default_config_before = snapshot(
        DEFAULT_CONFIG
    )

    install_isolated()

    layer = load_correction_layer(
        INSTALLED_LAYER
    )

    if len(layer.get("models") or []) != 6:
        raise AssertionError(
            "Installed layer must contain six models"
        )

    run_disabled_test(layer)
    run_nf270_test(layer)
    run_nf90_test(layer)

    assert_unchanged(
        DEFAULT_LAYER,
        default_layer_before,
    )

    assert_unchanged(
        DEFAULT_CONFIG,
        default_config_before,
    )

    print("=" * 80)
    print("V130 NF ISOLATED INSTALL SMOKE")
    print("=" * 80)
    print(f"source={SOURCE_LAYER}")
    print(f"installed_layer={INSTALLED_LAYER}")
    print(f"installed_config={INSTALLED_CONFIG}")
    print("default_layer_unchanged=True")
    print("default_config_unchanged=True")
    print("global_enabled=False")
    print(
        "\nV130 NF isolated install smoke PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
