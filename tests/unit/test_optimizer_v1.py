from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from pact.phase0d.funnel import FrozenProxyContext
from pact.phase0d.optimizer_v1 import (
    Bounds2D,
    ParetoArchive2D,
    PhysicalCostModel,
    TargetCompatibility,
    construct_architecture,
    dominates2,
    hypervolume2,
    lns_candidate,
)
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.scan.phase0d_operators import structural_proof


ROOT = Path(__file__).resolve().parents[2]


def load_runner():
    spec = importlib.util.spec_from_file_location("phase0d_optimizer_v1", ROOT / "scripts/phase0d_optimizer_v1.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def synthetic_problem() -> tuple[ScanArchitecture, PhysicalCostModel, TargetCompatibility, list[dict[str, int]]]:
    cells = tuple(ScanCell(f"ff{index:02d}", float(index % 4), float(index // 4), "clk") for index in range(16))
    architecture = ScanArchitecture(
        cells,
        (
            ScanChain("C00", tuple(cell.name for cell in cells[:8]), "test_si", "test_so"),
            ScanChain("C01", tuple(cell.name for cell in cells[8:]), "test_si_1", "test_so_1"),
        ),
    )
    coordinates = {cell.name: (cell.x_um, cell.y_um) for cell in cells}
    physical = PhysicalCostModel(coordinates, ((-1.0, 0.0), (5.0, 0.0)),
                                 ((-1.0, 3.0), (5.0, 3.0)), 7.0)
    patterns = [
        {cell.name: (index + pattern) % 2 for index, cell in enumerate(cells)}
        for pattern in range(4)
    ]
    activity = TargetCompatibility(patterns, {cell.name: 1 + (index % 3) for index, cell in enumerate(cells)})
    return architecture, physical, activity, patterns


def test_two_objective_archive_and_hypervolume() -> None:
    assert dominates2((1, 2), (2, 2))
    archive = ParetoArchive2D()
    assert archive.insert({"architecture_sha256": "a", "objectives": [1, 3, 99]})
    assert archive.insert({"architecture_sha256": "b", "objectives": [2, 2, 99]})
    assert not archive.insert({"architecture_sha256": "c", "objectives": [3, 3, 1]})
    assert len(archive.entries) == 2
    assert hypervolume2(((1, 3), (2, 2)), Bounds2D((0, 0), (4, 4))) == pytest.approx(0.3125)


def test_global_constructor_is_deterministic_legal_and_reconstructs_atpg() -> None:
    base, physical, activity, patterns = synthetic_problem()
    first = construct_architecture(base, physical, activity, 0.5, regret=True)
    second = construct_architecture(base, physical, activity, 0.5, regret=True)
    assert first.sha256() == second.sha256()
    proof = structural_proof(base, first, patterns)
    assert proof["FF_inventory_verified"]
    assert proof["ATPG_patterns_verified"] == len(patterns)
    assert [len(chain.cells) for chain in first.chains] == [8, 8]


@pytest.mark.parametrize("operator", ["region", "hotspot", "segment", "cross_chain", "guided"])
def test_lns_destroy_repair_is_legal_and_incremental_delta_is_exact(operator: str) -> None:
    base, physical, activity, patterns = synthetic_problem()
    child, move = lns_candidate(
        base, physical, activity, operator=operator, fraction=0.20,
        repair_strategy="balanced", iteration=3,
    )
    proof = structural_proof(base, child, patterns)
    assert proof["exact_parallel_loading_verified"]
    full_delta = physical.architecture_cost(child) - physical.architecture_cost(base)
    assert move["incremental_physical_delta_um"] == pytest.approx(full_delta)


def test_real_physical_decomposition_matches_qualified_proxy() -> None:
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    model = PhysicalCostModel.from_architecture(context.start_architecture, context.frozen_def)
    exact = phase0c_scan_geometry(context.start_architecture, context.frozen_def)["total_scan_hpwl_um"]
    assert model.architecture_cost(context.start_architecture) == pytest.approx(exact, abs=1e-9)


def test_completed_checkpoint_is_resumed_without_new_work(tmp_path: Path) -> None:
    runner = load_runner()
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    contract_sha = runner.file_sha256(runner.CONTRACT_PATH)
    hashes = runner.source_hashes()
    state = runner.initial_state(context, contract_sha, hashes, 0.01)
    state["status"] = "COMPLETE"
    output = tmp_path / "run"
    output.mkdir()
    (output / "optimizer_state.json").write_text(json.dumps(state), encoding="utf-8")
    resumed = runner.run_optimizer(context, output, 0.01, [])
    assert resumed == state
    assert resumed["counters"]["candidates_proposed"] == 0


def test_runtime_accounting_fields_are_explicit() -> None:
    runner = load_runner()
    contract = runner.read_json(runner.CONTRACT_PATH)
    names = set(contract["runtime"]["accounting"])
    assert names == {
        "process_invocation_wall_seconds", "search_wall_clock_seconds",
        "accumulated_new_proxy_wall_seconds", "route_wall_seconds",
        "total_campaign_elapsed_seconds",
    }
