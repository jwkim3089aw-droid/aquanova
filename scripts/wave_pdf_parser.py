from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz

logger = logging.getLogger("WAVE_PDF_Parser_V3")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname).4s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)

SCHEMA_VERSION = 3
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
WHOLE_NUMBER_RE = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?%?$")

ION_ORDER = [
    "nh4", "k", "na", "mg", "ca", "sr", "ba", "co3", "hco3", "no3",
    "f", "cl", "br", "so4", "po4", "sio2", "b", "co2", "tds", "conductivity", "ph",
]

ION_ALIASES = {
    "nh4": "NH4", "k": "K", "na": "Na", "mg": "Mg", "ca": "Ca", "sr": "Sr",
    "ba": "Ba", "co3": "CO3", "hco3": "HCO3", "no3": "NO3", "f": "F", "cl": "Cl",
    "br": "Br", "so4": "SO4", "po4": "PO4", "sio2": "SiO2", "b": "B", "co2": "CO2",
}

MODEL_RULES = [
    (re.compile(r"SOAR\s*3000", re.I), "FilmTec SOAR 3000i"),
    (re.compile(r"SOAR\s*4000", re.I), "FilmTec SOAR 4000i"),
    (re.compile(r"SOAR\s*5000", re.I), "FilmTec SOAR 5000i"),
    (re.compile(r"SOAR\s*6000", re.I), "FilmTec SOAR 6000i"),
    (re.compile(r"SOAR\s*7000", re.I), "FilmTec SOAR 7000i"),
    (re.compile(r"SW30HRLE", re.I), "FilmTec SW30HRLE-400"),
    (re.compile(r"SW30XHR", re.I), "FilmTec SW30XHR-440"),
    (re.compile(r"SW30XLE", re.I), "FilmTec SW30XLE-440i"),
    (re.compile(r"NF270", re.I), "FilmTec NF270-400"),
    (re.compile(r"BW30XFR", re.I), "FilmTec BW30XFR-400/34i"),
    (re.compile(r"BW30PRO", re.I), "FilmTec BW30PRO-400"),
    (re.compile(r"BW30[- ]?400", re.I), "FilmTec BW30-400"),
    (re.compile(r"ECO\s*PRO", re.I), "FilmTec ECO PRO-440"),
    (re.compile(r"SFP[- ]?2860", re.I), "IntegraFlux SFP-2860XP"),
    (re.compile(r"SFP[- ]?2880", re.I), "IntegraFlux SFP-2880XP"),
]

STOP_TOKENS = (
    "Created:", "Project Name:", "WAVE Version:", "WATER APPLICATION VALUE ENGINE",
    "RO Solute Concentrations", "Solute Concentrations", "RO Flow Table (Element Level)",
    "RO Design Warnings", "Footnotes:", "Special Comments", "Concentrations (mg/L as ion)",
)


@dataclass
class ExtractedDocument:
    pages: List[str]
    method: str

    @property
    def text(self) -> str:
        return "\n".join(self.pages)


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def _numbers(value: str) -> List[float]:
    return [float(token.replace(",", "")) for token in NUMBER_RE.findall(str(value))]


def _is_numeric_line(line: str) -> bool:
    return bool(WHOLE_NUMBER_RE.match(str(line).strip()))


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", str(line).replace("\u00a0", " ")).strip()


def _clean_lines(text: str) -> List[str]:
    return [_clean_line(line) for line in text.splitlines() if _clean_line(line)]


def extract_text_native(pdf_path: Path) -> ExtractedDocument:
    with fitz.open(pdf_path) as doc:
        pages = [page.get_text("text") or "" for page in doc]
    visible = sum(len(re.sub(r"\s+", "", page)) for page in pages)
    if visible < max(200, 100 * len(pages)):
        raise ValueError("PDF native text layer is too sparse")
    return ExtractedDocument(pages=pages, method="pymupdf_native")


def extract_text_ocr(pdf_path: Path) -> ExtractedDocument:
    """Optional Google Vision fallback. It is imported only when explicitly needed."""
    try:
        from google.cloud import vision
    except ImportError as exc:
        raise RuntimeError("OCR fallback requires google-cloud-vision") from exc

    client = vision.ImageAnnotatorClient()
    pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
            image = vision.Image(content=pix.tobytes("png"))
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise RuntimeError(response.error.message)
            pages.append(response.full_text_annotation.text if response.full_text_annotation else "")
    return ExtractedDocument(pages=pages, method="google_vision_ocr")


