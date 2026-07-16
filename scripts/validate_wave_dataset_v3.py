from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def audit_dataset(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    issues: List[Dict[str, Any]] = []
    schema_counts = Counter()
    process_counts = Counter()
    pass_counts = Counter()
    stage_counts = Counter()

    for index, record in enumerate(data):
        source = str(record.get("source_file") or f"record_{index}")
        schema = int(record.get("schema_version") or 1)
        schema_counts[str(schema)] += 1
        passes = record.get("passes") if isinstance(record.get("passes"), list) else []
        stages = record.get("stages") if isinstance(record.get("stages"), list) else []
        pass_counts[str(len(passes) or 1)] += 1
        stage_counts[str(len(stages))] += 1

        model = str(record.get("membrane_model") or "").upper()
        report_type = str(record.get("report_type") or "").upper()
        if report_type == "CCRO" or "SOAR" in model:
            process = "HRRO"
        elif "NF" in model:
            process = "NF"
        elif any(token in model for token in ("SFP", "UF", "MF", "INTEGRAFLUX")):
            process = "UF/MF"
        else:
            process = "RO"
        process_counts[process] += 1

        required = ["feed_flow", "feed_tds", "feed_pressure", "permeate_tds", "system_recovery"]
        missing = [key for key in required if record.get(key) is None]
        if missing:
            issues.append({"source_file": source, "severity": "error", "issue": "missing_targets", "fields": missing})
        if process in {"RO", "NF", "HRRO"} and not stages:
            issues.append({"source_file": source, "severity": "error", "issue": "missing_stage_topology"})
        if process in {"RO", "NF", "HRRO"} and not record.get("feed_ions"):
            issues.append({"source_file": source, "severity": "warning", "issue": "missing_actual_ion_composition"})
        if len(passes) > 1 and float(record.get("permeate_tds") or 0.0) == float(passes[0].get("permeate_tds_mgL") or -1.0):
            issues.append({"source_file": source, "severity": "error", "issue": "system_product_equals_pass1_product"})
        if report_type == "CCRO":
            if not record.get("ccro"):
                issues.append({"source_file": source, "severity": "error", "issue": "missing_ccro_cycle_parameters"})
            if float(record.get("feed_pressure") or 0.0) < float(record.get("feed_pressure_max") or 0.0):
                issues.append({"source_file": source, "severity": "error", "issue": "ccro_pressure_not_maximum"})

    return {
        "dataset": str(path),
        "records": len(data),
        "schema_counts": dict(schema_counts),
        "process_counts": dict(process_counts),
        "pass_counts": dict(pass_counts),
        "stage_counts": dict(stage_counts),
        "issue_count": len(issues),
        "error_count": sum(item["severity"] == "error" for item in issues),
        "warning_count": sum(item["severity"] == "warning" for item in issues),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit AquaNova WAVE schema-v3 dataset")
    parser.add_argument("--dataset", type=Path, default=Path("./.data/wave_extracted_dataset.json"))
    parser.add_argument("--output", type=Path, default=Path("./.data/wave_dataset_v3_audit.json"))
    args = parser.parse_args()
    result = audit_dataset(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["error_count"] else 0)


if __name__ == "__main__":
    main()
