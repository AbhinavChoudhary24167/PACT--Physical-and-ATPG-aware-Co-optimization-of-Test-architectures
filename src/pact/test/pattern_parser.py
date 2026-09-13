"""Parser for observed FAN_ATPG 2023 BASIC_SCAN .pat output."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from pact.scan.validate import validate_ff_identity_map


@dataclass(frozen=True)
class FanPattern:
    """Seven .pat vector fields in upstream writer order."""

    pi1: str
    pi2: str
    ppi: str
    scan_in: str
    po1: str
    po2: str
    ppo: str


@dataclass(frozen=True)
class FanPatternFile:
    """Ordered named FAN primary and pseudo-primary signals."""

    primary_inputs: tuple[str, ...]
    pseudo_primary_inputs: tuple[str, ...]
    primary_outputs: tuple[str, ...]
    pattern_type: str
    patterns: tuple[FanPattern, ...]


def parse_fan_pat(path: Path) -> FanPatternFile:
    """Parse actual FAN .pat syntax and reject ambiguous field widths.

    The upstream writer defines PI1|PI2|PPI|SI|PO1|PO2|PPO. Only BASIC_SCAN
    is accepted for Phase 0. X values are retained but cannot be shifted until
    a documented fill is applied.
    """
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 5:
        raise ValueError("FAN pattern file is truncated")
    pi = tuple(lines[0].removesuffix("|").split())
    ppi = tuple(lines[1].removesuffix("|").split())
    po = tuple(lines[2].split())
    if any(len(signals) != len(set(signals)) for signals in (pi, ppi, po)):
        raise ValueError("Duplicate FAN signal header names")
    if lines[3] != "BASIC_SCAN":
        raise ValueError(f"Unsupported FAN pattern type: {lines[3]}")
    count_match = re.fullmatch(r"_num_of_pattern_(\d+)", lines[4])
    if not count_match:
        raise ValueError("Missing FAN pattern count")
    count = int(count_match.group(1))
    patterns: list[FanPattern] = []
    for index, line in enumerate(lines[5:], 1):
        match = re.fullmatch(r"_pattern_(\d+)\s+(.+)", line)
        if not match or int(match.group(1)) != index:
            raise ValueError(f"Nonconsecutive FAN pattern number at {index}")
        fields = [field.strip() for field in match.group(2).split("|")]
        if len(fields) != 7:
            raise ValueError(f"FAN pattern {index} requires seven fields")
        record = FanPattern(*fields)
        for name, value, required in (
            ("PI1", record.pi1, len(pi)), ("PPI", record.ppi, len(ppi)),
            ("PO1", record.po1, len(po)), ("PPO", record.ppo, len(ppi)),
        ):
            if len(value) != required:
                raise ValueError(f"Pattern {index} {name} width {len(value)} != {required}")
        for name, value, width in (("PI2", record.pi2, len(pi)), ("PO2", record.po2, len(po))):
            if value and len(value) != width:
                raise ValueError(f"Pattern {index} {name} width mismatch")
        if any(set(value) - {"0", "1", "X"} for value in fields):
            raise ValueError(f"Invalid logic symbol in pattern {index}")
        patterns.append(record)
    if len(patterns) != count:
        raise ValueError(f"FAN header count {count} != observed {len(patterns)}")
    return FanPatternFile(pi, ppi, po, "BASIC_SCAN", tuple(patterns))


def map_ppi_patterns(patterns: FanPatternFile, ff_map: Iterable[dict[str, str]]) -> list[dict[str, int]]:
    """Map ordered PPI bits to physical FFs using a verified bijection."""
    records = list(ff_map)
    validate_ff_identity_map(records)
    by_atpg = {r["atpg_signal"]: r["physical_instance"] for r in records}
    if set(by_atpg) != set(patterns.pseudo_primary_inputs):
        raise ValueError("FAN PPI names and FF map differ")
    mapped = []
    for index, record in enumerate(patterns.patterns):
        if set(record.ppi) - {"0", "1"}:
            raise ValueError(f"Unknown PPI bit in pattern {index}; explicit X-fill required")
        mapped.append({by_atpg[name]: int(bit) for name, bit in zip(patterns.pseudo_primary_inputs, record.ppi)})
    return mapped
