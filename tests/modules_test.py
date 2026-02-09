# tests\modules_test.py
# tests/modules_test.py
# pytest unit tests for HRRO (hrro.py)
#
# 실행 예시 (PowerShell, 프로젝트 루트=...\AquaNova\code):
#   $env:PYTHONPATH="."
#   pytest -q app/services/simulation/modules/test_hrro_unit.py
#
# 또는 (PYTHONPATH 설정 없이) 프로젝트가 패키지로 잡혀있다면:
#   pytest -q

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.simulation.modules.hrro import (
    ExcelInputs,
    compute_excel,
    choose_guideline_profile,
    build_guideline_violations,
    excel_only_compute_cp_cc,
    solve_inlet_pressure_for_target_avg_flux,
    HRROModule,
)


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
def ns(**kwargs):
    """SimpleNamespace shorthand"""
    return SimpleNamespace(**kwargs)


# -----------------------------------------------------------------------------
# 1) compute_excel
# -----------------------------------------------------------------------------
def test_compute_excel_ccro_baseline():
    inp = ExcelInputs(
        q_raw_m3h=100.0,
        ccro_recovery_pct=80.0,  # %
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        vessel_count=2,
        elements_per_vessel=6,
        area_m2_per_element=37.0,
    )
    r = compute_excel(inp)

    total_elements = 2 * 6
    total_area = total_elements * 37.0
    exp_qp = 100.0 * 0.80
    exp_qc = 100.0 - exp_qp
    exp_flux = (exp_qp * 1000.0) / total_area

    assert r.total_elements == total_elements
    assert r.total_area_m2 == pytest.approx(total_area, rel=0, abs=1e-9)

    assert r.ccro_qp_m3h == pytest.approx(exp_qp, rel=0, abs=1e-12)
    assert r.ccro_qc_m3h == pytest.approx(exp_qc, rel=0, abs=1e-12)
    assert r.ccro_flux_lmh == pytest.approx(exp_flux, rel=0, abs=1e-12)


def test_compute_excel_pf_branch_k5_ge_101():
    # K5 >= 101이면 PF helper의 T7 계산이 켜짐
    inp = ExcelInputs(
        q_raw_m3h=100.0,
        ccro_recovery_pct=80.0,
        pf_feed_ratio_pct=110.0,  # >=101
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        vessel_count=1,
        elements_per_vessel=6,
        area_m2_per_element=37.0,
    )
    r = compute_excel(inp)

    # 엑셀 로직:
    # T7 = (q*(rec/100))/10 = (100*0.8)/10 = 8
    # V7 = (K5-100)/10 = 1
    # V8 = 8*1 = 8
    # V9 = q + V8 = 108
    assert r.pf_feed_m3h == pytest.approx(108.0, rel=0, abs=1e-12)


def test_compute_excel_pf_branch_k5_lt_101():
    # K5 < 101이면 T7=0 -> V8=0 -> V9=q
    inp = ExcelInputs(
        q_raw_m3h=100.0,
        ccro_recovery_pct=80.0,
        pf_feed_ratio_pct=100.0,  # <101
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        vessel_count=1,
        elements_per_vessel=6,
        area_m2_per_element=37.0,
    )
    r = compute_excel(inp)
    assert r.pf_feed_m3h == pytest.approx(100.0, rel=0, abs=1e-12)


# -----------------------------------------------------------------------------
# 2) guideline profile selection + violation builder
# -----------------------------------------------------------------------------
def test_choose_guideline_profile_basic_cases():
    # RO permeate 조건
    profile, reason = choose_guideline_profile(
        water_type="anything",
        water_subtype=None,
        sdi15=0.8,
        tds_mgL=150.0,
    )
    assert profile == "RO Pemeate"
    assert "tds<=200" in reason

    # seawater + beach
    profile, _ = choose_guideline_profile(
        water_type="Seawater",
        water_subtype="beach well",
        sdi15=4.0,
        tds_mgL=35000.0,
    )
    assert profile == "Seawater Beach Wells"

    # surface + mf/uf
    profile, _ = choose_guideline_profile(
        water_type="surface water",
        water_subtype="UF",
        sdi15=5.0,
        tds_mgL=500.0,
    )
    assert profile == "Surface Water MF/UF Filteration"

    # brackish
    profile, _ = choose_guideline_profile(
        water_type="brackish wells",
        water_subtype=None,
        sdi15=3.0,
        tds_mgL=5000.0,
    )
    assert profile == "Brackish Wells"


