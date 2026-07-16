# app/cli.py

from __future__ import annotations

import json
import typer
from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine

app = typer.Typer()


@app.command("simulate")
def simulate(json_path: str, pretty: bool = True):
    # 1. 입력 데이터 로드 및 검증
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        payload = ScenarioInput(**data)

    # 2. 시뮬레이션 엔진 초기화 및 실행 (정석 방식)
    engine = SimulationEngine()
    out = engine.run(payload)

    # 3. 결과 출력
    output_json = out.model_dump_json(indent=2 if pretty else None)
    print(output_json)


if __name__ == "__main__":
    app()
