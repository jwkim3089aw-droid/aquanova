# scripts/diagnose_dataset.py
import json
import statistics


def diagnose():
    with open("./.data/wave_extracted_dataset.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 모델별 데이터 변동성 확인
    report = {}
    for r in data:
        model = r["membrane_model"]
        if model not in report:
            report[model] = []
        if r.get("feed_pressure"):
            report[model].append(r["feed_pressure"])

    print(f"{'Membrane Model':<30} | {'Count':<6} | {'Pressure StdDev'}")
    for model, pressures in report.items():
        std = statistics.stdev(pressures) if len(pressures) > 1 else 0
        print(f"{model:<30} | {len(pressures):<6} | {std:.2f}")


if __name__ == "__main__":
    diagnose()
