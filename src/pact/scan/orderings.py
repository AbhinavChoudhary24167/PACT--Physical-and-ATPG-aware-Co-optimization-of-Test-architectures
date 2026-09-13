"""Deterministic conventional baselines; no learned model."""
from __future__ import annotations

import random
from typing import Mapping, Sequence

import numpy as np

from .model import ScanArchitecture, ScanChain
from .validate import ScanConstraints, validate_scan


def _rebuild(base: ScanArchitecture, chains: list[ScanChain]) -> ScanArchitecture:
    result = ScanArchitecture(base.cells, tuple(chains))
    validate_scan(result, ScanConstraints(expected_chain_lengths=tuple(len(c.cells) for c in base.chains)))
    return result


def random_order(base: ScanArchitecture, seed: int) -> ScanArchitecture:
    """Permute each fixed chain's members with a saved seed."""
    validate_scan(base)
    rng = random.Random(seed)
    chains = []
    for chain in base.chains:
        members = sorted(chain.cells)
        rng.shuffle(members)
        chains.append(ScanChain(chain.chain_id, tuple(members), chain.scan_in, chain.scan_out))
    return _rebuild(base, chains)


def nearest_neighbor(base: ScanArchitecture) -> ScanArchitecture:
    """Start at lexicographically first FF and greedily minimize Manhattan distance."""
    validate_scan(base)
    by_name = {c.name: c for c in base.cells}
    chains = []
    for chain in base.chains:
        remaining = set(chain.cells)
        current = min(remaining)
        order = [current]
        remaining.remove(current)
        while remaining:
            here = by_name[current]
            current = min(remaining, key=lambda n: (abs(here.x_um - by_name[n].x_um) + abs(here.y_um - by_name[n].y_um), n))
            order.append(current)
            remaining.remove(current)
        chains.append(ScanChain(chain.chain_id, tuple(order), chain.scan_in, chain.scan_out))
    return _rebuild(base, chains)


def serpentine(base: ScanArchitecture, y_bins: int = 8) -> ScanArchitecture:
    """Sweep horizontal Y bins, alternating the X direction."""
    validate_scan(base)
    if y_bins < 1:
        raise ValueError("y_bins must be positive")
    by_name = {c.name: c for c in base.cells}
    chains = []
    for chain in base.chains:
        cells = [by_name[n] for n in chain.cells]
        ymin, ymax = min(c.y_um for c in cells), max(c.y_um for c in cells)
        def bin_index(y: float) -> int:
            return min(y_bins - 1, int((y - ymin) / (ymax - ymin) * y_bins)) if ymax > ymin else 0
        ordered = sorted(cells, key=lambda c: (bin_index(c.y_um), c.x_um if bin_index(c.y_um) % 2 == 0 else -c.x_um, c.name))
        chains.append(ScanChain(chain.chain_id, tuple(c.name for c in ordered), chain.scan_in, chain.scan_out))
    return _rebuild(base, chains)


def _activity_penalties(base: ScanArchitecture, patterns: Sequence[Mapping[str, int]]) -> dict[tuple[str, str], float]:
    names = sorted(c.name for c in base.cells)
    if not patterns:
        raise ValueError("Activity ordering requires validated ATPG patterns")
    if any(set(pattern) != set(names) or any(type(value) is not int or value not in (0, 1) for value in pattern.values()) for pattern in patterns):
        raise ValueError("Patterns must provide known bits for every scan FF")
    data = np.asarray([[pattern[name] for name in names] for pattern in patterns], dtype=float)
    centered = data - data.mean(axis=0)
    scale = np.sqrt((centered * centered).sum(axis=0))
    denominator = np.outer(scale, scale)
    correlation = np.divide(centered.T @ centered, denominator, out=np.zeros_like(denominator), where=denominator > 0)
    correlation = np.clip(correlation, -1.0, 1.0)
    return {(a, b): float((correlation[i, j] + 1) / 2) for i, a in enumerate(names) for j, b in enumerate(names) if a != b}


def _greedy_cost_order(base: ScanArchitecture, cost) -> ScanArchitecture:
    chains = []
    for chain in base.chains:
        remaining = set(chain.cells)
        current = min(remaining)
        order = [current]
        remaining.remove(current)
        while remaining:
            current = min(remaining, key=lambda name: (cost(order[-1], name), name))
            order.append(current)
            remaining.remove(current)
        chains.append(ScanChain(chain.chain_id, tuple(order), chain.scan_in, chain.scan_out))
    return _rebuild(base, chains)


def activity_only(base: ScanArchitecture, patterns: Sequence[Mapping[str, int]]) -> ScanArchitecture:
    """Greedily avoid positive PPI-bit correlation, without reading placement."""
    validate_scan(base)
    penalty = _activity_penalties(base, patterns)
    return _greedy_cost_order(base, lambda a, b: penalty[(a, b)])


def physical_activity(base: ScanArchitecture, patterns: Sequence[Mapping[str, int]], alpha: float) -> ScanArchitecture:
    """Greedy joint normalized Manhattan-distance/PPI-correlation baseline."""
    validate_scan(base)
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must lie in [0,1]")
    penalty = _activity_penalties(base, patterns)
    by_name = {c.name: c for c in base.cells}
    max_distance = max((abs(a.x_um - b.x_um) + abs(a.y_um - b.y_um) for a in base.cells for b in base.cells), default=0.0) or 1.0
    def cost(a: str, b: str) -> float:
        left, right = by_name[a], by_name[b]
        distance = (abs(left.x_um - right.x_um) + abs(left.y_um - right.y_um)) / max_distance
        return alpha * distance + (1 - alpha) * penalty[(a, b)]
    return _greedy_cost_order(base, cost)
