from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

logger = logging.getLogger("AquaNova_DOE_Diagnostics")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def _usable_records(dataset: List[dict], model_filter: str) -> List[dict]:
    selected = []
    for record in dataset:
        model = str(record.get("membrane_model", ""))
        passes = record.get("passes") if isinstance(record.get("passes"), list) else []
        stages = record.get("stages") if isinstance(record.get("stages"), list) else []
        if model_filter.lower() not in model.lower():
            continue
        if len(passes) > 1 or len(stages) > 1:
            continue
        if str(record.get("report_type", "RO")).upper() == "CCRO":
            continue
        required = ("temperature", "system_recovery", "feed_tds", "feed_flow", "feed_pressure", "permeate_tds")
        if any(record.get(key) is None for key in required):
            continue
        selected.append(record)
    return selected


def _features(record: dict) -> List[float]:
    area = 37.2 * float(record.get("number_of_elements") or 60)
    q_perm = float(record["feed_flow"]) * float(record["system_recovery"]) / 100.0
    flux = q_perm * 1000.0 / max(area, 1e-9)
    return [
        float(record["temperature"]),
        float(record["system_recovery"]),
        math.log1p(float(record["feed_tds"])),
        flux,
    ]


def build_response_surface(dataset_path: Path, model_filter: str, output_path: Path) -> Dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    records = _usable_records(dataset, model_filter)
    if len(records) < 6:
        raise RuntimeError(
            f"At least 6 comparable single-pass records are required; found {len(records)}"
        )

    X = np.asarray([_features(record) for record in records], dtype=float)
    y_pressure = np.asarray([float(record["feed_pressure"]) for record in records], dtype=float)
    y_log_tds = np.log1p(np.asarray([float(record["permeate_tds"]) for record in records], dtype=float))

    def fit_target(y: np.ndarray) -> Tuple[object, np.ndarray]:
        model = make_pipeline(
            PolynomialFeatures(degree=2, include_bias=False),
            StandardScaler(),
            Ridge(alpha=1.0),
        )
        predictions = cross_val_predict(model, X, y, cv=LeaveOneOut())
        model.fit(X, y)
        return model, predictions

    pressure_model, pressure_cv = fit_target(y_pressure)
    tds_model, tds_cv_log = fit_target(y_log_tds)
    tds_cv = np.expm1(tds_cv_log)

    result = {
        "purpose": "diagnostic response surface only; not a replacement for the physics engine",
        "dataset": str(dataset_path),
        "model_filter": model_filter,
        "records": [record.get("source_file") for record in records],
        "feature_order": ["temperature_C", "recovery_pct", "log1p_feed_tds", "flux_lmh"],
        "leave_one_out": {
            "pressure_mape_pct": float(mean_absolute_percentage_error(y_pressure, pressure_cv) * 100.0),
            "tds_mape_pct": float(mean_absolute_percentage_error(np.expm1(y_log_tds), tds_cv) * 100.0),
        },
        "warning": (
            "Do not paste polynomial coefficients into engine.py unless holdout errors are acceptable. "
            "The previous hard-coded 9-point surface leaked WAVE targets into production tuning."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-validated DOE diagnostics")
    parser.add_argument("--dataset", type=Path, default=Path("./.data/wave_extracted_dataset.json"))
    parser.add_argument("--model", default="BW30-400")
    parser.add_argument("--output", type=Path, default=Path("./.data/doe_diagnostics.json"))
    args = parser.parse_args()
    result = build_response_surface(args.dataset, args.model, args.output)
    logger.info(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