def test_build_guideline_violations_multiple_hits():
    # municipal Supply / 8inch 기준:
    # avg_flux_range 20~26, lead_flux_max 31, conc_flow_min 3.6, feed_flow_max 15, dp_max 2,
    # element_recovery_max 15, beta_max 1.2, flux_decline_ratio_max 13
    guideline_used, violations = build_guideline_violations(
        profile="municipal Supply",
        inch=8,
        checks={
            "avg_flux_lmh": 30.0,  # out of range
            "lead_flux_lmh": 33.0,  # exceed max
            "conc_flow_m3h_per_vessel": 3.0,  # below min
            "feed_flow_m3h_per_vessel": 16.0,  # above max
            "dp_bar_per_vessel": 3.0,  # above max
            "element_recovery_pct": 20.0,  # above max
            "beta_max": 1.25,  # above max
            "flux_decline_ratio_pct": 15.0,  # above max
        },
    )

    keys = {v["key"] for v in violations}
    assert guideline_used["profile"] == "municipal Supply"
    assert guideline_used["element_inch"] == 8

    # 대표적으로 여러 개가 잡혀야 함
    assert "avg_flux_range" in keys
    assert "lead_flux_max" in keys
    assert "conc_flow_min" in keys
    assert "feed_flow_max" in keys
    assert "dp_max" in keys
    assert "element_recovery_max" in keys
    assert "beta_max" in keys
    assert "flux_decline_ratio_max" in keys


# -----------------------------------------------------------------------------
# 3) excel_only Cp/Cc 모델
# -----------------------------------------------------------------------------
def test_excel_only_compute_cp_cc_fixed_rejection():
    cp, cc, dbg = excel_only_compute_cp_cc(
        cf_mgL=1000.0,
        qf_m3h=100.0,
        qp_m3h=80.0,
        qc_m3h=20.0,
        cp_mode="fixed_rejection",
        fixed_rejection_pct=99.0,
        min_model_rejection_pct=None,
        fallback_rejection_pct=99.63,
    )

    # Cp = Cf*(1-rej)
    assert cp == pytest.approx(10.0, rel=0, abs=1e-12)
    assert dbg["cp_mode"] == "fixed_rejection"
    assert dbg["rejection_pct"] == pytest.approx(99.0, rel=0, abs=1e-12)

    # salt balance:
    # salt_in = 100*1000 = 100000
    # salt_perm = 80*10 = 800
    # salt_out = 99200 -> Cc = 99200/20 = 4960
    assert cc == pytest.approx(4960.0, rel=0, abs=1e-9)


def test_excel_only_compute_cp_cc_none_mode():
    cp, cc, dbg = excel_only_compute_cp_cc(
        cf_mgL=1000.0,
        qf_m3h=100.0,
        qp_m3h=80.0,
        qc_m3h=20.0,
        cp_mode="none",
        fixed_rejection_pct=99.0,
        min_model_rejection_pct=None,
        fallback_rejection_pct=99.63,
    )
    assert cp is None
    assert cc is None
    assert dbg["cp_mode"] == "none"


# -----------------------------------------------------------------------------
# 4) solve_inlet_pressure_for_target_avg_flux (간단 sanity)
# -----------------------------------------------------------------------------
def test_solve_inlet_pressure_for_target_avg_flux_cp_off_sanity():
    # CP를 사실상 끄기 위해 cp_exp_max=0 => beta=1 고정
    target_flux = 10.0  # LMH

    axial_kwargs = dict(
        temp_c=25.0,
        A_lmh_bar_base=1.0,
        B_lmh_base=0.0,
        area_total_m2=37.0 * 6,  # per PV area
        nseg=1,
        dp_total_bar=0.0,
        q_in_m3h=10.0,
        c_in_mgL=100.0,
        channel_area_m2=0.015,
        spacer_voidage=0.85,
        dh_m=0.0012,
        diffusivity_m2_s=1.5e-9,
        cp_exp_max=0.0,
        cp_max_iter=10,
        cp_rel_tol=1e-6,
        cp_abs_tol_lmh=1e-6,
        cp_relax=0.5,
        flux_init_lmh=target_flux,
        a_mu_exp=0.0,
        b_mu_exp=0.0,
        b_sal_slope=0.0,
        compaction_k_per_bar=0.0,
        k_mt_multiplier=1.0,
        k_mt_min_m_s=0.0,
    )

    p_in, axial_res = solve_inlet_pressure_for_target_avg_flux(
        target_flux_lmh=target_flux,
        p_limit_bar=60.0,
        axial_kwargs=axial_kwargs,
        tol_lmh=0.05,
        max_iter=30,
    )

    # 결과 avg_flux는 target 근처여야 함
    avg_flux = axial_res[1]
    assert 0.0 <= p_in <= 60.0
    assert avg_flux == pytest.approx(target_flux, abs=0.2)