def extract_document(pdf_path: Path, allow_ocr: bool = False) -> ExtractedDocument:
    try:
        return extract_text_native(pdf_path)
    except Exception as native_exc:
        if not allow_ocr:
            raise RuntimeError(f"Native text extraction failed: {native_exc}") from native_exc
        logger.warning("Native extraction failed for %s; using OCR fallback", pdf_path.name)
        return extract_text_ocr(pdf_path)


def normalize_model_name(raw: str, fallback_text: str = "") -> str:
    text = re.sub(r"[™®Ρ]", " ", f"{raw} {fallback_text}")
    text = re.sub(r"\s+", " ", text).strip()
    for pattern, normalized in MODEL_RULES:
        if pattern.search(text):
            return normalized
    return text or "Unknown membrane"


def _find_all(lines: Sequence[str], predicate) -> List[int]:
    return [index for index, line in enumerate(lines) if predicate(line)]


def _extract_stream_row(flat: str, description: str) -> Optional[Dict[str, float]]:
    pattern = re.compile(
        re.escape(description).replace(r"\ ", r"\s+")
        + r"\s+([-+]?\d[\d,]*(?:\.\d+)?)"
        + r"\s+([-+]?\d[\d,]*(?:\.\d+)?)"
        + r"\s+([-+]?\d[\d,]*(?:\.\d+)?|-)",
        re.I,
    )
    match = pattern.search(flat)
    if not match:
        return None
    return {
        "flow_m3h": _to_float(match.group(1), 0.0) or 0.0,
        "tds_mgL": _to_float(match.group(2), 0.0) or 0.0,
        "pressure_bar": _to_float(match.group(3), 0.0) or 0.0,
    }


def parse_summary_rows(page_text: str) -> Dict[str, Dict[str, float]]:
    flat = re.sub(r"\s+", " ", page_text.replace("\u00a0", " ")).strip()
    descriptions = [
        "Raw Feed to RO System", "Net Feed to Pass 1", "Total Concentrate from Pass 1",
        "Total Permeate from Pass 1", "Net Product from RO System", "Net Feed to Pass 2",
        "Total Concentrate from Pass 2", "Net Concentrate from RO System",
    ]
    result: Dict[str, Dict[str, float]] = {}
    for description in descriptions:
        row = _extract_stream_row(flat, description)
        if row:
            result[description] = row
    return result


def _stage_header_index(lines: Sequence[str], start: int) -> Optional[int]:
    limit = min(len(lines) - 3, start + 450)
    for index in range(start, limit):
        if (
            lines[index].lower() == "feed"
            and lines[index + 1].lower() == "concentrate"
            and lines[index + 2].lower() == "permeate"
            and lines[index + 3].lower() == "stage"
        ):
            return index
    return None


def _stage_header_end(lines: Sequence[str], header_start: int) -> Optional[int]:
    for index in range(header_start, min(len(lines), header_start + 80)):
        if lines[index].lower() == "(mg/l)":
            return index
    return None


def _is_stage_label(lines: Sequence[str], index: int) -> Tuple[Optional[str], int]:
    token = lines[index].strip()
    if re.fullmatch(r"\d+", token):
        return token, 1
    upper = token.upper()
    if upper in {"PF", "CC1"}:
        return upper, 1
    if upper == "CC" and index + 1 < len(lines) and lines[index + 1].strip().upper() == "FINAL":
        return "CC Final", 2
    if upper == "CC FINAL":
        return "CC Final", 1
    return None, 0


