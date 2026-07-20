from pathlib import Path

import pytest

from app.services.simulation.calibration.wave_runtime_correction import (
    DEFAULT_LAYER_PATH,
    PACKAGED_LAYER_PATH,
    load_correction_layer,
)


def test_default_layer_uses_packaged_fallback(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(
        "AQUANOVA_WAVE_CORRECTION_LAYER",
        raising=False,
    )

    assert not Path(DEFAULT_LAYER_PATH).exists()
    assert PACKAGED_LAYER_PATH.is_file()

    actual = load_correction_layer()
    expected = load_correction_layer(PACKAGED_LAYER_PATH)

    assert actual == expected


def test_explicit_missing_layer_does_not_silently_fallback(
    tmp_path,
):
    missing_path = tmp_path / "missing-layer.json"

    with pytest.raises(FileNotFoundError):
        load_correction_layer(missing_path)
