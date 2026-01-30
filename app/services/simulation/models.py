# app/services/simulation/models.py
from dataclasses import dataclass, field
from typing import Optional, Any, List


@dataclass
class StageResult:
    # 1. 필수 기본 정보
    stage_index: int
    Qf: float  # Feed Flow
    Cf: float  # Feed TDS
    Qp: float  # Permeate Flow
    Cp: float  # Permeate TDS
    Qc: float  # Concentrate Flow
    Cc: float  # Concentrate TDS

    pressure_in: float
    pressure_out: float
    recovery: float
    sec_kwhm3: float

    # 2. [추가됨] 고급 분석 데이터 (그래프/리포트용)
    # 없는 경우를 대비해 기본값(None/0.0) 설정
    avg_flux_lmh: float = 0.0
    power_kw: float = 0.0

    # 3. [추가됨] 화학적 프로파일 (스케일링 분석용)
    chem_profile: Optional[Any] = None

    # 4. [핵심] HRRO 그래프용 시계열 데이터
    time_history: Optional[List[Any]] = field(default=None)