def parse_stage_tables(lines: Sequence[str]) -> List[Dict[str, Any]]:
    title_positions: List[Tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.search(r"RO Flow Table \(Stage Level\)\s*-\s*Pass\s*(\d+)", line, re.I)
        if match:
            title_positions.append((index, int(match.group(1))))

    stages: List[Dict[str, Any]] = []
    used_headers: set[int] = set()
    for title_index, pass_idx in title_positions:
        header = _stage_header_index(lines, title_index)
        if header is None or header in used_headers:
            continue
        used_headers.add(header)
        end = _stage_header_end(lines, header)
        if end is None:
            continue
        cursor = end + 1
        while cursor < len(lines):
            if any(lines[cursor].startswith(token) for token in STOP_TOKENS):
                break
            label, consumed = _is_stage_label(lines, cursor)
            if not label:
                cursor += 1
                if cursor > end + 180:
                    break
                continue
            cursor += consumed
            model_parts: List[str] = []
            while cursor < len(lines) and not _is_numeric_line(lines[cursor]):
                if any(lines[cursor].startswith(token) for token in STOP_TOKENS):
                    break
                model_parts.append(lines[cursor])
                cursor += 1
            numeric_values: List[float] = []
            while cursor < len(lines) and len(numeric_values) < 13:
                if _is_numeric_line(lines[cursor]):
                    numeric_values.append(_to_float(lines[cursor], 0.0) or 0.0)
                    cursor += 1
                else:
                    break
            if len(numeric_values) != 13:
                break
            pv, els, feed_flow, recirc_flow, feed_press, boost_press, conc_flow, conc_press, dp, perm_flow, flux, perm_press, perm_tds = numeric_values
            stage_number = int(label) if label.isdigit() else len([s for s in stages if s["pass_idx"] == pass_idx]) + 1
            raw_model = " ".join(model_parts)
            stages.append(
                {
                    "pass_idx": pass_idx,
                    "stage_idx": stage_number,
                    "stage_label": label,
                    "membrane_model_raw": raw_model,
                    "membrane_model": normalize_model_name(raw_model),
                    "pressure_vessels": int(round(pv)),
                    "elements_per_vessel": int(round(els)),
                    "feed_flow_m3h": feed_flow,
                    "recirc_flow_m3h": recirc_flow,
                    "feed_pressure_bar": feed_press,
                    "boost_pressure_bar": boost_press,
                    "concentrate_flow_m3h": conc_flow,
                    "concentrate_pressure_bar": conc_press,
                    "pressure_drop_bar": dp,
                    "permeate_flow_m3h": perm_flow,
                    "avg_flux_lmh": flux,
                    "permeate_pressure_bar": perm_press,
                    "permeate_tds_mgL": perm_tds,
                }
            )
    return stages


def _label_block(lines: Sequence[str], label: str, next_labels: Sequence[str]) -> List[str]:
    try:
        start = next(i for i, line in enumerate(lines) if line.lower() == label.lower())
    except StopIteration:
        return []
    result: List[str] = []
    for line in lines[start + 1 :]:
        if any(line.lower() == item.lower() for item in next_labels):
            break
        if line.startswith("Created:") or line.startswith("Footnotes:"):
            break
        if re.fullmatch(r"\([^)]*\)", line):
            continue
        result.append(line)
    return result


def _split_factor_line(value: str) -> List[float]:
    return _numbers(value)


def parse_pass_overview(pages: Sequence[str], pass_count: int) -> Dict[int, Dict[str, Any]]:
    overview_page = next((page for page in pages if "Flow Factor Per Stage" in page and "Pass Average flux" in page), pages[0])
    lines = _clean_lines(overview_page)
    boundaries = [
        "Number of Elements", "Total Active Area", "Feed Flow per Pass", "Feed Pressure",
        "Flow Factor Per Stage", "Permeate Flow per Pass", "Pass Average flux", "Pass Recovery",
        "Average NDP", "Specific Energy", "Temperature", "pH", "Chemical Dose", "RO System Recovery",
        "Net RO System Recovery", "Footnotes:",
    ]

    result: Dict[int, Dict[str, Any]] = {i: {"pass_idx": i} for i in range(1, pass_count + 1)}

    def numeric_values(label: str, count: int) -> List[float]:
        block = _label_block(lines, label, [item for item in boundaries if item != label])
        values: List[float] = []
        for item in block:
            values.extend(_numbers(item))
            if len(values) >= count:
                break
        return values[:count]

    for label, key in [
        ("Number of Elements", "number_of_elements"),
        ("Total Active Area", "total_active_area_m2"),
        ("Feed Flow per Pass", "feed_flow_m3h"),
        ("Feed Pressure", "feed_pressure_bar"),
        ("Permeate Flow per Pass", "permeate_flow_m3h"),
        ("Pass Average flux", "avg_flux_lmh"),
        ("Pass Recovery", "recovery_pct"),
        ("Average NDP", "average_ndp_bar"),
        ("Temperature", "temperature_C"),
    ]:
        values = numeric_values(label, pass_count)
        for pass_idx, value in enumerate(values, start=1):
            result[pass_idx][key] = value

    # The OCR/native glyphs in the TDS labels are not stable. Use context between neighboring labels.
    feed_tds_block = []
    try:
        ff_index = next(i for i, line in enumerate(lines) if line == "Feed Pressure")
        # Search backward for the nearest mg/L-labelled field after Feed Flow per Pass.
        start = next(i for i, line in enumerate(lines) if line == "Feed Flow per Pass")
        feed_tds_block = lines[start + 1 : ff_index]
    except StopIteration:
        pass
    feed_tds_values: List[float] = []
    for item in feed_tds_block:
        if item.lower() in {"(m³/h)", "(mg/l)"}:
            continue
        feed_tds_values.extend(_numbers(item))
    # The first values belong to feed flow. Keep the last pass_count values.
    if len(feed_tds_values) >= pass_count:
        for pass_idx, value in enumerate(feed_tds_values[-pass_count:], start=1):
            result[pass_idx]["feed_tds_mgL"] = value

    try:
        start = next(i for i, line in enumerate(lines) if line == "Pass Average flux")
        end = next(i for i, line in enumerate(lines[start + 1 :], start + 1) if line == "Pass Recovery")
        perm_tds_values: List[float] = []
        for item in lines[start + 1 : end]:
            if item.lower() in {"(lmh)", "(mg/l)"}:
                continue
            perm_tds_values.extend(_numbers(item))
        if len(perm_tds_values) >= 2 * pass_count:
            perm_tds_values = perm_tds_values[-pass_count:]
        else:
            perm_tds_values = perm_tds_values[-pass_count:]
        for pass_idx, value in enumerate(perm_tds_values, start=1):
            result[pass_idx]["permeate_tds_mgL"] = value
    except StopIteration:
        pass

    flow_block = _label_block(lines, "Flow Factor Per Stage", ["Permeate Flow per Pass"])
    factor_lines = [item for item in flow_block if _numbers(item)]
    for pass_idx, item in enumerate(factor_lines[:pass_count], start=1):
        result[pass_idx]["flow_factors"] = _split_factor_line(item)

    ph_block = _label_block(lines, "pH", ["Chemical Dose"])
    ph_values = []
    for item in ph_block:
        nums = _numbers(item)
        if nums:
            ph_values.append({"value": nums[0], "after_adjustment": "ADJUST" in item.upper()})
    for pass_idx, item in enumerate(ph_values[:pass_count], start=1):
        result[pass_idx]["ph"] = item["value"]
        result[pass_idx]["ph_after_adjustment"] = item["after_adjustment"]

    dose_block = _label_block(lines, "Chemical Dose", ["RO System Recovery"])
    dose_values = [item for item in dose_block if item and item not in {"-"}]
    if pass_count == 1:
        result[1]["chemical_dose"] = dose_values[0] if dose_values else "-"
    else:
        # Preserve '-' for the first pass when the report shows it.
        raw_block = _label_block(lines, "Chemical Dose", ["RO System Recovery"])
        cleaned = [item for item in raw_block if not re.fullmatch(r"\([^)]*\)", item)]
        for pass_idx in range(1, pass_count + 1):
            result[pass_idx]["chemical_dose"] = cleaned[pass_idx - 1] if pass_idx - 1 < len(cleaned) else "-"

    return result


def _canonical_chem_label(line: str, seen: Sequence[str]) -> Optional[str]:
    compact = re.sub(r"[^A-Za-z0-9]", "", line).lower()
    if not compact:
        return None
    if compact in {
        "feed", "concentrate", "concentrat", "permeate", "rawfeed", "phadjustedfeed",
        "stage1", "stage2", "total", "totaltopass2", "pf", "cc1", "ccfinal",
    }:
        return None
    if compact.startswith("nh"):
        return "nh4"
    if compact == "k" or compact.startswith("k0"):
        return "k"
    if compact.startswith("na"):
        return "na"
    if compact.startswith("mg"):
        return "mg"
    if compact.startswith("ca"):
        return "ca"
    if compact.startswith("sr"):
        return "sr"
    if compact.startswith("ba"):
        return "ba"
    if compact.startswith("hco"):
        return "hco3"
    if compact.startswith("no"):
        return "no3"
    if compact == "f" or compact.startswith("f0"):
        return "f"
    if compact.startswith("cl"):
        return "cl"
    if compact.startswith("br"):
        return "br"
    if compact.startswith("so"):
        return "so4"
    if compact.startswith("po"):
        return "po4"
    if compact.startswith("sio"):
        return "sio2"
    if compact.startswith("boron"):
        return "b"
    if compact.startswith("co"):
        return "co2" if "b" in seen else "co3"
    if compact.startswith("cond"):
        return "conductivity"
    if compact == "ph":
        return "ph"
    # WAVE's embedded font often corrupts the TDS label beyond recognition.
    if "tds" in compact or (compact.startswith("d") and len(compact) <= 8):
        return "tds"
    return None


def _chemistry_column_names(value_count: int, header: str) -> List[str]:
    upper = header.upper()
    if value_count == 4:
        return ["feed", "concentrate_stage1", "permeate_stage1", "permeate_total"]
    if value_count == 8 and "PF" in upper and "CC" in upper:
        return [
            "feed", "concentrate_pf", "concentrate_cc1", "concentrate_cc_final",
            "permeate_pf", "permeate_cc1", "permeate_cc_final", "permeate_total",
        ]
    if value_count == 7:
        return [
            "raw_feed", "adjusted_feed", "concentrate_stage1", "concentrate_stage2",
            "permeate_stage1", "permeate_stage2", "permeate_total",
        ]
    if value_count == 6:
        return [
            "feed", "concentrate_stage1", "concentrate_stage2",
            "permeate_stage1", "permeate_stage2", "permeate_total",
        ]
    return [f"column_{index + 1}" for index in range(value_count)]


def parse_chemistry_tables(lines: Sequence[str]) -> List[Dict[str, Any]]:
    starts = _find_all(lines, lambda line: "Concentrations (mg/L as ion)" in line)
    tables: List[Dict[str, Any]] = []
    for start in starts:
        end = len(lines)
        for index in range(start + 1, min(len(lines), start + 300)):
            if index > start + 10 and (
                lines[index].startswith("RO Solute Concentrations")
                or lines[index].startswith("Solute Concentrations")
                or lines[index].startswith("Footnotes:")
                or lines[index].startswith("RO Flow Table (Element Level)")
            ):
                end = index
                break
        section = list(lines[start + 1 : end])
        seen_labels: List[str] = []
        row_positions: List[Tuple[int, str]] = []
        for local_index, line in enumerate(section):
            label = _canonical_chem_label(line, seen_labels)
            if label and label not in seen_labels:
                row_positions.append((local_index, label))
                seen_labels.append(label)
        if not row_positions:
            continue

        rows: Dict[str, List[float]] = {}
        for pos_index, (local_index, label) in enumerate(row_positions):
            next_index = row_positions[pos_index + 1][0] if pos_index + 1 < len(row_positions) else len(section)
            values: List[float] = []
            for item in section[local_index + 1 : next_index]:
                if _is_numeric_line(item):
                    value = _to_float(item)
                    if value is not None:
                        values.append(value)
            if values:
                rows[label] = values

        ion_lengths = [len(values) for key, values in rows.items() if key in ION_ALIASES]
        if not ion_lengths:
            continue
        value_count = max(set(ion_lengths), key=ion_lengths.count)
        rows = {key: values[:value_count] for key, values in rows.items() if len(values) >= value_count}
        first_row_position = row_positions[0][0]
        header = " ".join(section[:first_row_position])
        columns = _chemistry_column_names(value_count, header)

        streams: Dict[str, Dict[str, float]] = {name: {} for name in columns}
        metadata: Dict[str, Dict[str, float]] = {name: {} for name in columns}
        for key, values in rows.items():
            for column, value in zip(columns, values):
                if key in ION_ALIASES:
                    streams[column][ION_ALIASES[key]] = value
                else:
                    metadata[column][key] = value

        context = " ".join(lines[max(0, start - 40) : min(len(lines), end + 40)])
        pass_matches = [int(value) for value in re.findall(r"(?:Pass|PASS)\s*(\d+)", context)]
        pass_idx = pass_matches[-1] if pass_matches else len(tables) + 1
        tables.append(
            {
                "pass_idx": pass_idx,
                "columns": columns,
                "streams": streams,
                "metadata": metadata,
                "header": header,
            }
        )
    # The nearest-context heuristic can assign both tables to pass 2. Preserve report order as fallback.
    if len(tables) > 1:
        for index, table in enumerate(tables, start=1):
            table["pass_idx"] = index
    return tables


def parse_ccro_parameters(lines: Sequence[str]) -> Dict[str, Any]:
    labels = {
        "CC Recovery": "cc_recovery_pct",
        "PF Recovery": "pf_recovery_pct",
        "PF Feed Ratio": "pf_feed_ratio_pct",
        "CC Concentrate Flow": "cc_concentrate_flow_m3h_per_pv",
        "PF Concentrate Flow": "pf_concentrate_flow_m3h_per_pv",
        "CC Net Feed Flow": "cc_net_feed_flow_m3h_per_pv",
        "PF Feed Flow": "pf_feed_flow_m3h_per_pv",
        "Total Cycles": "total_cycles",
        "PF Sequence Duration": "pf_sequence_duration_min",
        "CC Sequence Duration": "cc_sequence_duration_min",
        "Complete Cycle Duration": "complete_cycle_duration_min",
        "CC System Volume": "cc_system_volume_m3",
    }
    result: Dict[str, Any] = {}
    for index, line in enumerate(lines):
        for label, key in labels.items():
            if line.lower() == label.lower():
                for candidate in lines[index + 1 : index + 5]:
                    values = _numbers(candidate)
                    if values:
                        result[key] = values[0]
                        break
    return result


def _stream_ions(table: Dict[str, Any], candidates: Sequence[str]) -> Dict[str, float]:
    streams = table.get("streams", {})
    for key in candidates:
        if key in streams:
            return dict(streams[key])
    return {}


def _stream_meta(table: Dict[str, Any], candidates: Sequence[str]) -> Dict[str, float]:
    metadata = table.get("metadata", {})
    for key in candidates:
        if key in metadata:
            return dict(metadata[key])
    return {}


def parse_wave_document(document: ExtractedDocument, filename: str) -> Dict[str, Any]:
    pages = document.pages
    all_lines = _clean_lines("\n".join(pages))
    summary_rows = parse_summary_rows(pages[0])
    stages = parse_stage_tables(all_lines)
    pass_count = max([stage["pass_idx"] for stage in stages], default=1)
    pass_overview = parse_pass_overview(pages, pass_count)
    chemistry_tables = parse_chemistry_tables(all_lines)
    ccro = parse_ccro_parameters(all_lines)

    report_type = "CCRO" if any("CCRO Summary Report" in page for page in pages) else "RO"
    primary_stage = stages[0] if stages else None
    fallback_model_text = f"{filename} {document.text[:3000]}"
    membrane_model = (
        primary_stage["membrane_model"] if primary_stage else normalize_model_name("", fallback_model_text)
    )

    net_feed = summary_rows.get("Net Feed to Pass 1") or summary_rows.get("Raw Feed to RO System") or {}
    raw_feed = summary_rows.get("Raw Feed to RO System") or net_feed
    net_product = summary_rows.get("Net Product from RO System")
    if not net_product:
        net_product = summary_rows.get("Total Permeate from Pass 1") or {}

    first_pass_overview = pass_overview.get(1, {})
    pressure_range: List[float] = []
    overview_page = next((page for page in pages if "Feed Pressure" in page and "Flow Factor Per Stage" in page), pages[0])
    flat_overview = re.sub(r"\s+", " ", overview_page)
    pressure_match = re.search(r"Feed Pressure\s*\(bar\)\s*([\d,.]+)\s*-\s*([\d,.]+)", flat_overview, re.I)
    if pressure_match:
        pressure_range = [_to_float(pressure_match.group(1), 0.0) or 0.0, _to_float(pressure_match.group(2), 0.0) or 0.0]

    # Attach stages and chemistry to each pass.
    passes: List[Dict[str, Any]] = []
    for pass_idx in range(1, pass_count + 1):
        pass_stages = [dict(stage) for stage in stages if stage["pass_idx"] == pass_idx]
        info = dict(pass_overview.get(pass_idx, {}))
        info["pass_idx"] = pass_idx
        info["stages"] = pass_stages
        if pass_stages:
            info.setdefault("number_of_elements", sum(s["pressure_vessels"] * s["elements_per_vessel"] for s in pass_stages))
            info.setdefault("feed_flow_m3h", pass_stages[0]["feed_flow_m3h"])
            info.setdefault("feed_pressure_bar", pass_stages[0]["feed_pressure_bar"] + pass_stages[0]["boost_pressure_bar"])
            info.setdefault("permeate_flow_m3h", sum(s["permeate_flow_m3h"] for s in pass_stages))
            total_perm = sum(s["permeate_flow_m3h"] for s in pass_stages)
            if total_perm > 0:
                info.setdefault(
                    "permeate_tds_mgL",
                    sum(s["permeate_flow_m3h"] * s["permeate_tds_mgL"] for s in pass_stages) / total_perm,
                )
                info.setdefault("recovery_pct", total_perm / max(pass_stages[0]["feed_flow_m3h"], 1e-9) * 100.0)
        chem = next((table for table in chemistry_tables if table["pass_idx"] == pass_idx), None)
        if chem:
            info["chemistry_table"] = chem
            info["feed_ions"] = _stream_ions(chem, ["adjusted_feed", "feed", "raw_feed"])
            info["raw_feed_ions"] = _stream_ions(chem, ["raw_feed", "feed"])
            info["permeate_ions"] = _stream_ions(chem, ["permeate_total", "permeate_stage2", "permeate_stage1"])
            info["concentrate_ions"] = _stream_ions(chem, ["concentrate_cc_final", "concentrate_stage2", "concentrate_stage1"])
            info["feed_chemistry_meta"] = _stream_meta(chem, ["adjusted_feed", "feed", "raw_feed"])
            info["permeate_chemistry_meta"] = _stream_meta(chem, ["permeate_total", "permeate_stage2", "permeate_stage1"])
        passes.append(info)

    feed_pressure = _to_float(net_feed.get("pressure_bar"), 0.0) or 0.0
    if pressure_range:
        feed_pressure = max(pressure_range)

    first_pass = passes[0] if passes else {}
    final_pass = passes[-1] if passes else {}
    system_recovery = 0.0
    raw_flow = _to_float(raw_feed.get("flow_m3h"), 0.0) or 0.0
    product_flow = _to_float(net_product.get("flow_m3h"), 0.0) or 0.0
    if raw_flow > 0:
        system_recovery = product_flow / raw_flow * 100.0
    if not system_recovery:
        system_recovery = _to_float(first_pass.get("recovery_pct"), 0.0) or 0.0

    flow_factors = first_pass.get("flow_factors") or [0.85]
    top_flow_factor = float(flow_factors[0]) if flow_factors else 0.85

    record: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_file": filename,
        "extraction_method": document.method,
        "report_type": report_type,
        "membrane_model": membrane_model,
        "feed_flow": _to_float(net_feed.get("flow_m3h"), raw_flow) or raw_flow,
        "raw_feed_flow": raw_flow,
        "system_recovery": system_recovery,
        "feed_tds": _to_float(net_feed.get("tds_mgL"), _to_float(first_pass.get("feed_tds_mgL"), 0.0)) or 0.0,
        "raw_feed_tds": _to_float(raw_feed.get("tds_mgL"), 0.0) or 0.0,
        "temperature": _to_float(first_pass.get("temperature_C"), 25.0) or 25.0,
        "permeate_tds": _to_float(net_product.get("tds_mgL"), _to_float(final_pass.get("permeate_tds_mgL"), 0.0)) or 0.0,
        "feed_pressure": feed_pressure,
        "feed_pressure_min": min(pressure_range) if pressure_range else feed_pressure,
        "feed_pressure_max": max(pressure_range) if pressure_range else feed_pressure,
        "feed_ph": _to_float(first_pass.get("ph"), 7.5) or 7.5,
        "flow_factor": top_flow_factor,
        "flow_factors": flow_factors,
        "pressure_vessels": primary_stage["pressure_vessels"] if primary_stage else 10,
        "elements_per_vessel": primary_stage["elements_per_vessel"] if primary_stage else 6,
        "number_of_elements": int(first_pass.get("number_of_elements") or (primary_stage["pressure_vessels"] * primary_stage["elements_per_vessel"] if primary_stage else 60)),
        "passes": passes,
        "stages": stages,
        "summary_streams": summary_rows,
        "ccro": ccro,
        "feed_ions": first_pass.get("feed_ions", {}),
        "raw_feed_ions": first_pass.get("raw_feed_ions", {}),
        "permeate_ions": final_pass.get("permeate_ions", {}),
        "concentrate_ions": final_pass.get("concentrate_ions", {}),
        "chemical_dose": first_pass.get("chemical_dose", "-"),
        "pass2_target_ph": _to_float(final_pass.get("ph")) if pass_count > 1 else None,
        "data_quality": {
            "native_text_chars": sum(len(page) for page in pages),
            "stage_rows": len(stages),
            "chemistry_tables": len(chemistry_tables),
            "pass_count": pass_count,
            "has_actual_ion_composition": bool(first_pass.get("feed_ions")),
            "has_system_product": bool(net_product),
        },
    }

    if report_type == "CCRO" and ccro:
        record["recirc_flow_m3h"] = float(ccro.get("cc_net_feed_flow_m3h_per_pv", 0.0)) * float(record["pressure_vessels"])
        record["loop_volume_m3"] = ccro.get("cc_system_volume_m3")
        record["max_minutes"] = ccro.get("complete_cycle_duration_min")
        record["pf_feed_ratio_pct"] = ccro.get("pf_feed_ratio_pct")
        record["pf_recovery_pct"] = ccro.get("pf_recovery_pct")
        record["cc_recovery_pct"] = ccro.get("cc_recovery_pct")

    # Backward-compatible UF placeholders retained for existing reports/scripts.
    record["uf_gross_feed_flow"] = record["raw_feed_flow"]
    record["uf_recovery"] = record["system_recovery"]
    record["uf_net_product_flow"] = product_flow
    record["sec"] = 1.0
    return record


