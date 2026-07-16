from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import apply_and_verify as calibration


def _find(data: list[dict], source_file: str) -> dict:
    for record in data:
        if record.get("source_file") == source_file:
            return record
    raise RuntimeError(f"Required validation case not found: {source_file}")


def _pressure_membrane_records(data: list[dict]) -> list[dict]:
    records = []
    for record in data:
        model, _ = calibration.resolve_case_identity(record)
        if model and not re.search(r"SFP|INTEGRAFLUX|UF|MF", model.upper()):
            records.append(record)
    return records


def verify(dataset_path: Path) -> Dict[str, Any]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise RuntimeError("Dataset is empty or is not a JSON array")

    pressure_records = _pressure_membrane_records(data)
    schema_counts = Counter(int(record.get("schema_version") or 1) for record in data)
    if schema_counts.get(3, 0) != len(data):
        raise RuntimeError(f"Expected only schema-v3 records, found: {dict(schema_counts)}")

    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for record in pressure_records:
        model, process_type = calibration.resolve_case_identity(record)
        regime = calibration._determine_generalized_regime(record)
        groups[(model, process_type, regime)].append(str(record.get("source_file")))

    neutral = [1.0, 1.0, 1.0, 1.0, 0.5]

    split_record = _find(data, "BW30PRO-400_PermeateSplit_50.pdf")
    split_model, split_type = calibration.resolve_case_identity(split_record)
    split_request = calibration._build_request(
        split_model, split_type, split_record, neutral, "verify-split"
    )
    if len(split_request.stages) < 2:
        raise RuntimeError("Permeate-split case did not create two pass stages")
    second_pass = next(
        (stage for stage in split_request.stages if int(stage.pass_idx or 1) == 2),
        None,
    )
    if second_pass is None:
        raise RuntimeError("Permeate-split case is missing pass 2")
    split_fraction = float(second_pass.pass_feed_fraction or 1.0)
    if not (0.45 <= split_fraction <= 0.55):
        raise RuntimeError(f"Unexpected permeate-split route fraction: {split_fraction}")
    if not bool(second_pass.split_remainder_to_product):
        raise RuntimeError("Permeate-split product branch is not enabled")
    split_targets = calibration._system_targets(split_record)

    minflow = _find(data, "BW30-400_MinFlow_CP_Explosion.pdf")
    minflow_model, minflow_type = calibration.resolve_case_identity(minflow)
    minflow_request = calibration._build_request(
        minflow_model, minflow_type, minflow, neutral, "verify-minflow"
    )
    if int(minflow_request.stages[0].vessel_count or 0) != 1:
        raise RuntimeError("MinFlow must use one pressure vessel")

    swro = _find(data, "SWRO_2Pass_NaOH_Boron_Baseline.pdf")
    swro_model, swro_type = calibration.resolve_case_identity(swro)
    swro_request = calibration._build_request(
        swro_model, swro_type, swro, neutral, "verify-swro"
    )
    swro_passes = sorted({int(stage.pass_idx or 1) for stage in swro_request.stages})
    if swro_passes != [1, 2]:
        raise RuntimeError(f"SWRO case must contain passes 1 and 2, found {swro_passes}")

    report = {
        "status": "PASS",
        "dataset": str(dataset_path),
        "records": len(data),
        "pressure_membrane_records": len(pressure_records),
        "schema_counts": dict(schema_counts),
        "generalized_group_count": len(groups),
        "generalized_singleton_groups": sum(len(items) == 1 for items in groups.values()),
        "generalized_multi_case_groups": sum(len(items) > 1 for items in groups.values()),
        "permeate_split": {
            "pass_feed_fraction": split_fraction,
            "split_remainder_to_product": True,
            "derived_product_flow_m3h": split_targets.get("product_flow_m3h"),
            "derived_product_tds_mgL": split_targets.get("tds_mgL"),
            "derived_recovery_pct": split_targets.get("recovery_pct"),
        },
        "minflow_pressure_vessels": int(minflow_request.stages[0].vessel_count or 0),
        "swro_passes": swro_passes,
        "v4_stage_fields": [
            "b_salinity_slope",
            "pass_feed_fraction",
            "split_remainder_to_product",
            "dp_correlation_enabled",
            "dp_correlation_multiplier",
        ],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify AquaNova V4 installation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("./.data/wave_extracted_dataset.json"),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = verify(args.dataset)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
