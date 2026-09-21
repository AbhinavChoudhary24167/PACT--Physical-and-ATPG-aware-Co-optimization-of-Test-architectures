from __future__ import annotations

import math
import random

import numpy as np
import pytest

from pact.analysis.phase0c_activity import parallel_activity_metrics
from pact.phase0d.optimizer_v1 import PhysicalCostModel
from pact.phase0d.optimizer_v2 import (
    ArchiveEntry,
    BoundedParetoArchive,
    OptimizerV2Config,
    PhysicalArcCost,
    optimize_v2,
)
from pact.phase0d.v2_activity import IncrementalHEff8
from pact.phase0d.v2_architecture import MutableScanArchitecture
from pact.phase0d.v2_sparse import SparsePhysicalGraph
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def problem(n: int = 24, k: int = 3):
    cells = tuple(
        ScanCell(f"ff{index:03d}", float((index * 7) % 13), float((index * 11) % 17), "clk")
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
    coords = {cell.name: (cell.x_um, cell.y_um) for cell in cells}
    physical = PhysicalCostModel(
        coords,
        tuple((-2.0, float(chain * 3)) for chain in range(k)),
        tuple((15.0, float(chain * 3)) for chain in range(k)),
        30.0,
    )
    patterns = [
        {cell.name: ((index * 3 + pattern * 5 + index // 3) & 1)
         for index, cell in enumerate(cells)}
        for pattern in range(5)
    ]
    weights = {cell.name: 1 + (index % 5) for index, cell in enumerate(cells)}
    return architecture, physical, patterns, weights


def apply_random_move(architecture, physical, rng: random.Random, kind: int):
    orders = architecture.orders()
    if kind == 0:
        chain = rng.randrange(architecture.chain_count)
        first, second = rng.sample(orders[chain], 2)
        return architecture.swap(first, second, physical)
    if kind == 1:
        chain = rng.randrange(architecture.chain_count)
        order = orders[chain]
        node = rng.choice(order)
        anchors = [other for other in order if other != node and architecture.predecessor[node] != other]
        return architecture.relocate(node, chain, rng.choice(anchors), physical)
    if kind == 2:
        chain = rng.randrange(architecture.chain_count)
        order = orders[chain]
        left = rng.randrange(len(order) - 1)
        right = rng.randrange(left + 1, len(order))
        return architecture.reverse_segment(order[left], order[right], physical)
    if kind == 3:
        first_chain, second_chain = rng.sample(range(architecture.chain_count), 2)
        return architecture.swap(rng.choice(orders[first_chain]), rng.choice(orders[second_chain]), physical)
    if kind == 4:
        first_chain, second_chain = rng.sample(range(architecture.chain_count), 2)
        left = rng.randrange(len(orders[first_chain]) - 1)
        right = rng.randrange(len(orders[second_chain]) - 1)
        return architecture.exchange_segments(
            orders[first_chain][left], orders[first_chain][left + 1],
            orders[second_chain][right], orders[second_chain][right + 1], physical,
        )
    source, target = rng.sample(range(architecture.chain_count), 2)
    return architecture.relocate(rng.choice(orders[source]), target, rng.choice(orders[target]), physical)


def test_sparse_graph_is_knn_and_linear_storage() -> None:
    architecture, _, _, _ = problem(40, 4)
    coordinates = np.asarray([(cell.x_um, cell.y_um) for cell in architecture.cells])
    graph = SparsePhysicalGraph.build(coordinates, 5)
    assert graph.neighbors.shape == (40, 5)
    assert graph.stats.directed_edge_count == 200
    assert graph.stats.memory_bytes == graph.neighbors.nbytes + graph.distances.nbytes
    for node, row in enumerate(graph.neighbors):
        assert node not in row


def test_all_local_moves_have_exact_physical_delta_and_rollback() -> None:
    base, model, _, _ = problem()
    architecture = MutableScanArchitecture.from_scan_architecture(base)
    physical = PhysicalArcCost(base, model)
    rng = random.Random(901)
    for iteration in range(150):
        before_orders = architecture.orders()
        before_key = architecture.architecture_key
        before_cost = physical.full_cost(architecture)
        patch = apply_random_move(architecture, physical, rng, iteration % 6)
        architecture.validate_internal()
        after_cost = physical.full_cost(architecture)
        assert before_cost + patch.physical_delta == pytest.approx(after_cost, abs=1e-9)
        boundary_cost = model.architecture_cost(architecture.to_scan_architecture())
        assert after_cost == pytest.approx(boundary_cost, abs=1e-9)
        architecture.rollback(patch)
        architecture.validate_internal()
        assert architecture.orders() == before_orders
        assert architecture.architecture_key == before_key


def test_incremental_h_eff8_is_exact_over_randomized_moves() -> None:
    base, model, patterns, weights = problem()
    architecture = MutableScanArchitecture.from_scan_architecture(base)
    physical = PhysicalArcCost(base, model)
    evaluator = IncrementalHEff8(base, patterns, weights)
    state = evaluator.full_state(architecture.orders())
    authoritative = parallel_activity_metrics(base, patterns, weights, grid_sizes=(8,))["grids"]["8"]["H_eff"]
    assert state.value == pytest.approx(authoritative, abs=1e-12)
    rng = random.Random(443)
    for iteration in range(60):
        patch = apply_random_move(architecture, physical, rng, iteration % 6)
        after = {chain: architecture.order(chain) for chain in patch.affected_chains}
        all_orders = architecture.orders() if max(architecture.lengths) != state.longest_chain else None
        candidate = evaluator.evaluate(
            state, patch.before_orders, after, architecture.lengths, all_orders
        )
        boundary = architecture.to_scan_architecture()
        exact = parallel_activity_metrics(boundary, patterns, weights, grid_sizes=(8,))["grids"]["8"]["H_eff"]
        assert candidate.value == pytest.approx(exact, abs=1e-12)
        if iteration % 3:
            state = evaluator.accept(state, candidate)
        else:
            architecture.rollback(patch)
    architecture.validate_internal()


def test_archive_pruning_preserves_both_extremes_and_dominance() -> None:
    archive = BoundedParetoArchive(4, 0.0, (0.0, 0.0), (10.0, 10.0))
    for index, point in enumerate(((1, 9), (2, 7), (3, 6), (4, 4), (6, 3), (9, 1))):
        archive.insert(ArchiveEntry(index, point, "test", index))
    assert len(archive.entries) == 4
    assert min(row.objectives[0] for row in archive.entries) == 1
    assert min(row.objectives[1] for row in archive.entries) == 1
    retained, dominated, _ = archive.insert(ArchiveEntry(99, (10, 10), "dominated", 0))
    assert not retained and dominated == 1


def test_optimizer_is_deterministic_valid_and_strictly_bounded() -> None:
    base, model, patterns, weights = problem(30, 3)
    config = OptimizerV2Config(
        wall_clock_seconds=10,
        maximum_exact_evaluations=14,
        maximum_local_moves=20,
        maximum_archive_size=6,
        maximum_neighborhood_size=12,
        graph_k=6,
        parent_refresh_interval=5,
        seed=77,
    )
    first = optimize_v2(base, patterns, weights, model, config)
    second = optimize_v2(base, patterns, weights, model, config)
    assert first.stop_reason in {
        "EXACT_EVALUATION_BUDGET_EXHAUSTED", "LOCAL_MOVE_BUDGET_EXHAUSTED"
    }
    assert first.counters["exact_evaluations"] <= config.maximum_exact_evaluations
    assert first.counters["local_moves_attempted"] <= config.maximum_local_moves
    assert first.counters["final_archive_size"] <= config.maximum_archive_size
    assert [(row["architecture_key"], row["objectives"]) for row in first.archive] == [
        (row["architecture_key"], row["objectives"]) for row in second.archive
    ]
    assert all(math.isfinite(value) for row in first.archive for value in row["objectives"])