def parse_pdf(pdf_path: Path, allow_ocr: bool = False) -> Dict[str, Any]:
    document = extract_document(pdf_path, allow_ocr=allow_ocr)
    return parse_wave_document(document, pdf_path.name)


def load_master_db(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def write_dataset(records: Sequence[Dict[str, Any]], json_path: Path, csv_path: Optional[Path] = None) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(list(records), ensure_ascii=False, indent=2), encoding="utf-8")
    if csv_path:
        # CSV is intentionally a flat compatibility view. Nested topology remains authoritative in JSON.
        flat_records = []
        for record in records:
            flat_records.append({key: value for key, value in record.items() if not isinstance(value, (dict, list))})
        headers = sorted(set().union(*(row.keys() for row in flat_records))) if flat_records else []
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(flat_records)


def process_directory(
    input_dir: Path,
    output_json: Path,
    output_csv: Optional[Path],
    completed_dir: Optional[Path] = None,
    failed_dir: Optional[Path] = None,
    rebuild: bool = False,
    allow_ocr: bool = False,
) -> List[Dict[str, Any]]:
    files = sorted(input_dir.glob("*.pdf"))
    if not files:
        logger.info("No PDF files found in %s", input_dir)
        return []

    existing = [] if rebuild else load_master_db(output_json)
    by_name = {str(item.get("source_file")): item for item in existing if item.get("source_file")}

    for index, pdf_path in enumerate(files, start=1):
        logger.info("[%d/%d] Parsing %s", index, len(files), pdf_path.name)
        try:
            record = parse_pdf(pdf_path, allow_ocr=allow_ocr)
            by_name[pdf_path.name] = record
            if completed_dir:
                completed_dir.mkdir(parents=True, exist_ok=True)
                target = completed_dir / pdf_path.name
                if pdf_path.resolve() != target.resolve():
                    shutil.move(str(pdf_path), str(target))
        except Exception as exc:
            logger.exception("Failed to parse %s: %s", pdf_path.name, exc)
            if failed_dir:
                failed_dir.mkdir(parents=True, exist_ok=True)
                target = failed_dir / pdf_path.name
                if pdf_path.resolve() != target.resolve():
                    shutil.move(str(pdf_path), str(target))

    records = list(by_name.values())
    records.sort(key=lambda item: str(item.get("source_file", "")))
    write_dataset(records, output_json, output_csv)
    logger.info("Saved %d records to %s", len(records), output_json)
    return records


