"""Batch output/PDF artifact helpers.

V130A extracted low-risk leaf artifact helpers from ``wave_batch_legacy.py``.
The legacy module imports these names back for compatibility, so existing
callers should keep working.

Keep this module free of WAVE UI desktop automation side effects.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple, Union

def _parse_pdf_summary_number(value: str) -> Optional[float]:
    """Parse one numeric cell from WAVE's pass-summary table."""
    match = re.fullmatch(
        r"\s*([-+]?[0-9]+(?:[.,][0-9]+)?)\s*%?\s*", value
    )
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None

def _pdf_percent_values(normalized: str, label_pattern: str) -> list[float]:
    """Return percentage values printed near a PDF label.

    WAVE reports many values to one decimal place.  A requested 75% recovery can
    therefore appear as ``Pass Recovery 75.1 %`` when the displayed feed flow is
    99.9 m3/h and permeate flow is 75.0 m3/h.  Exact string matching is too strict
    for this report format, so callers compare the parsed numbers with a small,
    explicit tolerance.
    """
    pattern = re.compile(
        rf"{label_pattern}[\s\S]{{0,96}}?(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
        re.I,
    )
    values: list[float] = []
    for match in pattern.finditer(normalized):
        try:
            values.append(float(match.group("value").replace(",", ".")))
        except (TypeError, ValueError):
            continue
    return values

def _pdf_pass_summary_lines(normalized: str, pass_count: int) -> list[str]:
    """Return only the Pass 1/Pass 2 summary-table body.

    PyMuPDF emits each table cell on its own line.  The table begins with a
    ``Pass`` cell followed by the exact pass column headers.  Scoping row
    parsing to this block prevents similarly named labels elsewhere in the
    report from being mistaken for pass-specific values.
    """
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    expected_headers = [f"pass {index}" for index in range(1, pass_count + 1)]
    for index, line in enumerate(lines):
        if line.casefold() != "pass":
            continue
        headers = lines[index + 1 : index + 1 + pass_count]
        if [header.casefold() for header in headers] != expected_headers:
            continue
        next_header_index = index + 1 + pass_count
        if (
            next_header_index < len(lines)
            and lines[next_header_index].casefold() == f"pass {pass_count + 1}"
        ):
            # Do not parse the first N columns of a larger stale topology.
            continue
        start = next_header_index
        end = len(lines)
        for cursor in range(start, len(lines)):
            lowered = lines[cursor].casefold()
            if lowered in {"footnotes:", "ro design warnings"}:
                end = cursor
                break
        return lines[start:end]
    return []

def _pdf_detect_pass_count(normalized: str) -> int:
    """Detect the exact number of pass columns in the WAVE summary table."""
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.casefold() != "pass":
            continue
        if index + 1 >= len(lines) or lines[index + 1].casefold() != "pass 1":
            continue
        count = 1
        while (
            index + 1 + count < len(lines)
            and lines[index + 1 + count].casefold() == f"pass {count + 1}"
        ):
            count += 1
        return count
    return 0

def _pdf_pass_summary_row_text_values(
    normalized: str, label: str, pass_count: int
) -> list[str]:
    """Extract one raw summary-table cell per pass for text/comma rows."""
    body = _pdf_pass_summary_lines(normalized, pass_count)
    target = " ".join(label.split()).casefold()
    for index, line in enumerate(body):
        if " ".join(line.split()).casefold() != target:
            continue
        cursor = index + 1
        if cursor < len(body) and body[cursor].startswith("(") and body[cursor].endswith(")"):
            cursor += 1
        cells = body[cursor : cursor + pass_count]
        if len(cells) == pass_count:
            return cells
    return []

def _pdf_flow_factor_per_stage_values(
    normalized: str, pass_count: int
) -> list[list[float]]:
    cells = _pdf_pass_summary_row_text_values(
        normalized, "Flow Factor Per Stage", pass_count
    )
    result: list[list[float]] = []
    for cell in cells:
        values: list[float] = []
        for token in re.split(r"\s*,\s*", cell.strip()):
            if not token:
                continue
            try:
                values.append(float(token.replace(",", ".")))
            except ValueError:
                values = []
                break
        result.append(values)
    return result if len(result) == pass_count else []

