"""Keep the frozen FAN pattern and report counts tied to source FF inventory."""
from __future__ import annotations

from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.test.pattern_parser import parse_fan_pat


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_fan_benchmark_counts_match_reports():
    expected = {"s5378": (179, 117), "s9234": (211, 156), "s15850": (534, 133)}
    raw = ROOT / "artifacts/raw/tool_qualification/fan_atpg"
    for design, (ff_count, pattern_count) in expected.items():
        source = raw / f"benchmarks/{design}.v"
        report = (raw / f"reports/FAN_{design}.rpt").read_text(encoding="utf-8")
        log = (raw / f"{design}.atpg.log").read_text(encoding="utf-8")
        patterns = parse_fan_pat(raw / f"patterns/FAN_{design}.pat")
        reported = re.search(r"(?m)^#\s*#Patterns\s+(\d+)\s*$", report)
        assert reported is not None
        assert len(scan_ff_instances(source)) == ff_count
        assert len(patterns.patterns) == int(reported.group(1)) == pattern_count
        for command in ("set_fault_type saf", "set_static_compression on",
                        "set_dynamic_compression on", "set_X-Fill on"):
            assert command in log
