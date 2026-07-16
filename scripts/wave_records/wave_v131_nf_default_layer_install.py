from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
    load_correction_layer,
)
from app.services.simulation.wave_corrected_engine import (
    maybe_apply_wave_correction,
)

CANONICAL_PATH = (
    ROOT
    / "app/services/simulation/calibration/layers"
    / "wave_correction_layer_v131.json"
)

DEFAULT_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer.json"
)

CONFIG_PATH = (
    ROOT
    / ".data"
    / "wave_correction_runtime_config.json"
)

BACKUP_DIR = (
    ROOT
    / ".data"
    / "wave_correction_backups"
)

EXPECTED_NF_IDS = {
    "v130_nf270_feed_pressure_scale_only",
    "v130_nf270_product_tds_affine_raw",
    "v130_nf270_specific_energy_scale_only",
    "v130_nf90_feed_pressure_scale_only",
    "v130_nf90_specific_energy_scale_only",
    "v130_nf90_product_tds_affine_raw",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def boolish(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
        "enabled",
    }


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


def validate_layer(
    layer: dict[str, Any],
) -> None:
    models = list(
        layer.get("models") or []
    )

    if len(models) != 11:
        raise RuntimeError(
            f"Expected 11 models, actual={len(models)}"
        )

    ids = [
        str(model.get("model_id") or "")
        for model in models
    ]

    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "Duplicate model IDs"
        )

    nf_models = [
        model
        for model in models
        if model.get("process_type") == "nf"
    ]

    nf_ids = {
        str(model.get("model_id"))
        for model in nf_models
    }

    if nf_ids != EXPECTED_NF_IDS:
        raise RuntimeError(
            "Unexpected NF model set"
        )

    if bool(
        layer.get("runtime_enabled_by_default")
    ):
        raise RuntimeError(
            "Global runtime default must remain disabled"
        )


def correction(
    report: dict[str, Any],
    metric: str,
) -> dict[str, Any]:
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return dict(row)

    raise AssertionError(
        f"Missing correction metric: {metric}"
    )


def runtime_smoke(
    layer: dict[str, Any],
) -> None:
    disabled_raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    disabled_request = {
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF270-400/34"
                ),
            },
        ],
    }

    disabled_output, disabled_report = (
        maybe_apply_wave_correction(
            disabled_raw,
            request=disabled_request,
            correction_layer=layer,
            config={"enabled": False},
        )
    )

    if disabled_report.get("status") != "disabled":
        raise AssertionError(disabled_report)

    if disabled_output != disabled_raw:
        raise AssertionError(
            "Disabled runtime modified output"
        )

    nf270_raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    nf270_request = {
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

    nf270_output, nf270_report = (
        maybe_apply_wave_correction(
            nf270_raw,
            request=nf270_request,
            correction_layer=layer,
            config={"enabled": False},
        )
    )

    if nf270_report.get("applied_count") != 3:
        raise AssertionError(nf270_report)

    if nf270_report.get("shadow_count") != 0:
        raise AssertionError(nf270_report)

    for metric in (
        "feed_pressure",
        "product_tds",
        "specific_energy",
    ):
        row = correction(
            nf270_report,
            metric,
        )

        if row.get("status") != "applied":
            raise AssertionError(row)

        if not str(
            row.get("model_id") or ""
        ).startswith("v130_nf270_"):
            raise AssertionError(row)

    if close(
        nf270_output["system"][
            "feed_pressure_bar"
        ],
        nf270_raw["system"][
            "feed_pressure_bar"
        ],
    ):
        raise AssertionError(
            "NF270 pressure was not corrected"
        )

    nf90_raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 434.5,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    nf90_request = {
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

    nf90_output, nf90_report = (
        maybe_apply_wave_correction(
            nf90_raw,
            request=nf90_request,
            correction_layer=layer,
            config={"enabled": False},
        )
    )

    if nf90_report.get("applied_count") != 2:
        raise AssertionError(nf90_report)

    if nf90_report.get("shadow_count") != 1:
        raise AssertionError(nf90_report)

    product_row = correction(
        nf90_report,
        "product_tds",
    )

    if product_row.get("status") != "shadow_only":
        raise AssertionError(product_row)

    if not close(
        nf90_output["system"]["product_tds_mgL"],
        nf90_raw["system"]["product_tds_mgL"],
    ):
        raise AssertionError(
            "NF90 shadow changed product TDS"
        )

    missing_raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
        },
    }

    missing_output, missing_report = (
        apply_wave_runtime_corrections_to_output(
            missing_raw,
            layer,
            options={
                "enable_wave_correction": True,
            },
            config={"enabled": False},
        )
    )

    if missing_report.get("status") != (
        "missing_membrane_context"
    ):
        raise AssertionError(missing_report)

    if missing_output != missing_raw:
        raise AssertionError(
            "Missing membrane modified output"
        )


def config_enabled() -> bool:
    if not CONFIG_PATH.exists():
        return False

    config = json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    return boolish(config.get("enabled"))


def latest_manifest() -> Path:
    manifests = sorted(
        BACKUP_DIR.glob(
            "v131_install_*.json"
        ),
        reverse=True,
    )

    if not manifests:
        raise FileNotFoundError(
            "No V131 install manifest found"
        )

    return manifests[0]


