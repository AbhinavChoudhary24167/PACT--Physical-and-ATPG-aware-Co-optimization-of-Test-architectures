"""Deterministic multi-chain architectures and exact parallel-shift semantics.

Chain cells are ordered SI to SO. Every chain receives a clock on every one of
Lmax parallel shift cycles. Shorter chains receive leading zero padding; the
last len(chain) input bits, in reverse target order, establish the ATPG state.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence

from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import ScanConstraints, validate_scan


def chain_statistics(arch: ScanArchitecture, pattern_count: int) -> dict[str, object]:
    validate_scan(arch)
    lengths = [len(c.cells) for c in arch.chains]
    longest, shortest = max(lengths), min(lengths)
    return {
        "K": len(lengths), "chain_lengths": lengths, "Lmax": longest,
        "Lmin": shortest, "Lmean": sum(lengths) / len(lengths),
        "normalized_imbalance": (longest - shortest) / (sum(lengths) / len(lengths)),
        "parallel_shift_cycles": pattern_count * longest,
        "serial_shift_work": pattern_count * sum(lengths),
        "capture_cycles_if_one_per_pattern": pattern_count,
    }


def parallel_schedule(arch: ScanArchitecture, target: Mapping[str, int]) -> tuple[tuple[int, ...], ...]:
    """Return cycle-major SI bits, including real leading pad clocks."""
    validate_scan(arch)
    names = {cell.name for cell in arch.cells}
    if set(target) != names or any(type(v) is not int or v not in (0, 1) for v in target.values()):
        raise ValueError("Target must have exactly one known bit per scan FF")
    longest = max(len(c.cells) for c in arch.chains)
    streams = []
    for chain in arch.chains:
        sequence = [target[name] for name in reversed(chain.cells)]
        streams.append((0,) * (longest - len(chain.cells)) + tuple(sequence))
    return tuple(tuple(stream[cycle] for stream in streams) for cycle in range(longest))


def verify_parallel_schedule(arch: ScanArchitecture, target: Mapping[str, int],
                             initial: Mapping[str, int] | None = None) -> dict[str, object]:
    """Independent clock-by-clock state and scan-out verifier."""
    validate_scan(arch)
    names = {cell.name for cell in arch.cells}
    state = dict(initial) if initial is not None else dict.fromkeys(names, 0)
    if set(state) != names or any(type(v) is not int or v not in (0, 1) for v in state.values()):
        raise ValueError("Initial state must have exactly one known bit per scan FF")
    original = dict(state)
    observed = [[] for _ in arch.chains]
    for inputs in parallel_schedule(arch, target):
        previous = dict(state)
        for ci, (chain, bit) in enumerate(zip(arch.chains, inputs)):
            observed[ci].append(previous[chain.cells[-1]])
            state[chain.cells[0]] = bit
            for i in range(1, len(chain.cells)):
                state[chain.cells[i]] = previous[chain.cells[i - 1]]
    if state != dict(target):
        raise AssertionError("Parallel loading did not reconstruct ATPG target")
    for ci, chain in enumerate(arch.chains):
        expected = [original[name] for name in reversed(chain.cells)]
        if observed[ci][:len(chain.cells)] != expected:
            raise AssertionError("Scan-out traversal does not preserve initial state")
    return {"loaded_state_exact": True, "scan_out_traversal_exact": True,
            "clock_count": len(observed[0]), "scan_out": observed}


def _distance(a: str, b: str, cells: dict) -> float:
    x, y = cells[a], cells[b]
    return abs(x.x_um - y.x_um) + abs(x.y_um - y.y_um)


def _mismatch(patterns: Sequence[Mapping[str, int]], names: tuple[str, ...]) -> dict[tuple[str, str], float]:
    if not patterns:
        raise ValueError("Frozen ATPG patterns required")
    return {(a, b): sum(p[a] != p[b] for p in patterns) / len(patterns)
            for a in names for b in names if a != b}


def generate_architecture(base: ScanArchitecture, k: int, method: str,
                          patterns: Sequence[Mapping[str, int]], architecture_seed: int = 101) -> ScanArchitecture:
    """Generate balanced assignment and ordering without outcome-dependent tuning.

    B0 splits supplied order contiguously. P uses x-sorted balanced partitions
    and nearest-neighbor within each. A/J/T greedily extend balanced chains;
    A reads only ATPG bits, J uses a fixed normalized mix, and T minimizes a
    squared normalized edge-length risk proxy. R uses only its fixed seed.
    """
    validate_scan(base)
    n = len(base.cells)
    if k < 1 or k > n or n // k < 8:
        raise ValueError("Degenerate or impossible chain count")
    names = tuple(c.name for c in base.cells)
    capacities = [n // k + (i < n % k) for i in range(k)]
    source = tuple(name for chain in base.chains for name in chain.cells)
    coords = {c.name: c for c in base.cells}
    if method == "B0":
        groups, offset = [], 0
        for size in capacities:
            groups.append(list(source[offset:offset + size]))
            offset += size
    elif method == "R":
        shuffled = sorted(names)
        random.Random(architecture_seed).shuffle(shuffled)
        groups, offset = [], 0
        for size in capacities:
            groups.append(shuffled[offset:offset + size])
            offset += size
    elif method == "P":
        sorted_x = sorted(names, key=lambda name: (coords[name].x_um, coords[name].y_um, name))
        groups, offset = [], 0
        for size in capacities:
            members = set(sorted_x[offset:offset + size])
            offset += size
            current = min(members, key=lambda name: (coords[name].x_um + coords[name].y_um, name))
            ordered = [current]
            members.remove(current)
            while members:
                current = min(members, key=lambda name: (_distance(ordered[-1], name, coords), name))
                ordered.append(current)
                members.remove(current)
            groups.append(ordered)
    elif method in {"A", "J25", "J50", "J75", "T"}:
        mismatch = _mismatch(patterns, names) if method != "T" else {}
        extent = max(coords[c].x_um for c in names) - min(coords[c].x_um for c in names)
        extent += max(coords[c].y_um for c in names) - min(coords[c].y_um for c in names)
        extent = extent or 1.0
        alpha = {"A": 0.0, "J25": 0.25, "J50": 0.5, "J75": 0.75, "T": 1.0}[method]
        remaining = set(names)
        starts = sorted(names, key=lambda name: (coords[name].x_um, coords[name].y_um, name)) if method != "A" else sorted(names)
        groups = []
        for j in range(k):
            index = min(len(starts) - 1, j * len(starts) // k)
            seed = next((name for name in starts[index:] + starts[:index] if name in remaining), None)
            assert seed is not None
            groups.append([seed])
            remaining.remove(seed)
        while remaining:
            candidates = []
            for j, group in enumerate(groups):
                if len(group) >= capacities[j]:
                    continue
                tail = group[-1]
                for name in remaining:
                    d = _distance(tail, name, coords) / extent
                    cost = d * d if method == "T" else alpha * d + (1 - alpha) * mismatch[(tail, name)]
                    candidates.append((cost, j, name))
            _, j, chosen = min(candidates)
            groups[j].append(chosen)
            remaining.remove(chosen)
    else:
        raise ValueError(f"Unknown architecture family: {method}")
    chains = tuple(ScanChain(f"C{i:02d}", tuple(group), f"test_si_{i}", f"test_so_{i}")
                   for i, group in enumerate(groups))
    result = ScanArchitecture(base.cells, chains)
    validate_scan(result, ScanConstraints(expected_chain_lengths=tuple(capacities)))
    return result


def experiment_id(design: str, physical_seed: int, k: int, method: str,
                  architecture_sha256: str, contract_sha256: str) -> str:
    data = ["PACT_PHASE0C", design, physical_seed, k, method, architecture_sha256, contract_sha256]
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def architecture_space_log10(n: int, k: int) -> float:
    """Ordered labelled nonempty chains: n! * binomial(n-1,k-1)."""
    if not 1 <= k <= n:
        raise ValueError("Invalid N or K")
    return (math.lgamma(n + 1) + math.lgamma(n) - math.lgamma(k)
            - math.lgamma(n - k + 1)) / math.log(10)
