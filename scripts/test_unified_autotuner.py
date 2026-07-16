"""Compatibility entry point for the unified AquaNova WAVE autotuner.

V3 intentionally uses the exact same SimulationEngine execution path as
apply_and_verify.py. This removes the historical mismatch between direct module
calls and production verification.
"""
from pathlib import Path

from scripts.apply_and_verify import run_pipeline


if __name__ == "__main__":
    run_pipeline(
        dataset_path=Path("./.data/wave_extracted_dataset.json"),
        output_path=Path("./.data/unified_autotuner_regime_constants.json"),
    )
