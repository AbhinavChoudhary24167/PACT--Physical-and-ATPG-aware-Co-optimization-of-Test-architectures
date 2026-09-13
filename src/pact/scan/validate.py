"""Strong legality and identity checks for scan transformations."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Iterable

from .model import ScanArchitecture


@dataclass(frozen=True)
class ScanConstraints:
    """Fixed chain topology and optional physical restrictions."""

    min_chain_length: int = 1
    max_chain_length: int | None = None
    expected_chain_lengths: tuple[int, ...] | None = None
    enforce_clock_domain: bool = True
    allowed_scan_in: frozenset[str] | None = None
    allowed_scan_out: frozenset[str] | None = None


def validate_scan(architecture: ScanArchitecture, constraints: ScanConstraints = ScanConstraints()) -> None:
    """Raise ValueError on duplicate, missing, invalid, or illegal scan cells."""
    if not architecture.cells or not architecture.chains:
        raise ValueError("Architecture requires cells and chains")
    names = [c.name for c in architecture.cells]
    if any(not n for n in names):
        raise ValueError("Scan cell name cannot be empty")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate scan cell definitions")
    for cell in architecture.cells:
        if not all(math.isfinite(v) for v in (cell.x_um, cell.y_um)):
            raise ValueError(f"Non-finite placement for {cell.name}")
        if not cell.clock_domain:
            raise ValueError(f"Missing clock domain for {cell.name}")
    chain_ids = [c.chain_id for c in architecture.chains]
    if any(not c for c in chain_ids) or len(chain_ids) != len(set(chain_ids)):
        raise ValueError("Missing or duplicate chain IDs")
    visited = [n for chain in architecture.chains for n in chain.cells]
    counts = Counter(visited)
    repeated = sorted(n for n, count in counts.items() if count != 1)
    if repeated:
        raise ValueError(f"Duplicate scan cells in chains: {repeated}")
    unknown = sorted(set(visited) - set(names))
    missing = sorted(set(names) - set(visited))
    if unknown or missing:
        raise ValueError(f"Unknown cells: {unknown}; missing cells: {missing}")
    by_name = {c.name: c for c in architecture.cells}
    lengths = []
    ports: list[str] = []
    for chain in architecture.chains:
        length = len(chain.cells)
        lengths.append(length)
        if length < constraints.min_chain_length or (constraints.max_chain_length is not None and length > constraints.max_chain_length):
            raise ValueError(f"Illegal length for {chain.chain_id}: {length}")
        if constraints.enforce_clock_domain and len({by_name[n].clock_domain for n in chain.cells}) != 1:
            raise ValueError(f"Mixed clock domains in {chain.chain_id}")
        if chain.scan_in is not None:
            if not chain.scan_in or (constraints.allowed_scan_in is not None and chain.scan_in not in constraints.allowed_scan_in):
                raise ValueError(f"Invalid scan-in endpoint for {chain.chain_id}")
            ports.append(chain.scan_in)
        if chain.scan_out is not None:
            if not chain.scan_out or (constraints.allowed_scan_out is not None and chain.scan_out not in constraints.allowed_scan_out):
                raise ValueError(f"Invalid scan-out endpoint for {chain.chain_id}")
            ports.append(chain.scan_out)
    if len(ports) != len(set(ports)):
        raise ValueError("Scan endpoints must be unique")
    if constraints.expected_chain_lengths is not None and tuple(sorted(lengths)) != tuple(sorted(constraints.expected_chain_lengths)):
        raise ValueError("Chain lengths differ from fixed experiment")


def validate_ff_identity_map(records: Iterable[dict[str, str]], physical_cells: Iterable[str] | None = None) -> None:
    """Require bijective logical, physical, and ATPG FF identities."""
    records = list(records)
    if not records:
        raise ValueError("FF identity map is empty")
    fields = ("logical_ff", "physical_instance", "atpg_signal", "clock_domain")
    for record in records:
        if any(not isinstance(record.get(field), str) or not record[field] for field in fields):
            raise ValueError("Incomplete FF identity record")
    for field in fields[:3]:
        values = [r[field] for r in records]
        if len(values) != len(set(values)):
            raise ValueError(f"Ambiguous FF identity: {field}")
    if physical_cells is not None and set(r["physical_instance"] for r in records) != set(physical_cells):
        raise ValueError("FF identity map does not match physical FF set")
