from __future__ import annotations

import random

import numpy as np
import pytest

from pact.analysis.phase0c_activity import parallel_activity_metrics
from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility
from pact.phase0d.optimizer_v2 import OptimizerV2Config, PhysicalArcCost, optimize_v2
from pact.phase0d.v2_activity import IncrementalHEff8, RetainedIncrementalHEff8
from pact.phase0d.v2_architecture import MutableScanArchitecture
from pact.phase0d.v2_shared_frontier import construct_architectures_v2_1
from pact.phase0d.v2_sparse import SparsePhysicalGraph
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def problem(n: int = 36, k: int = 3, pattern_count: int = 11):
    cells = tuple(
        ScanCell(f"ff{index:03d}", float((index * 7) % 19),
                 float((index * 11) % 23), "clk")
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
    patterns = [
        {cell.name: ((index * 5 + pattern * 3 + index // 4) & 1)
         for index, cell in enumerate(cells)}
        for pattern in range(pattern_count)
    ]
    weights = {cell.name: 1 + index % 4 for index, cell in enumerate(cells)}
    coordinates = {cell.name: (cell.x_um, cell.y_um) for cell in cells}
    physical = PhysicalCostModel(
        coordinates,
        tuple((-3.0, float(chain * 5)) for chain in range(k)),
        tuple((24.0, float(chain * 5)) for chain in range(k)),
        50.0,
    )
    return architecture, physical, patterns, weights


@pytest.mark.parametrize("tile_size", [4, 8, 16, 32])
@pytest.mark.parametrize("workers", [1, 2, 4])
def test_tiled_full_matches_authoritative_for_nondivisible_patterns(
    tile_size: int, workers: int,
) -> None:
    base, _, patterns, weights = problem(pattern_count=11)
    mutable = MutableScanArchitecture.from_scan_architecture(base)
    evaluator = IncrementalHEff8(
        base, patterns, weights, tile_patterns=tile_size, workers=workers
    )
    state = evaluator.full_state(mutable.orders())
    exact = parallel_activity_metrics(
        base, patterns, weights, grid_sizes=(8,)
    )["grids"]["8"]["H_eff"]
    assert state.value == pytest.approx(exact, abs=1e-12)
    assert not hasattr(state, "chain_fields")
    assert evaluator.persistent_per_chain_bytes(state) == 0
    assert evaluator.memory_bytes(state) == state.global_field.nbytes


def test_tiled_incremental_reconstruction_lmax_fallback_and_rejection_rollback() -> None:
    base, model, patterns, weights = problem(pattern_count=9)
    mutable = MutableScanArchitecture.from_scan_architecture(base)
    physical = PhysicalArcCost(base, model)
    evaluator = IncrementalHEff8(base, patterns, weights, tile_patterns=4, workers=2)
    state = evaluator.full_state(mutable.orders())
    original_field = state.global_field.copy()
    original_value = state.value

    # A cross-chain relocation changes Lmax and must use the exact tiled full fallback.
    before = mutable.orders()
    node = before[0][-1]
    target_anchor = before[1][-1]
    patch = mutable.relocate(node, 1, target_anchor, physical)
    after = {chain: mutable.order(chain) for chain in patch.affected_chains}
    candidate = evaluator.evaluate(
        state, patch.before_orders, after, mutable.lengths, mutable.orders()
    )
    authoritative = parallel_activity_metrics(
        mutable.to_scan_architecture(), patterns, weights, grid_sizes=(8,)
    )["grids"]["8"]["H_eff"]
    assert candidate.value == pytest.approx(authoritative, abs=1e-12)

    # Rejecting the candidate and rolling back the architecture cannot modify E.
    mutable.rollback(patch)
    assert mutable.orders() == before
    assert state.value == original_value
    assert np.array_equal(state.global_field, original_field)

    # Re-evaluate and accept the same move; the committed global-only state must
    # agree with an independent retained/full recomputation.
    patch = mutable.relocate(node, 1, target_anchor, physical)
    after = {chain: mutable.order(chain) for chain in patch.affected_chains}
    candidate = evaluator.evaluate(
        state, patch.before_orders, after, mutable.lengths, mutable.orders()
    )
    state = evaluator.accept(state, candidate)
    retained = RetainedIncrementalHEff8(base, patterns, weights).full_state(mutable.orders())
    assert state.value == pytest.approx(retained.value, abs=1e-12)
    assert np.allclose(state.global_field, retained.global_field, rtol=0.0, atol=1e-12)


def test_randomized_incremental_old_new_reconstruction_is_exact_without_chain_state() -> None:
    base, model, patterns, weights = problem(42, 3, 13)
    mutable = MutableScanArchitecture.from_scan_architecture(base)
    physical = PhysicalArcCost(base, model)
    evaluator = IncrementalHEff8(base, patterns, weights, tile_patterns=8, workers=4)
    state = evaluator.full_state(mutable.orders())
    rng = random.Random(2209)
    for iteration in range(18):
        orders = mutable.orders()
        chain = rng.randrange(mutable.chain_count)
        left, right = rng.sample(orders[chain], 2)
        patch = mutable.swap(left, right, physical)
        after = {changed: mutable.order(changed) for changed in patch.affected_chains}
        candidate = evaluator.evaluate(
            state, patch.before_orders, after, mutable.lengths
        )
        exact = parallel_activity_metrics(
            mutable.to_scan_architecture(), patterns, weights, grid_sizes=(8,)
        )["grids"]["8"]["H_eff"]
        assert candidate.value == pytest.approx(exact, abs=1e-12)
        if iteration % 2:
            state = evaluator.accept(state, candidate)
        else:
            before_field = state.global_field.copy()
            mutable.rollback(patch)
            assert np.array_equal(state.global_field, before_field)


def test_worker_counts_preserve_optimizer_objectives_hashes_archive_and_stop_reason() -> None:
    base, model, patterns, weights = problem(30, 3, 9)
    results = []
    for workers in (1, 2, 4):
        config = OptimizerV2Config(
            wall_clock_seconds=20,
            maximum_exact_evaluations=12,
            maximum_local_moves=12,
            maximum_archive_size=8,
            maximum_neighborhood_size=12,
            graph_k=6,
            parent_refresh_interval=4,
            seed=2209,
            h_eff8_tile_patterns=4,
            h_eff8_workers=workers,
        )
        results.append(optimize_v2(base, patterns, weights, model, config, trace_limit=0))
    expected = [
        (row["architecture_sha256"], row["architecture_key"], row["objectives"])
        for row in results[0].archive
    ]
    for result in results[1:]:
        assert [
            (row["architecture_sha256"], row["architecture_key"], row["objectives"])
            for row in result.archive
        ] == expected
        assert result.stop_reason == results[0].stop_reason


def test_threaded_constructor_branches_preserve_v21_portfolio() -> None:
    base, physical, patterns, weights = problem(60, 4, 7)
    graph = SparsePhysicalGraph.build(
        np.asarray([(cell.x_um, cell.y_um) for cell in base.cells]), 8
    )
    activity = TargetCompatibility(patterns, weights)
    sequential, _ = construct_architectures_v2_1(
        base, graph, physical, activity, seed=2209, parallel_backend="sequential"
    )
    threaded, _ = construct_architectures_v2_1(
        base, graph, physical, activity, seed=2209, parallel_backend="thread"
    )
    assert [label for label, _ in threaded] == [label for label, _ in sequential]
    assert [architecture.canonical_digest() for _, architecture in threaded] == [
        architecture.canonical_digest() for _, architecture in sequential
    ]
