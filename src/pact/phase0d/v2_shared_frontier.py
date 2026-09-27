"""Optimizer-v2.1 shared-frontier sparse regret construction.

The final objectives are not used here.  All non-physical lanes consume one
bounded FF admission frontier, then choose independently from exact physical
insertion deltas and static activity-compatibility deltas. Candidate features
are cached across lanes while lane-local arc versions permit divergence.
"""
from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
import math
import random
import time
from typing import Iterable, Sequence

import numpy as np

from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility
from pact.phase0d.v2_architecture import INPUT, OUTPUT, MutableScanArchitecture
from pact.phase0d.v2_constructor_metrics import ConstructorStats
from pact.phase0d.v2_sparse import SparsePhysicalGraph, _AvailablePool
from pact.scan.model import ScanArchitecture


Arc = tuple[int, int, int]


def _lane_label(value: float) -> str:
    if value == 1.0:
        return "physical_greedy"
    if value == 0.0:
        return "activity_aware_greedy"
    return f"mixed_lambda_{value:.2f}"


@dataclass(frozen=True, slots=True)
class InsertionOpportunity:
    """One bounded, versioned insertion choice for an unassigned FF."""

    node: int
    chain: int
    predecessor: int
    successor: int
    physical_delta: float
    activity_delta: float
    score: float
    arc_version: int
    chain_generation: int

    @property
    def arc(self) -> Arc:
        return self.chain, self.predecessor, self.successor


