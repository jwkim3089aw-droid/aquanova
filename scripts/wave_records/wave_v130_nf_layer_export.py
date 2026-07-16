from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

CANDIDATE_FILES = {
    "nf270": (
        DATA_DIR
        / "v129_nf270_v91_model_candidates.csv"
    ),
    "nf90_strict": (
        DATA_DIR
        / "v129_nf90_v91_model_candidates.csv"
    ),
    "nf90_allrows": (
        DATA_DIR
        / "v129_nf90_allrows_v91_model_candidates.csv"
    ),
}

OUTPUT = (
    DATA_DIR
    / "v130_nf_membrane_correction_layer.json"
)

SELECTIONS = [
    {
        "membrane": "NF270",
        "metric": "feed_pressure",
        "source": "nf270",
        "model_type": "scale_only",
        "runtime_enabled": True,
        "holdout_limit_pct": 2.0,
        "selection_reason": (
            "V91 recommended; simple scale model with "
            "sub-1% holdout error"
        ),
    },
    {
        "membrane": "NF270",
        "metric": "product_tds",
        "source": "nf270",
        "model_type": "affine_raw",
        "runtime_enabled": True,
        "holdout_limit_pct": 10.0,
        "selection_reason": (
            "V91 recommended; membrane-specific quality "
            "model required"
        ),
    },
    {
        "membrane": "NF270",
        "metric": "specific_energy",
        "source": "nf270",
        "model_type": "scale_only",
        "runtime_enabled": True,
        "holdout_limit_pct": 5.0,
        "selection_reason": (
            "V91 recommended; simple scale model"
        ),
    },
    {
        "membrane": "NF90",
        "metric": "feed_pressure",
        "source": "nf90_strict",
        "model_type": "scale_only",
        "runtime_enabled": True,
        "holdout_limit_pct": 5.0,
        "selection_reason": (
            "Conservative override: simpler than affine "
            "and lower holdout error"
        ),
    },
    {
        "membrane": "NF90",
        "metric": "specific_energy",
        "source": "nf90_strict",
        "model_type": "scale_only",
        "runtime_enabled": True,
        "holdout_limit_pct": 5.0,
        "selection_reason": (
            "Conservative override: simpler than affine "
            "and lower holdout error"
        ),
    },
    {
        "membrane": "NF90",
        "metric": "product_tds",
        "source": "nf90_allrows",
        "model_type": "affine_raw",
        "runtime_enabled": False,
        "holdout_limit_pct": 20.0,
        "selection_reason": (
            "Severe-input fit; retained as shadow-only "
            "until more NF90 anchors exist"
        ),
    },
]

ALIASES = {
    "NF270": [
        "NF270",
        "NF270-400",
        "NF270-400/34",
        "FilmTec NF270",
        "FilmTec NF270-400",
        "FilmTec NF270-400/34",
    ],
    "NF90": [
        "NF90",
        "NF90-400",
        "NF90-400/34",
        "FilmTec NF90",
        "FilmTec NF90-400",
        "FilmTec NF90-400/34",
    ],
}

FLOAT_FIELDS = (
    "selection_score",
    "train_raw_mean_abs_error_pct",
    "train_corrected_mean_abs_error_pct",
    "train_improvement_pct",
    "holdout_raw_mean_abs_error_pct",
    "holdout_corrected_mean_abs_error_pct",
    "holdout_improvement_pct",
    "holdout_corrected_p90_abs_error_pct",
)

INT_FIELDS = (
    "train_n",
    "holdout_n",
    "negative_prediction_count",
)


def to_float(value: Any) -> float:
    return float(value)


def to_int(value: Any) -> int:
    return int(float(value))


def boolish(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def load_candidates(
    path: Path,
) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def select_candidate(
    rows: list[dict[str, str]],
    *,
    metric: str,
    model_type: str,
) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row.get("process_type") == "nf"
        and row.get("metric") == metric
        and row.get("model_type") == model_type
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one candidate: "
            f"metric={metric}, "
            f"model_type={model_type}, "
            f"actual={len(matches)}"
        )

    return matches[0]


def model_id(
    membrane: str,
    metric: str,
    model_type: str,
) -> str:
    return (
        "v130_"
        f"{membrane.lower()}_"
        f"{metric}_"
        f"{model_type}"
    )


