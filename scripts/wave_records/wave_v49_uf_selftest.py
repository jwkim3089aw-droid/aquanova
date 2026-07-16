#!/usr/bin/env python3
"""Offline checks for the V52 UF video automation patch."""
from __future__ import annotations

from wave_common import DEFAULT_POINTS
from wave_uf import UFVideoCase, _orange_pixel_fraction


def test_uf_default_points() -> None:
    required = [
        "uf_icon",
        "ultrafiltration_tab",
        "uf_feed_flow_auto",
        "uf_design_module_combo",
        "uf_config_module_combo",
        "uf_online_trains",
        "uf_modules_per_train",
        "uf_backwash_nav",
        "uf_ceb_nav",
        "uf_cip_nav",
        "uf_bw_air_scour_sec",
        "uf_ceb_mineral_acid_ph",
        "uf_ceb_alkali_ph",
        "uf_ceb_chemical_soak_min",
    ]
    missing = [key for key in required if key not in DEFAULT_POINTS]
    assert not missing, missing


def test_uf_case_defaults() -> None:
    case = UFVideoCase()
    assert case.uf_module == "Ultrafiltration SFP-2660"
    assert case.water_profile == "Well Water - Med Hardness"
    assert case.feed_flow_m3h == 100.0
    assert case.feed_temperature_min_c == 10.0
    assert case.feed_temperature_design_c == 15.0
    assert case.feed_temperature_max_c == 20.0
    assert case.modules_per_train == 24
    assert case.backwash_air_scour_s == 30
    assert case.backwash_forward_flush_s == 35
    assert case.ceb_mineral_acid_type == "HCl (32)"
    assert case.ceb_mineral_acid_ph == 2.0
    assert case.ceb_alkali_type == "NaOH (30)"
    assert case.ceb_alkali_ph == 12.0
    assert case.ceb_chemical_soak_min == 10


def test_orange_detector() -> None:
    from PIL import Image

    orange = Image.new("RGB", (20, 20), (205, 114, 43))
    blue = Image.new("RGB", (20, 20), (35, 160, 210))
    assert _orange_pixel_fraction(orange) > 0.95
    assert _orange_pixel_fraction(blue) < 0.01


if __name__ == "__main__":
    test_uf_default_points()
    test_uf_case_defaults()
    test_orange_detector()
    print("V52 UF selftest PASS")
