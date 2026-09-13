#!/usr/bin/env python3
"""Record FAN benchmark cell compatibility with pinned ORFS Nangate45."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pact.physical.netlist_compat import audit_masters


def main() -> None:
    """Audit one supported FAN benchmark without changing its source."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), default="s5378")
    design = parser.parse_args().design
    root = Path(__file__).resolve().parents[1]
    orfs = Path(os.environ["PACT_ORFS_ROOT"])
    platform = orfs / "flow/platforms/nangate45"
    result = audit_masters(
        root / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v",
        platform / "lib/NangateOpenCellLibrary_typical.lib",
        platform / "lef/NangateOpenCellLibrary.macro.mod.lef",
    )
    out = root / f"artifacts/derived/{design}/nangate_compat.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
