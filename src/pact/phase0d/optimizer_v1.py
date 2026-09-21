"""PACT Optimizer v1: global construction and bounded large-neighborhood search.

The primary archive is two-dimensional for a fixed chain count: the qualified
port-aware scan HPWL proxy and exact H_eff8.  Parallel shift cycles are retained
as a report field, not treated as an objective when K and chain capacities are
fixed.

The construction activity relation in this module is deliberately named
``target_compatibility``.  It is not H_eff8.  Exact H_eff8 is a maximum over
cycle-aligned, spatially convolved, direct-sink-weighted toggle fields and does
not decompose into independent scan edges.  Target compatibility is only a
repair/construction ranking heuristic; every archived candidate is evaluated
with the existing exact Phase-0C activity implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import random
from typing import Any, Iterable, Mapping, Sequence

from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.phase0d_operators import OperatorConstraints, structural_proof


Point2D = tuple[float, float]


def dominates2(left: Sequence[float], right: Sequence[float]) -> bool:
    """Strict Pareto dominance for the two fixed-K primary objectives."""
    if len(left) != 2 or len(right) != 2:
        raise ValueError("Optimizer-v1 dominance requires two objectives")
    a, b = tuple(map(float, left)), tuple(map(float, right))
    if any(not math.isfinite(value) for value in a + b):
        raise ValueError("Objectives must be finite")
    return a[0] <= b[0] and a[1] <= b[1] and (a[0] < b[0] or a[1] < b[1])


def nondominated2(items: Iterable[Any], key=lambda value: value) -> list[Any]:
    values = list(items)
    points = [tuple(map(float, key(value))) for value in values]
    return [
        value for index, value in enumerate(values)
        if not any(dominates2(other, points[index]) for j, other in enumerate(points) if j != index)
    ]


@dataclass(frozen=True)
class Bounds2D:
    ideal: Point2D
    reference: Point2D

    def __post_init__(self) -> None:
        if any(low >= high for low, high in zip(self.ideal, self.reference)):
            raise ValueError("Every reference value must exceed its ideal")

    def normalize(self, point: Sequence[float]) -> Point2D:
        if len(point) != 2:
            raise ValueError("Expected two objectives")
        return tuple(
            (float(value) - low) / (high - low)
            for value, low, high in zip(point, self.ideal, self.reference)
        )  # type: ignore[return-value]


def freeze_bounds2(points: Iterable[Sequence[float]], margin_fraction: float = 0.25) -> Bounds2D:
    checked = [tuple(map(float, point)) for point in points]
    if not checked or any(len(point) != 2 for point in checked):
        raise ValueError("At least one two-objective point is required")
    ideal = tuple(min(point[index] for point in checked) for index in range(2))
    high = tuple(max(point[index] for point in checked) for index in range(2))
    reference = tuple(
        value + (value - low) * margin_fraction if value > low else value + max(abs(value) * 0.1, 1.0)
        for low, value in zip(ideal, high)
    )
    return Bounds2D(ideal, reference)  # type: ignore[arg-type]


def hypervolume2(points: Iterable[Sequence[float]], bounds: Bounds2D) -> float:
    """Exact normalized dominated area for a minimization front."""
    normalized = [bounds.normalize(point) for point in points]
    front = sorted(nondominated2(
        [point for point in normalized if point[0] < 1.0 and point[1] < 1.0]
    ))
    area = 0.0
    best_y = 1.0
    for index, (x, y) in enumerate(front):
        best_y = min(best_y, y)
        next_x = front[index + 1][0] if index + 1 < len(front) else 1.0
        if next_x > x:
            area += (next_x - x) * max(0.0, 1.0 - best_y)
    return area


class ParetoArchive2D:
    """Deterministic nondominated archive keyed by architecture hash."""

    def __init__(self, entries: Iterable[Mapping[str, Any]] = ()) -> None:
        self.entries: list[dict[str, Any]] = []
        for entry in entries:
            self.insert(dict(entry))

    def insert(self, entry: dict[str, Any]) -> bool:
        sha = str(entry["architecture_sha256"])
        point = tuple(map(float, entry["objectives"][:2]))
        if any(row["architecture_sha256"] == sha for row in self.entries):
            return False
        if any(dominates2(row["objectives"][:2], point) for row in self.entries):
            return False
        self.entries = [row for row in self.entries if not dominates2(point, row["objectives"][:2])]
        self.entries.append(entry)
        self.entries.sort(key=lambda row: (*map(float, row["objectives"][:2]), row["architecture_sha256"]))
        return True

    def hypervolume(self, bounds: Bounds2D) -> float:
        return hypervolume2((row["objectives"][:2] for row in self.entries), bounds)


@dataclass(frozen=True)
class PhysicalCostModel:
    """Exact decomposition of the frozen port-aware Manhattan HPWL proxy."""
    coordinates: Mapping[str, tuple[float, float]]
    input_ports: tuple[tuple[float, float], ...]
    output_ports: tuple[tuple[float, float], ...]
    scale_um: float

    @classmethod
    def from_architecture(cls, architecture: ScanArchitecture, frozen_def) -> "PhysicalCostModel":
        ports, dbu_per_um = frozen_def_ports(frozen_def, len(architecture.chains))
        inputs, outputs = [], []
        for ci in range(len(architecture.chains)):
            si = "test_si" if ci == 0 else f"test_si_{ci}"
            so = "test_so" if ci == 0 else f"test_so_{ci}"
            inputs.append(tuple(value / dbu_per_um for value in ports[si]))
            outputs.append(tuple(value / dbu_per_um for value in ports[so]))
        coordinates = {cell.name: (cell.x_um, cell.y_um) for cell in architecture.cells}
        xs, ys = zip(*coordinates.values())
        scale = (max(xs) - min(xs)) + (max(ys) - min(ys))
        return cls(coordinates, tuple(inputs), tuple(outputs), scale or 1.0)

    @staticmethod
    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    def chain_cost(self, chain_index: int, cells: Sequence[str]) -> float:
        if not cells:
            return self.distance(self.input_ports[chain_index], self.output_ports[chain_index])
        result = self.distance(self.input_ports[chain_index], self.coordinates[cells[0]])
        result += sum(
            self.distance(self.coordinates[left], self.coordinates[right])
            for left, right in zip(cells, cells[1:])
        )
        result += self.distance(self.coordinates[cells[-1]], self.output_ports[chain_index])
        return result

    def architecture_cost(self, architecture: ScanArchitecture) -> float:
        return sum(self.chain_cost(ci, chain.cells) for ci, chain in enumerate(architecture.chains))

    def insertion_delta(self, chain_index: int, cells: Sequence[str], position: int, name: str) -> float:
        if not 0 <= position <= len(cells):
            raise ValueError("Invalid insertion position")
        before = self.input_ports[chain_index] if position == 0 else self.coordinates[cells[position - 1]]
        after = self.output_ports[chain_index] if position == len(cells) else self.coordinates[cells[position]]
        point = self.coordinates[name]
        return self.distance(before, point) + self.distance(point, after) - self.distance(before, after)

    def replacement_delta(self, before: ScanArchitecture, after: ScanArchitecture) -> float:
        """Exact delta using only chains whose ordered cells changed."""
        if len(before.chains) != len(after.chains):
            raise ValueError("K changed")
        delta = 0.0
        for ci, (old, new) in enumerate(zip(before.chains, after.chains)):
            if old.cells != new.cells:
                delta += self.chain_cost(ci, new.cells) - self.chain_cost(ci, old.cells)
        return delta


class TargetCompatibility:
    """Sparse, on-demand ATPG target similarity used only to rank construction moves.

    For directed adjacency ``left -> right``, the relation is the fraction of
    frozen target patterns in which their target bits differ, multiplied by the
    right FF's direct-sink weight divided by the mean FF weight.  It is a static
    same-target relation and intentionally does not claim cycle alignment or
    equality with exact H_eff8.
    """

    def __init__(self, patterns: Sequence[Mapping[str, int]], weights: Mapping[str, int]) -> None:
        if not patterns:
            raise ValueError("Frozen ATPG patterns are required")
        names = tuple(sorted(weights))
        if any(set(pattern) != set(names) for pattern in patterns):
            raise ValueError("Pattern and weight FF sets differ")
        self.pattern_count = len(patterns)
        self.signatures = {
            name: sum(int(pattern[name]) << index for index, pattern in enumerate(patterns))
            for name in names
        }
        mean_weight = sum(weights.values()) / len(weights)
        self.normalized_weights = {name: weights[name] / mean_weight for name in names}
        self.hotspot_scores = {
            name: self.normalized_weights[name] * sum(
                patterns[index - 1][name] != patterns[index][name]
                for index in range(1, len(patterns))
            ) / max(1, len(patterns) - 1)
            for name in names
        }

    def relation(self, left: str, right: str) -> float:
        mismatch = (self.signatures[left] ^ self.signatures[right]).bit_count() / self.pattern_count
        return mismatch * self.normalized_weights[right]

    def chain_score(self, cells: Sequence[str]) -> float:
        return sum(self.relation(left, right) for left, right in zip(cells, cells[1:]))

    def insertion_delta(self, cells: Sequence[str], position: int, name: str) -> float:
        removed = self.relation(cells[position - 1], cells[position]) if 0 < position < len(cells) else 0.0
        added = self.relation(cells[position - 1], name) if position > 0 else 0.0
        added += self.relation(name, cells[position]) if position < len(cells) else 0.0
        return added - removed

    def architecture_score(self, architecture: ScanArchitecture) -> float:
        return sum(self.chain_score(chain.cells) for chain in architecture.chains)


CONSTRUCTION_SPECS = (
    ("physical", 1.00, False),
    ("mostly_physical", 0.80, False),
    ("balanced_regret", 0.50, True),
    ("mostly_activity", 0.20, False),
    ("activity", 0.00, False),
)


def balanced_capacities(cell_count: int, chain_count: int) -> tuple[int, ...]:
    if chain_count < 1 or cell_count < chain_count:
        raise ValueError("Invalid cell/chain count")
    return tuple(cell_count // chain_count + int(index < cell_count % chain_count)
                 for index in range(chain_count))


def _insertion_options(
    name: str,
    groups: Sequence[Sequence[str]],
    capacities: Sequence[int],
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    alpha: float,
) -> list[tuple[float, float, float, int, int]]:
    options = []
    for ci, group in enumerate(groups):
        if len(group) >= capacities[ci]:
            continue
        for position in range(len(group) + 1):
            physical_delta = physical.insertion_delta(ci, group, position, name)
            activity_delta = activity.insertion_delta(group, position, name)
            score = alpha * (physical_delta / physical.scale_um) + (1.0 - alpha) * activity_delta
            options.append((score, physical_delta, activity_delta, ci, position))
    return sorted(options)


def repair_groups(
    partial_groups: Sequence[Sequence[str]],
    removed: Iterable[str],
    capacities: Sequence[int],
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    alpha: float,
    *,
    regret: bool = False,
) -> list[list[str]]:
    """Balanced cheapest or regret insertion with deterministic tie breaking."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0,1]")
    groups = [list(group) for group in partial_groups]
    remaining = set(removed)
    if sum(map(len, groups)) + len(remaining) != sum(capacities):
        raise ValueError("Repair inventory/capacity mismatch")
    while remaining:
        ranked = []
        for name in sorted(remaining):
            options = _insertion_options(name, groups, capacities, physical, activity, alpha)
            if not options:
                raise ValueError("No feasible insertion")
            best = options[0]
            second = options[1][0] if len(options) > 1 else best[0]
            regret_value = second - best[0]
            ranked.append((-regret_value if regret else best[0], best[0], name, best))
        _, _, chosen, best = min(ranked)
        _, _, _, chain_index, position = best
        groups[chain_index].insert(position, chosen)
        remaining.remove(chosen)
    if tuple(map(len, groups)) != tuple(capacities):
        raise AssertionError("Repair did not restore exact capacities")
    return groups


