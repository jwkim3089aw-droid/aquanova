"""Calibration helpers for WAVE-anchor nonlinear correction workflows."""

try:  # V84 module
    from .wave_calibration_features import (  # type: ignore[F401]
        CALIBRATION_TARGET_HINTS,
        FEATURE_HINTS,
        build_feature_rows,
        flatten_record,
        load_wave_corpus_records,
    )
except Exception:  # pragma: no cover - keeps patch tolerant if V84 is applied later
    CALIBRATION_TARGET_HINTS = ()
    FEATURE_HINTS = ()
    build_feature_rows = None  # type: ignore[assignment]
    flatten_record = None  # type: ignore[assignment]
    load_wave_corpus_records = None  # type: ignore[assignment]

from .wave_calibration_pairing import (  # noqa: E402
    build_pair_rows,
    infer_wave_case_metadata,
    summarize_pair_rows,
)

__all__ = [
    "CALIBRATION_TARGET_HINTS",
    "FEATURE_HINTS",
    "build_feature_rows",
    "flatten_record",
    "load_wave_corpus_records",
    "build_pair_rows",
    "infer_wave_case_metadata",
    "summarize_pair_rows",
]
