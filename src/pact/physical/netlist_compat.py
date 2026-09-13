"""Audit gate-master compatibility without altering upstream netlists."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


def instance_masters(verilog: Path) -> Counter[str]:
    """Count simple named gate instances in FAN's flat generated Verilog."""
    source = verilog.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^\s*([A-Za-z_][\w$]*)\s+([A-Za-z_][\w$]*)\s*\(", source)
    return Counter(master for master, _ in matches if master not in {"module", "task", "function"})


def liberty_masters(liberty: Path) -> set[str]:
    """Read Liberty cell names from a single library file."""
    return set(re.findall(r"\bcell\s*\(\s*([A-Za-z_][\w$]*)\s*\)", liberty.read_text(encoding="utf-8")))


def lef_masters(lef: Path) -> set[str]:
    """Read LEF macro names from a single macro LEF file."""
    return set(re.findall(r"(?m)^MACRO\s+([A-Za-z_][\w$]*)\s*$", lef.read_text(encoding="utf-8")))


def audit_masters(verilog: Path, liberty: Path, lef: Path) -> dict[str, object]:
    """Report missing physical/timing masters and exact counts."""
    used = instance_masters(verilog)
    available_liberty = liberty_masters(liberty)
    available_lef = lef_masters(lef)
    return {
        "instance_count": sum(used.values()),
        "master_counts": dict(sorted(used.items())),
        "missing_liberty": {name: used[name] for name in sorted(used.keys() - available_liberty)},
        "missing_lef": {name: used[name] for name in sorted(used.keys() - available_lef)},
    }
