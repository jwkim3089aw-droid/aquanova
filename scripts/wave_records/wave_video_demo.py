#!/usr/bin/env python3
"""Compatibility entrypoint for the refactored WAVE automation package (V69)."""
from __future__ import annotations

from wave_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
