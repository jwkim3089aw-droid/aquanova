import pytest

from app.services.simulation.modules.hrro import ExcelInputs, compute_excel


def test_compute_excel_k5_boundary_branching_is_preserved():
    # baseline case
    base = ExcelInputs(
        q_raw_m3h=10.0,
        ccro_recovery_pct=85.0,
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=4.54,
        vessel_count=1,
        elements_per_vessel=3,
        area_m2_per_element=37.1612,
    )
    r = compute_excel(base)
    assert pytest.approx(r.pf_feed_m3h, abs=1e-12) == 10.85  # K5>=101 가지
    assert pytest.approx(r.cc_feed_m3h, abs=1e-12) == 9.863636363636363

    # K5 just below 101 -> Excel IF branch should yield T7=0 path => pf_feed becomes q (10.0)
    near = ExcelInputs(**{**base.__dict__, "pf_feed_ratio_pct": 100.9})
    r2 = compute_excel(near)
    assert pytest.approx(r2.pf_feed_m3h, abs=1e-12) == 10.0
