#!/usr/bin/env python3
"""Translate only the verified unavailable FAN buffer master for a design."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from pact.physical.translate_netlist import translate_buf_x3_to_x4


def main() -> None:
    """Freeze a cell-master-only compatibility translation and its source hash."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), required=True)
    design = parser.parse_args().design
    expected = {"s5378": 34, "s9234": 96}[design]
    root = Path(__file__).resolve().parents[1]
    source = root / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v"
    output = root / f"artifacts/derived/{design}/{design}_nangate45_compatible.v"
    record = translate_buf_x3_to_x4(source, output, expected_count=expected)
    manifest = root / f"artifacts/manifests/{design}_translation.json"
    manifest.write_text(json.dumps({
        **asdict(record), "source": str(source.relative_to(root)),
        "output": str(output.relative_to(root)),
        "reason": "FAN BUF_X3 is a Boolean buffer absent from ORFS Nangate45; BUF_X4 is available",
        "physical_impact": "Drive strength differs; use this one translated netlist for all architecture comparisons",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
