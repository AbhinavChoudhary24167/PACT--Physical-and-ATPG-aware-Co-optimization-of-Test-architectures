"""Sparse spatial graph and bounded scalable construction for Optimizer-v2."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time
from typing import Sequence

import numpy as np

try:
    from scipy.spatial import cKDTree as _KDTree
except ImportError:  # pragma: no cover - exercised only in the documented fallback environment
    _KDTree = None

from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility
from pact.phase0d.v2_architecture import MutableScanArchitecture
from pact.scan.model import ScanArchitecture


@dataclass(frozen=True)
class SparseGraphStats:
    construction_seconds: float
    directed_edge_count: int
    undirected_edge_count: int
    memory_bytes: int
    backend: str
    k: int


@dataclass(frozen=True)
class SparsePhysicalGraph:
    """Fixed-width k-nearest-neighbor graph with O(kN) storage."""

    neighbors: np.ndarray
    distances: np.ndarray
    stats: SparseGraphStats

    @classmethod
    def build(cls, coordinates: np.ndarray, k: int = 16) -> "SparsePhysicalGraph":
        coordinates = np.asarray(coordinates, dtype=np.float64)
        if coordinates.ndim != 2 or coordinates.shape[1] != 2 or len(coordinates) < 2:
            raise ValueError("At least two 2-D coordinates are required")
        if k < 1:
            raise ValueError("k must be positive")
        actual_k = min(int(k), len(coordinates) - 1)
        started = time.perf_counter()
        if _KDTree is not None:
            tree = _KDTree(coordinates)
            # Query the KD-tree in the authoritative Manhattan (p=1) metric,
            # then apply stable distance/node ordering for reproducibility.
            _, candidates = tree.query(coordinates, k=actual_k + 1, p=1, workers=1)
            candidates = np.atleast_2d(candidates)
            neighbors = np.empty((len(coordinates), actual_k), dtype=np.int32)
            distances = np.empty((len(coordinates), actual_k), dtype=np.float64)
            for node, row in enumerate(candidates):
                selected = np.asarray([int(value) for value in row if int(value) != node][:actual_k], dtype=np.int32)
                manhattan = np.abs(coordinates[selected] - coordinates[node]).sum(axis=1)
                order = np.lexsort((selected, manhattan))
                neighbors[node] = selected[order]
                distances[node] = manhattan[order]
            backend = "scipy.spatial.cKDTree_exact_manhattan"
        else:
            # Clean low-memory fallback: O(N^2) construction time, but only one
            # O(N) distance row and the O(kN) result are resident at once.
            neighbors = np.empty((len(coordinates), actual_k), dtype=np.int32)
            distances = np.empty((len(coordinates), actual_k), dtype=np.float64)
            for node in range(len(coordinates)):
                row = np.abs(coordinates - coordinates[node]).sum(axis=1)
                row[node] = math.inf
                selected = np.argpartition(row, actual_k - 1)[:actual_k]
                order = np.lexsort((selected, row[selected]))
                neighbors[node] = selected[order]
                distances[node] = row[selected][order]
            backend = "streaming_bruteforce_manhattan_fallback"
        elapsed = time.perf_counter() - started
        undirected = {
            (min(node, int(other)), max(node, int(other)))
            for node, row in enumerate(neighbors)
            for other in row
        }
        stats = SparseGraphStats(
            construction_seconds=elapsed,
            directed_edge_count=int(neighbors.size),
            undirected_edge_count=len(undirected),
            memory_bytes=int(neighbors.nbytes + distances.nbytes),
            backend=backend,
            k=actual_k,
        )
        return cls(neighbors, distances, stats)


class _AvailablePool:
    """O(1) membership, random choice and swap-delete removal."""

    def __init__(self, size: int) -> None:
        self.items = list(range(size))
        self.position = list(range(size))
        self.available = np.ones(size, dtype=np.bool_)
        self.cursor = 0

    def __len__(self) -> int:
        return len(self.items)

    def remove(self, node: int) -> None:
        position = self.position[node]
        last = self.items[-1]
        self.items[position] = last
        self.position[last] = position
        self.items.pop()
        self.position[node] = -1
        self.available[node] = False

    def random_candidates(self, rng: random.Random, count: int) -> list[int]:
        if not self.items or count <= 0:
            return []
        if count >= len(self.items):
            return list(self.items)
        result: set[int] = set()
        attempts = max(8, count * 4)
        for _ in range(attempts):
            result.add(self.items[rng.randrange(len(self.items))])
            if len(result) >= count:
                break
        return sorted(result)

    def first(self) -> int:
        if not self.items:
            raise IndexError("No unassigned FF remains")
        while self.cursor < len(self.available) and not self.available[self.cursor]:
            self.cursor += 1
        return self.cursor if self.cursor < len(self.available) else self.items[0]


def construct_orders(
    base: ScanArchitecture,
    graph: SparsePhysicalGraph,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    physical_weight: float,
    *,
    seed: int = 20260921,
    activity_candidates: int = 8,
    nonlocal_candidates: int = 2,
    activity_neighbors: np.ndarray | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Construct K capacity-preserving chains in O(N(k+a+r)) expected time.

    Scalarization is used only for diverse starts. Final objective evaluation is
    always separate. The candidate set includes spatial neighbors, activity-
    ranked random samples, and explicit nonlocal candidates, so the sparse graph
    guides but never constrains connectivity.
    """
    if not 0.0 <= physical_weight <= 1.0:
        raise ValueError("physical_weight must be in [0,1]")
    names = tuple(cell.name for cell in base.cells)
    name_to_index = {name: index for index, name in enumerate(names)}
    capacities = tuple(len(chain.cells) for chain in base.chains)
    if sum(capacities) != len(names):
        raise ValueError("Base chain capacities do not cover all cells")
    coordinates = np.asarray([(cell.x_um, cell.y_um) for cell in base.cells], dtype=np.float64)
    rng = random.Random(seed + round(physical_weight * 1000))
    available = _AvailablePool(len(names))
    groups: list[list[int]] = [[] for _ in capacities]
    scale = max(float(physical.scale_um), 1e-12)

    def relation(left: int, right: int) -> float:
        return activity.relation(names[left], names[right])

    def choose_head(chain: int) -> int:
        # K is normally small; this one O(KN) pass avoids a dense port graph.
        candidates = available.items
        port = physical.input_ports[chain]
        return min(candidates, key=lambda node: (
            physical_weight * (abs(coordinates[node, 0] - port[0])
                               + abs(coordinates[node, 1] - port[1])) / scale
            + (1.0 - physical_weight) * activity.hotspot_scores[names[node]],
            node,
        ))

    for chain in range(len(capacities)):
        node = choose_head(chain)
        groups[chain].append(node)
        available.remove(node)

    while len(available):
        progressed = False
        for chain, capacity in enumerate(capacities):
            if len(groups[chain]) >= capacity:
                continue
            progressed = True
            left = groups[chain][-1]
            local = [int(node) for node in graph.neighbors[left] if available.available[int(node)]]
            if activity_neighbors is None:
                sample = available.random_candidates(rng, max(activity_candidates * 4, nonlocal_candidates))
                activity_ranked = sorted(sample, key=lambda node: (relation(left, node), node))[:activity_candidates]
            else:
                activity_ranked = [int(node) for node in activity_neighbors[left]
                                   if available.available[int(node)]]
            nonlocal_set = available.random_candidates(rng, nonlocal_candidates)
            candidates = sorted(set(local + activity_ranked + nonlocal_set))
            if not candidates:
                candidates = [available.first()]
            node = min(candidates, key=lambda right: (
                physical_weight * physical.distance(
                    physical.coordinates[names[left]], physical.coordinates[names[right]]) / scale
                + (1.0 - physical_weight) * relation(left, right),
                right,
            ))
            groups[chain].append(node)
            available.remove(node)
        if not progressed:
            raise AssertionError("Constructor capacities exhausted before FF inventory")
    return tuple(tuple(group) for group in groups)