def run_etl_pipeline() -> None:
    parser = argparse.ArgumentParser(description="Parse DuPont WAVE PDF reports into AquaNova schema v3")
    parser.add_argument("--input-dir", type=Path, default=Path("./WAVE_PIPELINE/1_INPUT"))
    parser.add_argument("--completed-dir", type=Path, default=Path("./WAVE_PIPELINE/2_COMPLETED"))
    parser.add_argument("--failed-dir", type=Path, default=Path("./WAVE_PIPELINE/3_FAILED"))
    parser.add_argument("--output-json", type=Path, default=Path("./.data/wave_extracted_dataset.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("./.data/wave_extracted_dataset.csv"))
    parser.add_argument("--rebuild", action="store_true", help="Replace records instead of merging by source_file")
    parser.add_argument("--ocr-fallback", action="store_true", help="Use Google Vision only when native text is unavailable")
    parser.add_argument("--no-move", action="store_true", help="Do not move successfully parsed files")
    args = parser.parse_args()

    process_directory(
        input_dir=args.input_dir,
        output_json=args.output_json,
        output_csv=args.output_csv,
        completed_dir=None if args.no_move else args.completed_dir,
        failed_dir=None if args.no_move else args.failed_dir,
        rebuild=args.rebuild,
        allow_ocr=args.ocr_fallback,
    )


if __name__ == "__main__":
    run_etl_pipeline()
