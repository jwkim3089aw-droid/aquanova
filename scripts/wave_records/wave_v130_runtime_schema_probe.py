from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

TOKENS = (
    "correction_layer",
    "runtime_enabled",
    "model_payload",
    "feature_stats",
    "apply_correction",
    "evaluate_model",
    "membrane_model_hint",
    "membrane_family_hint",
)

NAME_TOKENS = (
    "correction",
    "model",
    "predict",
    "shadow",
    "apply",
    "feature",
    "scope",
)


def walk_models(value: Any):
    if isinstance(value, dict):
        if (
            value.get("metric")
            and (
                value.get("model_payload")
                or value.get("model_type")
                or value.get("runtime_enabled") is not None
            )
        ):
            yield value

        for child in value.values():
            yield from walk_models(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_models(child)


def inspect_existing_layer() -> None:
    layers = sorted(
        DATA_DIR.glob("*_v92_correction_layer.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    print("=" * 100)
    print("LATEST V92 CORRECTION LAYER")
    print("=" * 100)

    if not layers:
        print("status=NOT_FOUND")
        return

    path = layers[0]
    payload = json.loads(path.read_text(encoding="utf-8"))

    print(f"path={path}")
    print(f"top_level_type={type(payload).__name__}")

    if isinstance(payload, dict):
        print(f"top_level_keys={list(payload.keys())}")

    models = list(walk_models(payload))

    print(f"detected_model_count={len(models)}")

    for index, model in enumerate(models, start=1):
        print(f"\nMODEL_{index}")
        print(f"keys={list(model.keys())}")

        summary = {
            "model_id": model.get("model_id") or model.get("id"),
            "process_type": model.get("process_type"),
            "metric": model.get("metric"),
            "model_type": model.get("model_type"),
            "runtime_enabled": model.get("runtime_enabled"),
            "promotion_status": model.get("promotion_status"),
            "feature_names": model.get("feature_names"),
            "scope": model.get("scope"),
            "applicability": model.get("applicability"),
            "guards": model.get("guards"),
            "model_payload": model.get("model_payload"),
        }

        print(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            )
        )


def relevant_python_files() -> list[Path]:
    roots = [
        ROOT / "app",
        ROOT / "scripts/wave_records",
    ]

    matches = []

    for search_root in roots:
        if not search_root.exists():
            continue

        for path in search_root.rglob("*.py"):
            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            lowered = text.lower()

            if any(token in lowered for token in TOKENS):
                matches.append(path)

    return sorted(set(matches))


def inspect_source_file(path: Path) -> None:
    relative = path.relative_to(ROOT)

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        print(f"READ_FAIL {relative}: {exc}")
        return

    lines = text.splitlines()

    print("\n" + "=" * 100)
    print(f"SOURCE: {relative}")
    print("=" * 100)

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        print(f"AST_FAIL: {exc}")
        tree = None

    if tree is not None:
        definitions = []

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                name = node.name.lower()

                if any(token in name for token in NAME_TOKENS):
                    definitions.append(
                        (
                            node.lineno,
                            type(node).__name__,
                            node.name,
                        )
                    )

        if definitions:
            print("RELEVANT DEFINITIONS")

            for lineno, kind, name in sorted(definitions):
                print(f"  L{lineno}: {kind} {name}")

    hit_lines = []

    for lineno, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(token in lowered for token in TOKENS):
            hit_lines.append(lineno)

    print(f"token_hit_count={len(hit_lines)}")

    shown_ranges = []
    shown_hits = 0

    for hit in hit_lines:
        if shown_hits >= 12:
            break

        start = max(1, hit - 3)
        end = min(len(lines), hit + 4)

        if any(
            start <= prior_end and end >= prior_start
            for prior_start, prior_end in shown_ranges
        ):
            continue

        shown_ranges.append((start, end))
        shown_hits += 1

        print(f"\n--- lines {start}-{end} ---")

        for number in range(start, end + 1):
            print(f"{number:05d}: {lines[number - 1]}")


def main() -> int:
    inspect_existing_layer()

    files = relevant_python_files()

    print("\n" + "=" * 100)
    print("RELEVANT SOURCE FILES")
    print("=" * 100)
    print(f"file_count={len(files)}")

    for path in files:
        print(path.relative_to(ROOT))

    # 런타임과 직접 관련성이 높은 파일부터 제한적으로 출력한다.
    priority = []

    for path in files:
        relative = str(path.relative_to(ROOT)).lower()

        score = 0

        if "wave_v92" in relative:
            score += 100
        if "wave_v93" in relative:
            score += 90
        if "correction" in relative:
            score += 80
        if "calibration" in relative:
            score += 40
        if "runtime" in relative:
            score += 30

        priority.append((score, path))

    for _, path in sorted(
        priority,
        key=lambda item: (-item[0], str(item[1])),
    )[:12]:
        inspect_source_file(path)

    print("\nV130 runtime schema probe PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
