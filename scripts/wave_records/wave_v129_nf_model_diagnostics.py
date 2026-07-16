from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

SCOPES = {
    "NF270": {
        "errors": DATA_DIR / "v129_nf270_v90_metric_errors.csv",
        "recommended": DATA_DIR / "v129_nf270_v91_recommended_models.json",
        "candidates": DATA_DIR / "v129_nf270_v91_model_candidates.csv",
    },
    "NF90": {
        "errors": DATA_DIR / "v129_nf90_v90_metric_errors.csv",
        "recommended": DATA_DIR / "v129_nf90_v91_recommended_models.json",
        "candidates": DATA_DIR / "v129_nf90_v91_model_candidates.csv",
    },
}

TARGET_METRICS = {
    "feed_pressure",
    "product_tds",
    "final_concentrate_tds",
    "specific_energy",
    "recovery",
}


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def walk_models(value: Any):
    if isinstance(value, dict):
        metric = value.get("metric")
        model_id = value.get("model_id") or value.get("id")

        if metric or model_id:
            yield value

        for child in value.values():
            yield from walk_models(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_models(child)


def first_value(row: dict[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def summarize_errors(rows: list[dict[str, str]]) -> None:
    by_metric: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        by_metric[row.get("metric", "")].append(row)

    print("RAW ERROR SUMMARY")

    for metric in sorted(TARGET_METRICS):
        metric_rows = by_metric.get(metric, [])

        errors = [
            value
            for row in metric_rows
            if (value := number(row.get("abs_error_pct"))) is not None
        ]

        train_errors = [
            value
            for row in metric_rows
            if row.get("split") == "train"
            if (value := number(row.get("abs_error_pct"))) is not None
        ]

        holdout_errors = [
            value
            for row in metric_rows
            if row.get("split") == "holdout"
            if (value := number(row.get("abs_error_pct"))) is not None
        ]

        classes: dict[str, int] = defaultdict(int)

        for row in metric_rows:
            classes[row.get("v90_error_class", "")] += 1

        eligible = sum(
            str(row.get("v90_fit_eligible", "")).lower()
            in {"true", "1", "yes", "y"}
            for row in metric_rows
        )

        print(
            f"{metric}: "
            f"n={len(metric_rows)} "
            f"eligible={eligible} "
            f"mae={mean(errors):.6f}% "
            f"train_mae={mean(train_errors):.6f}% "
            f"holdout_mae={mean(holdout_errors):.6f}% "
            f"max={max(errors):.6f}% "
            f"classes={dict(classes)}"
        )


def summarize_recommended(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))

    models = []

    seen = set()

    for model in walk_models(payload):
        model_id = first_value(model, "model_id", "id")
        metric = first_value(model, "metric", "metric_name")

        key = (str(model_id), str(metric))

        if key in seen:
            continue

        seen.add(key)
        models.append(model)

    print("\nRECOMMENDED MODELS")
    print(f"model_count={len(models)}")

    for model in models:
        metric = first_value(
            model,
            "metric",
            "metric_name",
        )

        model_id = first_value(
            model,
            "model_id",
            "id",
        )

        model_type = first_value(
            model,
            "model_type",
            "family",
            "kind",
        )

        train_n = first_value(
            model,
            "train_n",
            "n_train",
        )

        holdout_n = first_value(
            model,
            "holdout_n",
            "n_holdout",
        )

        train_error = first_value(
            model,
            "train_mean_abs_error_pct",
            "train_mae_pct",
            "train_error_pct",
        )

        holdout_error = first_value(
            model,
            "holdout_mean_abs_error_pct",
            "holdout_mae_pct",
            "holdout_error_pct",
        )

        holdout_improvement = first_value(
            model,
            "holdout_improvement_pct",
            "holdout_error_improvement_pct",
        )

        print(
            f"metric={metric} "
            f"model_id={model_id} "
            f"type={model_type} "
            f"train_n={train_n} "
            f"holdout_n={holdout_n} "
            f"train_error={train_error} "
            f"holdout_error={holdout_error} "
            f"holdout_improvement={holdout_improvement}"
        )


def summarize_candidates(path: Path) -> None:
    rows = load_csv(path)

    by_metric: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        by_metric[row.get("metric", "")].append(row)

    print("\nBEST CANDIDATE PER METRIC")

    for metric in sorted(by_metric):
        metric_rows = by_metric[metric]

        def score(row: dict[str, str]):
            holdout = number(
                first_value(
                    row,
                    "holdout_mean_abs_error_pct",
                    "holdout_mae_pct",
                    "holdout_error_pct",
                )
            )

            train = number(
                first_value(
                    row,
                    "train_mean_abs_error_pct",
                    "train_mae_pct",
                    "train_error_pct",
                )
            )

            return (
                float("inf") if holdout is None else holdout,
                float("inf") if train is None else train,
            )

        best = min(metric_rows, key=score)

        print(
            f"{metric}: "
            f"model_id={first_value(best, 'model_id', 'id')} "
            f"type={first_value(best, 'model_type', 'family', 'kind')} "
            f"train_n={first_value(best, 'train_n', 'n_train')} "
            f"holdout_n={first_value(best, 'holdout_n', 'n_holdout')} "
            f"train_error={first_value(best, 'train_mean_abs_error_pct', 'train_mae_pct', 'train_error_pct')} "
            f"holdout_error={first_value(best, 'holdout_mean_abs_error_pct', 'holdout_mae_pct', 'holdout_error_pct')} "
            f"holdout_improvement={first_value(best, 'holdout_improvement_pct', 'holdout_error_improvement_pct')}"
        )


def main() -> int:
    for membrane, paths in SCOPES.items():
        print("=" * 80)
        print(f"V129 {membrane} MODEL DIAGNOSTICS")
        print("=" * 80)

        for name, path in paths.items():
            if not path.exists():
                print(f"FAIL: missing {name}: {path}")
                return 1

        errors = load_csv(paths["errors"])

        summarize_errors(errors)
        summarize_recommended(paths["recommended"])
        summarize_candidates(paths["candidates"])

        print()

    print("V129 NF model diagnostics PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
