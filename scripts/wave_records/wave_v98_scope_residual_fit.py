from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_scope_residual_fit import fit_file


def main() -> int:
    parser = argparse.ArgumentParser(description="V98 scope-aware bounded residual correction fitting")
    parser.add_argument("--metric-errors", required=True, help="V90 metric error CSV/JSON")
    parser.add_argument("--output-base", default="", help="Optional output base path")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    result = fit_file(args.metric_errors, output_base=args.output_base or None)
    outputs = result["outputs"]
    print(f"V98 scope-aware residual fit written from: {args.metric_errors}")
    for key, path in outputs.items():
        print(f"{key}: {path}")
    if args.print_summary:
        print("summary=" + json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
