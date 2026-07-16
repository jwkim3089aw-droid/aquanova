from __future__ import annotations

import copy
import hashlib
import json
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

DEFAULT_LAYER_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer.json"
)

NF_LAYER_PATH = (
    ROOT
    / "scripts/wave_records/results/_report_corpus"
    / "v130_nf_membrane_correction_layer.json"
)

CANDIDATE_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer_v131_candidate.json"
)

SUMMARY_PATH = (
    ROOT
    / "scripts/wave_records/results/_report_corpus"
    / "v131_nf_default_layer_merge_summary.json"
)

EXPECTED_NF_MODELS = {
    "v130_nf270_feed_pressure_scale_only",
    "v130_nf270_product_tds_affine_raw",
    "v130_nf270_specific_energy_scale_only",
    "v130_nf90_feed_pressure_scale_only",
    "v130_nf90_specific_energy_scale_only",
    "v130_nf90_product_tds_affine_raw",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def model_ids(
    models: list[dict[str, Any]],
) -> list[str]:
    ids = []

    for index, model in enumerate(models):
        model_id = str(model.get("model_id") or "")

        if not model_id:
            raise RuntimeError(
                f"Missing model_id at index={index}"
            )

        ids.append(model_id)

    return ids


def assert_unique(
    ids: list[str],
    label: str,
) -> None:
    duplicates = sorted(
        model_id
        for model_id, count in Counter(ids).items()
        if count > 1
    )

    if duplicates:
        raise RuntimeError(
            f"{label} duplicate model IDs: {duplicates}"
        )


def main() -> int:
    if not DEFAULT_LAYER_PATH.exists():
        print(
            f"FAIL: default layer missing: "
            f"{DEFAULT_LAYER_PATH}"
        )
        return 1

    if not NF_LAYER_PATH.exists():
        print(
            f"FAIL: NF layer missing: "
            f"{NF_LAYER_PATH}"
        )
        return 1

    default_hash_before = sha256(
        DEFAULT_LAYER_PATH
    )

    default_layer = load_correction_layer(
        DEFAULT_LAYER_PATH
    )

    nf_layer = load_correction_layer(
        NF_LAYER_PATH
    )

    default_models = list(
        default_layer.get("models") or []
    )

    nf_models = list(
        nf_layer.get("models") or []
    )

    default_ids = model_ids(default_models)
    nf_ids = model_ids(nf_models)

    assert_unique(default_ids, "default")
    assert_unique(nf_ids, "NF")

    if set(nf_ids) != EXPECTED_NF_MODELS:
        raise RuntimeError(
            "Unexpected NF model set:\n"
            f"expected={sorted(EXPECTED_NF_MODELS)}\n"
            f"actual={sorted(nf_ids)}"
        )

    overlap = sorted(
        set(default_ids) & set(nf_ids)
    )

    if overlap:
        raise RuntimeError(
            "Default layer already contains V130 NF "
            f"model IDs: {overlap}"
        )

    if len(nf_models) != 6:
        raise RuntimeError(
            f"Expected six NF models, "
            f"actual={len(nf_models)}"
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
            f"Expected five runtime NF models, "
            f"actual={len(runtime_nf)}"
        )

    if len(shadow_nf) != 1:
        raise RuntimeError(
            f"Expected one shadow NF model, "
            f"actual={len(shadow_nf)}"
        )

    shadow_id = shadow_nf[0]["model_id"]

    if shadow_id != (
        "v130_nf90_product_tds_affine_raw"
    ):
        raise RuntimeError(
            f"Unexpected shadow model: {shadow_id}"
        )

    for model in nf_models:
        if model.get("process_type") != "nf":
            raise RuntimeError(
                "Non-NF model found in NF layer: "
                f"{model.get('model_id')}"
            )

        applicability = (
            model.get("applicability") or {}
        )

        membrane_models = (
            applicability.get("membrane_models")
            or []
        )

        if not membrane_models:
            raise RuntimeError(
                "NF model lacks membrane scope: "
                f"{model.get('model_id')}"
            )

    merged = copy.deepcopy(default_layer)

    merged["schema_version"] = (
        "aquanova.wave_correction_layer.v131"
    )

    # 안전 원칙: 전역 기본 보정은 계속 OFF.
    merged["runtime_enabled_by_default"] = False

    merged["models"] = (
        copy.deepcopy(default_models)
        + copy.deepcopy(nf_models)
    )

    summary = copy.deepcopy(
        merged.get("summary") or {}
    )

    summary["v131_nf_default_layer_merge"] = {
        "status": (
            "candidate_not_installed"
        ),
        "default_source_path": str(
            DEFAULT_LAYER_PATH
        ),
        "nf_source_path": str(
            NF_LAYER_PATH
        ),
        "default_source_sha256": (
            default_hash_before
        ),
        "existing_model_count": len(
            default_models
        ),
        "nf_model_count": len(nf_models),
        "nf_runtime_model_count": len(
            runtime_nf
        ),
        "nf_shadow_model_count": len(
            shadow_nf
        ),
        "merged_model_count": len(
            merged["models"]
        ),
        "global_default_enabled": False,
        "nf90_product_tds_mode": (
            "shadow_only"
        ),
    }

    merged["summary"] = summary

    CANDIDATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = CANDIDATE_PATH.with_suffix(
        ".json.tmp"
    )

    temp_path.write_text(
        json.dumps(
            merged,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 공식 loader로 임시 파일 검증.
    validated = load_correction_layer(
        temp_path
    )

    validated_models = list(
        validated.get("models") or []
    )

    if len(validated_models) != (
        len(default_models) + 6
    ):
        raise RuntimeError(
            "Validated candidate model count mismatch"
        )

    temp_path.replace(CANDIDATE_PATH)

    default_hash_after = sha256(
        DEFAULT_LAYER_PATH
    )

    if default_hash_after != default_hash_before:
        raise RuntimeError(
            "Default layer changed during candidate merge"
        )

    process_counts = Counter(
        str(model.get("process_type") or "")
        for model in validated_models
    )

    result = {
        "schema_version": (
            "aquanova.nf_default_layer_merge.v131"
        ),
        "status": "PASS",
        "default_layer_unchanged": True,
        "default_layer_sha256": (
            default_hash_before
        ),
        "candidate_path": str(
            CANDIDATE_PATH
        ),
        "existing_model_count": len(
            default_models
        ),
        "added_nf_model_count": 6,
        "merged_model_count": len(
            validated_models
        ),
        "nf_runtime_model_count": 5,
        "nf_shadow_model_count": 1,
        "process_counts": dict(
            process_counts
        ),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V131 NF DEFAULT-LAYER CANDIDATE MERGE")
    print("=" * 80)
    print(
        f"default_layer={DEFAULT_LAYER_PATH}"
    )
    print(
        f"nf_layer={NF_LAYER_PATH}"
    )
    print(
        f"candidate={CANDIDATE_PATH}"
    )
    print(
        f"existing_model_count="
        f"{len(default_models)}"
    )
    print("added_nf_model_count=6")
    print(
        f"merged_model_count="
        f"{len(validated_models)}"
    )
    print("nf_runtime_model_count=5")
    print("nf_shadow_model_count=1")
    print(
        f"process_counts={dict(process_counts)}"
    )
    print("default_layer_unchanged=True")
    print("global_default_enabled=False")
    print(
        "\nV131 NF default-layer "
        "candidate merge PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
