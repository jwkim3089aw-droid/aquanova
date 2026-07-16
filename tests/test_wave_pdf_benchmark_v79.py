import json

from app.services.simulation.wave_benchmark import (
    WAVE_1P82_HRRO_R90_SPECS,
    run_wave_1p82_hrro_r90_benchmark,
    wave_1p82_hrro_r90_payload,
)


def test_v79_wave_1p82_reference_contains_key_wave_pdf_values():
    specs = {spec.key: spec for spec in WAVE_1P82_HRRO_R90_SPECS}
    assert specs["system.product_flow_m3h"].target == 1.82
    assert specs["system.recovery_pct"].target == 90.0
    assert specs["ccro.pf_feed_ratio_pct"].target == 270.0
    assert specs["ccro.pf_feed_flow_m3h_per_pv"].target == 5.07
    assert specs["ccro.cc_system_volume_m3"].target == 0.09


def test_v79_default_payload_is_hrro_ccro_case():
    payload = wave_1p82_hrro_r90_payload()
    stage = payload["stages"][0]
    assert payload["feed"]["flow_m3h"] == 2.02
    assert stage["module_type"] == "HRRO"
    assert stage["vessel_count"] == 1
    assert stage["elements_per_vessel"] == 3
    assert stage["pf_feed_ratio_pct"] == 270.0


def test_v79_wave_benchmark_report_is_serializable_and_has_diff_rows():
    report = run_wave_1p82_hrro_r90_benchmark()
    data = report.model_dump()
    json.dumps(data, ensure_ascii=False)
    assert data["schema"] == "aquanova.wave_benchmark.v79"
    assert data["summary"]["row_count"] >= 15
    keys = {row["key"] for row in data["rows"]}
    assert "system.product_flow_m3h" in keys
    assert "ccro.pf_feed_ratio_pct" in keys
    assert "ccro.complete_cycle_duration_min" in keys
    statuses = {row["status"] for row in data["rows"]}
    assert statuses <= {"PASS", "WARN", "FAIL", "MISSING", "INFO"}


def test_v79_wave_benchmark_markdown_contains_table():
    report = run_wave_1p82_hrro_r90_benchmark()
    md = report.to_markdown()
    assert "AquaNova vs WAVE" in md
    assert "| Group | Key | WAVE target | AquaNova | Error | Status |" in md
    assert "ccro.pf_feed_ratio_pct" in md
