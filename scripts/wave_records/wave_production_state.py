#!/usr/bin/env python3
"""Production manifest/checkpoint persistence helpers for WAVE automation."""
from __future__ import annotations

from wave_common import *
from wave_production_plan import PRODUCTION_AUTOMATION_VERSION


PRODUCTION_STATE_DIR = RESULTS_DIR / "_production_state"


def _default_checkpoint_path(plan_path: str | Path) -> Path:
    PRODUCTION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(plan_path).stem or "production_plan"
    return PRODUCTION_STATE_DIR / f"{stem}_checkpoint_v69.json"

def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "automation_version": PRODUCTION_AUTOMATION_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "items": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WaveAutomationError(f"Production checkpoint를 읽지 못했습니다: {path} ({exc!r})")
    if not isinstance(data, dict):
        raise WaveAutomationError(f"Production checkpoint 형식이 올바르지 않습니다: {path}")
    data.setdefault("items", {})
    return data

def _write_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["updated"] = datetime.now().isoformat(timespec="seconds")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(_json_safe(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)

def _write_manifest(manifest: dict[str, Any]) -> None:
    if STATE.RUN_DIR is None:
        return
    (STATE.RUN_DIR / "production_manifest_v69.json").write_text(
        json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def _checkpoint_status(checkpoint: dict[str, Any], key: str) -> str:
    item = checkpoint.get("items", {}).get(key, {})
    return str(item.get("status", ""))

def _mark_checkpoint_item(
    checkpoint: dict[str, Any],
    key: str,
    *,
    status: str,
    attempt: int,
    payload: dict[str, Any] | None = None,
) -> None:
    checkpoint.setdefault("items", {})[key] = {
        "status": status,
        "attempt": attempt,
        "updated": datetime.now().isoformat(timespec="seconds"),
        **(payload or {}),
    }

__all__ = [name for name in globals() if not name.startswith("__")]
