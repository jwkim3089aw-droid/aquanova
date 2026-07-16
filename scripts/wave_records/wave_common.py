#!/usr/bin/env python3
"""Shared types, constants, dependencies, and mutable application state for WAVE automation."""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from wave_ro_catalog import RO_UI_CATALOG, write_catalog_json
from wave_ro_excel import load_ro_cases
from wave_ro_schema import ROCaseConfig, ROPassConfig, ROStageConfig


class WaveAutomationError(RuntimeError):
    pass


class LibraryTemperatureTransitionError(WaveAutomationError):
    """Water Library copy was interrupted by WAVE's transient temperature validation."""


class WaveConvergenceError(WaveAutomationError):
    """WAVE explicitly reported that the current RO design failed to converge."""


# Make Win32 coordinates physical-pixel aware before importing pyautogui.
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

PYAUTOGUI_IMPORT_ERROR: Optional[BaseException] = None
try:
    import pyautogui
except Exception as exc:  # pragma: no cover - environment-specific dependency
    PYAUTOGUI_IMPORT_ERROR = exc

    class _PyAutoGUIUnavailable:
        class FailSafeException(RuntimeError):
            pass

        FAILSAFE = True
        PAUSE = 0.08

        def __getattr__(self, name: str) -> Any:
            raise WaveAutomationError(
                "pyautogui를 초기화하지 못했습니다. Windows PowerShell에서 "
                "'pip install pyautogui'를 확인하세요. "
                f"원인={PYAUTOGUI_IMPORT_ERROR!r}"
            )

    pyautogui = _PyAutoGUIUnavailable()  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR = RESULTS_DIR / "_automation_logs"
CALIBRATION_FILE = BASE_DIR / "wave_ui_calibration.json"
REFERENCE_WIDTH = 1280
REFERENCE_HEIGHT = 1032
CALIBRATION_VERSION = 15


@dataclass
class AppState:
    RUN_DIR: Optional[Path] = None
    EVENTS_FILE: Optional[Path] = None
    ACTIVE_WAVE_HWND: Optional[int] = None
    LAST_RUN_ARCHIVE: Optional[Path] = None
    DIAGNOSTIC_SEQUENCE: int = 0


STATE = AppState()


from wave_calibration_data import CALIBRATION_ORDER, CONTROL_FALLBACK_OFFSETS, DEFAULT_POINTS


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    process_path: str
    rect: Rect
    process_id: int = 0
    class_name: str = ""


@dataclass
class Settings:
    water_profile: str = "Well Water - Med Hardness"
    temperature_c: str = "25"
    feed_flow_m3h: str = "100"
    recovery_pct: str = "75"
    pv_per_stage: str = "10"
    elements_per_pv: str = "6"
    membrane: str = "BW30-400"
    add_ro: bool = False
    pause: float = 0.7
    long_wait: float = 4.0
    validate_pdf: bool = True


TWO_RO_CASES: tuple[dict[str, str], ...] = (
    {
        "case_id": "RO_CASE_001",
        "water_profile": "Well Water - Med Hardness",
        "temperature_c": "25",
        "feed_flow_m3h": "100",
        "recovery_pct": "75",
        "pv_per_stage": "10",
        "elements_per_pv": "6",
        "membrane": "BW30-400",
        "pdf_name": "RO_CASE_001_MedHardness_F100_R75_T25_BW30-400.pdf",
    },
    {
        "case_id": "RO_CASE_002",
        "water_profile": "Well Water - High Hardness",
        "temperature_c": "20",
        "feed_flow_m3h": "80",
        "recovery_pct": "65",
        "pv_per_stage": "10",
        "elements_per_pv": "6",
        "membrane": "BW30-400",
        "pdf_name": "RO_CASE_002_HighHardness_F80_R65_T20_BW30-400.pdf",
    },
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Rect):
        return {
            "left": value.left, "top": value.top, "right": value.right, "bottom": value.bottom,
            "width": value.width, "height": value.height,
        }
    if isinstance(value, WindowInfo):
        return {
            "hwnd": value.hwnd, "title": value.title, "process_path": value.process_path,
            "process_id": value.process_id, "class_name": value.class_name, "rect": _json_safe(value.rect),
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value


def _fmt_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


__all__ = [name for name in globals() if not name.startswith("__")]
