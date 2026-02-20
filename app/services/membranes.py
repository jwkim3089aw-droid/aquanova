# app/services/membranes.py
from __future__ import annotations
from typing import Any, Optional, Dict, Tuple
from app.api.v1.schemas import MembraneSpec
from app.api.v1.schemas import MembraneOut
from app.data.membranes import MEMBRANES


def _as_list() -> list[dict[str, Any]]:
    src = MEMBRANES
    if isinstance(src, dict):
        return [dict(id=k, **(v or {})) for k, v in src.items()]
    return list(src or [])


def _normalize(raw: dict[str, Any]) -> MembraneSpec:
    # 다양한 키 대응
    def pick_num(d: dict, *keys: str) -> Optional[float]:
        for k in keys:
            v = d.get(k)
            if v is None:
                continue
            try:
                vv = float(v)
                if vv == vv:  # not NaN
                    return vv
            except Exception:
                pass
        return None

    return MembraneSpec(
        id=str(raw.get("id") or raw.get("code") or raw.get("name") or "").strip(),
        name=raw.get("name") or raw.get("display_name"),
        vendor=raw.get("vendor") or raw.get("brand") or raw.get("maker"),
        series=raw.get("series") or raw.get("model"),
        family=raw.get("family") or raw.get("type"),
        size=raw.get("size"),
        area_m2=pick_num(raw, "area_m2", "active_area_m2", "area"),
        A_lmh_bar=pick_num(
            raw, "A_lmh_bar", "A", "water_perm_Lmh_bar", "water_permeability"
        ),
        B_mps=pick_num(raw, "B_mps", "B", "salt_perm_mps", "salt_permeability"),
        salt_rejection_pct=pick_num(
            raw,
            "salt_rejection_pct",
            "rejection_pct",
            "NaCl_rejection_pct",
            "rejection",
        ),
        notes=raw.get("notes"),
    )


def load_by_id(code: str) -> Optional[MembraneSpec]:
    if not code:
        return None
    cid = str(code).strip().lower()
    for m in _as_list():
        mid = str(m.get("id") or "").strip().lower()
        if mid == cid:
            spec = _normalize(m)
            # 최소 안전 기본값 보정
            if spec.area_m2 is None:
                spec.area_m2 = 40.9 if (spec.size or "").startswith("8040") else 7.9
            return spec
    return None


def normalize_spec(obj: Any) -> Optional[MembraneSpec]:
    """dict/str/None 무엇이 오든 MembraneSpec으로 정규화."""
    if obj is None:
        return None

    if isinstance(obj, MembraneSpec):
        return obj
    if isinstance(obj, dict):
        # dict로 직접 넘어오면 최대한 맞춰서 보정
        try:
            spec = MembraneSpec(**obj)
        except Exception:
            spec = _normalize(obj)
        if spec.area_m2 is None:
            spec.area_m2 = 40.9
        return spec
    if isinstance(obj, str):
        return load_by_id(obj)
    return None


def resolve_from_options(options: Dict[str, Any] | None) -> MembraneSpec:
    """options에서 membrane_spec 또는 membrane_code/문자열을 찾아 정규화."""
    opts = options or {}
    # 우선순위: 명시 스펙(dict) > 코드/문자열
    spec = normalize_spec(opts.get("membrane_spec"))
    if spec:
        return spec
    spec = normalize_spec(opts.get("membrane_code") or opts.get("membrane"))
    if spec:
        return spec
    # 최종 기본값 (엔진이 반드시 필요로 할 값)
    return MembraneSpec(
        id="default-8040",
        name="Default 8040",
        area_m2=40.9,
        A_lmh_bar=3.0,
        B_mps=1.5e-7,
    )


