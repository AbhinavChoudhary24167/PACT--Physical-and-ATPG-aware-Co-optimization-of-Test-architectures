from __future__ import annotations

import random

import numpy as np
import pytest

from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility
from pact.phase0d.v2_constructor_metrics import ConstructorStats
from pact.phase0d.v2_shared_frontier import (
    InsertionOpportunity,
    SharedInsertionFeatures,
    _SharedLaneState,
    construct_architectures_v2_1,
)
from pact.phase0d.v2_sparse import SparsePhysicalGraph
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.scan.validate import validate_scan


def problem(n: int = 36, k: int = 3):
    cells = tuple(
        ScanCell(f"ff{index:03d}", float((index * 7) % 19), float((index * 11) % 23), "clk")
        for index in range(n)
    )
    capacities = [n // k + int(chain < n % k) for chain in range(k)]
    chains = []
    cursor = 0
    for chain, length in enumerate(capacities):
        names = tuple(cell.name for cell in cells[cursor:cursor + length])
        chains.append(ScanChain(
            f"C{chain:02d}", names,
            "test_si" if chain == 0 else f"test_si_{chain}",
            "test_so" if chain == 0 else f"test_so_{chain}",
        ))
        cursor += length
    architecture = ScanArchitecture(cells, tuple(chains))
    coordinates = {cell.name: (cell.x_um, cell.y_um) for cell in cells}
    physical = PhysicalCostModel(
        coordinates,
        tuple((-3.0, float(chain * 5)) for chain in range(k)),
        tuple((24.0, float(chain * 5)) for chain in range(k)),
        50.0,
    )
    patterns = [
        {cell.name: ((index * 5 + pattern * 3 + index // 4) & 1)
         for index, cell in enumerate(cells)}
        for pattern in range(7)
    ]
    weights = {cell.name: 1 + index % 4 for index, cell in enumerate(cells)}
    activity = TargetCompatibility(patterns, weights)
    graph = SparsePhysicalGraph.build(
        np.asarray([(cell.x_um, cell.y_um) for cell in cells]), 6
    )
    return architecture, physical, activity, graph


def test_shared_constructor_is_complete_capacity_preserving_and_deterministic() -> None:
    base, physical, activity, graph = problem()
    first, first_stats = construct_architectures_v2_1(
        base, graph, physical, activity, seed=771
    )
    second, second_stats = construct_architectures_v2_1(
        base, graph, physical, activity, seed=771
    )
    capacities = tuple(len(chain.cells) for chain in base.chains)
    assert len(first) == 5
    assert [label for label, _ in first] == [label for label, _ in second]
    assert first_stats.accepted_insertions == 5 * (len(base.cells) - len(base.chains))
    assert first_stats.insertion_candidates_scored < 5 * len(base.cells) * 16
    assert first_stats.to_dict() | {"total_seconds": 0, "lane_seconds": {}} == (
        second_stats.to_dict() | {"total_seconds": 0, "lane_seconds": {}}
    )
    for (first_label, first_arch), (second_label, second_arch) in zip(first, second):
        assert first_label == second_label
        first_arch.validate_internal()
        boundary = first_arch.to_scan_architecture()
        validate_scan(boundary)
        assert tuple(map(len, first_arch.orders())) == capacities
        assert sorted(node for order in first_arch.orders() for node in order) == list(range(len(base.cells)))
        assert first_arch.canonical_digest() == second_arch.canonical_digest()


def test_cached_physical_and_activity_insertion_deltas_are_exact() -> None:
    base, physical, activity, _ = problem()
    stats = ConstructorStats("test")
    features = SharedInsertionFeatures(
        base, physical, activity, stats,
        candidate_cache_limit=4096,
        activity_cache_limit=4096,
    )
    names = tuple(cell.name for cell in base.cells)
    rng = random.Random(9182)
    for lane in range(3):
        for _ in range(80):
            chain = rng.randrange(len(base.chains))
            candidate = rng.randrange(len(names))
            pool = [node for node in range(len(names)) if node != candidate]
            rng.shuffle(pool)
            order = pool[:rng.randrange(1, min(12, len(pool)) + 1)]
            position = rng.randrange(len(order) + 1)
            predecessor = -1 if position == 0 else order[position - 1]
            successor = -2 if position == len(order) else order[position]
            arc = (chain, predecessor, successor)
            physical_delta, activity_delta = features.feature(candidate, arc, lane)
            before_names = [names[node] for node in order]
            after_names = before_names.copy()
            after_names.insert(position, names[candidate])
            expected_physical = (
                physical.chain_cost(chain, after_names)
                - physical.chain_cost(chain, before_names)
            )
            expected_activity = (
                activity.chain_score(after_names) - activity.chain_score(before_names)
            )
            assert physical_delta == pytest.approx(expected_physical, abs=1e-12)
            assert activity_delta == pytest.approx(expected_activity, abs=1e-12)


def test_lazy_versions_reject_stale_and_refresh_matches_clean_recomputation() -> None:
    base, physical, activity, _ = problem(18, 3)
    stats = ConstructorStats("test")
    features = SharedInsertionFeatures(
        base, physical, activity, stats,
        candidate_cache_limit=1024,
        activity_cache_limit=1024,
    )
    capacities = tuple(len(chain.cells) for chain in base.chains)
    heads = [0, capacities[0], capacities[0] + capacities[1]]
    lane = _SharedLaneState(
        lane=0,
        weight=0.5,
        label="test",
        capacities=capacities,
        groups=[[head] for head in heads],
        versions=[1, 1, 1],
    )
    node = 1
    arc = (0, heads[0], -2)
    physical_delta, activity_delta = features.feature(node, arc, 0)
    old = InsertionOpportunity(
        node, 0, arc[1], arc[2], physical_delta, activity_delta,
        0.5 * physical_delta / features.scale + 0.5 * activity_delta,
        1, 0,
    )
    assert lane.valid(old)
    lane.groups[0].append(node)
    lane.versions[0] += 1
    assert not lane.valid(old)
    refreshed_node = 2
    refreshed_arc = (0, node, -2)
    refreshed_physical, refreshed_activity = features.feature(refreshed_node, refreshed_arc, 0)
    refreshed = InsertionOpportunity(
        refreshed_node, 0, node, -2, refreshed_physical, refreshed_activity,
        0.5 * refreshed_physical / features.scale + 0.5 * refreshed_activity,
        2, 0,
    )
    assert lane.valid(refreshed)
    chain_names = [features.names[item] for item in lane.groups[0]]
    expected = physical.insertion_delta(0, chain_names, len(chain_names), features.names[refreshed_node])
    assert refreshed.physical_delta == pytest.approx(expected, abs=1e-12)


def test_shared_lane_cache_preserves_independent_scalar_scores() -> None:
    base, physical, activity, _ = problem()
    stats = ConstructorStats("test")
    features = SharedInsertionFeatures(
        base, physical, activity, stats,
        candidate_cache_limit=1024,
        activity_cache_limit=1024,
    )
    arc = (0, 0, -2)
    for lane, weight in enumerate((1.0, 0.75, 0.5, 0.25, 0.0)):
        physical_delta, heuristic = features.feature(5, arc, lane)
        shared_score = weight * physical_delta / features.scale + (1.0 - weight) * heuristic
        names = features.names
        independent_physical = physical.insertion_delta(0, [names[0]], 1, names[5])
        independent_heuristic = activity.insertion_delta([names[0]], 1, names[5])
        independent_score = (
            weight * independent_physical / physical.scale_um
            + (1.0 - weight) * independent_heuristic
        )
        assert shared_score == pytest.approx(independent_score, abs=1e-12)
    assert stats.shared_candidate_feature_hits == 4
    assert stats.repeated_equivalent_candidate_evaluations_across_lanes == 4


def test_constructor_observes_and_discards_stale_entries() -> None:
    base, physical, activity, graph = problem(48, 4)
    _, stats = construct_architectures_v2_1(base, graph, physical, activity, seed=97)
    assert stats.candidates_invalidated > 0
    assert stats.stale_candidates_rejected > 0
    assert stats.frontier_rebuilds > 0
