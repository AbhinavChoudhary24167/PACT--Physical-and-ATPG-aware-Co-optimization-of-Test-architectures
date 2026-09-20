from pathlib import Path

from pact.phase0d.funnel import FrozenProxyContext, historical_route_resources, projection
from pact.scan.phase0d_operators import apply_operator, sample_operations


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_context_reuses_phase0c_and_freezes_bounds() -> None:
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    assert len(context.patterns) == 117
    assert len(context.start_architecture.cells) == 179
    assert context.start().evaluation.metadata["status"] == "REUSED_VERIFIED"
    bounds = context.frozen_bounds()
    assert all(low < high for low, high in zip(bounds.ideal, bounds.reference))


def test_one_real_candidate_passes_full_proxy_funnel(tmp_path: Path) -> None:
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    operation = sample_operations(context.start_architecture, 1, proposal_seed=901)[0]
    child, record = apply_operator(context.start_architecture, operation)
    first = context.evaluate(child, record, tmp_path)
    assert first.metadata["status"] == "EXECUTED_NEW"
    assert first.objectives[0] > 0 and first.objectives[1] > 0 and first.objectives[2] == 10530
    second = context.evaluate(child, record, tmp_path)
    assert second.metadata["status"] == "REUSED_VERIFIED"
    assert second.objectives == first.objectives


def test_resource_projection_distinguishes_new_routes() -> None:
    historical = historical_route_resources(ROOT)
    assert historical["existing_qualified_routes_reused"] == 375
    assert historical["historical_successful_route_samples"] == 375
    result = projection(0.1, historical)
    assert result["projected_proxy_evaluations"] == 30_720
    assert result["projected_new_routes"] == 1_920
    assert result["runtime_policy"] == "VERY_LONG_REDUCE_AND_STAGE"
