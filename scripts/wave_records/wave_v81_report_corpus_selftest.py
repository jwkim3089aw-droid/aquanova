#!/usr/bin/env python3
"""Selftest for V81 WAVE report corpus parsing."""
from __future__ import annotations

from wave_report_corpus import (
    classify_report,
    corpus_summary,
    parse_design_warnings,
    parse_pressure_membrane_metrics,
    parse_uf_metrics,
    WaveReportRecord,
)


def main() -> int:
    ccro_text = """
    RO System Overview
    # Description Flow TDS Pressure
    1 Raw Feed to RO System 2.02 412.4 0.0
    4 Total Concentrate from Pass 1 0.20 4,038 7.8
    6 Net Product from RO System 1.82 9.28 0.0
    Feed Pressure (bar) 6.4 - 8.2
    Pass Average flux (LMH) 16.3
    Average NDP (bar) 6
    Specific Energy (kWh/m³) 0.30
    RO System Recovery 90.0 %
    CCRO Overview
    CC Recovery (%) 29.26
    PF Recovery (%) 10.00
    PF Feed Ratio (%) 270.00
    CC Concentrate Flow (m³/h/pv) 4.54
    PF Concentrate Flow (m³/h/pv) 4.56
    CC Net Feed Flow (m³/h/pv) 6.42
    PF Feed Flow (m³/h/pv) 5.07
    Total Cycles 22.50
    PF Sequence Duration (min) 1.24
    CC Sequence Duration (min) 26.87
    Complete Cycle Duration (min) 28.11
    CC System Volume (m³) 0.09
    RO Design Warnings
    PF Feed Ratio > Maximum Value (%) 150.00 270.00 1 - - FilmTec SOAR 5000i
    """
    process, family = classify_report("sample_ccro.pdf", ccro_text)
    assert process == "ccro", process
    assert family == "pressure_membrane", family
    metrics = parse_pressure_membrane_metrics(ccro_text)
    assert metrics["system.feed_flow_m3h"] == 2.02
    assert metrics["system.product_flow_m3h"] == 1.82
    assert metrics["system.product_tds_mgL"] == 9.28
    assert metrics["pass.final_concentrate_tds_mgL"] == 4038.0
    assert metrics["ccro.pf_feed_ratio_pct"] == 270.0
    assert metrics["ccro.cc_system_volume_m3"] == 0.09
    warnings = parse_design_warnings(ccro_text)
    assert warnings and "PF Feed Ratio" in warnings[0]

    uf_text = """
    Ultrafiltration Summary Report
    Feed Flow 100.0 m3/h
    Filtrate Flow 95.0 m3/h
    Net Product 92.0 m3/h
    Recovery 92.0 %
    Filtration Duration 30 min
    Backwash Duration 60 sec
    Initial TMP 0.2 bar
    Final TMP 0.8 bar
    """
    process, family = classify_report("V56_UF_SFP2660_F100.pdf", uf_text)
    assert process == "uf", process
    assert family == "ultrafiltration", family
    uf_metrics = parse_uf_metrics(uf_text)
    assert uf_metrics["uf.feed_flow_m3h"] == 100.0
    assert uf_metrics["uf.recovery_pct"] == 92.0

    summary = corpus_summary(
        [
            WaveReportRecord("a.pdf", "a.pdf", "ccro", "pressure_membrane", "fixture", metrics=metrics),
            WaveReportRecord("b.pdf", "b.pdf", "uf", "ultrafiltration", "fixture", metrics=uf_metrics),
        ]
    )
    assert summary["record_count"] == 2
    assert summary["by_process"] == {"ccro": 1, "uf": 1}
    print("V81 report corpus selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
