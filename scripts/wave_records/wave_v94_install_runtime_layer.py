#!/usr/bin/env python3
"""Install a reviewed V92 correction-layer JSON into AquaNova runtime config.

Default behavior is intentionally safe: the layer is copied to .data, but the
runtime config remains disabled.  Pass --enable only for a local opt-in test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    DEFAULT_LAYER_PATH,
    install_runtime_layer,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install V92 WAVE correction layer for V94 opt-in runtime use.")
    parser.add_argument("--correction-layer", required=True, help="V92 *_correction_layer.json")
    parser.add_argument("--layer-dest", default=DEFAULT_LAYER_PATH)
    parser.add_argument("--config-dest", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--enable", action="store_true", help="Write runtime config enabled=true. Default is disabled.")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    outputs = install_runtime_layer(
        args.correction_layer,
        layer_dest=args.layer_dest,
        config_dest=args.config_dest,
        enabled=bool(args.enable),
    )
    print("V94 runtime correction layer installed")
    print(f"layer: {Path(outputs['layer']).resolve()}")
    print(f"config: {Path(outputs['config']).resolve()}")
    if args.print_summary:
        cfg = json.loads(Path(outputs["config"]).read_text(encoding="utf-8"))
        print("summary=" + json.dumps({"enabled": cfg.get("enabled"), "layer": outputs["layer"], "config": outputs["config"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