# === 추가: 시뮬레이터가 바로 쓸 수 있는 파라미터 추출기 ===
def get_params_from_options(
    options: Dict[str, Any] | None,
    stage_type: str | None = "RO",
) -> Dict[str, float]:
    """
    options + 카탈로그(MEMBRANES + 사용자가 넣은 spec)를 병합해
    시뮬 엔진에서 바로 쓰는 dict로 변환.
    반환 키:
      - A (LMH/bar), B_lmh (LMH), area (m2/element), max_flux (LMH), salt_rejection_pct (0~1)
    """  # [ADDED]
    opts = dict(options or {})
    st = (stage_type or "RO").upper()

    # 1) 카탈로그/스펙
    spec = resolve_from_options(opts)

    # 2) 면적/투과도 (옵션이 우선)
    area = float(
        opts.get("area_m2") or opts.get("membrane_area_m2") or spec.area_m2 or 40.9
    )
    A = float(opts.get("A_lmh_bar") or opts.get("A") or spec.A_lmh_bar or 2.0)

    # B: LMH 또는 m/s → LMH 변환(1 m/s = 3,600,000 LMH)
    if "B_lmh" in opts:
        B_lmh = float(opts["B_lmh"])
    elif "B" in opts:
        B_lmh = float(opts["B"])
    else:
        B_lmh = (
            (float(spec.B_mps) * 3_600_000.0) if (spec.B_mps is not None) else 0.40
        )  # 기본값 [ADDED]

    # 3) max_flux 기본치
    max_flux = float(opts.get("max_flux") or 40.0)

    # 4) 제거율 기본치 (0~1)
    if "salt_rejection_pct" in opts:
        rej = float(opts["salt_rejection_pct"])
        salt_rejection_pct = rej if rej <= 1.0 else rej / 100.0
    elif spec.salt_rejection_pct is not None:
        salt_rejection_pct = float(spec.salt_rejection_pct)
        salt_rejection_pct = (
            salt_rejection_pct
            if salt_rejection_pct <= 1.0
            else salt_rejection_pct / 100.0
        )
    else:
        # 타입별 기본
        salt_rejection_pct = {
            "RO": 0.99,
            "SWRO": 0.995,
            "NF": 0.60,
            "UF": 0.0,
            "MF": 0.0,
        }.get(st, 0.99)

    return dict(
        A=A,
        B_lmh=B_lmh,
        area=area,
        max_flux=max_flux,
        salt_rejection_pct=salt_rejection_pct,
    )  # [ADDED]


def family_for_stage(stage_type: str | None) -> str | None:  # [ADDED]
    st = (stage_type or "").upper()
    if st in ("RO", "HRRO"):
        return "RO"
    if st in ("NF", "UF", "MF"):
        return st
    return None


# --- NEW: Spec → API Out 변환 헬퍼 ---  # [ADDED]
def _to_out(spec: MembraneSpec) -> MembraneOut:  # [ADDED]
    return MembraneOut(**spec.model_dump())


def list_membranes(  # [CHANGED] 필터 확장
    family: str | None = None,
    size: str | None = None,
    q: str | None = None,
    limit: int | None = None,
) -> list[MembraneOut]:
    fam = family.upper() if family else None
    ql = (q or "").strip().lower()
    out: list[MembraneOut] = []
    for raw in _as_list():
        spec = _normalize(raw)

        if fam:
            s_fam = (spec.family or "").upper()
            if s_fam != fam:
                continue
        if (
            size
            and spec.size
            and str(spec.size).strip().lower() != str(size).strip().lower()
        ):
            continue
        if ql:
            hay = " ".join(
                [
                    spec.id or "",
                    spec.name or "",
                    spec.vendor or "",
                    spec.series or "",
                    spec.family or "",
                    spec.size or "",
                ]
            ).lower()
            if ql not in hay:
                continue

        out.append(_to_out(spec))
        if limit and len(out) >= limit:
            break
    return out


# --- NEW: 단건 조회용 ---  # [ADDED]
def get_membrane_out_by_id(membrane_id: str) -> Optional[MembraneOut]:  # [ADDED]
    spec = load_by_id(membrane_id)
    return _to_out(spec) if spec else None