def _architecture_from_groups(base: ScanArchitecture, groups: Sequence[Sequence[str]]) -> ScanArchitecture:
    return ScanArchitecture(
        base.cells,
        tuple(
            ScanChain(chain.chain_id, tuple(group), chain.scan_in, chain.scan_out)
            for chain, group in zip(base.chains, groups)
        ),
    )


def construct_architecture(
    base: ScanArchitecture,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    alpha: float,
    *,
    regret: bool = False,
) -> ScanArchitecture:
    """Build all K chains from empty routes under exact balanced capacities."""
    capacities = balanced_capacities(len(base.cells), len(base.chains))
    groups = repair_groups(
        [[] for _ in base.chains],
        (cell.name for cell in base.cells),
        capacities,
        physical,
        activity,
        alpha,
        regret=regret,
    )
    architecture = _architecture_from_groups(base, groups)
    structural_proof(base, architecture, (), OperatorConstraints())
    return architecture


LNS_DESTROY_OPERATORS = ("region", "hotspot", "segment", "cross_chain", "guided")
LNS_REPAIR_STRATEGIES = (
    ("physical_best", 1.0, False),
    ("balanced", 0.5, False),
    ("activity_best", 0.0, False),
    ("regret", 0.5, True),
)


def _removal_count(architecture: ScanArchitecture, fraction: float) -> int:
    if fraction not in {0.05, 0.10, 0.20}:
        raise ValueError("Optimizer-v1 neighborhood fractions are frozen to 5%, 10%, or 20%")
    return max(2, min(len(architecture.cells) - len(architecture.chains), round(len(architecture.cells) * fraction)))


