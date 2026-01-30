# ./app/cli.py

from __future__ import annotations
import json
import typer
from app.api.v1.schemas import ScenarioInput
from app.services.simulation import run_l1_simulation

app = typer.Typer()

@app.command("simulate")
def simulate(json_path: str, pretty: bool = True):
    with open(json_path, "r", encoding="utf-8") as f:
        payload = ScenarioInput(**json.load(f))
    out = run_l1_simulation(payload)
    print(out.model_dump_json(indent=2 if pretty else None))

if __name__ == "__main__":
    app()
