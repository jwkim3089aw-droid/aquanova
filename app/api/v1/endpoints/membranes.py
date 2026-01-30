# app\api\v1\endpoints\membranes.py
from __future__ import annotations
from typing import List, Optional, Any, Dict, Literal

from fastapi import APIRouter, Query, HTTPException
from app.api.v1.schemas import MembraneOut

# [Data Source]
try:
    from app.data.membranes import MEMBRANES
except ImportError:
    MEMBRANES = []

router = APIRouter()

# ==============================================================================
# 1. Constants & Defaults
# ==============================================================================
DEFAULT_GENERICS: List[Dict[str, Any]] = [
    {
        "id": "BWRO-8040-generic",
        "name": "Generic BWRO 8040",
        "vendor": "Generic",
        "family": "RO",
        "size": "8040",
        "area_m2": 37.0,
        "A_lmh_bar": 2.0,
        "B_mps": 0.40,
        "salt_rejection_pct": 99.5,
    },
    {
        "id": "SWRO-8040-generic",
        "name": "Generic SWRO 8040",
        "vendor": "Generic",
        "family": "RO",
        "size": "8040",
        "area_m2": 32.0,
        "A_lmh_bar": 1.2,
        "B_mps": 0.25,
        "salt_rejection_pct": 99.8,
    },
    {
        "id": "NF-8040-generic",
        "name": "Generic NF 8040",
        "vendor": "Generic",
        "family": "NF",
        "size": "8040",
        "area_m2": 37.0,
        "A_lmh_bar": 3.0,
        "B_mps": 0.80,
        "salt_rejection_pct": 60.0,
    },
    {
        "id": "UF-8040-generic",
        "name": "Generic UF 8040",
        "vendor": "Generic",
        "family": "UF",
        "size": "8040",
        "area_m2": 40.0,
        "A_lmh_bar": 60.0,
        "B_mps": 50.0,
        "salt_rejection_pct": 0.0,
    },
    {
        "id": "MF-8040-generic",
        "name": "Generic MF 8040",
        "vendor": "Generic",
        "family": "MF",
        "size": "8040",
        "area_m2": 40.0,
        "A_lmh_bar": 120.0,
        "B_mps": 80.0,
        "salt_rejection_pct": 0.0,
    },
]

FAMILY_SYNONYMS = {
    "RO": ["ro", "bwro", "swro", "reverse osmosis", "hrro"],  # HRRO도 RO 계열
    "NF": ["nf", "nano", "nanofiltration"],
    "UF": ["uf", "ultra", "ultrafiltration"],
    "MF": ["mf", "micro", "microfiltration"],
}


# ==============================================================================
# 2. Helper Functions
# ==============================================================================
def _as_list() -> List[Dict[str, Any]]:
    src = MEMBRANES
    if isinstance(src, dict):
        return [dict(id=k, **(v or {})) for k, v in src.items()]
    return list(src)


def _norm(x: Any) -> str:
    return str(x if x is not None else "").strip().lower()


def _eq_ci(a: Any, b: Any) -> bool:
    return _norm(a) == _norm(b)


def _family_key(x: Any) -> Optional[str]:
    v = _norm(x)
    if not v:
        return None
    for k, vals in FAMILY_SYNONYMS.items():
        if v == _norm(k) or v in (_norm(y) for y in vals):
            return k
    return v.upper()


def _haystack(m: Dict[str, Any]) -> str:
    parts = [
        str(m.get("id", "")),
        str(m.get("name", "")),
        str(m.get("vendor", "")),
        str(m.get("series", "")),
        str(m.get("family", "")),
        str(m.get("type", "")),
        str(m.get("size", "")),
    ]
    return " ".join(parts).lower()


# ==============================================================================
# 3. Endpoints
# ==============================================================================
@router.get("/", response_model=List[MembraneOut])
def list_membranes(
    q: Optional[str] = Query(None, description="통합 검색"),
    family: Optional[str] = Query(None, description="필터: RO, NF, UF, MF"),
    stage_type: Optional[Literal["RO", "HRRO", "NF", "UF", "MF"]] = Query(
        None, description="스테이지 타입으로 필터링"
    ),
    size: Optional[str] = Query(None, description="필터: 8040, 4040"),
    limit: int = Query(200, ge=1, le=2000),
):
    """
    [멤브레인 목록 조회]
    - stage_type이 주어지면 자동으로 family를 결정합니다.
    - 검색(q) 및 필터링 지원
    """
    items = _as_list()

    # 파라미터 우선순위 결정 (stage_type이 있으면 family 자동 설정)
    target_family = family
    if not target_family and stage_type:
        target_family = "RO" if stage_type == "HRRO" else stage_type

    fam_q = _family_key(target_family) if target_family else None
    size_q = _norm(size) if size else None
    query_text = _norm(q) if q else None

    # 1. Family 필터
    if fam_q:
        items = [
            m for m in items if _family_key(m.get("family") or m.get("type")) == fam_q
        ]

    # 2. Size 필터
    if size_q:
        items = [m for m in items if _eq_ci(m.get("size"), size_q)]

    # 3. Text 검색
    if query_text:
        items = [m for m in items if query_text in _haystack(m)]

    # 4. Fallback (결과 없을 때 Generic 추천)
    if not items and (fam_q or size_q):
        candidates = DEFAULT_GENERICS[:]
        if fam_q:
            candidates = [
                g for g in candidates if _family_key(g.get("family")) == fam_q
            ]
        if size_q:
            candidates = [g for g in candidates if _eq_ci(g.get("size"), size_q)]
        if candidates:
            items = candidates

    # 5. 정렬 및 페이징
    items.sort(
        key=lambda m: (
            str(m.get("vendor", "")),
            str(m.get("series", "")),
            str(m.get("name", "")),
        )
    )
    return items[:limit]


@router.get("/{membrane_id}", response_model=MembraneOut)
def get_membrane(membrane_id: str):
    target_id = _norm(membrane_id)
    full_pool = _as_list() + DEFAULT_GENERICS

    for m in full_pool:
        if _norm(m.get("id")) == target_id:
            return m

    raise HTTPException(status_code=404, detail=f"Membrane '{membrane_id}' not found")
