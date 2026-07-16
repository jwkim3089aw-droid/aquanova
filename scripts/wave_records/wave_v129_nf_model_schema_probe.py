from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

SCOPES = {
    "NF270_STRICT": {
        "recommended": DATA_DIR / "v129_nf270_v91_recommended_models.json",
        "candidates": DATA_DIR / "v129_nf270_v91_model_candidates.csv",
    },
    "NF90_STRICT": {
        "recommended": DATA_DIR / "v129_nf90_v91_recommended_models.json",
        "candidates": DATA_DIR / "v129_nf90_v91_model_candidates.csv",
    },
    "NF90_ALLROWS": {
        "recommended": DATA_DIR / "v129_nf90_allrows_v91_recommended_models.json",
        "candidates": DATA_DIR / "v129_nf90_allrows_v91_model_candidates.csv",
    },
}

TARGET_METRICS = {
    "feed_pressure",
    "product_tds",
    "final_concentrate_tds",
    "specific_energy",
}


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def find_metric_dicts(value: Any):
    if isinstance(value, dict):
        metric = value.get("metric")

        if metric:
            yield value

        for child in value.values():
            yield from find_metric_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from find_metric_dicts(child)


def compact_dict(row: dict[str, Any]) -> dict[str, Any]:
    selected = {}

    important_tokens = (
        "metric",
        "model",
        "family",
        "type",
        "train",
        "holdout",
        "error",
        "improvement",
        "coefficient",
        "intercept",
        "slope",
        "scale",
        "parameter",
        "formula",
        "feature",
        "sample",
        "count",
        "_n",
    )

    for key, value in row.items():
        key_lower = key.lower()

        if any(token in key_lower for token in important_tokens):
            selected[key] = value

    return selected


def inspect_scope(
    name: str,
    recommended_path: Path,
    candidates_path: Path,
) -> None:
    print("=" * 100)
    print(name)
    print("=" * 100)

    if not recommended_path.exists():
        raise FileNotFoundError(recommended_path)

    if not candidates_path.exists():
        raise FileNotFoundError(candidates_path)

    payload = json.loads(
        recommended_path.read_text(encoding="utf-8")
    )

    print("\nRECOMMENDED JSON")
    print(f"path={recommended_path}")
    print(f"top_level_type={type(payload).__name__}")

    if isinstance(payload, dict):
        print(f"top_level_keys={list(payload.keys())}")

    models = []

    seen = set()

    for model in find_metric_dicts(payload):
        metric = str(model.get("metric", ""))

        if metric not in TARGET_METRICS:
            continue

        signature = json.dumps(
            model,
            sort_keys=True,
            ensure_ascii=False,
        )

        if signature in seen:
            continue

        seen.add(signature)
        models.append(model)

    print(f"detected_target_model_count={len(models)}")

    for index, model in enumerate(models, start=1):
        print(f"\nRECOMMENDED_MODEL_{index}")
        print(
            json.dumps(
                compact_dict(model),
                ensure_ascii=False,
                indent=2,
            )
        )

    headers, rows = load_csv(candidates_path)

    print("\nCANDIDATE CSV")
    print(f"path={candidates_path}")
    print(f"row_count={len(rows)}")
    print(f"headers={headers}")

    for metric in sorted(TARGET_METRICS):
        metric_rows = [
            row
            for row in rows
            if row.get("metric") == metric
        ]

        print(f"\nCANDIDATES metric={metric} count={len(metric_rows)}")

        for index, row in enumerate(metric_rows, start=1):
            print(f"CANDIDATE_{index}")
            print(
                json.dumps(
                    compact_dict(row),
                    ensure_ascii=False,
                    indent=2,
                )
            )


def main() -> int:
    for name, paths in SCOPES.items():
        inspect_scope(
            name,
            paths["recommended"],
            paths["candidates"],
        )
        print()

    print("V129 NF model schema probe PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
