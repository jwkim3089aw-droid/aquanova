#!/usr/bin/env python3
"""Refactored WAVE automation module: runtime."""
from __future__ import annotations

from wave_common import *

def record_event(kind: str, **payload: Any) -> None:
    if STATE.EVENTS_FILE is None:
        return
    row = {
        "time": datetime.now().isoformat(timespec="milliseconds"),
        "kind": kind,
        **{key: _json_safe(value) for key, value in payload.items()},
    }
    try:
        with STATE.EVENTS_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def setup_logging() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    STATE.RUN_DIR = LOG_DIR / f"run_{stamp}"
    STATE.RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATE.EVENTS_FILE = STATE.RUN_DIR / "events.jsonl"
    STATE.DIAGNOSTIC_SEQUENCE = 0
    log_path = STATE.RUN_DIR / f"wave_demo_{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    try:
        source_dir = STATE.RUN_DIR / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        for source_path in sorted(BASE_DIR.glob("*.py")):
            shutil.copy2(source_path, source_dir / source_path.name)
        # Keep the historical single-file snapshot name for feedback tooling.
        shutil.copy2(
            BASE_DIR / "wave_video_demo.py",
            STATE.RUN_DIR / "wave_video_demo_source.py",
        )
        (STATE.RUN_DIR / "source_manifest.json").write_text(
            json.dumps(
                {
                    "automation_version": "V69",
                    "entrypoint": "wave_video_demo.py",
                    "modules": [p.name for p in sorted(source_dir.glob("*.py"))],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    record_event(
        "run_started", argv=sys.argv, python=sys.version, platform=platform.platform()
    )
    return log_path


def create_run_archive() -> Optional[Path]:
    """Pack the current run directory into a directly shareable ZIP.

    The unpacked run directory is intentionally retained for local inspection,
    while the sibling run_YYYYMMDD_HHMMSS.zip can be attached without any
    manual compression step.
    """
    if STATE.RUN_DIR is None:
        return None

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = LOG_DIR / f"{STATE.RUN_DIR.name}.zip"
    temp_path = archive_path.with_suffix(".zip.tmp")
    temp_path.unlink(missing_ok=True)

    record_event("run_archive_creating", path=archive_path)
    with zipfile.ZipFile(
        temp_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(STATE.RUN_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(STATE.RUN_DIR.parent))

    os.replace(temp_path, archive_path)
    STATE.LAST_RUN_ARCHIVE = archive_path
    logging.info("실행 폴더 ZIP 생성: %s", archive_path)
    record_event("run_archive_created", path=archive_path)
    return archive_path


def create_feedback_bundle(
    status: str, exc: Optional[BaseException] = None
) -> Optional[Path]:
    if STATE.RUN_DIR is None:
        return None
    summary = [
        f"status={status}",
        f"created={datetime.now().isoformat(timespec='seconds')}",
        f"python={sys.version}",
        f"platform={platform.platform()}",
        f"argv={sys.argv!r}",
    ]
    if exc is not None:
        summary += [
            f"exception={type(exc).__name__}: {exc}",
            "",
            traceback.format_exc(),
        ]
    (STATE.RUN_DIR / "feedback_summary.txt").write_text("\n".join(summary), encoding="utf-8")
    if CALIBRATION_FILE.exists():
        try:
            shutil.copy2(CALIBRATION_FILE, STATE.RUN_DIR / CALIBRATION_FILE.name)
        except Exception:
            pass

    # Always create the plain run_*.zip requested by the user first.
    # A second, status-labelled feedback ZIP is retained for compatibility.
    create_run_archive()

    bundle = LOG_DIR / f"WAVE_feedback_{STATE.RUN_DIR.name}_{status}.zip"
    temp_bundle = bundle.with_suffix(".zip.tmp")
    temp_bundle.unlink(missing_ok=True)
    with zipfile.ZipFile(
        temp_bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(STATE.RUN_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(STATE.RUN_DIR.parent))
    os.replace(temp_bundle, bundle)
    logging.info("피드백 번들 생성: %s", bundle)
    return bundle
