#!/usr/bin/env python3
"""Minimal dependency-free XLSX/JSON reader for WAVE RO batch cases."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
import zipfile
import xml.etree.ElementTree as ET

from wave_ro_schema import ROCaseConfig

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref.upper())
    if not letters:
        return 0
    value = 0
    for ch in letters.group(0):
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for si in root.findall(f"{{{_NS_MAIN}}}si"):
        texts = [node.text or "" for node in si.iter(f"{{{_NS_MAIN}}}t")]
        values.append("".join(texts))
    return values


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{_NS_REL_PKG}}}Relationship")
    }
    selected_id = None
    available: list[str] = []
    for sheet in workbook.findall(f".//{{{_NS_MAIN}}}sheet"):
        name = sheet.attrib.get("name", "")
        available.append(name)
        if name == sheet_name:
            selected_id = sheet.attrib.get(f"{{{_NS_REL_DOC}}}id")
            break
    if selected_id is None:
        raise ValueError(
            f"worksheet {sheet_name!r} not found; available={available}"
        )
    target = target_by_id[selected_id].replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target.lstrip("/")


def _cell_value(cell: ET.Element, shared: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_NS_MAIN}}}t"))
    value_node = cell.find(f"{{{_NS_MAIN}}}v")
    if value_node is None:
        formula = cell.find(f"{{{_NS_MAIN}}}f")
        return "" if formula is None else None
    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except Exception:
            return raw
    if cell_type in {"str", "e"}:
        return raw
    if cell_type == "b":
        return raw == "1"
    try:
        number = float(raw)
        if number.is_integer():
            return int(number)
        return number
    except ValueError:
        return raw


def read_xlsx_rows(path: str | Path, sheet_name: str) -> list[dict[str, Any]]:
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        root = ET.fromstring(archive.read(_sheet_path(archive, sheet_name)))
        matrix: list[list[Any]] = []
        for row in root.findall(f".//{{{_NS_MAIN}}}sheetData/{{{_NS_MAIN}}}row"):
            values: list[Any] = []
            for cell in row.findall(f"{{{_NS_MAIN}}}c"):
                index = _column_index(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append(None)
                values[index] = _cell_value(cell, shared)
            matrix.append(values)
    while matrix and not any(value not in (None, "") for value in matrix[0]):
        matrix.pop(0)
    if not matrix:
        return []
    headers = [str(value or "").strip() for value in matrix[0]]
    rows: list[dict[str, Any]] = []
    for values in matrix[1:]:
        if not any(value not in (None, "") for value in values):
            continue
        rows.append(
            {
                header: values[index] if index < len(values) else None
                for index, header in enumerate(headers)
                if header
            }
        )
    return rows


def load_ro_cases(path: str | Path, sheet_name: str = "01_PASS_STAGE") -> list[ROCaseConfig]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_rows = payload.get("cases", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_rows, list):
            raise ValueError("JSON must be a list or {'cases': [...]} object")
    elif path.suffix.lower() == ".xlsx":
        raw_rows = read_xlsx_rows(path, sheet_name)
    else:
        raise ValueError("RO batch input must be .xlsx or .json")

    cases: list[ROCaseConfig] = []
    for index, row in enumerate(raw_rows, start=2):
        case = ROCaseConfig.from_mapping(row, source_row=index)
        if case.run_enabled:
            cases.append(case)
    cases.sort(key=lambda item: (item.batch_order, item.source_row, item.case_id))
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise ValueError(f"duplicate Case_ID: {case.case_id}")
        seen.add(case.case_id)
    return cases


__all__ = ["read_xlsx_rows", "load_ro_cases"]