class SharedInsertionFeatures:
    """Bounded cache of reusable exact/static insertion features."""

    def __init__(
        self,
        base: ScanArchitecture,
        physical: PhysicalCostModel,
        activity: TargetCompatibility,
        stats: ConstructorStats,
        *,
        candidate_cache_limit: int,
        activity_cache_limit: int,
    ) -> None:
        self.names = tuple(cell.name for cell in base.cells)
        self.coordinates = np.asarray(
            [physical.coordinates[name] for name in self.names], dtype=np.float64
        )
        self.input_ports = np.asarray(physical.input_ports, dtype=np.float64)
        self.output_ports = np.asarray(physical.output_ports, dtype=np.float64)
        self.scale = max(float(physical.scale_um), 1e-12)
        self.activity = activity
        self.stats = stats
        self.candidate_cache_limit = max(1, int(candidate_cache_limit))
        self.activity_cache_limit = max(1, int(activity_cache_limit))
        self._candidate_cache: dict[tuple[int, int, int, int], tuple[float, float, int]] = {}
        self._activity_cache: dict[tuple[int, int], float] = {}

    @staticmethod
    def _distance(left: np.ndarray, right: np.ndarray) -> float:
        return float(abs(left[0] - right[0]) + abs(left[1] - right[1]))

    def _relation(self, left: int, right: int) -> float:
        key = (int(left), int(right))
        self.stats.activity_heuristic_lookups += 1
        cached = self._activity_cache.get(key)
        if cached is not None:
            return cached
        value = float(self.activity.relation(self.names[left], self.names[right]))
        self.stats.activity_heuristic_computations += 1
        if len(self._activity_cache) >= self.activity_cache_limit:
            self._activity_cache.clear()
        self._activity_cache[key] = value
        self.stats.maximum_activity_cache_entries = max(
            self.stats.maximum_activity_cache_entries, len(self._activity_cache)
        )
        return value

    def _physical_delta(self, node: int, arc: Arc) -> float:
        chain, predecessor, successor = arc
        point = self.coordinates[node]
        left = self.input_ports[chain] if predecessor == INPUT else self.coordinates[predecessor]
        right = self.output_ports[chain] if successor == OUTPUT else self.coordinates[successor]
        return (
            self._distance(left, point)
            + self._distance(point, right)
            - self._distance(left, right)
        )

    def _activity_delta(self, node: int, predecessor: int, successor: int) -> float:
        value = 0.0
        if predecessor >= 0:
            value += self._relation(predecessor, node)
        if successor >= 0:
            value += self._relation(node, successor)
        if predecessor >= 0 and successor >= 0:
            value -= self._relation(predecessor, successor)
        return value

    def feature(self, node: int, arc: Arc, lane: int) -> tuple[float, float]:
        key = (int(node), *arc)
        cached = self._candidate_cache.get(key)
        if cached is not None:
            physical_delta, activity_delta, creator_lane = cached
            self.stats.shared_candidate_feature_hits += 1
            if creator_lane != lane:
                self.stats.repeated_equivalent_candidate_evaluations_across_lanes += 1
            return physical_delta, activity_delta
        physical_delta = self._physical_delta(node, arc)
        activity_delta = self._activity_delta(node, arc[1], arc[2])
        self.stats.physical_delta_computations += 1
        self.stats.candidate_feature_computations += 1
        if len(self._candidate_cache) >= self.candidate_cache_limit:
            self._candidate_cache.clear()
            self.stats.candidate_feature_cache_resets += 1
        self._candidate_cache[key] = (physical_delta, activity_delta, lane)
        self.stats.maximum_candidate_feature_cache_entries = max(
            self.stats.maximum_candidate_feature_cache_entries,
            len(self._candidate_cache),
        )
        return physical_delta, activity_delta

    def feature_batch(
        self,
        nodes: Sequence[int],
        arcs: Sequence[Arc],
        lanes: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the same features from compact structure-of-arrays inputs.

        Unique cache misses use one NumPy geometry kernel. Activity relations
        retain their exact Python-integer bit-count definition. Duplicate keys
        are replayed in request order so cache-hit instrumentation and creator
        lane semantics remain identical to repeated :meth:`feature` calls.
        """
        if not (len(nodes) == len(arcs) == len(lanes)):
            raise ValueError("Feature batch columns must have equal length")
        count = len(nodes)
        physical_result = np.empty(count, dtype=np.float64)
        activity_result = np.empty(count, dtype=np.float64)
        missing: dict[tuple[int, int, int, int], list[int]] = {}
        creators: dict[tuple[int, int, int, int], int] = {}
        for position, (raw_node, raw_arc, raw_lane) in enumerate(zip(nodes, arcs, lanes)):
            node = int(raw_node)
            arc = tuple(map(int, raw_arc))
            lane = int(raw_lane)
            key = (node, *arc)
            cached = self._candidate_cache.get(key)
            if cached is not None:
                physical_result[position], activity_result[position], creator_lane = cached
                self.stats.shared_candidate_feature_hits += 1
                if creator_lane != lane:
                    self.stats.repeated_equivalent_candidate_evaluations_across_lanes += 1
                continue
            positions = missing.setdefault(key, [])
            if positions:
                self.stats.shared_candidate_feature_hits += 1
                if creators[key] != lane:
                    self.stats.repeated_equivalent_candidate_evaluations_across_lanes += 1
            else:
                creators[key] = lane
            positions.append(position)

        keys = list(missing)
        if keys:
            node_array = np.asarray([key[0] for key in keys], dtype=np.int32)
            chain_array = np.asarray([key[1] for key in keys], dtype=np.int32)
            predecessor_array = np.asarray([key[2] for key in keys], dtype=np.int32)
            successor_array = np.asarray([key[3] for key in keys], dtype=np.int32)
            points = self.coordinates[node_array]
            left = np.empty((len(keys), 2), dtype=np.float64)
            right = np.empty((len(keys), 2), dtype=np.float64)
            input_mask = predecessor_array == INPUT
            output_mask = successor_array == OUTPUT
            left[input_mask] = self.input_ports[chain_array[input_mask]]
            left[~input_mask] = self.coordinates[predecessor_array[~input_mask]]
            right[output_mask] = self.output_ports[chain_array[output_mask]]
            right[~output_mask] = self.coordinates[successor_array[~output_mask]]
            physical_values = (
                np.abs(left - points).sum(axis=1)
                + np.abs(points - right).sum(axis=1)
                - np.abs(left - right).sum(axis=1)
            )
            for key, physical_delta in zip(keys, physical_values):
                node, _, predecessor, successor = key
                activity_delta = self._activity_delta(node, predecessor, successor)
                self.stats.physical_delta_computations += 1
                self.stats.candidate_feature_computations += 1
                if len(self._candidate_cache) >= self.candidate_cache_limit:
                    self._candidate_cache.clear()
                    self.stats.candidate_feature_cache_resets += 1
                value = (float(physical_delta), activity_delta, creators[key])
                self._candidate_cache[key] = value
                for position in missing[key]:
                    physical_result[position] = value[0]
                    activity_result[position] = value[1]
            self.stats.maximum_candidate_feature_cache_entries = max(
                self.stats.maximum_candidate_feature_cache_entries,
                len(self._candidate_cache),
            )
        return physical_result, activity_result


class _NodePool:
    """O(1) unassigned inventory with deterministic bounded sampling."""

    def __init__(self, size: int, salt: int) -> None:
        self.items = list(range(size))
        self.position = list(range(size))
        self.salt = int(salt)
        self.generation = 0

    def __len__(self) -> int:
        return len(self.items)

    def contains(self, node: int) -> bool:
        return self.position[int(node)] >= 0

    def remove(self, node: int) -> None:
        position = self.position[node]
        if position < 0:
            return
        last = self.items[-1]
        self.items[position] = last
        self.position[last] = position
        self.items.pop()
        self.position[node] = -1

    def sample(self, count: int) -> list[int]:
        count = min(int(count), len(self.items))
        if count <= 0:
            return []
        if count == len(self.items):
            return sorted(self.items)
        size = len(self.items)
        start = (self.salt * 0x9E3779B1 + self.generation * 0x85EBCA77) % size
        self.generation += 1
        stride = ((self.salt * 2 + self.generation * 2 + 1) % size) or 1
        while math.gcd(stride, size) != 1:
            stride = (stride + 2) % size or 1
        return [self.items[(start + offset * stride) % size] for offset in range(count)]


def _build_activity_neighbors(
    names: Sequence[str],
    activity: TargetCompatibility,
    seed: int,
    count: int,
    stats: ConstructorStats,
) -> np.ndarray:
    actual = min(max(1, int(count)), len(names) - 1)
    result = np.empty((len(names), actual), dtype=np.int32)
    rng = random.Random(seed ^ 0xA5A5A5A5)
    for node in range(len(names)):
        sample: set[int] = set()
        target = min(len(names) - 1, actual * 4)
        while len(sample) < target:
            candidate = rng.randrange(len(names))
            if candidate != node:
                sample.add(candidate)
        ranked: list[tuple[float, int]] = []
        for other in sample:
            stats.activity_heuristic_lookups += 1
            stats.activity_heuristic_computations += 1
            ranked.append((activity.relation(names[node], names[other]), other))
        ranked.sort()
        result[node] = [other for _, other in ranked[:actual]]
    return result


def _physical_anchor_orders(
    base: ScanArchitecture,
    graph: SparsePhysicalGraph,
    physical: PhysicalCostModel,
    activity_neighbors: np.ndarray,
    seed: int,
    stats: ConstructorStats,
) -> tuple[tuple[int, ...], ...]:
    """Reproduce the frozen v2 physical extreme without unused activity work."""
    names = tuple(cell.name for cell in base.cells)
    capacities = tuple(len(chain.cells) for chain in base.chains)
    coordinates = np.asarray(
        [physical.coordinates[name] for name in names], dtype=np.float64
    )
    available = _AvailablePool(len(names))
    groups: list[list[int]] = [[] for _ in capacities]
    for chain in range(len(capacities)):
        port = physical.input_ports[chain]
        stats.head_candidates_scored += len(available.items)
        node = min(available.items, key=lambda item: (
            abs(coordinates[item, 0] - port[0]) + abs(coordinates[item, 1] - port[1]),
            item,
        ))
        groups[chain].append(node)
        available.remove(node)
    rng = random.Random(seed + 1000)
    while len(available):
        for chain, capacity in enumerate(capacities):
            if len(groups[chain]) >= capacity:
                continue
            left = groups[chain][-1]
            local = [int(node) for node in graph.neighbors[left]
                     if available.available[int(node)]]
            activity_ranked = [int(node) for node in activity_neighbors[left]
                               if available.available[int(node)]]
            nonlocal_set = available.random_candidates(rng, 2)
            candidates = sorted(set(local + activity_ranked + nonlocal_set))
            if not candidates:
                candidates = [available.first()]
                stats.exhausted_frontier_fallbacks += 1
            stats.insertion_candidates_generated += len(candidates)
            stats.insertion_candidates_scored += len(candidates)
            stats.physical_delta_computations += len(candidates)
            stats.candidates_discarded += max(0, len(candidates) - 1)
            node = min(candidates, key=lambda right: (
                abs(coordinates[left, 0] - coordinates[right, 0])
                + abs(coordinates[left, 1] - coordinates[right, 1]),
                right,
            ))
            groups[chain].append(node)
            available.remove(node)
    stats.full_chain_traversals += len(groups)
    return tuple(tuple(group) for group in groups)


def _physical_anchor_job(
    base: ScanArchitecture,
    graph: SparsePhysicalGraph,
    physical: PhysicalCostModel,
    activity_neighbors: np.ndarray,
    seed: int,
) -> tuple[tuple[tuple[int, ...], ...], ConstructorStats]:
    """Pickle-safe branch entry point used by thread and process executors."""
    stats = ConstructorStats(mode="physical_anchor")
    started = time.perf_counter()
    orders = _physical_anchor_orders(
        base, graph, physical, activity_neighbors, seed, stats
    )
    elapsed = time.perf_counter() - started
    stats.total_seconds = elapsed
    stats.lane_seconds[_lane_label(1.0)] = elapsed
    return orders, stats


def _merge_stats(target: ConstructorStats, branch: ConstructorStats) -> None:
    """Merge deterministic work counts while leaving wall time to the caller."""
    for name in target.__dataclass_fields__:
        if name in {"mode", "total_seconds", "lane_seconds"}:
            continue
        setattr(target, name, getattr(target, name) + getattr(branch, name))
    for label, seconds in branch.lane_seconds.items():
        target.lane_seconds[label] = target.lane_seconds.get(label, 0.0) + seconds


@dataclass(slots=True)
class _SharedLaneState:
    lane: int
    weight: float
    label: str
    capacities: tuple[int, ...]
    groups: list[list[int]]
    versions: list[int]

    def eligible(self) -> list[int]:
        return sorted(
            (chain for chain, group in enumerate(self.groups)
             if len(group) < self.capacities[chain]),
            key=lambda chain: (-(self.capacities[chain] - len(self.groups[chain])), chain),
        )

    def valid(self, opportunity: InsertionOpportunity) -> bool:
        return (
            len(self.groups[opportunity.chain]) < self.capacities[opportunity.chain]
            and opportunity.arc_version == self.versions[opportunity.chain]
            and opportunity.predecessor == self.groups[opportunity.chain][-1]
            and opportunity.successor == OUTPUT
        )


@dataclass(slots=True)
class _SharedNodeRecord:
    node: int
    lane_opportunities: list[list[InsertionOpportunity]]
    priority: tuple[float, float, int]


def construct_architectures_v2_1(
    base: ScanArchitecture,
    graph: SparsePhysicalGraph,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    lambdas: Sequence[float] = (1.0, 0.75, 0.5, 0.25, 0.0),
    seed: int = 20260921,
    *,
    frontier_bound: int = 4,
    activity_candidates: int = 8,
    graph_neighbor_limit: int = 2,
    activity_neighbor_limit: int = 1,
    nonlocal_candidates: int = 1,
    parallel_backend: str = "sequential",
    vectorized_records: bool = False,
) -> tuple[list[tuple[str, MutableScanArchitecture]], ConstructorStats]:
    """Production shared sparse regret constructor with versioned tail arcs.

    All scalar lanes consume the same FF admission frontier and therefore share
    FF discovery, candidate identity, and cached feature extraction.  A chosen
    FF is inserted once into every lane, but each lane independently chooses
    its scalarized best legal tail arc.  The lane architectures consequently
    diverge without repeating the outer construction walk five times.
    """
    if len(base.cells) < 2:
        raise ValueError("Shared-frontier construction requires at least two FFs")
    if frontier_bound < 2:
        raise ValueError("Regret construction requires at least two frontier FFs")
    if any(not 0.0 <= float(value) <= 1.0 for value in lambdas):
        raise ValueError("Constructor lambdas must be in [0,1]")
    if parallel_backend not in {"sequential", "thread", "process"}:
        raise ValueError("Parallel backend must be sequential, thread, or process")
    capacities = tuple(len(chain.cells) for chain in base.chains)
    if any(capacity < 1 for capacity in capacities) or sum(capacities) != len(base.cells):
        raise ValueError("Base chain capacities must be nonempty and cover every FF")
    started = time.perf_counter()
    stats = ConstructorStats(mode="shared_frontier_sparse_regret")
    names = tuple(cell.name for cell in base.cells)
    activity_neighbors = _build_activity_neighbors(
        names, activity, seed, activity_candidates, stats
    )
    anchor_future: Future[tuple[tuple[tuple[int, ...], ...], ConstructorStats]] | None = None
    anchor_executor: ThreadPoolExecutor | ProcessPoolExecutor | None = None
    has_anchor = 1.0 in lambdas
    if has_anchor and parallel_backend != "sequential":
        executor_type = ThreadPoolExecutor if parallel_backend == "thread" else ProcessPoolExecutor
        anchor_executor = executor_type(max_workers=1)
        anchor_future = anchor_executor.submit(
            _physical_anchor_job,
            base,
            graph,
            physical,
            activity_neighbors,
            seed,
        )
    features = SharedInsertionFeatures(
        base, physical, activity, stats,
        candidate_cache_limit=max(1024, len(names) * 4),
        activity_cache_limit=max(1024, len(names) * 8),
    )
    coordinates = features.coordinates
    assigned = np.zeros(len(names), dtype=np.bool_)
    heads: list[int] = []
    lane_seconds = [0.0 for _ in lambdas]
    # A common physical seed makes the FF inventory shareable and preserves a
    # strong qualified-proxy anchor. Lambda-specific choices begin with the
    # first insertion; final objectives remain separate.
    for port in features.input_ports:
        distances = np.abs(coordinates - port).sum(axis=1)
        scores = distances / features.scale
        node = int(np.argmin(np.where(assigned, math.inf, scores)))
        assigned[node] = True
        heads.append(node)
        stats.head_candidates_scored += len(names) - int(assigned.sum()) + 1
    lanes: list[_SharedLaneState] = []
    for lane, weight in enumerate(map(float, lambdas)):
        lanes.append(_SharedLaneState(
            lane=lane,
            weight=weight,
            label=_lane_label(weight),
            capacities=capacities,
            groups=[[head] for head in heads],
            versions=[1] * len(capacities),
        ))
    available = _NodePool(len(names), seed ^ 0x51F15EED)
    for head in heads:
        available.remove(head)
    frontier: dict[int, _SharedNodeRecord] = {}

    def build_record(node: int) -> _SharedNodeRecord:
        lane_opportunities: list[list[InsertionOpportunity]] = [[] for _ in lanes]
        total_regret = 0.0
        total_best = 0.0
        requests: list[tuple[int, int, Arc]] = []
        for lane_index, lane in enumerate(lanes):
            for chain in lane.eligible()[:2]:
                arc = (chain, lane.groups[chain][-1], OUTPUT)
                requests.append((lane_index, chain, arc))

        if vectorized_records:
            physical_values, activity_values = features.feature_batch(
                [node] * len(requests),
                [arc for _, _, arc in requests],
                [lane_index for lane_index, _, _ in requests],
            )
        else:
            scalar = [
                features.feature(node, arc, lane_index)
                for lane_index, _, arc in requests
            ]
            physical_values = np.asarray([value[0] for value in scalar], dtype=np.float64)
            activity_values = np.asarray([value[1] for value in scalar], dtype=np.float64)

        for request_index, (lane_index, chain, arc) in enumerate(requests):
            lane = lanes[lane_index]
            physical_delta = float(physical_values[request_index])
            activity_delta = float(activity_values[request_index])
            score = (
                lane.weight * physical_delta / features.scale
                + (1.0 - lane.weight) * activity_delta
            )
            lane_opportunities[lane_index].append(InsertionOpportunity(
                node=node,
                chain=chain,
                predecessor=arc[1],
                successor=OUTPUT,
                physical_delta=physical_delta,
                activity_delta=activity_delta,
                score=score,
                arc_version=lane.versions[chain],
                chain_generation=0,
            ))
            stats.insertion_candidates_generated += 1
            stats.insertion_candidates_scored += 1
            stats.candidates_refreshed += 1

        for lane_index, lane in enumerate(lanes):
            lane_started = time.perf_counter()
            ranked = lane_opportunities[lane_index]
            ranked.sort(key=lambda item: (
                item.score, item.physical_delta, item.activity_delta,
                item.chain, item.node,
            ))
            if not ranked:
                raise AssertionError("No legal shared-frontier insertion remains")
            regret = 1e30 if len(ranked) == 1 else ranked[1].score - ranked[0].score
            total_regret += regret
            total_best += ranked[0].score
            lane_opportunities.append(ranked)
            lane_seconds[lane_index] += time.perf_counter() - lane_started
        stats.frontier_refreshes += 1
        return _SharedNodeRecord(node, lane_opportunities, (-total_regret, total_best, node))

    def admit(preferred: Iterable[int] = ()) -> None:
        target = min(frontier_bound, len(available))
        if len(frontier) >= target:
            return
        seen: set[int] = set()
        ordered: list[int] = []
        for raw in preferred:
            node = int(raw)
            if node not in seen and available.contains(node) and node not in frontier:
                seen.add(node)
                ordered.append(node)
        fallback = available.sample(max(
            nonlocal_candidates,
            target - len(frontier),
        ))
        for node in fallback:
            if node not in seen and available.contains(node) and node not in frontier:
                seen.add(node)
                ordered.append(node)
        for node in ordered:
            frontier[node] = build_record(node)
            if len(frontier) >= target:
                break
        stats.frontier_rebuilds += 1
        stats.maximum_frontier_entries = max(
            stats.maximum_frontier_entries,
            sum(len(entries) for record in frontier.values()
                for entries in record.lane_opportunities),
        )

    initial_preferred: list[int] = []
    for head in heads:
        initial_preferred.extend(map(int, graph.neighbors[head][:graph_neighbor_limit]))
        initial_preferred.extend(map(int, activity_neighbors[head][:activity_neighbor_limit]))
    admit(initial_preferred)
    while len(available):
        if not frontier:
            admit()
        record = min(frontier.values(), key=lambda item: item.priority)
        stale = sum(
            not lane.valid(opportunity)
            for lane, entries in zip(lanes, record.lane_opportunities)
            for opportunity in entries
        )
        if stale:
            stats.stale_candidates_rejected += stale
            stats.candidates_discarded += stale
            record = build_record(record.node)
            frontier[record.node] = record
        node = record.node
        frontier.pop(node)
        for lane_index, (lane, entries) in enumerate(zip(lanes, record.lane_opportunities)):
            lane_started = time.perf_counter()
            opportunity = entries[0]
            if not lane.valid(opportunity):
                raise AssertionError("Attempted to accept a stale shared-frontier entry")
            chain = opportunity.chain
            old_version = lane.versions[chain]
            lane.groups[chain].append(node)
            lane.versions[chain] += 1
            stats.candidates_invalidated += sum(
                candidate.chain == chain and candidate.arc_version == old_version
                for other in frontier.values()
                for candidate in other.lane_opportunities[lane_index]
            )
            stats.candidates_discarded += max(0, len(entries) - 1)
            stats.accepted_insertions += 1
            lane_seconds[lane_index] += time.perf_counter() - lane_started
        available.remove(node)
        preferred = list(map(int, graph.neighbors[node][:graph_neighbor_limit]))
        preferred.extend(map(int, activity_neighbors[node][:activity_neighbor_limit]))
        admit(preferred)
    results: list[tuple[str, MutableScanArchitecture]] = []
    for lane_index, lane in enumerate(lanes):
        lane_started = time.perf_counter()
        flat = [node for group in lane.groups for node in group]
        if sorted(flat) != list(range(len(names))):
            raise AssertionError("Constructed architecture dropped or duplicated an FF")
        if any(len(group) != capacity for group, capacity in zip(lane.groups, capacities)):
            raise AssertionError("Constructed chain capacity mismatch")
        stats.full_chain_traversals += len(lane.groups)
        orders = tuple(tuple(group) for group in lane.groups)
        results.append((lane.label, MutableScanArchitecture.from_orders(base, orders)))
        lane_seconds[lane_index] += time.perf_counter() - lane_started
        stats.lane_seconds[lane.label] = lane_seconds[lane_index]
    # Preserve one measured v2 physical extreme as a safety anchor.  The four
    # non-physical lanes still come from the shared regret frontier; this costs
    # one lightweight sparse walk, not five repeated scalar constructions.
    if has_anchor:
        anchor_index = list(map(float, lambdas)).index(1.0)
        if anchor_future is None:
            anchor_orders, anchor_stats = _physical_anchor_job(
                base, graph, physical, activity_neighbors, seed
            )
        else:
            anchor_orders, anchor_stats = anchor_future.result()
        if anchor_executor is not None:
            anchor_executor.shutdown(wait=True)
        results[anchor_index] = (
            _lane_label(1.0),
            MutableScanArchitecture.from_orders(base, anchor_orders),
        )
        _merge_stats(stats, anchor_stats)
        stats.lane_seconds[_lane_label(1.0)] = (
            lane_seconds[anchor_index] + anchor_stats.total_seconds
        )
    stats.total_seconds = time.perf_counter() - started
    return results, stats
