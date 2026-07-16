#!/usr/bin/env python3
"""Production-plan parsing and dry-run helpers for WAVE automation.

Split out in V73 from the former monolithic wave_production.py.  This module is
intentionally runtime-light: it does not click WAVE or launch processes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from wave_common import *
from wave_ro_engine import _validate_case_automation_support


PRODUCTION_SCHEMA_VERSION = 1
PRODUCTION_AUTOMATION_VERSION = "V69"


@dataclass
class ProductionItem:
    key: str
    kind: str
    source_index: int
    raw: dict[str, Any]
    ro_case: ROCaseConfig | None = None
    description: str = ""
    expected_outputs: list[str] = field(default_factory=list)

    def manifest_input(self) -> dict[str, Any]:
        data = dict(self.raw)
        if self.ro_case is not None:
            data["resolved_ro_case_id"] = self.ro_case.case_id
            data["resolved_pdf_name"] = self.ro_case.pdf_name
            data["resolved_batch_order"] = self.ro_case.batch_order
            data["resolved_pass_count"] = self.ro_case.pass_count
        return _json_safe(data)

def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WaveAutomationError(f"Production plan JSON을 읽지 못했습니다: {path} ({exc!r})")
    if not isinstance(data, dict):
        raise WaveAutomationError("Production plan 최상위는 JSON object여야 합니다.")
    return data

def _resolve_plan_path(value: Any, base_dir: Path) -> Path:
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        p = base_dir / p
    return p

def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

def _item_kind(raw: dict[str, Any]) -> str:
    kind = str(raw.get("kind") or raw.get("type") or raw.get("process") or "").strip().casefold()
    aliases = {
        "ro": "ro_excel",
        "nf": "ro_excel",
        "ro_excel_case": "ro_excel",
        "excel": "ro_excel",
        "uf": "uf_video",
        "uf_video_case": "uf_video",
        "ccro": "ccro_video",
        "ccro_video_case": "ccro_video",
    }
    return aliases.get(kind, kind)

def _plan_defaults(plan: dict[str, Any]) -> dict[str, Any]:
    defaults = plan.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise WaveAutomationError("Production plan defaults는 object여야 합니다.")
    return defaults

def _bool_from_raw(raw: dict[str, Any], defaults: dict[str, Any], key: str, fallback: bool) -> bool:
    if key in raw:
        return bool(raw[key])
    if key in defaults:
        return bool(defaults[key])
    return fallback

def _prepare_ro_items(
    raw: dict[str, Any],
    *,
    defaults: dict[str, Any],
    source_index: int,
    plan_base: Path,
) -> list[ProductionItem]:
    input_value = raw.get("path") or raw.get("excel") or raw.get("input") or raw.get("run_ro_excel")
    if not input_value:
        raise WaveAutomationError(f"Production item #{source_index}: ro_excel에는 path/excel/input이 필요합니다.")
    input_path = _resolve_plan_path(input_value, plan_base)
    sheet = str(raw.get("sheet") or raw.get("ro_sheet") or defaults.get("ro_sheet") or "01_PASS_STAGE")
    cases = load_ro_cases(input_path, sheet)

    if raw.get("batch_group") is not None:
        wanted_group = str(raw.get("batch_group")).strip().casefold()
        cases = [case for case in cases if case.batch_group.strip().casefold() == wanted_group]
    selected_ids = {str(v) for v in _as_list(raw.get("case_id") or raw.get("case_ids")) if str(v).strip()}
    if selected_ids:
        cases = [case for case in cases if case.case_id in selected_ids]
    if raw.get("start_order") is not None:
        start = int(raw.get("start_order"))
        cases = [case for case in cases if case.batch_order >= start]
    if raw.get("end_order") is not None:
        end = int(raw.get("end_order"))
        cases = [case for case in cases if case.batch_order <= end]
    if not cases:
        raise WaveAutomationError(
            f"Production item #{source_index}: {input_path.name}:{sheet}에서 실행할 RO/NF 사례가 없습니다."
        )

    allow_experimental = _bool_from_raw(raw, defaults, "allow_experimental_ro", True)
    for case in cases:
        _validate_case_automation_support(case, allow_experimental=allow_experimental)

    base_id = str(raw.get("id") or raw.get("name") or input_path.stem).strip()
    result: list[ProductionItem] = []
    for case in sorted(cases, key=lambda c: (c.batch_order, c.case_id)):
        key = str(raw.get("production_key") or f"{base_id}:{case.case_id}")
        if len(cases) > 1 or not raw.get("production_key"):
            key = f"{base_id}:{case.case_id}"
        result.append(
            ProductionItem(
                key=key,
                kind="ro_excel",
                source_index=source_index,
                raw={
                    **raw,
                    "path": str(input_path),
                    "sheet": sheet,
                    "case_id": case.case_id,
                    "allow_experimental_ro": allow_experimental,
                },
                ro_case=case,
                description=f"RO/NF Excel {sheet} {case.case_id}",
                expected_outputs=[case.pdf_name],
            )
        )
    return result

def _prepare_direct_item(raw: dict[str, Any], *, source_index: int, kind: str) -> ProductionItem:
    key = str(raw.get("id") or raw.get("case_id") or raw.get("name") or f"{kind}_{source_index:04d}").strip()
    if not key:
        key = f"{kind}_{source_index:04d}"
    pdf_name = str(raw.get("pdf_name") or raw.get("uf_pdf_name") or raw.get("ccro_pdf_name") or "")
    return ProductionItem(
        key=key,
        kind=kind,
        source_index=source_index,
        raw=dict(raw),
        description=kind,
        expected_outputs=[pdf_name] if pdf_name else [],
    )

def load_production_plan(plan_path: str | Path) -> tuple[dict[str, Any], list[ProductionItem]]:
    path = Path(plan_path).expanduser().resolve()
    plan = _load_json_file(path)
    if int(plan.get("schema_version", PRODUCTION_SCHEMA_VERSION)) != PRODUCTION_SCHEMA_VERSION:
        raise WaveAutomationError(
            f"지원하지 않는 Production plan schema_version={plan.get('schema_version')!r}"
        )
    defaults = _plan_defaults(plan)
    raw_cases = plan.get("cases") or plan.get("items")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise WaveAutomationError("Production plan에는 비어 있지 않은 cases 배열이 필요합니다.")

    items: list[ProductionItem] = []
    for index, raw in enumerate(raw_cases, start=1):
        if not isinstance(raw, dict):
            raise WaveAutomationError(f"Production item #{index}는 object여야 합니다.")
        kind = _item_kind(raw)
        if kind == "ro_excel":
            items.extend(_prepare_ro_items(raw, defaults=defaults, source_index=index, plan_base=path.parent))
        elif kind in {"uf_video", "ccro_video"}:
            items.append(_prepare_direct_item(raw, source_index=index, kind=kind))
        else:
            raise WaveAutomationError(
                f"Production item #{index}: 지원하지 않는 kind/process={kind!r}. "
                "지원값: ro_excel, uf_video, ccro_video"
            )
    keys = [item.key for item in items]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise WaveAutomationError(f"Production item key가 중복됩니다: {duplicates}")
    return plan, items

def write_production_plan_example(output_dir: Path = RESULTS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "wave_production_plan_example_v69.json"
    example = {
        "schema_version": 1,
        "name": "V69 mixed-process smoke plan",
        "defaults": {
            "allow_experimental_ro": True,
            "allow_experimental_batch": True,
            "ro_sheet": "09_NF_BASELINE"
        },
        "cases": [
            {
                "id": "NF270_BASELINE",
                "kind": "ro_excel",
                "path": "../AquaNova_WAVE_RO_NF_Experimental_Test_Matrix_V46_2026-07-03.xlsx",
                "sheet": "09_NF_BASELINE",
                "case_id": "V46_NF_001"
            },
            {
                "id": "UF_SFP2660_F100",
                "kind": "uf_video",
                "uf_module": "Ultrafiltration SFP-2660",
                "uf_water_profile": "Well Water - Med Hardness",
                "uf_feed_flow": 100,
                "uf_pdf_name": "V69_UF_SFP2660_F100.pdf"
            },
            {
                "id": "CCRO_2PASS_90_90",
                "kind": "ccro_video",
                "ccro_element": "FilmTec™ SOAR 5000i",
                "ccro_water_profile": "Well Water - Med Hardness",
                "ccro_feed_flow": 100,
                "ccro_pass_count": 2,
                "ccro_recovery": 90,
                "ccro_pass2_recovery": 90,
                "ccro_pdf_name": "V69_CCRO_2PASS_SOAR5000i_F100_P1R90_P2R90.pdf"
            }
        ]
    }
    path.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def dry_run_production_plan(plan_path: str | Path) -> dict[str, Any]:
    plan, items = load_production_plan(plan_path)
    return {
        "schema_version": PRODUCTION_SCHEMA_VERSION,
        "automation_version": PRODUCTION_AUTOMATION_VERSION,
        "name": plan.get("name", ""),
        "case_count": len(items),
        "items": [
            {
                "index": index,
                "key": item.key,
                "kind": item.kind,
                "description": item.description,
                "expected_outputs": item.expected_outputs,
                "input": item.manifest_input(),
            }
            for index, item in enumerate(items, start=1)
        ],
    }

def _production_family(item: ProductionItem) -> str:
    """Return the mutually exclusive WAVE process family for case isolation."""
    if item.kind == "ro_excel":
        return "ro_nf"
    if item.kind == "uf_video":
        return "uf"
    if item.kind == "ccro_video":
        return "ccro"
    return item.kind

def _plan_requires_case_isolation(plan: dict[str, Any], items: list[ProductionItem]) -> bool:
    """Decide whether the runner should create a fresh WAVE Case before process-family changes.

    WAVE does not allow RO/NF, UF, and CCRO process icons to be mixed arbitrarily
    in one system design.  Single-process batches can keep using the existing
    per-case soft-reset logic, but mixed-process smoke/production plans need a
    blank WAVE project for each isolated production item, including the first
    executable item because the operator may have left WAVE on any previous case.
    """
    raw = plan.get("fresh_project_per_item")
    if raw is None:
        raw = plan.get("fresh_case_per_process")
    if raw is None:
        raw = plan.get("isolate_process_families")
    if raw is None:
        defaults = plan.get("defaults") if isinstance(plan.get("defaults"), dict) else {}
        if "fresh_project_per_item" in defaults:
            raw = defaults.get("fresh_project_per_item")
        elif "fresh_case_per_process" in defaults:
            raw = defaults.get("fresh_case_per_process")
        elif "isolate_process_families" in defaults:
            raw = defaults.get("isolate_process_families")
    if raw is not None:
        return bool(raw)
    return len({_production_family(item) for item in items}) > 1

__all__ = [name for name in globals() if not name.startswith("__")]
