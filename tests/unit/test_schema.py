from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate


def test_json_schema() -> None:
    schema = json.loads((Path(__file__).parents[2] / "config/schemas/result.schema.json").read_text(encoding="utf-8"))
    record = {
        "schema_version": "0.1", "design": "pact_sanity", "platform": "sky130hd", "seed": 11,
        "method": "nearest_neighbor", "architecture_sha256": "0" * 64,
        "tool_versions": {"openroad": None, "yosys": None, "fan_atpg": None},
        "scan": {"num_cells": 4, "num_chains": 1, "total_hpwl_um": 6.0, "mean_edge_um": 2.0, "max_edge_um": 3.0},
        "test": {"fault_model": "stuck_at", "fault_coverage_pct": None, "pattern_count": 0, "total_shift_toggles": 0, "peak_simultaneous_toggles": 0, "p99_simultaneous_toggles": 0.0, "peak_local_activity": 0.0},
        "physical": {"wns_ns": None, "tns_ns": None, "congestion_metric": None, "drv_count": None, "routed_wirelength_um": None},
        "pdn": {"classification": "NOT_RUN", "worst_drop_v": None}, "runtime_s": 0.0,
        "status": "BLOCKED", "evidence": ["artifacts/raw/tool_qualification/environment/system.txt"],
    }
    validate(instance=record, schema=schema)