def build_model(
    spec: dict[str, Any],
    row: dict[str, str],
) -> dict[str, Any]:
    payload = json.loads(
        row["model_payload_json"]
    )

    if payload.get("model_type") != spec["model_type"]:
        raise RuntimeError(
            "Payload model-type mismatch: "
            f"{spec['membrane']}/"
            f"{spec['metric']}"
        )

    train_n = to_int(row["train_n"])
    holdout_n = to_int(row["holdout_n"])
    negative_count = to_int(
        row["negative_prediction_count"]
    )

    corrected_holdout = to_float(
        row["holdout_corrected_mean_abs_error_pct"]
    )
    holdout_improvement = to_float(
        row["holdout_improvement_pct"]
    )

    if train_n < 5:
        raise RuntimeError(
            f"Insufficient train rows: {spec}"
        )

    if holdout_n < 2:
        raise RuntimeError(
            f"Insufficient holdout rows: {spec}"
        )

    if negative_count != 0:
        raise RuntimeError(
            f"Negative predictions detected: {spec}"
        )

    if corrected_holdout > float(
        spec["holdout_limit_pct"]
    ):
        raise RuntimeError(
            "Holdout error exceeds V130 limit: "
            f"{spec['membrane']}/"
            f"{spec['metric']} "
            f"error={corrected_holdout}, "
            f"limit={spec['holdout_limit_pct']}"
        )

    if holdout_improvement <= 0:
        raise RuntimeError(
            f"No holdout improvement: {spec}"
        )

    performance = {}

    for field in FLOAT_FIELDS:
        performance[field] = to_float(row[field])

    for field in INT_FIELDS:
        performance[field] = to_int(row[field])

    membrane = spec["membrane"]

    return {
        "model_id": model_id(
            membrane,
            spec["metric"],
            spec["model_type"],
        ),
        "process_type": "nf",
        "metric": spec["metric"],
        "model_type": spec["model_type"],
        "regime": "nf_standard",
        "runtime_enabled": bool(
            spec["runtime_enabled"]
        ),
        "validation_mode": (
            "runtime_candidate"
            if spec["runtime_enabled"]
            else "shadow_only"
        ),
        "nonnegative_output": True,
        "applicability": {
            "membrane_family": membrane,
            "membrane_models": ALIASES[membrane],
        },
        "model_payload": payload,
        "performance": performance,
        "source": {
            "candidate_file": str(
                CANDIDATE_FILES[spec["source"]]
            ),
            "v91_recommended": boolish(
                row.get("recommended")
            ),
            "v91_promotion_status": (
                row.get("promotion_status") or ""
            ),
            "v91_promotion_flags": (
                row.get("promotion_flags") or ""
            ),
        },
        "selection_reason": (
            spec["selection_reason"]
        ),
    }


def main() -> int:
    candidate_sets = {
        name: load_candidates(path)
        for name, path in CANDIDATE_FILES.items()
    }

    models = []

    for spec in SELECTIONS:
        row = select_candidate(
            candidate_sets[spec["source"]],
            metric=spec["metric"],
            model_type=spec["model_type"],
        )

        models.append(
            build_model(spec, row)
        )

    identifiers = [
        model["model_id"]
        for model in models
    ]

    if len(set(identifiers)) != 6:
        raise RuntimeError(
            f"Duplicate model ids: {identifiers}"
        )

    runtime_models = [
        model
        for model in models
        if model["runtime_enabled"]
    ]

    shadow_models = [
        model
        for model in models
        if not model["runtime_enabled"]
    ]

    if len(runtime_models) != 5:
        raise RuntimeError(
            "Expected five runtime models, "
            f"actual={len(runtime_models)}"
        )

    if len(shadow_models) != 1:
        raise RuntimeError(
            "Expected one shadow model, "
            f"actual={len(shadow_models)}"
        )

    layer = {
        "schema_version": (
            "aquanova.wave_correction_layer.v130"
        ),
        "runtime_enabled_by_default": False,
        "summary": {
            "model_count": len(models),
            "runtime_model_count": len(
                runtime_models
            ),
            "shadow_model_count": len(
                shadow_models
            ),
            "process_counts": {
                "nf": len(models),
            },
            "membrane_counts": {
                "NF270": sum(
                    model["applicability"][
                        "membrane_family"
                    ] == "NF270"
                    for model in models
                ),
                "NF90": sum(
                    model["applicability"][
                        "membrane_family"
                    ] == "NF90"
                    for model in models
                ),
            },
            "excluded_metrics": [
                "recovery",
                "final_concentrate_tds",
            ],
            "installation_status": (
                "not_installed_shadow_validation_required"
            ),
        },
        "models": models,
    }

    OUTPUT.write_text(
        json.dumps(
            layer,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V130 NF MEMBRANE CORRECTION LAYER")
    print("=" * 80)
    print(f"output={OUTPUT}")
    print(f"model_count={len(models)}")
    print(
        f"runtime_model_count="
        f"{len(runtime_models)}"
    )
    print(
        f"shadow_model_count="
        f"{len(shadow_models)}"
    )

    print("\nMODELS")

    for model in models:
        perf = model["performance"]

        print(
            f"{model['model_id']} | "
            f"{model['validation_mode']} | "
            f"train_n={perf['train_n']} | "
            f"holdout_n={perf['holdout_n']} | "
            f"holdout_raw="
            f"{perf['holdout_raw_mean_abs_error_pct']:.6f}% | "
            f"holdout_corrected="
            f"{perf['holdout_corrected_mean_abs_error_pct']:.6f}% | "
            f"improvement="
            f"{perf['holdout_improvement_pct']:.6f}%"
        )

    print(
        "\nV130 NF membrane correction "
        "layer export PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
