#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import json
import keyword
from datetime import datetime
from pathlib import Path

TARGET_FUNCTIONS = [
    "_canonical_temperature_mode",
    "_temperature_variant_suffix",
    "_clone_case_for_global_temperature",
    "expand_cases_for_wave_global_temperature",
]

IMPORT_MARKER_START = "# V131A_PLAN_SCHEMA_IMPORT_START"
IMPORT_MARKER_END = "# V131A_PLAN_SCHEMA_IMPORT_END"
PLAN_MARKER = "# V134C_PLAN_SCHEMA_CLUSTER_APPLIED"
MANIFEST_NAME = "v134c_plan_schema_cluster_extraction_manifest.json"

ALLOWED_EXTERNALS = set(dir(builtins)) | {
    "re", "os", "json", "csv", "math", "time", "datetime", "Path", "Counter",
    "defaultdict", "Any", "Dict", "List", "Tuple", "Set", "Optional", "Iterable",
    "Iterator", "Sequence", "Mapping", "MutableMapping", "Union",
    "None", "True", "False", "ROCaseConfig", "copy", "WaveAutomationError",
}

ERROR_BRIDGE =
