#!/usr/bin/env python3
"""Freeze the sole s5378 physical library compatibility translation."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from pact.physical.translate_netlist import translate_buf_x3_to_x4


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "artifacts/raw/tool_qualification/fan_atpg/benchmarks/s5378.v"
    output = root / "artifacts/derived/s5378/s5378_nangate45_compatible.v"
    record = translate_buf_x3_to_x4(source, output, expected_count=34)
    manifest = root / "artifacts/manifests/s5378_translation.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({
        **asdict(record),
        "source": str(source.relative_to(root)),
        "output": str(output.relative_to(root)),
        "reason": "FAN BUF_X3 is Boolean buffer; ORFS Nangate45 lacks it; BUF_X4 is an available Boolean buffer",
        "physical_impact": "Drive strength differs; use this one translated netlist for all architecture comparisons",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