def _pdf_pass_summary_row_values(
    normalized: str, label: str, pass_count: int
) -> list[float]:
    """Extract all pass-column values from one summary-table row.

    The old regex captured only the first value after a row label.  In a
    two-pass report, for example, ``Pass Recovery`` is followed by both
    ``75.1 %`` and ``80.1 %``.  This parser reads exactly one cell per pass and
    skips the optional unit cell such as ``(m³/h)``.
    """
    body = _pdf_pass_summary_lines(normalized, pass_count)
    target = " ".join(label.split()).casefold()
    for index, line in enumerate(body):
        if " ".join(line.split()).casefold() != target:
            continue
        cursor = index + 1
        if cursor < len(body) and body[cursor].startswith("(") and body[cursor].endswith(")"):
            cursor += 1
        values: list[float] = []
        while cursor < len(body) and len(values) < pass_count:
            parsed = _parse_pdf_summary_number(body[cursor])
            if parsed is None:
                break
            values.append(parsed)
            cursor += 1
        if len(values) == pass_count:
            return values
    return []

def _pdf_flow_per_pass_values(
    normalized: str, label: str, pass_count: int
) -> list[float]:
    """Extract every pass value from a summary-table flow row."""
    values = _pdf_pass_summary_row_values(normalized, label, pass_count)
    if values:
        return values

    # Compatibility fallback for old/single-column report layouts.
    pattern = re.compile(
        rf"{re.escape(label)}\s*\n\s*\([^\n)]*\)\s*\n\s*"
        r"(?P<value>[0-9]+(?:[.,][0-9]+)?)",
        re.I,
    )
    fallback: list[float] = []
    for match in pattern.finditer(normalized):
        try:
            fallback.append(float(match.group("value").replace(",", ".")))
        except (TypeError, ValueError):
            continue
    return fallback

def _extract_pdf_solubility_warnings(normalized: str) -> dict[str, Any]:
    """Parse WAVE's RO Solubility Warnings table.

    Unlike the Design Warnings table, these rows are printed as a message
    followed by a Pass number.  They are valid evidence that WAVE has moved to
    a physically constrained achieved recovery (for example silica saturation
    or positive LSI), but never excuse a topology/membrane/input mismatch.
    """
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    try:
        start = next(
            index for index, line in enumerate(lines)
            if line.casefold() == "ro solubility warnings"
        )
    except StopIteration:
        return {"count": 0, "messages": [], "counts_by_message": {}, "items": []}

    stop = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].casefold() in {"footnotes:", "created:"}:
            stop = index
            break
    segment = lines[start + 1 : stop]
    ignored = {"warning", "pass no", "pass", "pass number"}
    items: list[dict[str, Any]] = []
    i = 0
    while i < len(segment):
        message = " ".join(segment[i].split())
        if message.casefold() in ignored or _parse_pdf_number_line(message) is not None:
            i += 1
            continue
        pass_no: int | None = None
        if i + 1 < len(segment):
            parsed = _parse_pdf_number_line(segment[i + 1])
            if parsed is not None and abs(parsed - round(parsed)) < 1e-6:
                pass_no = int(round(parsed))
                i += 1
        if (
            ">" in message
            or "<" in message
            or "required" in message.casefold()
            or "maximum allowable" in message.casefold()
            or "saturation" in message.casefold()
            or "index" in message.casefold()
        ):
            items.append(
                {
                    "message": message,
                    "pass_no": pass_no,
                    "line_index": start + 1 + i,
                }
            )
        i += 1

    counts: dict[str, int] = {}
    for item in items:
        message = str(item["message"])
        counts[message] = counts.get(message, 0) + 1
    return {
        "count": len(items),
        "messages": sorted(counts),
        "counts_by_message": counts,
        "items": items,
    }

def _merge_constraint_warnings(
    design_warnings: dict[str, Any], solubility_warnings: dict[str, Any]
) -> dict[str, Any]:
    items = [
        *[
            {**item, "section": "RO Design Warnings"}
            for item in design_warnings.get("items", [])
        ],
        *[
            {**item, "section": "RO Solubility Warnings"}
            for item in solubility_warnings.get("items", [])
        ],
    ]
    counts: dict[str, int] = {}
    for item in items:
        message = str(item.get("message", ""))
        counts[message] = counts.get(message, 0) + 1
    return {
        "count": len(items),
        "messages": sorted(counts),
        "counts_by_message": counts,
        "items": items,
        "sections": {
            "design": design_warnings,
            "solubility": solubility_warnings,
        },
    }

