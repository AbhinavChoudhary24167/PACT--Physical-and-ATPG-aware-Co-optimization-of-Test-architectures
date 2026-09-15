import importlib.util
import json
from pathlib import Path

import pytest


def classifier_module():
    path = Path(__file__).resolve().parents[2] / "scripts/phase0c_classify.py"
    spec = importlib.util.spec_from_file_location("phase0c_classify_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pareto_retains_tradeoff_and_excludes_dominated():
    module = classifier_module()
    rows = [{"method": "P", "physical_primary_um": 100, "H_eff8": 10},
            {"method": "A", "physical_primary_um": 150, "H_eff8": 5},
            {"method": "R", "physical_primary_um": 200, "H_eff8": 11}]
    assert [row["method"] for row in module.pareto(rows)] == ["P", "A"]


def test_descriptive_regret_and_rank_correlation_are_paired():
    module = classifier_module()
    rows = [
        {"method": "P", "physical_primary_um": 100.0, "H_eff8": 10.0,
         "parallel_shift_cycles": 100},
        {"method": "A", "physical_primary_um": 120.0, "H_eff8": 8.0,
         "parallel_shift_cycles": 100},
        {"method": "R", "physical_primary_um": 150.0, "H_eff8": 11.0,
         "parallel_shift_cycles": 100},
    ]
    pair, stats = module.describe_complete_pairs({("d", 11, 2): rows})
    assert pair[0]["physical_penalty_percent"] == pytest.approx(20.0)
    assert pair[0]["H_eff_gain_percent"] == pytest.approx(20.0)
    assert pair[0]["pareto_methods"] == ["A", "P"]
    assert pair[0]["method_regrets"]["A"]["physical_percent"] == 20.0
    assert stats["pareto_membership_counts"] == {"A": 1, "P": 1}
    assert module.spearman([1, 2, 3], [3, 2, 1]) == -1.0


def test_missing_physical_campaign_cannot_pass_learning_gate(tmp_path: Path):
    module = classifier_module()
    module.ROOT = tmp_path
    files = {
        "config/phase0c_campaign.json": {
            "status": "FROZEN_FOR_FINAL_CAMPAIGN", "designs": ["d"],
            "physical_seeds": [11], "K_values": [1],
            "route_families_each_K": ["B0", "P"], "native_B1_k1_method": "B1"},
        "config/phase0c_analysis_contract.json": {
            "status": "FROZEN_FOR_FINAL_CAMPAIGN",
            "C2": {"minimum_route_completion_fraction": .9,
                   "minimum_complete_pair_fraction": .8, "minimum_complete_designs": 1},
            "C3": {"physical_penalty_min_percent": 10, "H_eff_improvement_min_percent": 5},
            "C4": {"minimum_supporting_seeds_per_design": 1},
            "C5": {"minimum_replicated_designs": 1},
            "C6": {"methods": ["B0", "P"], "simple_heuristic_epsilon_fraction": .02,
                   "maximum_fraction_of_pairs_covered_by_one_simple_heuristic": .8,
                   "maximum_fraction_of_pairs_covered_by_deterministic_portfolio": .8,
                   "portfolio_methods": ["B0", "P"]},
            "C7": {"minimum_matched_interventions_per_pair": 20,
                   "minimum_opposite_sign_fraction_per_class": .2,
                   "minimum_seeds_per_design": 1, "minimum_designs": 1},
            "C8": {"minimum_log10_legal_architectures": 100}},
        "artifacts/manifests/phase0b/benchmark_manifest.json": {
            "designs": [{"design": "d", "scan_ff_count": 179}]},
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    script = tmp_path / "scripts/phase0c_rewire_odb.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fixed policy\n")
    result = module.classify()
    assert result["gates"]["C1"]["status"] == "NOT QUALIFIED"
    assert result["gates"]["C2"]["status"] == "NOT QUALIFIED"
    assert result["gates"]["C8"]["status"] == "PASS"
    assert result["gates"]["C9"]["status"] == "FAIL"
    assert result["classification"] == "PACT_PHASE0C_LEARNING_GATE_FAIL"