def construct_architectures_v2(
    base: ScanArchitecture,
    graph: SparsePhysicalGraph,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    lambdas: Sequence[float] = (1.0, 0.75, 0.5, 0.25, 0.0),
    seed: int = 20260921,
) -> list[tuple[str, MutableScanArchitecture]]:
    """Return physical, mixed-scalarized and activity-aware diverse starts."""
    names = tuple(cell.name for cell in base.cells)
    activity_count = 8
    activity_neighbors = np.empty((len(names), activity_count), dtype=np.int32)
    rng = random.Random(seed ^ 0xA5A5A5A5)
    for node in range(len(names)):
        sample: set[int] = set()
        target = min(len(names) - 1, activity_count * 4)
        while len(sample) < target:
            candidate = rng.randrange(len(names))
            if candidate != node:
                sample.add(candidate)
        ranked = sorted(
            sample,
            key=lambda other: (activity.relation(names[node], names[other]), other),
        )[:activity_count]
        if len(ranked) < activity_count:
            ranked.extend([ranked[-1]] * (activity_count - len(ranked)))
        activity_neighbors[node] = ranked
    results = []
    for value in lambdas:
        if value == 1.0:
            label = "physical_greedy"
        elif value == 0.0:
            label = "activity_aware_greedy"
        else:
            label = f"mixed_lambda_{value:.2f}"
        orders = construct_orders(
            base, graph, physical, activity, value, seed=seed,
            activity_candidates=activity_count,
            activity_neighbors=activity_neighbors,
        )
        results.append((label, MutableScanArchitecture.from_orders(base, orders)))
    return results
