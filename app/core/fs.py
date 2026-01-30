# ./app/core/fs.py

from pathlib import Path
from app.core.config import settings

def ensure_dirs() -> None:
    Path(".data").mkdir(parents=True, exist_ok=True)
    Path(settings.REPORT_DIR_ABS).mkdir(parents=True, exist_ok=True)

def report_output_path(job_id: str) -> Path:
    return Path(settings.REPORT_DIR_ABS) / f"report_{job_id}.pdf"

def find_report_pdf(job_id: str) -> Path | None:
    candidates = [
        report_output_path(job_id),
        Path(settings.REPORT_DIR_ABS) / f"{job_id}.pdf",
        Path(settings.REPORT_DIR_ABS) / f"{job_id}.PDF",
        Path(settings.REPORT_DIR_ABS) / f"report_{job_id}.PDF"
    ]
    for c in candidates:
        if c.exists():
            return c
    return None