def install() -> int:
    if not CANONICAL_PATH.exists():
        raise FileNotFoundError(
            CANONICAL_PATH
        )

    if not DEFAULT_PATH.exists():
        raise FileNotFoundError(
            DEFAULT_PATH
        )

    if config_enabled():
        raise RuntimeError(
            "Runtime config is globally enabled; "
            "installation stopped"
        )

    canonical = load_correction_layer(
        CANONICAL_PATH
    )

    validate_layer(canonical)

    old_layer = load_correction_layer(
        DEFAULT_PATH
    )

    old_models = list(
        old_layer.get("models") or []
    )

    if len(old_models) != 5:
        raise RuntimeError(
            "Expected five existing default models, "
            f"actual={len(old_models)}"
        )

    config_hash_before = (
        sha256(CONFIG_PATH)
        if CONFIG_PATH.exists()
        else None
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_path = (
        BACKUP_DIR
        / f"wave_correction_layer_pre_v131_"
        f"{timestamp}.json"
    )

    manifest_path = (
        BACKUP_DIR
        / f"v131_install_{timestamp}.json"
    )

    shutil.copy2(
        DEFAULT_PATH,
        backup_path,
    )

    temp_path = DEFAULT_PATH.with_suffix(
        ".json.v131.tmp"
    )

    try:
        shutil.copy2(
            CANONICAL_PATH,
            temp_path,
        )

        temp_layer = load_correction_layer(
            temp_path
        )

        validate_layer(temp_layer)

        if list(
            temp_layer.get("models") or []
        )[: len(old_models)] != old_models:
            raise RuntimeError(
                "Existing model order/content changed"
            )

        os.replace(
            temp_path,
            DEFAULT_PATH,
        )

        installed = load_correction_layer(
            DEFAULT_PATH
        )

        validate_layer(installed)

        if sha256(DEFAULT_PATH) != sha256(
            CANONICAL_PATH
        ):
            raise RuntimeError(
                "Installed layer hash mismatch"
            )

        if list(
            installed.get("models") or []
        )[: len(old_models)] != old_models:
            raise RuntimeError(
                "Installed existing models changed"
            )

        runtime_smoke(installed)

        config_hash_after = (
            sha256(CONFIG_PATH)
            if CONFIG_PATH.exists()
            else None
        )

        if config_hash_after != config_hash_before:
            raise RuntimeError(
                "Runtime config changed during install"
            )

        if config_enabled():
            raise RuntimeError(
                "Global runtime correction became enabled"
            )

        manifest = {
            "schema_version": (
                "aquanova.wave_layer_install.v131"
            ),
            "status": "PASS",
            "installed_at_utc": timestamp,
            "canonical_path": str(
                CANONICAL_PATH
            ),
            "default_path": str(
                DEFAULT_PATH
            ),
            "backup_path": str(
                backup_path
            ),
            "canonical_sha256": sha256(
                CANONICAL_PATH
            ),
            "installed_sha256": sha256(
                DEFAULT_PATH
            ),
            "backup_sha256": sha256(
                backup_path
            ),
            "existing_model_count": 5,
            "installed_model_count": 11,
            "nf_model_count": 6,
            "global_enabled": False,
            "runtime_smoke": "PASS",
        }

        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        restore_temp = DEFAULT_PATH.with_suffix(
            ".json.restore.tmp"
        )

        shutil.copy2(
            backup_path,
            restore_temp,
        )

        os.replace(
            restore_temp,
            DEFAULT_PATH,
        )

        raise

    print("=" * 80)
    print("V131 NF DEFAULT-LAYER INSTALL")
    print("=" * 80)
    print(f"canonical={CANONICAL_PATH}")
    print(f"default={DEFAULT_PATH}")
    print(f"backup={backup_path}")
    print(f"manifest={manifest_path}")
    print("existing_model_count=5")
    print("installed_model_count=11")
    print("added_nf_model_count=6")
    print("runtime_smoke=PASS")
    print("config_unchanged=True")
    print("global_enabled=False")
    print(
        "\nV131 NF default-layer install PASS"
    )

    return 0


def verify() -> int:
    installed = load_correction_layer(
        DEFAULT_PATH
    )

    validate_layer(installed)
    runtime_smoke(installed)

    if sha256(DEFAULT_PATH) != sha256(
        CANONICAL_PATH
    ):
        raise RuntimeError(
            "Default/canonical hash mismatch"
        )

    if config_enabled():
        raise RuntimeError(
            "Global runtime correction is enabled"
        )

    print("=" * 80)
    print("V131 NF DEFAULT-LAYER VERIFY")
    print("=" * 80)
    print("installed_model_count=11")
    print("nf_model_count=6")
    print("runtime_smoke=PASS")
    print("canonical_hash_match=True")
    print("global_enabled=False")
    print(
        "\nV131 NF default-layer verify PASS"
    )

    return 0


def rollback_latest() -> int:
    manifest_path = latest_manifest()

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    backup_path = Path(
        manifest["backup_path"]
    )

    if not backup_path.exists():
        raise FileNotFoundError(
            backup_path
        )

    restore_temp = DEFAULT_PATH.with_suffix(
        ".json.rollback.tmp"
    )

    shutil.copy2(
        backup_path,
        restore_temp,
    )

    load_correction_layer(
        restore_temp
    )

    os.replace(
        restore_temp,
        DEFAULT_PATH,
    )

    print("=" * 80)
    print("V131 NF DEFAULT-LAYER ROLLBACK")
    print("=" * 80)
    print(f"manifest={manifest_path}")
    print(f"restored_from={backup_path}")
    print(f"default={DEFAULT_PATH}")
    print(
        "\nV131 NF default-layer rollback PASS"
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "action",
        choices=(
            "install",
            "verify",
            "rollback-latest",
        ),
    )

    args = parser.parse_args()

    if args.action == "install":
        return install()

    if args.action == "verify":
        return verify()

    return rollback_latest()


if __name__ == "__main__":
    raise SystemExit(main())
