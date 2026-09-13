"""Prove FAN PPI identities against unchanged placed scan FF instances."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from pact.test.pattern_parser import FanPatternFile
from .validate import validate_ff_identity_map


@dataclass(frozen=True)
class ScanFFInstance:
    """Named scan FF and its relevant nets in a flat gate netlist."""

    name: str
    q_net: str
    d_net: str
    si_net: str
    clock_net: str


def scan_ff_instances(path: Path) -> tuple[ScanFFInstance, ...]:
    """Parse named SDFF_X1 instances and reject missing or ambiguous pins."""
    source = path.read_text(encoding="utf-8")
    records = []
    for match in re.finditer(r"\bSDFF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", source, re.DOTALL):
        name, body = match.group(1), match.group(2)
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", body))
        required = ("Q", "D", "SI", "CK")
        if any(pin not in pins for pin in required):
            raise ValueError(f"Scan FF {name} lacks required pins")
        records.append(ScanFFInstance(name, pins["Q"], pins["D"], pins["SI"], pins["CK"]))
    if not records or len({r.name for r in records}) != len(records):
        raise ValueError("No scan FFs or duplicate instance names")
    if len({r.q_net for r in records}) != len(records):
        raise ValueError("Ambiguous scan FF Q nets")
    return tuple(records)


def ff_identity_map(source: Path, placed: Path, patterns: FanPatternFile) -> list[dict[str, str]]:
    """Require PPI, source FF, and placed FF names/Q nets to match exactly."""
    originals = {record.name: record for record in scan_ff_instances(source)}
    physical = {record.name: record for record in scan_ff_instances(placed)}
    if set(originals) != set(physical) or set(originals) != set(patterns.pseudo_primary_inputs):
        raise ValueError("Source, physical, and ATPG FF sets differ")
    if any(originals[name].q_net != physical[name].q_net for name in originals):
        raise ValueError("Placed FF Q identity changed")
    records = [
        {
            "logical_ff": originals[name].q_net,
            "physical_instance": name,
            "atpg_signal": name,
            "clock_domain": originals[name].clock_net,
        }
        for name in patterns.pseudo_primary_inputs
    ]
    validate_ff_identity_map(records, physical.keys())
    return records


def supplied_scan_order(source: Path, scan_in: str = "test_si", scan_out: str = "test_so") -> tuple[str, ...]:
    """Reconstruct the upstream chain from each SDFF's actual SI and Q nets."""
    records = scan_ff_instances(source)
    by_si: dict[str, ScanFFInstance] = {}
    for record in records:
        if record.si_net in by_si:
            raise ValueError(f"Multiple FFs driven from scan net {record.si_net}")
        by_si[record.si_net] = record
    order = []
    net = scan_in
    while net in by_si:
        record = by_si[net]
        if record.name in order:
            raise ValueError("Scan chain contains a loop")
        order.append(record.name)
        net = record.q_net
    if len(order) != len(records):
        raise ValueError("Scan chain is disconnected")
    source_text = source.read_text(encoding="utf-8")
    endpoint = re.search(rf"\bassign\s+{re.escape(scan_out)}\s*=\s*([A-Za-z_][\w$]*)\s*;", source_text)
    if not endpoint or endpoint.group(1) != net:
        raise ValueError("Scan-out endpoint does not match terminal FF")
    return tuple(order)
