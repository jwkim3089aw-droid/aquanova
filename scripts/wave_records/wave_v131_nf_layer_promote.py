from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (
    load_correction_layer,
)

CANDIDATE_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer_v131_candidate.json"
)

CANONICAL_DIR = (
    ROOT
    / "app/services/simulation/calibration/layers"
)

CANONICAL_PATH = (
    CANONICAL_DIR
    / "wave_correction_layer_v131.json"
)

EXPECTED_NF_IDS = {
    "v130_nf270_feed_pressure_scale_only",
    "v130_nf270_product_tds_affine_raw",
    "v130_nf270_specific_energy_scale_only",
    "v130_nf90_feed_pressure_scale_only",
    "v130_nf90_specific_energy_scale_only",
    "v130_nf90_product_tds_affine_raw",
}

DRIVE_PATH_PATTERN = re.compile(
    r"^[A-Za-z]:[\\/]"
)


def sanitize_string(value: str) -> str:
    normalized = value.replace("\\", "/")
    root_text = str(ROOT.resolve()).replace("\\", "/")

    prefix = root_text.rstrip("/") + "/"

    if normalized.lower().startswith(
        prefix.lower()
    ):
        return normalized[len(prefix):]

    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize(child)
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [
            sanitize(child)
            for child in value
        ]

    if isinstance(value, str):
        return sanitize_string(value)

    return value


def iter_strings(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)

    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)

    elif isinstance(value, str):
        yield value


def validate(layer: dict[str, Any]) -> None:
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

    if len(set(ids)) != len(ids):
        raise RuntimeError(
            "Duplicate model IDs detected"
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
            "Unexpected NF model set:\n"
            f"expected={sorted(EXPECTED_NF_IDS)}\n"
            f"actual={sorted(nf_ids)}"
        )

    runtime_nf = [
        model
        for model in nf_models
        if bool(model.get("runtime_enabled"))
    ]

    shadow_nf = [
        model
        for model in nf_models
        if not bool(model.get("runtime_enabled"))
    ]

    if len(runtime_nf) != 5:
        raise RuntimeError(
            "Expected five NF runtime models"
        )

    if len(shadow_nf) != 1:
        raise RuntimeError(
            "Expected one NF shadow model"
        )

    if shadow_nf[0].get("model_id") != (
        "v130_nf90_product_tds_affine_raw"
    ):
        raise RuntimeError(
            "NF90 product TDS must remain shadow-only"
        )

    if bool(
        layer.get("runtime_enabled_by_default")
    ):
        raise RuntimeError(
            "Global default correction must remain OFF"
        )

    absolute_paths = [
        text
        for text in iter_strings(layer)
        if DRIVE_PATH_PATTERN.match(text)
    ]

    if absolute_paths:
        raise RuntimeError(
            "Absolute paths remain in canonical layer:\n"
            + "\n".join(absolute_paths[:10])
        )


def main() -> int:
    if not CANDIDATE_PATH.exists():
        print(
            f"FAIL: candidate missing: "
            f"{CANDIDATE_PATH}"
        )
        return 1

    candidate = json.loads(
        CANDIDATE_PATH.read_text(
            encoding="utf-8"
        )
    )

    promoted = sanitize(candidate)

    promoted["schema_version"] = (
        "aquanova.wave_correction_layer.v131"
    )

    promoted[
        "runtime_enabled_by_default"
    ] = False

    summary = dict(
        promoted.get("summary") or {}
    )

    summary[
        "v131_nf_default_layer_merge"
    ] = {
        "status": "reviewed_runtime_artifact",
        "existing_model_count": 5,
        "nf_model_count": 6,
        "nf_runtime_model_count": 5,
        "nf_shadow_model_count": 1,
        "merged_model_count": 11,
        "global_default_enabled": False,
        "nf90_product_tds_mode": (
            "shadow_only"
        ),
        "source_campaign": (
            "V126-V130 NF membrane calibration"
        ),
    }

    promoted["summary"] = summary

    promoted["artifact"] = {
        "artifact_name": (
            "AquaNova V131 reviewed "
            "WAVE correction layer"
        ),
        "artifact_status": (
            "approved_for_opt_in_runtime"
        ),
        "installation_default": "disabled",
        "contains_machine_paths": False,
    }

    validate(promoted)

    CANONICAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = CANONICAL_PATH.with_suffix(
        ".json.tmp"
    )

    temp_path.write_text(
        json.dumps(
            promoted,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    validated = load_correction_layer(
        temp_path
    )

    validate(validated)

    os.replace(
        temp_path,
        CANONICAL_PATH,
    )

    process_counts = Counter(
        str(model.get("process_type") or "")
        for model in validated.get("models") or []
    )

    print("=" * 80)
    print("V131 CANONICAL LAYER PROMOTION")
    print("=" * 80)
    print(f"output={CANONICAL_PATH}")
    print("model_count=11")
    print("nf_runtime_model_count=5")
    print("nf_shadow_model_count=1")
    print(
        f"process_counts={dict(process_counts)}"
    )
    print("absolute_paths=0")
    print("global_default_enabled=False")
    print(
        "\nV131 canonical layer promotion PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