# -----------------------------------------------------------------------------
# 5) HRROModule.compute (엔드-투-엔드 "unit-ish" test)
#    - config/feed를 SimpleNamespace로 줘도 getattr 기반이라 동작함
# -----------------------------------------------------------------------------
def test_hrro_module_excel_only_stage_no_and_cp_present():
    m = HRROModule()

    config = ns(
        stage=2,
        hrro_engine="excel_only",
        vessel_count=2,
        elements_per_vessel=6,
        membrane_area_m2_per_element=37.0,
        feed_flow_m3h=100.0,
        ccro_recovery_pct=80.0,
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        hrro_excel_only_cp_mode="fixed_rejection",
        hrro_excel_only_fixed_rejection_pct=99.0,
    )
    feed = ns(
        temperature_C=25.0,
        tds_mgL=1000.0,
        pressure_bar=10.0,
        water_type="brackish",
        water_subtype=None,
        sdi15=3.0,
    )

    out = m.compute(config, feed)

    # stage_no 반영 확인
    assert out.stage == 2

    # Excel baseline: Qp = 100*0.8=80, Qc=20
    assert out.Qp == pytest.approx(80.0, abs=1e-6)
    assert out.Qc == pytest.approx(20.0, abs=1e-6)

    # Cp가 None이 아니어야 함 (fixed rejection)
    assert out.Cp is not None
    assert out.chemistry is not None
    assert "violations" in out.chemistry


def test_hrro_module_excel_physics_excel_baseline_flow_mode():
    m = HRROModule()

    config = ns(
        stage=1,
        hrro_engine="excel_physics",
        vessel_count=2,
        elements_per_vessel=6,
        membrane_area_m2_per_element=37.0,
        feed_flow_m3h=100.0,
        ccro_recovery_pct=80.0,
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        # flux_lmh 미지정 => Excel baseline 모드
        membrane_A_lmh_bar=1.2,
        membrane_B_lmh=0.1,
        pump_eff=0.8,
        hrro_pressure_limit_bar=60.0,
    )
    feed = ns(
        temperature_C=25.0,
        tds_mgL=5000.0,
        pressure_bar=10.0,
        water_type="brackish",
        water_subtype=None,
        sdi15=3.0,
    )

    out = m.compute(config, feed)

    # Excel baseline Qp/Qc 유지
    assert out.Qp == pytest.approx(80.0, abs=1e-6)
    assert out.Qc == pytest.approx(20.0, abs=1e-6)

    physics = out.chemistry["design_excel"]["physics"]
    assert physics["flow_mode"] == "excel_baseline"
    assert physics["qp_total_m3h"] == pytest.approx(80.0, abs=1e-6)
    assert physics["qc_total_m3h"] == pytest.approx(20.0, abs=1e-6)


def test_hrro_module_excel_physics_flux_override_flow_mode():
    m = HRROModule()

    config = ns(
        stage=1,
        hrro_engine="excel_physics",
        vessel_count=1,
        elements_per_vessel=6,
        membrane_area_m2_per_element=37.0,
        feed_flow_m3h=100.0,
        ccro_recovery_pct=80.0,  # Excel baseline과 무관하게 override 해볼 것
        pf_feed_ratio_pct=110.0,
        pf_recovery_pct=10.0,
        cc_recycle_m3h_per_pv=0.0,
        # 여기서 flux override
        flux_lmh=5.0,
        membrane_A_lmh_bar=1.2,
        membrane_B_lmh=0.1,
        pump_eff=0.8,
        hrro_pressure_limit_bar=60.0,
    )
    feed = ns(
        temperature_C=25.0,
        tds_mgL=5000.0,
        pressure_bar=10.0,
        water_type="brackish",
        water_subtype=None,
        sdi15=3.0,
    )

    out = m.compute(config, feed)

    # total_area = 1*6*37 = 222 m2
    # Qp = flux(5) * area(222) / 1000 = 1.11 m3/h
    assert out.Qp == pytest.approx(1.11, abs=1e-6)
    assert out.Qc == pytest.approx(98.89, abs=1e-6)

    # achieved flux should match override target closely (since Qp is derived from it)
    assert out.flux_lmh == pytest.approx(5.0, abs=1e-3)

    physics = out.chemistry["design_excel"]["physics"]
    assert physics["flow_mode"] == "flux_override"
    assert physics["qp_total_from_flux_m3h"] == pytest.approx(1.11, abs=1e-6)
    assert physics["qp_total_clamped"] is False
