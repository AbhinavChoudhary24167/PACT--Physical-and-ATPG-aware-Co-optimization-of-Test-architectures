from __future__ import annotations

import pytest

from pact.phase0d.pareto import (
    ObjectiveBounds,
    additive_epsilon_coverage,
    dominates,
    freeze_bounds,
    hypervolume_3d,
    nondominated,
    objective_regret,
)
from pact.phase0d.search import (
    SEARCH_METHODS,
    Evaluation,
    EvaluatedArchitecture,
    SearchConfig,
    run_search,
)
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def architecture() -> ScanArchitecture:
    names = tuple(f"f{i:02d}" for i in range(20))
    cells = tuple(ScanCell(name, float(i % 5), float(i // 5), "CK") for i, name in enumerate(names))
    return ScanArchitecture(cells, (
        ScanChain("C00", names[:10], "test_si_0", "test_so_0"),
        ScanChain("C01", names[10:], "test_si_1", "test_so_1"),
    ))


def toy_objectives(arch: ScanArchitecture) -> tuple[float, float, float]:
    values = [int(name[1:]) for chain in arch.chains for name in chain.cells]
    physical = float(sum(abs(int(a[1:]) - int(b[1:])) for chain in arch.chains for a, b in zip(chain.cells, chain.cells[1:])))
    activity = float(sum((index + 1) * (value % 3) for index, value in enumerate(values)))
    cycles = float(max(len(chain.cells) for chain in arch.chains))
    return physical, activity, cycles


def evaluator(arch: ScanArchitecture, record) -> Evaluation:
    return Evaluation(toy_objectives(arch), {"operator": record["type"]})


def test_pareto_and_exact_hypervolume() -> None:
    assert dominates((1, 2, 3), (1, 3, 4))
    assert not dominates((1, 2, 3), (1, 2, 3))
    front = nondominated([(1, 3, 3), (2, 2, 2), (3, 1, 3), (4, 4, 4)])
    assert len(front) == 3
    assert hypervolume_3d([(0.2, 0.8, 0.8), (0.8, 0.2, 0.2)]) == pytest.approx(0.152)


def test_frozen_bounds_epsilon_and_regret() -> None:
    bounds = freeze_bounds([(10, 5, 2), (20, 3, 2)])
    assert bounds.ideal == (10, 3, 2)
    assert all(value == pytest.approx(0.0) for value in bounds.normalize(bounds.ideal))
    reference = [(0.0, 0.0, 0.0), (0.2, -0.1, 0.0)]
    approximation = [(0.1, 0.1, 0.0)]
    assert additive_epsilon_coverage(approximation, reference) == pytest.approx(0.2)
    assert objective_regret(approximation, reference) == pytest.approx((0.1, 0.2, 0.0))


@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_search_methods_are_deterministic_and_strictly_budgeted(method: str) -> None:
    arch = architecture()
    start = EvaluatedArchitecture(arch, Evaluation(toy_objectives(arch), {"source": "start"}))
    bounds = ObjectiveBounds((0.0, 0.0, 8.0), (100.0, 1000.0, 14.0))
    config = SearchConfig(proxy_budget=12, candidate_batch_size=4, beam_width=2,
                          plateau_legal_evaluations=12, hypervolume_window=12,
                          wall_clock_seconds=10, proposal_seed=7)
    first = run_search(method, start, evaluator, bounds, config)
    second = run_search(method, start, evaluator, bounds, config)
    for key in ("proposed_candidates", "legal_candidates", "proxy_evaluations", "accepted_moves",
                "rejected_moves", "invalid_candidates", "stop_reason", "final_hypervolume",
                "unique_pareto_solutions", "pareto_archive"):
        assert first[key] == second[key]
    assert 1 <= first["proxy_evaluations"] <= 12
    assert first["routed_evaluations"] == 0
    assert first["legal_candidates"] >= first["proxy_evaluations"]
    assert first["accepted_moves"] + first["rejected_moves"] == first["proxy_evaluations"]
    assert all(record["evaluation_index"] <= 12 for record in first["trace"]
               if record["event"] == "PROXY_EVALUATION")


def test_invalid_method_and_budget_are_rejected() -> None:
    with pytest.raises(ValueError, match="proxy_budget"):
        SearchConfig(proxy_budget=129)
    arch = architecture()
    start = EvaluatedArchitecture(arch, Evaluation(toy_objectives(arch)))
    with pytest.raises(ValueError, match="Unknown search"):
        run_search("magic", start, evaluator, ObjectiveBounds((0, 0, 0), (1, 1, 1)), SearchConfig(4))
