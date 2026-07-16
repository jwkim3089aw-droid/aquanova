#!/usr/bin/env python3
"""Build a local corpus of exported WAVE PDF reports.

V81 intentionally runs offline.  It does not drive the WAVE GUI.  It scans the
existing ``scripts/wave_records/results`` PDF outputs, extracts native PDF text,
parses WAVE-style summary metrics, and writes JSON/CSV/Markdown artifacts that
can be used as benchmark targets before tuning AquaNova's own engines.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import argparse
import csv
import json
import re
import statistics
import sys

SCHEMA_VERSION = "aquanova.wave_report_corpus.v81"


@dataclass
class WaveReportRecord:
    pdf_path: str
    pdf_name: str
    process: str
    report_family: str
    extraction_provider: str
    parse_warnings: list[str] = field(default_factory=list)
    design_warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float | str | bool | None] = field(default_factory=dict)
    text_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_pdf_text(path: Path) -> tuple[str, str]:
    """Extract native PDF text with PyMuPDF first, then pypdf fallback."""
    try:
        import fitz  # type: ignore

        doc = fitz.open(path)
        try:
            return "\n".join(page.get_text("text") for page in doc), "PyMuPDF"
        finally:
            doc.close()
    except Exception as fitz_exc:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages), "pypdf"
        except Exception as pypdf_exc:
            raise RuntimeError(
                f"PDF text extraction failed for {path}: PyMuPDF={fitz_exc!r}; pypdf={pypdf_exc!r}"
            ) from pypdf_exc


def _clean_text(text: str) -> str:
    return text.replace("\r", "\n").replace("\u00a0", " ")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", _clean_text(text)).strip()


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ""))
    except Exception:
        return None


def _first_number_after(label: str, text: str, *, window: int = 180) -> float | None:
    """Return the first number after a label in normalized text.

    WAVE's PDF text extraction may flatten tables, so this intentionally keeps a
    short search window after the label instead of relying on fixed columns.
    """
    c = _compact(text)
    m = re.search(re.escape(label), c, flags=re.I)
    if not m:
        return None
    chunk = c[m.end() : m.end() + window]
    n = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", chunk)
    return _to_float(n.group(0)) if n else None


def _first_number_before(label: str, text: str, *, window: int = 120) -> float | None:
    c = _compact(text)
    m = re.search(re.escape(label), c, flags=re.I)
    if not m:
        return None
    chunk = c[max(0, m.start() - window) : m.start()]
    nums = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", chunk)
    return _to_float(nums[-1]) if nums else None


def _regex_float(pattern: str, text: str, group: int = 1) -> float | None:
    m = re.search(pattern, _compact(text), flags=re.I | re.S)
    if not m:
        return None
    return _to_float(m.group(group))


def _numbers_after(label: str, text: str, *, count: int = 4, window: int = 240) -> list[float]:
    c = _compact(text)
    m = re.search(re.escape(label), c, flags=re.I)
    if not m:
        return []
    chunk = c[m.end() : m.end() + window]
    values: list[float] = []
    for raw in re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", chunk):
        val = _to_float(raw)
        if val is not None:
            values.append(val)
        if len(values) >= count:
            break
    return values


def classify_report(pdf_name: str, text: str) -> tuple[str, str]:
    blob = f"{pdf_name}\n{text}".casefold()
    if "ccro summary" in blob or "ccro overview" in blob or "pf feed ratio" in blob:
        return "ccro", "pressure_membrane"
    if "ultrafiltration" in blob or re.search(r"\bUF\b", pdf_name, flags=re.I):
        return "uf", "ultrafiltration"
    if re.search(r"\bNF\b|NF270|NF90", blob, flags=re.I):
        return "nf", "pressure_membrane"
    if "ro system overview" in blob or "reverse osmosis" in blob or re.search(r"\bRO\b", pdf_name, flags=re.I):
        return "ro", "pressure_membrane"
    return "unknown", "unknown"


def parse_design_warnings(text: str) -> list[str]:
    clean = _clean_text(text)
    warnings: list[str] = []
    for block_label in ["RO Design Warnings", "RO Solubility Warnings", "Design Warnings", "Warnings"]:
        idx = clean.lower().find(block_label.lower())
        if idx < 0:
            continue
        block = clean[idx : idx + 1200]
        if re.search(r"\bNone\b", block[:220], re.I):
            continue
        for line in block.splitlines()[1:12]:
            s = re.sub(r"\s+", " ", line).strip()
            if not s or len(s) < 5:
                continue
            if re.search(r"^(pass|stage|element|product|limit|value|concentrations|feed|project name)", s, re.I):
                continue
            if any(ch.isdigit() for ch in s) or "warning" in s.casefold() or ">" in s or "<" in s:
                warnings.append(s)
        if warnings:
            break
    # Stable de-duplication.
    seen: set[str] = set()
    result: list[str] = []
    for item in warnings:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result[:20]


def parse_pressure_membrane_metrics(text: str) -> dict[str, float | str | bool | None]:
    metrics: dict[str, float | str | bool | None] = {}

    # System overview values.
    metrics["system.feed_flow_m3h"] = _first_number_after("Raw Feed to RO System", text)
    metrics["system.concentrate_flow_m3h"] = _first_number_after("Total Concentrate from Pass 1", text)
    metrics["system.product_flow_m3h"] = _first_number_after("Net Product from RO System", text)
    metrics["system.recovery_pct"] = _first_number_after("RO System Recovery", text)
    metrics["system.net_recovery_pct"] = _first_number_after("Net RO System Recovery", text)
    metrics["system.product_tds_mgL"] = _first_number_after("Permeate", text)  # fallback overwritten below where possible

    metrics["pass.feed_flow_m3h"] = _first_number_after("Feed Flow per Pass", text)
    metrics["pass.feed_pressure_bar"] = _regex_float(r"Feed Pressure \(bar\)\s+[-+]?\d+(?:\.\d+)?\s*-\s*([-+]?\d+(?:\.\d+)?)", text)
    if metrics["pass.feed_pressure_bar"] is None:
        metrics["pass.feed_pressure_bar"] = _first_number_after("Feed Pressure", text)
    metrics["pass.permeate_flow_m3h"] = _first_number_after("Permeate Flow per Pass", text)
    metrics["pass.average_flux_lmh"] = _first_number_after("Pass Average flux", text)
    metrics["pass.recovery_pct"] = _first_number_after("Pass Recovery", text)
    metrics["pass.ndp_bar"] = _first_number_after("Average NDP", text)
    metrics["system.specific_energy_kwh_m3"] = _first_number_after("Specific Energy", text)
    metrics["system.temperature_c"] = _first_number_after("Temperature", text)

    # More specific product TDS patterns.  The text extraction may corrupt the
    # label, so use both label-based and overview row heuristics.
    product_tds = _first_number_after("Permeate TDS", text)
    if product_tds is None:
        product_tds = _first_number_after("Net Product from RO System", text, window=260)
        # Net product row is often: flow, TDS, pressure.  Use the second number.
        vals = _numbers_after("Net Product from RO System", text, count=3, window=260)
        if len(vals) >= 2:
            product_tds = vals[1]
    metrics["system.product_tds_mgL"] = product_tds

    concentrate_vals = _numbers_after("Total Concentrate from Pass 1", text, count=3, window=260)
    if len(concentrate_vals) >= 2:
        metrics["pass.final_concentrate_tds_mgL"] = concentrate_vals[1]
    else:
        metrics["pass.final_concentrate_tds_mgL"] = _first_number_after("Pass Conc", text)

    # CCRO-specific values if present.
    ccro_labels = {
        "ccro.cc_recovery_pct": "CC Recovery (%)",
        "ccro.pf_recovery_pct": "PF Recovery (%)",
        "ccro.pf_feed_ratio_pct": "PF Feed Ratio (%)",
        "ccro.cc_concentrate_flow_m3h_per_pv": "CC Concentrate Flow",
        "ccro.pf_concentrate_flow_m3h_per_pv": "PF Concentrate Flow",
        "ccro.cc_net_feed_flow_m3h_per_pv": "CC Net Feed Flow",
        "ccro.pf_feed_flow_m3h_per_pv": "PF Feed Flow",
        "ccro.total_cycles": "Total Cycles",
        "ccro.pf_sequence_duration_min": "PF Sequence Duration",
        "ccro.cc_sequence_duration_min": "CC Sequence Duration",
        "ccro.complete_cycle_duration_min": "Complete Cycle Duration",
        "ccro.cc_system_volume_m3": "CC System Volume",
    }
    for key, label in ccro_labels.items():
        metrics[key] = _first_number_after(label, text)

    # Remove empty keys for cleaner output.
    return {k: v for k, v in metrics.items() if v is not None}


def parse_uf_metrics(text: str) -> dict[str, float | str | bool | None]:
    metrics: dict[str, float | str | bool | None] = {}
    candidates = {
        "uf.feed_flow_m3h": "Feed Flow",
        "uf.filtrate_flow_m3h": "Filtrate Flow",
        "uf.net_product_flow_m3h": "Net Product",
        "uf.recovery_pct": "Recovery",
        "uf.temperature_c": "Temperature",
        "uf.tmp_initial_bar": "Initial TMP",
        "uf.tmp_final_bar": "Final TMP",
        "uf.filtration_duration_min": "Filtration Duration",
        "uf.backwash_duration_sec": "Backwash Duration",
        "uf.air_scour_flow": "Air Scour",
        "uf.ceb_interval": "CEB",
    }
    for key, label in candidates.items():
        metrics[key] = _first_number_after(label, text)
    return {k: v for k, v in metrics.items() if v is not None}


def parse_wave_report(pdf_path: Path) -> WaveReportRecord:
    text, provider = _read_pdf_text(pdf_path)
    clean = _clean_text(text)
    process, family = classify_report(pdf_path.name, clean)
    warnings = parse_design_warnings(clean)
    parse_warnings: list[str] = []
    if process == "uf":
        metrics = parse_uf_metrics(clean)
    elif family == "pressure_membrane":
        metrics = parse_pressure_membrane_metrics(clean)
    else:
        metrics = {}
        parse_warnings.append("unknown_report_family")
    if not metrics:
        parse_warnings.append("no_metrics_parsed")
    return WaveReportRecord(
        pdf_path=str(pdf_path),
        pdf_name=pdf_path.name,
        process=process,
        report_family=family,
        extraction_provider=provider,
        parse_warnings=parse_warnings,
        design_warnings=warnings,
        metrics=metrics,
        text_excerpt=_compact(clean)[:1200],
    )


def scan_reports(results_dir: Path, *, recursive: bool = False) -> list[WaveReportRecord]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdfs = sorted(results_dir.glob(pattern))
    records: list[WaveReportRecord] = []
    for pdf in pdfs:
        if pdf.is_file():
            try:
                records.append(parse_wave_report(pdf))
            except Exception as exc:
                records.append(
                    WaveReportRecord(
                        pdf_path=str(pdf),
                        pdf_name=pdf.name,
                        process="error",
                        report_family="error",
                        extraction_provider="none",
                        parse_warnings=[f"parse_error: {exc!r}"],
                        metrics={},
                    )
                )
    return records


def flatten_record(record: WaveReportRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "pdf_name": record.pdf_name,
        "pdf_path": record.pdf_path,
        "process": record.process,
        "report_family": record.report_family,
        "extraction_provider": record.extraction_provider,
        "parse_warnings": "; ".join(record.parse_warnings),
        "design_warnings": " | ".join(record.design_warnings),
    }
    for key, value in sorted(record.metrics.items()):
        data[key] = value
    return data


def corpus_summary(records: Iterable[WaveReportRecord]) -> dict[str, Any]:
    records = list(records)
    by_process: dict[str, int] = {}
    warning_records = 0
    metric_counts: list[int] = []
    for rec in records:
        by_process[rec.process] = by_process.get(rec.process, 0) + 1
        if rec.parse_warnings or rec.design_warnings:
            warning_records += 1
        metric_counts.append(len(rec.metrics))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "by_process": dict(sorted(by_process.items())),
        "records_with_warnings": warning_records,
        "avg_metric_count": round(statistics.mean(metric_counts), 2) if metric_counts else 0,
        "max_metric_count": max(metric_counts) if metric_counts else 0,
    }


def write_corpus(records: list[WaveReportRecord], output_dir: Path, *, stem: str | None = None) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if stem is None:
        stem = "wave_report_corpus_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = corpus_summary(records)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "records": [rec.to_dict() for rec in records],
    }
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = [flatten_record(rec) for rec in records]
    all_fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in all_fields:
                all_fields.append(key)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_fields)
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        "# WAVE Report Corpus V81",
        "",
        f"- Schema: `{SCHEMA_VERSION}`",
        f"- Records: {summary['record_count']}",
        f"- By process: {summary['by_process']}",
        f"- Records with warnings: {summary['records_with_warnings']}",
        "",
        "| Process | PDF | Metrics | Design warnings | Parse warnings |",
        "|---|---|---:|---|---|",
    ]
    for rec in records:
        md_lines.append(
            "| "
            + " | ".join(
                [
                    rec.process,
                    f"`{rec.pdf_name}`",
                    str(len(rec.metrics)),
                    "<br>".join(rec.design_warnings[:3]).replace("|", "\\|") or "-",
                    "<br>".join(rec.parse_warnings).replace("|", "\\|") or "-",
                ]
            )
            + " |"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": md_path}


def default_results_dir() -> Path:
    return Path(__file__).resolve().parent / "results"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build WAVE PDF report corpus artifacts.")
    parser.add_argument("--results-dir", type=Path, default=default_results_dir())
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)

    results_dir = args.results_dir.expanduser().resolve()
    if not results_dir.exists():
        raise SystemExit(f"results dir not found: {results_dir}")
    output_dir = args.output_dir or (results_dir / "_report_corpus")
    records = scan_reports(results_dir, recursive=args.recursive)
    paths = write_corpus(records, output_dir)
    print("V81 WAVE report corpus written:")
    for label, path in paths.items():
        print(f"{label}: {path}")
    summary = corpus_summary(records)
    print(f"summary={summary}")
    if args.print_summary:
        for proc, count in summary["by_process"].items():
            print(f"{proc}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
