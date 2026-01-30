# app\services\simulation\modules\base.py
from abc import ABC, abstractmethod
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric


class SimulationModule(ABC):
    """
    모든 수처리 모듈(RO, NF, HRRO 등)의 공통 부모 클래스.
    Strategy 패턴의 Interface 역할을 합니다.
    """

    @abstractmethod
    def compute(self, stage_conf: StageConfig, feed: FeedInput) -> StageMetric:
        """
        입력: 스테이지 설정(Config), 유입수(Feed)
        출력: 결과 메트릭(Metric)
        """
        pass
