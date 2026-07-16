from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.wave_benchmark import run_wave_1p82_hrro_r90_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the V80 WAVE 1.82 m3/h HRRO water-quality benchmark.")
    parser.add_argument("--out-dir", default="results/wave_benchmarks")
    parser.add_argument("--print-markdown", action="store_true")
    args = parser.parse_args()

    report = run_wave_1p82_hrro_r90_benchmark()
    # Keep the underlying comparison engine compatible with V79 while making the
    # artifact name explicit for the V80 water-quality correction pass.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"wave_v80_1p82_hrro_r90_quality_benchmark_{stamp}.json"
    md_path = out_dir / f"wave_v80_1p82_hrro_r90_quality_benchmark_{stamp}.md"
    json_path.write_text(report.to_json(), encoding="utf-8")
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    print("V80 WAVE quality benchmark written:")
    print(json_path)
    print(md_path)
    print(f"summary={report.summary}")
    if args.print_markdown:
        print()
        print(report.to_markdown())


if __name__ == "__main__":
    main()
