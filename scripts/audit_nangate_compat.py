#!/usr/bin/env python3
"""Record FAN s5378 physical-cell compatibility with pinned ORFS Nangate45."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pact.physical.netlist_compat import audit_masters


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    orfs = Path(os.environ["PACT_ORFS_ROOT"])
    platform = orfs / "flow/platforms/nangate45"
    result = audit_masters(
        root / "artifacts/raw/tool_qualification/fan_atpg/benchmarks/s5378.v",
        platform / "lib/NangateOpenCellLibrary_typical.lib",
        platform / "lef/NangateOpenCellLibrary.macro.mod.lef",
    )
    out = root / "artifacts/derived/s5378/nangate_compat.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
