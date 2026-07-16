#!/usr/bin/env python3
from __future__ import annotations
import ast, json, shutil
from datetime import datetime
from pathlib import Path

TARGET = [
    "_canonical_temperature_mode",
    "_temperature_variant_suffix",
    "_choose_stable_global_temperature_mode",
    "_clone_case_for_global_temperature",
    "_settings_from_case",
    "_write_two_case_summary",
    "expand_cases_for_wave_global_temperature",
]

HEADER = Batch plan/case schema helpers extracted by V131.
