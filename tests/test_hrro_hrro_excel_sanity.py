# tests/test_hrro_hrro_excel_sanity.py
import math
import pytest

from app.services.simulation.modules.hrro import (
    ExcelInputs,
    compute_excel,
    excel_only_compute_cp_cc,
)


def test_compute_excel_mass_balance_and_flux_units():
    inp = ExcelInputs(
        q_raw_m3h=100.0,
        ccro_recovery_pct=85.0,
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        vessel_count=10,
        elements_per_vessel=6,
        area_m2_per_element=37.0,
    )
    r = compute_excel(inp)

    # mass balance
    assert (
        pytest.approx(r.ccro_qp_m3h + r.ccro_qc_m3h, rel=0, abs=1e-9) == inp.q_raw_m3h
    )

    # flux definition (LMH)
    expected_flux = (r.ccro_qp_m3h * 1000.0) / r.total_area_m2
    assert pytest.approx(r.ccro_flux_lmh, rel=0, abs=1e-12) == expected_flux


def test_excel_only_cp_cc_salt_balance():
    cf = 35000.0
    qf, qp = 100.0, 50.0
    qc = qf - qp

    cp, cc, dbg = excel_only_compute_cp_cc(
        cf_mgL=cf,
        qf_m3h=qf,
        qp_m3h=qp,
        qc_m3h=qc,
        cp_mode="fixed_rejection",
        fixed_rejection_pct=99.5,
        min_model_rejection_pct=None,
        fallback_rejection_pct=99.63,
    )
    assert cp is not None and cc is not None

    salt_in = qf * cf
    salt_perm = qp * cp
    salt_out = qc * cc
    assert pytest.approx(salt_in, rel=1e-10, abs=1e-6) == salt_perm + salt_out
