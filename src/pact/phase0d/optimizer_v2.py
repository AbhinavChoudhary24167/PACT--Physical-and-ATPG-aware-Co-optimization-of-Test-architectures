"""PACT Optimizer-v2: sparse, incremental, bounded multi-objective search."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, field
import math
import random
import time
import tracemalloc
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility, dominates2
from pact.phase0d.v2_activity import HEffCandidate, HEffState, IncrementalHEff8
from pact.phase0d.v2_architecture import (
    ArchitecturePatch,
    ArchitectureSnapshot,
    MutableScanArchitecture,
    NONE,
)
from pact.phase0d.v2_sparse import SparsePhysicalGraph, construct_architectures_v2
from pact.scan.model import ScanArchitecture


Point2D = tuple[float, float]


@dataclass(frozen=True)
class OptimizerV2Config:
    """Every termination and growth dimension is explicit and bounded."""

    wall_clock_seconds: float = 30.0
    maximum_exact_evaluations: int = 64
    maximum_local_moves: int = 256
    maximum_archive_size: int = 24
    maximum_neighborhood_size: int = 32
    graph_k: int = 16
    activity_candidates: int = 6
    random_nonlocal_candidates: int = 3
    maximum_segment_length: int = 8
    minimum_chain_length: int = 1
    maximum_chain_length_difference: int = 1
    archive_epsilon_fraction: float = 0.01
    parent_refresh_interval: int = 16
    seen_cache_size: int = 4096
    seed: int = 20260921
    constructor_lambdas: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25, 0.0)

    def __post_init__(self) -> None:
        positive = (
            self.wall_clock_seconds,
            self.maximum_exact_evaluations,
            self.maximum_local_moves,
            self.maximum_archive_size,
            self.maximum_neighborhood_size,
            self.graph_k,
            self.maximum_segment_length,
            self.minimum_chain_length,
            self.seen_cache_size,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("Optimizer-v2 budgets and sizes must be positive")
        if self.maximum_archive_size < 2:
            raise ValueError("Archive must preserve two objective extremes")
        if not 0.0 <= self.archive_epsilon_fraction < 1.0:
            raise ValueError("Invalid archive epsilon fraction")
        if any(not 0.0 <= value <= 1.0 for value in self.constructor_lambdas):
            raise ValueError("Constructor lambdas must be in [0,1]")


@dataclass
class V2Counters:
    candidates_considered: int = 0
    candidates_accepted: int = 0
    candidates_dominated: int = 0
    candidates_pruned_archive_size: int = 0
    duplicate_candidates: int = 0
    invalid_moves: int = 0
    local_moves_attempted: int = 0
    local_moves_accepted: int = 0
    exact_evaluations: int = 0
    incremental_physical_evaluations: int = 0
    screened_move_options: int = 0
    full_physical_recomputations: int = 0
    incremental_h_eff8_evaluations: int = 0
    full_h_eff8_recomputations: int = 0
    complete_architecture_copies: int = 0
    parent_restarts: int = 0
    cache_evictions: int = 0
    neighborhood_total: int = 0
    neighborhood_samples: int = 0


class PhysicalArcCost:
    """Integer-indexed exact decomposition of the qualified physical proxy."""

    def __init__(self, architecture: ScanArchitecture, model: PhysicalCostModel) -> None:
        self.names = tuple(cell.name for cell in architecture.cells)
        self.coordinates = np.asarray([model.coordinates[name] for name in self.names], dtype=np.float64)
        self.input_ports = np.asarray(model.input_ports, dtype=np.float64)
        self.output_ports = np.asarray(model.output_ports, dtype=np.float64)

    @staticmethod
    def _distance(left: np.ndarray, right: np.ndarray) -> float:
        return float(abs(left[0] - right[0]) + abs(left[1] - right[1]))

    def arc_cost(self, arc: tuple[int, int, int]) -> float:
        chain, left, right = arc
        if left == -1:
            return self._distance(self.input_ports[chain], self.coordinates[right])
        if right == -2:
            return self._distance(self.coordinates[left], self.output_ports[chain])
        return self._distance(self.coordinates[left], self.coordinates[right])

    def full_cost(self, architecture: MutableScanArchitecture) -> float:
        return float(sum(self.arc_cost(arc) for arc in architecture.all_arcs()))


@dataclass
class ArchiveEntry:
    architecture_key: int
    objectives: Point2D
    source: str
    move_index: int
    snapshot: ArchitectureSnapshot | None = None
    canonical_sha256: str | None = None


class BoundedParetoArchive:
    """Strict Pareto archive with epsilon bins and crowding cap.

    Strict objective dominance is always honored. Epsilon binning only selects
    among nondominated near-duplicates. If the cap is exceeded, the least
    crowded non-extreme point is removed; the physical and H_eff8 extremes are
    never both discarded.
    """

    def __init__(self, maximum_size: int, epsilon_fraction: float,
                 ideal: Point2D, scale: Point2D) -> None:
        self.maximum_size = maximum_size
        self.epsilon_fraction = epsilon_fraction
        self.ideal = ideal
        self.scale = tuple(max(float(value), 1e-12) for value in scale)
        self.entries: list[ArchiveEntry] = []

    def _normalized(self, point: Point2D) -> Point2D:
        return tuple((point[i] - self.ideal[i]) / self.scale[i] for i in range(2))  # type: ignore[return-value]

    def _bin(self, point: Point2D) -> tuple[int, int] | None:
        if self.epsilon_fraction == 0:
            return None
        normalized = self._normalized(point)
        return tuple(math.floor(value / self.epsilon_fraction) for value in normalized)  # type: ignore[return-value]

    def insert(self, candidate: ArchiveEntry) -> tuple[bool, int, int]:
        """Return retained, dominated-count, pruned-count."""
        if any(row.architecture_key == candidate.architecture_key for row in self.entries):
            return False, 0, 0
        if any(dominates2(row.objectives, candidate.objectives) for row in self.entries):
            return False, 1, 0
        dominated = [row for row in self.entries if dominates2(candidate.objectives, row.objectives)]
        if dominated:
            doomed = {row.architecture_key for row in dominated}
            self.entries = [row for row in self.entries if row.architecture_key not in doomed]

        pruned = 0
        candidate_bin = self._bin(candidate.objectives)
        if candidate_bin is not None:
            same_bin = [row for row in self.entries if self._bin(row.objectives) == candidate_bin]
            if same_bin:
                incumbent = min(same_bin, key=lambda row: (sum(self._normalized(row.objectives)), row.architecture_key))
                candidate_key = (sum(self._normalized(candidate.objectives)), candidate.architecture_key)
                incumbent_key = (sum(self._normalized(incumbent.objectives)), incumbent.architecture_key)
                if candidate_key >= incumbent_key:
                    return False, 0, 1
                self.entries.remove(incumbent)
                pruned += 1

        self.entries.append(candidate)
        while len(self.entries) > self.maximum_size:
            removed = self._prune_one()
            pruned += 1
            if removed.architecture_key == candidate.architecture_key:
                return False, 0, pruned
        self.entries.sort(key=lambda row: (row.objectives, row.architecture_key))
        return True, 0, pruned

    def _crowding(self) -> dict[int, float]:
        result = {row.architecture_key: 0.0 for row in self.entries}
        for objective in range(2):
            ordered = sorted(self.entries, key=lambda row: (row.objectives[objective], row.architecture_key))
            result[ordered[0].architecture_key] = math.inf
            result[ordered[-1].architecture_key] = math.inf
            low, high = ordered[0].objectives[objective], ordered[-1].objectives[objective]
            span = max(high - low, 1e-12)
            for index in range(1, len(ordered) - 1):
                result[ordered[index].architecture_key] += (
                    ordered[index + 1].objectives[objective]
                    - ordered[index - 1].objectives[objective]
                ) / span
        return result

    def _prune_one(self) -> ArchiveEntry:
        physical_extreme = min(self.entries, key=lambda row: (row.objectives[0], row.objectives[1]))
        activity_extreme = min(self.entries, key=lambda row: (row.objectives[1], row.objectives[0]))
        protected = {physical_extreme.architecture_key, activity_extreme.architecture_key}
        crowding = self._crowding()
        candidates = [row for row in self.entries if row.architecture_key not in protected]
        if not candidates:
            candidates = [row for row in self.entries if row.architecture_key != physical_extreme.architecture_key]
        removed = min(candidates, key=lambda row: (crowding[row.architecture_key], row.architecture_key))
        self.entries.remove(removed)
        return removed

    def diverse_parent(self, iteration: int) -> ArchiveEntry:
        if not self.entries:
            raise ValueError("Archive is empty")
        physical = min(self.entries, key=lambda row: (row.objectives[0], row.objectives[1]))
        activity = min(self.entries, key=lambda row: (row.objectives[1], row.objectives[0]))
        if iteration % 3 == 0:
            return physical
        if iteration % 3 == 1:
            return activity
        crowding = self._crowding()
        return max(self.entries, key=lambda row: (crowding[row.architecture_key], -sum(row.objectives)))


class _BoundedSeen:
    def __init__(self, maximum_size: int, counters: V2Counters) -> None:
        self.maximum_size = maximum_size
        self.values: OrderedDict[int, None] = OrderedDict()
        self.counters = counters

    def add(self, key: int) -> bool:
        if key in self.values:
            self.values.move_to_end(key)
            return False
        self.values[key] = None
        if len(self.values) > self.maximum_size:
            self.values.popitem(last=False)
            self.counters.cache_evictions += 1
        return True


@dataclass
class OptimizerV2Result:
    config: OptimizerV2Config
    graph: Mapping[str, Any]
    archive: list[Mapping[str, Any]]
    counters: Mapping[str, Any]
    runtime: Mapping[str, Any]
    memory: Mapping[str, Any]
    stop_reason: str
    trace: list[Mapping[str, Any]] = field(default_factory=list)
    architecture_objects: dict[str, ScanArchitecture] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pact-optimizer-v2-result-1",
            "config": asdict(self.config),
            "graph": dict(self.graph),
            "archive": [dict(row) for row in self.archive],
            "counters": dict(self.counters),
            "runtime": dict(self.runtime),
            "memory": dict(self.memory),
            "stop_reason": self.stop_reason,
            "trace": [dict(row) for row in self.trace],
        }


def _candidate_nodes(architecture: MutableScanArchitecture, graph: SparsePhysicalGraph,
                     activity: TargetCompatibility, node: int, config: OptimizerV2Config,
                     rng: random.Random) -> list[int]:
    names = architecture.names
    local = [int(value) for value in graph.neighbors[node]]
    sampled: set[int] = set()
    sample_target = max(config.activity_candidates * 4, config.random_nonlocal_candidates)
    for _ in range(max(8, sample_target * 4)):
        sampled.add(rng.randrange(architecture.cell_count))
        if len(sampled) >= sample_target:
            break
    sampled.discard(node)
    activity_nodes = sorted(
        sampled, key=lambda other: (activity.relation(names[node], names[other]), other)
    )[:config.activity_candidates]
    nonlocal_nodes: set[int] = set()
    for _ in range(config.random_nonlocal_candidates * 4 + 4):
        nonlocal_nodes.add(rng.randrange(architecture.cell_count))
        if len(nonlocal_nodes) >= config.random_nonlocal_candidates:
            break
    nonlocal_nodes.discard(node)
    combined = list(dict.fromkeys(local + activity_nodes + sorted(nonlocal_nodes)))
    return combined[:config.maximum_neighborhood_size]


def _step_successor(architecture: MutableScanArchitecture, node: int, steps: int) -> int:
    current = int(node)
    for _ in range(steps):
        current = int(architecture.successor[current])
        if current == NONE:
            return NONE
    return current


def _apply_generated_move(architecture: MutableScanArchitecture, graph: SparsePhysicalGraph,
                          activity: TargetCompatibility, physical: PhysicalArcCost,
                          config: OptimizerV2Config, rng: random.Random,
                          move_index: int, counters: V2Counters) -> ArchitecturePatch:
    operators = ("swap", "relocate", "two_opt", "migration", "cross_chain_swap", "segment_exchange")
    operator = operators[move_index % len(operators)]
    lane_weight = config.constructor_lambdas[move_index % len(config.constructor_lambdas)]
    physical_scale = max(float(np.mean(graph.distances)), 1e-12)

    def apply_spec(spec: tuple[Any, ...]) -> ArchitecturePatch:
        kind = spec[0]
        if kind in {"swap", "cross_chain_swap"}:
            return architecture.swap(spec[1], spec[2], physical)
        if kind in {"relocate", "migration"}:
            return architecture.relocate(spec[1], spec[2], spec[3], physical)
        if kind == "two_opt":
            return architecture.reverse_segment(
                spec[1], spec[2], physical, config.maximum_segment_length + 1
            )
        return architecture.exchange_segments(
            spec[1], spec[2], spec[3], spec[4], physical, config.maximum_segment_length
        )

    def legal_lengths() -> bool:
        lengths = list(map(int, architecture.lengths))
        return min(lengths) >= config.minimum_chain_length and (
            max(lengths) - min(lengths) <= config.maximum_chain_length_difference
        )

    for _ in range(24):
        node = rng.randrange(architecture.cell_count)
        candidates = _candidate_nodes(architecture, graph, activity, node, config, rng)
        counters.neighborhood_total += len(candidates)
        counters.neighborhood_samples += 1
        if not candidates:
            continue
        source = int(architecture.chain_of[node])
        specs: list[tuple[Any, ...]] = []
        if operator in {"swap", "relocate"}:
            choices = [other for other in candidates if int(architecture.chain_of[other]) == source]
            specs = [
                (operator, node, source, other) if operator == "relocate" else (operator, node, other)
                for other in choices
            ]
        elif operator == "two_opt":
            for steps in range(1, config.maximum_segment_length + 1):
                last = _step_successor(architecture, node, steps)
                if last != NONE:
                    specs.append((operator, node, last))
        elif operator in {"migration", "cross_chain_swap"}:
            choices = [other for other in candidates if int(architecture.chain_of[other]) != source]
            if operator == "migration" and int(architecture.lengths[source]) <= config.minimum_chain_length:
                continue
            specs = [
                (operator, node, int(architecture.chain_of[other]), other)
                if operator == "migration" else (operator, node, other)
                for other in choices
            ]
        else:
            choices = [other for other in candidates if int(architecture.chain_of[other]) != source]
            for index, other in enumerate(choices):
                length = 1 + (move_index + index) % config.maximum_segment_length
                last_a = _step_successor(architecture, node, length - 1)
                last_b = _step_successor(architecture, other, length - 1)
                if last_a != NONE and last_b != NONE:
                    specs.append((operator, node, last_a, other, last_b))
        if not specs:
            continue

        ranked: list[tuple[float, float, tuple[Any, ...]]] = []
        for spec in specs[:config.maximum_neighborhood_size]:
            try:
                candidate_patch = apply_spec(spec)
            except (ValueError, IndexError):
                continue
            if not legal_lengths():
                architecture.rollback(candidate_patch)
                continue
            heuristic_delta = sum(
                activity.relation(architecture.names[left], architecture.names[right])
                for _, left, right in candidate_patch.added_arcs if left >= 0 and right >= 0
            ) - sum(
                activity.relation(architecture.names[left], architecture.names[right])
                for _, left, right in candidate_patch.removed_arcs if left >= 0 and right >= 0
            )
            score = (lane_weight * candidate_patch.physical_delta / physical_scale
                     + (1.0 - lane_weight) * heuristic_delta)
            ranked.append((score, candidate_patch.physical_delta, spec))
            counters.screened_move_options += 1
            architecture.rollback(candidate_patch)
        if ranked:
            _, _, best = min(ranked, key=lambda row: (row[0], row[1], row[2]))
            patch = apply_spec(best)
            if not legal_lengths():
                architecture.rollback(patch)
                continue
            return patch
    raise ValueError(f"Could not generate legal bounded {operator} move")


def _scales(points: Sequence[Point2D]) -> tuple[Point2D, Point2D]:
    ideal = tuple(min(point[index] for point in points) for index in range(2))
    high = tuple(max(point[index] for point in points) for index in range(2))
    scale = tuple(max(high[index] - ideal[index], abs(ideal[index]) * 0.05, 1.0) for index in range(2))
    return ideal, scale  # type: ignore[return-value]


def _scalar(point: Point2D, weight: float, ideal: Point2D, scale: Point2D) -> float:
    normalized = tuple((point[i] - ideal[i]) / scale[i] for i in range(2))
    return weight * normalized[0] + (1.0 - weight) * normalized[1]


def optimize_v2(
    base: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    physical_model: PhysicalCostModel,
    config: OptimizerV2Config = OptimizerV2Config(),
    *,
    seed_architectures: Sequence[tuple[str, ScanArchitecture]] = (),
    trace_limit: int = 256,
) -> OptimizerV2Result:
    """Run bounded sparse search without OpenROAD or complete candidate copies."""
    started = time.perf_counter()
    tracemalloc.start()
    counters = V2Counters()
    trace: list[Mapping[str, Any]] = []
    coordinates = np.asarray([(cell.x_um, cell.y_um) for cell in base.cells], dtype=np.float64)
    graph = SparsePhysicalGraph.build(coordinates, config.graph_k)
    physical = PhysicalArcCost(base, physical_model)
    activity_heuristic = TargetCompatibility(patterns, weights)
    h_evaluator = IncrementalHEff8(base, patterns, weights)
    constructors = [("input_architecture", MutableScanArchitecture.from_scan_architecture(base))]
    base_names = tuple(cell.name for cell in base.cells)
    base_topology = tuple((chain.chain_id, chain.scan_in, chain.scan_out) for chain in base.chains)
    for label, seed in seed_architectures:
        if tuple(cell.name for cell in seed.cells) != base_names:
            raise ValueError("Seed FF inventory/order differs from the base indexing")
        if tuple((chain.chain_id, chain.scan_in, chain.scan_out) for chain in seed.chains) != base_topology:
            raise ValueError("Seed K or endpoint topology differs from the base")
        constructors.append((label, MutableScanArchitecture.from_scan_architecture(seed)))
    generated = construct_architectures_v2(
        base, graph, physical_model, activity_heuristic, config.constructor_lambdas, config.seed
    )
    # Evaluate the two named extremes before mixed starts when a tight wall
    # budget cannot cover every constructor.
    constructors.extend([row for row in generated if row[0] == "physical_greedy"])
    constructors.extend([row for row in generated if row[0] == "activity_aware_greedy"])
    constructors.extend([row for row in generated if row[0].startswith("mixed_")])
    counters.complete_architecture_copies += len(constructors)

    initial: list[tuple[ArchiveEntry, MutableScanArchitecture]] = []
    initial_keys: set[int] = set()
    for label, architecture in constructors:
        if architecture.architecture_key in initial_keys:
            continue
        if counters.exact_evaluations >= config.maximum_exact_evaluations:
            break
        if initial and time.perf_counter() - started >= config.wall_clock_seconds:
            break
        physical_value = physical.full_cost(architecture)
        counters.full_physical_recomputations += 1
        h_state = h_evaluator.full_state(architecture.orders())
        counters.exact_evaluations += 1
        entry = ArchiveEntry(
            architecture.architecture_key,
            (physical_value, h_state.value),
            label,
            0,
            ArchitectureSnapshot.capture(architecture),
        )
        counters.complete_architecture_copies += 1
        initial.append((entry, architecture))
        initial_keys.add(architecture.architecture_key)
    del h_state

    points = [row[0].objectives for row in initial]
    ideal, scale = _scales(points)
    archive = BoundedParetoArchive(
        config.maximum_archive_size, config.archive_epsilon_fraction, ideal, scale
    )
    for entry, _ in initial:
        retained, dominated, pruned = archive.insert(entry)
        counters.candidates_considered += 1
        counters.candidates_accepted += int(retained)
        counters.candidates_dominated += dominated
        counters.candidates_pruned_archive_size += pruned

    current_entry, architecture = min(
        initial, key=lambda row: (_scalar(row[0].objectives, 0.5, ideal, scale), row[0].architecture_key)
    )
    # Initial objective states are not retained per seed. Rebuild only the
    # selected active parent, avoiding O(number_of_starts * P * L * 64) memory.
    current_h = h_evaluator.full_state(architecture.orders())
    current_physical = current_entry.objectives[0]
    seen = _BoundedSeen(config.seen_cache_size, counters)
    for entry, _ in initial:
        seen.add(entry.architecture_key)
    rng = random.Random(config.seed)
    stop_reason = "COMPLETED"

    while True:
        elapsed = time.perf_counter() - started
        if elapsed >= config.wall_clock_seconds:
            stop_reason = "WALL_CLOCK_BUDGET_EXHAUSTED"
            break
        if counters.exact_evaluations >= config.maximum_exact_evaluations:
            stop_reason = "EXACT_EVALUATION_BUDGET_EXHAUSTED"
            break
        if counters.local_moves_attempted >= config.maximum_local_moves:
            stop_reason = "LOCAL_MOVE_BUDGET_EXHAUSTED"
            break

        move_index = counters.local_moves_attempted
        if (config.parent_refresh_interval > 0 and move_index > 0
                and move_index % config.parent_refresh_interval == 0 and archive.entries):
            parent = archive.diverse_parent(move_index // config.parent_refresh_interval)
            if parent.snapshot is not None and parent.architecture_key != architecture.architecture_key:
                architecture = parent.snapshot.restore(base)
                current_physical = parent.objectives[0]
                current_h = h_evaluator.full_state(architecture.orders())
                counters.complete_architecture_copies += 1
                counters.parent_restarts += 1

        counters.local_moves_attempted += 1
        try:
            patch = _apply_generated_move(
                architecture, graph, activity_heuristic, physical, config, rng, move_index, counters
            )
        except ValueError:
            counters.invalid_moves += 1
            continue
        if not seen.add(patch.hash_after):
            counters.duplicate_candidates += 1
            architecture.rollback(patch)
            continue

        after_orders = {chain: architecture.order(chain) for chain in patch.affected_chains}
        all_orders = None
        if max(map(int, architecture.lengths)) != current_h.longest_chain:
            all_orders = architecture.orders()
        h_candidate = h_evaluator.evaluate(
            current_h, patch.before_orders, after_orders, architecture.lengths, all_orders
        )
        counters.exact_evaluations += 1
        counters.incremental_physical_evaluations += 1
        candidate_point = (current_physical + patch.physical_delta, h_candidate.value)
        candidate = ArchiveEntry(
            patch.hash_after, candidate_point, patch.kind, counters.local_moves_attempted
        )
        retained, dominated, pruned = archive.insert(candidate)
        counters.candidates_considered += 1
        counters.candidates_accepted += int(retained)
        counters.candidates_dominated += dominated
        counters.candidates_pruned_archive_size += pruned
        if retained:
            candidate.snapshot = ArchitectureSnapshot.capture(architecture)
            counters.complete_architecture_copies += 1

        weight = config.constructor_lambdas[move_index % len(config.constructor_lambdas)]
        current_point = (current_physical, current_h.value)
        accept_local = dominates2(candidate_point, current_point)
        accept_local = accept_local or _scalar(candidate_point, weight, ideal, scale) < _scalar(
            current_point, weight, ideal, scale
        )
        # Archive discoveries occasionally seed the trajectory even when the
        # active scalar lane does not improve, preserving objective diversity.
        accept_local = accept_local or (retained and rng.random() < 0.25)
        if accept_local:
            current_h = h_evaluator.accept(current_h, h_candidate)
            current_physical = candidate_point[0]
            counters.local_moves_accepted += 1
        else:
            architecture.rollback(patch)

        if len(trace) < trace_limit:
            trace.append({
                "move": counters.local_moves_attempted,
                "operator": patch.kind,
                "affected_chains": list(patch.affected_chains),
                "removed_arcs": len(patch.removed_arcs),
                "added_arcs": len(patch.added_arcs),
                "physical_delta": patch.physical_delta,
                "objectives": list(candidate_point),
                "archive_retained": retained,
                "local_accepted": accept_local,
            })

    # Boundary verification is deliberately limited to the capped final
    # archive. It proves exact deltas without returning full recomputation to the
    # inner loop.
    output_rows: list[Mapping[str, Any]] = []
    architecture_objects: dict[str, ScanArchitecture] = {}
    for entry in archive.entries:
        if entry.snapshot is None:
            continue
        restored = entry.snapshot.restore(base)
        restored.validate_internal()
        full_physical = physical.full_cost(restored)
        counters.full_physical_recomputations += 1
        if not math.isclose(full_physical, entry.objectives[0], rel_tol=0.0, abs_tol=1e-8):
            raise AssertionError("Incremental physical objective differs from full recomputation")
        boundary = restored.to_scan_architecture()
        counters.complete_architecture_copies += 1
        entry.canonical_sha256 = boundary.sha256()
        architecture_objects[entry.canonical_sha256] = boundary
        output_rows.append({
            "architecture_sha256": entry.canonical_sha256,
            "architecture_key": f"{entry.architecture_key:032x}",
            "objectives": list(entry.objectives),
            "source": entry.source,
            "move_index": entry.move_index,
            "chain_lengths": list(map(len, entry.snapshot.orders)),
        })

    counters.incremental_h_eff8_evaluations = h_evaluator.incremental_evaluations
    counters.full_h_eff8_recomputations = h_evaluator.full_evaluations
    elapsed = time.perf_counter() - started
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    average_neighborhood = (
        counters.neighborhood_total / counters.neighborhood_samples
        if counters.neighborhood_samples else 0.0
    )
    counter_dict = asdict(counters)
    counter_dict["final_archive_size"] = len(output_rows)
    counter_dict["average_candidate_neighborhood_size"] = average_neighborhood
    counter_dict["evaluations_per_second"] = counters.exact_evaluations / max(elapsed, 1e-12)
    counter_dict["local_moves_per_second"] = counters.local_moves_attempted / max(elapsed, 1e-12)
    graph_dict = asdict(graph.stats)
    return OptimizerV2Result(
        config=config,
        graph=graph_dict,
        archive=output_rows,
        counters=counter_dict,
        runtime={
            "optimizer_wall_seconds": elapsed,
            "graph_construction_seconds": graph.stats.construction_seconds,
            "openroad_calls": 0,
        },
        memory={
            "tracemalloc_peak_bytes": int(peak_memory),
            "sparse_graph_bytes": graph.stats.memory_bytes,
            "current_h_eff8_state_bytes": IncrementalHEff8.memory_bytes(current_h),
            "seen_cache_entries": len(seen.values),
        },
        stop_reason=stop_reason,
        trace=trace,
        architecture_objects=architecture_objects,
    )
