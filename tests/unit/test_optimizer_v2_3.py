from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pact.analysis.phase0c_activity import parallel_activity_metrics
from pact.experiment_storage import configure_experiment_storage
from pact.phase0d.optimizer_v1 import PhysicalCostModel
from pact.phase0d.optimizer_v2 import OptimizerV2Config, optimize_v2
from pact.phase0d.optimizer_v2_3 import (
    ParallelParetoConfig,
    _GlobalCandidate,
    deterministic_archive_merge,
    optimize_parallel_pareto,
)
from pact.phase0d.v2_architecture import MutableScanArchitecture
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def problem(n: int = 24, k: int = 3):
    cells = tuple(
        ScanCell(f"ff{index:03d}", float((index * 7) % 13),
                 float((index * 11) % 17), "clk")
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
        tuple((-2.0, float(chain * 3)) for chain in range(k)),
        tuple((15.0, float(chain * 3)) for chain in range(k)),
        30.0,
    )
    patterns = [
        {cell.name: ((index * 3 + pattern * 5 + index // 3) & 1)
         for index, cell in enumerate(cells)}
        for pattern in range(5)
    ]
    weights = {cell.name: 1 + index % 5 for index, cell in enumerate(cells)}
    return architecture, physical, patterns, weights


def optimizer_config(seed: int = 77) -> OptimizerV2Config:
    return OptimizerV2Config(
        wall_clock_seconds=30,
        maximum_exact_evaluations=10,
        maximum_local_moves=64,
        maximum_archive_size=8,
        maximum_neighborhood_size=12,
        graph_k=6,
        parent_refresh_interval=4,
        seed=seed,
        h_eff8_tile_patterns=4,
    )


def storage(tmp_path: Path):
    return configure_experiment_storage(tmp_path / "experiments", environ={})


def test_w1_reproduces_existing_serial_search(tmp_path: Path) -> None:
    base, physical, patterns, weights = problem()
    config = optimizer_config()
    direct = optimize_v2(base, patterns, weights, physical, config, trace_limit=0)
    wrapped = optimize_parallel_pareto(
        base, patterns, weights, physical, config,
        ParallelParetoConfig(
            worker_count=1,
            total_exact_evaluations=config.maximum_exact_evaluations,
            master_seed=config.seed,
            parallel_backend="sequential",
        ),
        frozen_ideal=(0.0, 0.0),
        frozen_reference=(1000.0, 1000.0),
        storage_paths=storage(tmp_path),
    )
    assert [
        (row["architecture_sha256"], row["objectives"]) for row in wrapped.archive
    ] == [
        (row["architecture_sha256"], row["objectives"]) for row in direct.archive
    ]
    assert wrapped.accounting["total_exact_evaluations"] == direct.counters["exact_evaluations"]
    assert wrapped.stop_reason == direct.stop_reason


@pytest.mark.parametrize("workers,epochs,budget", [(2, 2, 12), (4, 1, 12)])
def test_repeated_parallel_runs_are_identical_and_exactly_accounted(
    tmp_path: Path, workers: int, epochs: int, budget: int,
) -> None:
    base, physical, patterns, weights = problem()
    parallel = ParallelParetoConfig(
        worker_count=workers,
        epochs=epochs,
        total_exact_evaluations=budget,
        master_seed=901,
        parallel_backend="sequential",
        run_id=f"repeat-{workers}",
    )
    arguments = dict(
        base=base,
        patterns=patterns,
        weights=weights,
        physical_model=physical,
        optimizer_config=optimizer_config(901),
        parallel_config=parallel,
        frozen_ideal=(0.0, 0.0),
        frozen_reference=(1000.0, 1000.0),
        storage_paths=storage(tmp_path),
    )
    first = optimize_parallel_pareto(**arguments)
    second = optimize_parallel_pareto(**arguments)
    assert first.archive == second.archive
    assert first.accounting["total_exact_evaluations"] == budget
    assert first.accounting["evaluation_budget_exact"] is True
    assert len({row["architecture_sha256"] for row in first.archive}) == len(first.archive)


def test_completion_order_cannot_change_global_archive() -> None:
    base, _, _, _ = problem()
    candidates = []
    points = ((10.0, 90.0), (20.0, 60.0), (45.0, 45.0), (60.0, 20.0), (90.0, 10.0))
    for index, point in enumerate(points):
        candidates.append(_GlobalCandidate(
            base.sha256() + str(index),
            index + 1,
            point,
            "test",
            index,
            index % 2,
            f"L{index % 2}",
            base,
        ))
    forward = deterministic_archive_merge(
        candidates, maximum_size=4, epsilon_fraction=0.0,
        ideal=(0.0, 0.0), scale=(100.0, 100.0),
    )
    reverse = deterministic_archive_merge(
        reversed(candidates), maximum_size=4, epsilon_fraction=0.0,
        ideal=(0.0, 0.0), scale=(100.0, 100.0),
    )
    assert [(row.architecture_key, row.objectives) for row in forward] == [
        (row.architecture_key, row.objectives) for row in reverse
    ]


def test_lane_mutable_architecture_states_do_not_share_arrays() -> None:
    base, _, _, _ = problem()
    first = MutableScanArchitecture.from_scan_architecture(base)
    second = MutableScanArchitecture.from_scan_architecture(base)
    assert first is not second
    for name in ("predecessor", "successor", "chain_of", "heads", "tails", "lengths"):
        assert not np.shares_memory(getattr(first, name), getattr(second, name))


def test_parallel_archive_matches_authoritative_objectives_and_inputs_are_immutable(
    tmp_path: Path,
) -> None:
    base, physical, patterns, weights = problem()
    original = base.sha256()
    result = optimize_parallel_pareto(
        base, patterns, weights, physical, optimizer_config(55),
        ParallelParetoConfig(
            worker_count=2,
            epochs=1,
            total_exact_evaluations=8,
            master_seed=55,
            parallel_backend="sequential",
            run_id="exactness",
        ),
        frozen_ideal=(0.0, 0.0),
        frozen_reference=(1000.0, 1000.0),
        storage_paths=storage(tmp_path),
    )
    assert base.sha256() == original
    for row in result.archive:
        architecture = result.architecture_objects[row["architecture_sha256"]]
        assert physical.architecture_cost(architecture) == pytest.approx(row["objectives"][0])
        exact_h = parallel_activity_metrics(
            architecture, patterns, weights, grid_sizes=(8,)
        )["grids"]["8"]["H_eff"]
        assert exact_h == pytest.approx(row["objectives"][1], abs=1e-12)
