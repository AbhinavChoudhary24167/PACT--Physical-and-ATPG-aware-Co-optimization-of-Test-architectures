"""Exact serial loading of full-scan target states under explicit assumptions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


@dataclass(frozen=True)
class ShiftCycle:
    """Every cell's state before/after one parallel scan-shift clock."""

    pattern_index: int
    cycle_index: int
    before: dict[str, int]
    after: dict[str, int]
    toggles: dict[str, int]


@dataclass(frozen=True)
class ShiftTrace:
    """Reproducible trace plus the state assumption between patterns."""

    cycles: tuple[ShiftCycle, ...]
    between_pattern_state: str
    initial_state: dict[str, int]


def simulate_shift(
    architecture: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]],
    *,
    initial_state: Mapping[str, int] | None = None,
    between_pattern_state: str = "carry_loaded",
) -> ShiftTrace:
    """Shift scan-in bits tail-first so every chain reaches its logical target.

    With `carry_loaded`, the next pattern starts from the previous loaded state;
    capture effects are not modeled. With `reset_zero`, each pattern starts at
    zero. A measured capture-state stream is needed for physical power claims.
    """
    validate_scan(architecture)
    if between_pattern_state not in {"carry_loaded", "reset_zero"}:
        raise ValueError("Unsupported between-pattern state assumption")
    names = {c.name for c in architecture.cells}
    state = dict(initial_state) if initial_state is not None else {name: 0 for name in names}
    _validate_bits(state, names, "initial state")
    start_state = dict(sorted(state.items()))
    trace: list[ShiftCycle] = []
    for pattern_index, pattern in enumerate(patterns):
        _validate_bits(pattern, names, f"pattern {pattern_index}")
        if pattern_index > 0 and between_pattern_state == "reset_zero":
            state = {name: 0 for name in names}
        max_length = max(len(chain.cells) for chain in architecture.chains)
        for cycle_index in range(max_length):
            before = dict(sorted(state.items()))
            after = before.copy()
            for chain in architecture.chains:
                length = len(chain.cells)
                if cycle_index >= length:
                    continue
                scan_in_bit = pattern[chain.cells[length - 1 - cycle_index]]
                for index in range(length - 1, 0, -1):
                    after[chain.cells[index]] = before[chain.cells[index - 1]]
                after[chain.cells[0]] = scan_in_bit
            toggles = {name: before[name] ^ after[name] for name in sorted(names)}
            trace.append(ShiftCycle(pattern_index, cycle_index, before, after, toggles))
            state = after
        if state != dict(pattern):
            raise AssertionError("Serial scan loading did not reach target pattern")
    return ShiftTrace(tuple(trace), between_pattern_state, start_state)


def _validate_bits(bits: Mapping[str, int], expected: set[str], label: str) -> None:
    if set(bits) != expected:
        raise ValueError(f"{label} cell set mismatch: missing={sorted(expected - set(bits))}, extra={sorted(set(bits) - expected)}")
    if any(type(value) is not int or value not in (0, 1) for value in bits.values()):
        raise ValueError(f"{label} must contain only known binary values")