def _extract_pdf_chemical_observations(normalized: str) -> dict[str, Any]:
    """Capture non-failing chemistry output metadata for model training.

    The exact report layout varies by WAVE version, so V52 stores raw nearby
    numeric evidence instead of pretending every table has a fixed width.
    """
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    labels = (
        "pH",
        "LSI",
        "Stiff & Davis Index",
        "TDS (mg/L)",
        "Ionic Strength (molar)",
        "HCO3- (mg/L)",
        "CO2 (mg/L)",
        "CO3-- (mg/L)",
        "CaSO4 (% saturation)",
        "BaSO4 (% saturation)",
        "SrSO4 (% saturation)",
        "CaF2 (% saturation)",
        "SiO2 (% saturation)",
        "Mg(OH)2 (% saturation)",
    )
    normalized_labels = {
        re.sub(r"[^a-z0-9]+", "", label.casefold()): label for label in labels
    }
    rows: dict[str, list[dict[str, Any]]] = {}
    for index, line in enumerate(lines):
        clean = re.sub(r"[^a-z0-9]+", "", line.casefold())
        matched = next(
            (
                canonical
                for token, canonical in normalized_labels.items()
                if token and (clean == token or clean.startswith(token))
            ),
            None,
        )
        if not matched:
            continue
        values: list[float] = []
        raw: list[str] = []
        for candidate in lines[index + 1 : index + 7]:
            raw.append(candidate)
            parsed = _parse_pdf_number_line(candidate)
            if parsed is not None:
                values.append(parsed)
        rows.setdefault(matched, []).append(
            {"line_index": index, "values": values, "raw_context": raw}
        )

    chemical_dose: list[str] = []
    for index, line in enumerate(lines):
        if line.casefold() == "chemical dose":
            chemical_dose.extend(lines[index + 1 : index + 4])
    return {"rows": rows, "chemical_dose_context": chemical_dose}

def _parse_pdf_number_line(value: str) -> Optional[float]:
    cleaned = value.strip().replace(",", "")
    if not re.fullmatch(r"[-+]?[0-9]+(?:[.][0-9]+)?", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def _extract_pdf_stage_rows(
    normalized: str,
    pass_index: int,
    expected_stage_count: int,
) -> dict[int, dict[str, Any]]:
    """Parse the Stage Level table as exact ordered rows.

    pdftotext emits each table cell on a separate line.  The stage rows begin
    with stage number, membrane name, #PV and #Els/PV, followed by hydraulic
    values.  Parsing this ordered prefix avoids the old loose regex that could
    match Stage 1 values again for Stage 2 when every stage used BW30-400.
    """
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    marker = f"RO Flow Table (Stage Level) - Pass {pass_index}".lower()
    try:
        start = next(i for i, line in enumerate(lines) if marker in line.lower())
    except StopIteration:
        return {}
    segment = lines[start + 1 :]
    for stop_marker in (
        "concentrations (mg/l as ion)",
        "ro solute concentrations",
        "ro design warnings",
        "ro flow table (element level)",
    ):
        for i, line in enumerate(segment):
            if stop_marker in line.lower():
                segment = segment[:i]
                break

    rows: dict[int, dict[str, Any]] = {}
    expected_stage = 1
    i = 0
    while i + 3 < len(segment) and expected_stage <= expected_stage_count:
        if segment[i] != str(expected_stage):
            i += 1
            continue
        membrane = segment[i + 1].strip()
        pv = _parse_pdf_number_line(segment[i + 2])
        elements = _parse_pdf_number_line(segment[i + 3])
        # A genuine row has a nonnumeric product name and integer-like PV/Els.
        if (
            membrane
            and _parse_pdf_number_line(membrane) is None
            and pv is not None
            and elements is not None
            and abs(pv - round(pv)) < 1e-6
            and abs(elements - round(elements)) < 1e-6
        ):
            rows[expected_stage] = {
                "stage": expected_stage,
                "membrane": membrane,
                "pv": int(round(pv)),
                "elements_per_pv": int(round(elements)),
                "line_index": start + 1 + i,
            }
            expected_stage += 1
            # Each hydraulic row has many more cells; scanning forward for the
            # next stage number is safer than assuming a fixed total width.
            i += 4
            continue
        i += 1
    return rows