def destroy(
    architecture: ScanArchitecture,
    operator: str,
    fraction: float,
    activity: TargetCompatibility,
    iteration: int,
    seed: int,
) -> tuple[list[list[str]], list[str]]:
    """Return partial chains and the deterministic FF removal set."""
    if operator not in LNS_DESTROY_OPERATORS:
        raise ValueError(f"Unknown destroy operator: {operator}")
    count = _removal_count(architecture, fraction)
    groups = [list(chain.cells) for chain in architecture.chains]
    flat = [name for group in groups for name in group]
    coords = {cell.name: (cell.x_um, cell.y_um) for cell in architecture.cells}
    material = json.dumps([architecture.sha256(), operator, fraction, iteration, seed], separators=(",", ":"))
    rng = random.Random(int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big"))

    if operator == "region":
        center = flat[rng.randrange(len(flat))]
        cx, cy = coords[center]
        removed = sorted(flat, key=lambda name: (
            abs(coords[name][0] - cx) + abs(coords[name][1] - cy), name
        ))[:count]
    elif operator == "hotspot":
        removed = sorted(flat, key=lambda name: (-activity.hotspot_scores[name], name))[:count]
    elif operator == "segment":
        chain_index = iteration % len(groups)
        group = groups[chain_index]
        take = min(count, max(1, len(group) - 8))
        start = rng.randrange(len(group) - take + 1)
        removed = group[start:start + take]
        if len(removed) < count:
            extras = [name for name in flat if name not in set(removed)]
            removed += extras[:count - len(removed)]
    elif operator == "cross_chain":
        removed = []
        per_chain = [count // len(groups) + int(ci < count % len(groups)) for ci in range(len(groups))]
        for ci, (group, take) in enumerate(zip(groups, per_chain)):
            take = min(take, max(1, len(group) - 8))
            start = (iteration * 7 + ci * 11) % (len(group) - take + 1)
            removed.extend(group[start:start + take])
        if len(removed) < count:
            extras = [name for name in flat if name not in set(removed)]
            removed.extend(extras[:count - len(removed)])
    else:
        pool_size = min(len(flat), max(count * 4, count))
        pool = sorted(flat, key=lambda name: (-activity.hotspot_scores[name], name))[:pool_size]
        removed = rng.sample(pool, count)

    removed = list(dict.fromkeys(removed))[:count]
    removed_set = set(removed)
    partial = [[name for name in group if name not in removed_set] for group in groups]
    if sum(map(len, partial)) + len(removed) != len(flat):
        raise AssertionError("Destroy inventory mismatch")
    return partial, removed


def lns_candidate(
    parent: ScanArchitecture,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    *,
    operator: str,
    fraction: float,
    repair_strategy: str,
    iteration: int,
    seed: int = 20260921,
) -> tuple[ScanArchitecture, dict[str, Any]]:
    strategies = {name: (alpha, regret) for name, alpha, regret in LNS_REPAIR_STRATEGIES}
    if repair_strategy not in strategies:
        raise ValueError(f"Unknown repair strategy: {repair_strategy}")
    partial, removed = destroy(parent, operator, fraction, activity, iteration, seed)
    alpha, regret = strategies[repair_strategy]
    capacities = tuple(len(chain.cells) for chain in parent.chains)
    groups = repair_groups(partial, removed, capacities, physical, activity, alpha, regret=regret)
    child = _architecture_from_groups(parent, groups)
    proof = structural_proof(parent, child, (), OperatorConstraints())
    if child.sha256() == parent.sha256():
        raise ValueError("LNS repair reproduced its parent")
    exact_delta = physical.replacement_delta(parent, child)
    record = {
        "schema_version": "pact-optimizer-v1-lns-move-1",
        "type": f"lns_{operator}_{repair_strategy}",
        "destroy_operator": operator,
        "repair_strategy": repair_strategy,
        "neighborhood_fraction": fraction,
        "removed_count": len(removed),
        "removed_FFs": removed,
        "parent_sha256": parent.sha256(),
        "child_sha256": child.sha256(),
        "incremental_physical_delta_um": exact_delta,
        "activity_ranking_metric": "static_direct_sink_weighted_target_compatibility_not_H_eff8",
        "activity_heuristic_parent": activity.architecture_score(parent),
        "activity_heuristic_child": activity.architecture_score(child),
        "legality": proof,
    }
    return child, record


def candidate_features(
    architecture: ScanArchitecture,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    move: Mapping[str, Any],
) -> dict[str, Any]:
    lengths = [len(chain.cells) for chain in architecture.chains]
    edge_lengths = []
    for chain in architecture.chains:
        edge_lengths.extend(
            physical.distance(physical.coordinates[left], physical.coordinates[right])
            for left, right in zip(chain.cells, chain.cells[1:])
        )
    return {
        "physical_descriptors": {
            "exact_proxy_from_decomposition_um": physical.architecture_cost(architecture),
            "mean_internal_edge_um": sum(edge_lengths) / len(edge_lengths),
            "max_internal_edge_um": max(edge_lengths),
        },
        "activity_descriptors": {
            "target_compatibility_score": activity.architecture_score(architecture),
            "definition": "static_direct_sink_weighted_target_compatibility_not_H_eff8",
        },
        "chain_descriptors": {
            "K": len(lengths), "lengths": lengths,
            "maximum_length_difference": max(lengths) - min(lengths),
        },
        "move_type": move.get("type"),
        "neighborhood_fraction": move.get("neighborhood_fraction", 1.0),
    }
