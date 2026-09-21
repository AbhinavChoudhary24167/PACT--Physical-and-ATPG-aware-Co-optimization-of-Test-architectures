import pytest

from pact.analysis.phase0b_conflict import classify_pair, pareto_frontier, paired_effect_summary


def row(method, cost, h8):
    return {"method": method, "architecture_sha256": method,
            "primary_physical_cost_um": cost, "H8": h8}


def test_pareto_excludes_dominated_and_retains_ties():
    rows = [row("P", 100, 4), row("A", 140, 3.5), row("J50", 150, 4.1)]
    assert [r["method"] for r in pareto_frontier(rows)] == ["P", "A"]


def test_strict_conflict_can_fail_effect_size_gate():
    result = classify_pair([row("P", 100, 4.0), row("A", 500, 3.99)])
    assert result["strict_conflict"]
    assert not result["practically_meaningful_conflict"]
    assert result["C_distinct_architectures_on_frontier"]


def test_meaningful_conflict_and_joint_domination():
    result = classify_pair([row("P", 100, 4.0), row("A", 150, 3.6), row("J50", 130, 3.5)])
    assert result["strict_conflict"]
    assert result["practically_meaningful_conflict"]
    assert result["D_joint_meaningfully_dominates_single_objective"]
    assert not result["D_joint_meaningfully_dominates_P"]
    assert result["D_joint_meaningfully_dominates_A"]
    assert not result["D_joint_meaningfully_dominates_both"]
    assert result["physical_percent_penalty_for_H8_optimum"] == pytest.approx(30.0)


def test_joint_candidate_can_dominate_both_single_objective_candidates():
    result = classify_pair([row("P", 120, 4.0), row("A", 150, 3.9), row("J50", 100, 3.5)])
    assert result["D_joint_meaningfully_dominates_P"]
    assert result["D_joint_meaningfully_dominates_A"]
    assert result["D_joint_meaningfully_dominates_both"]


def test_same_architecture_minimizes_both():
    result = classify_pair([row("P", 100, 3.0), row("A", 150, 4.0)])
    assert not result["strict_conflict"]
    assert result["A_physical_optimum_also_minimizes_H8"]
    assert result["B_H8_optimum_also_minimizes_physical"]


def test_paired_effects_do_not_bootstrap_tiny_n():
    pair = classify_pair([row("P", 100, 4.0), row("A", 130, 3.5)])
    observed = paired_effect_summary([pair, pair])
    assert observed["n_physical_seeds"] == 2
    assert observed["H8_percent_improvement"]["bootstrap_median_ci95"] is None


def test_five_paired_physical_effects_have_deterministic_descriptive_interval():
    pairs = [classify_pair([row("P", 100, 4.0), row("A", 100 + penalty, 4.0 - gain)])
             for penalty, gain in ((20, 0.4), (30, 0.2), (10, 0.1), (40, 0.3), (50, 0.5))]
    first = paired_effect_summary(pairs, bootstrap_seed=17)
    second = paired_effect_summary(pairs, bootstrap_seed=17)
    effect = first["H8_percent_improvement"]
    assert effect["median"] == pytest.approx(7.5)
    assert effect["iqr"] == pytest.approx(5.0)
    assert effect["positive_direction_count"] == 5
    assert effect["bootstrap_median_ci95"] == second["H8_percent_improvement"]["bootstrap_median_ci95"]
    assert effect["bootstrap_median_ci95"][0] <= effect["median"] <= effect["bootstrap_median_ci95"][1]
