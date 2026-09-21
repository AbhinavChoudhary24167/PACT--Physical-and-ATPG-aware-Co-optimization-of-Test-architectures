"""Predeclared paired Pareto and practical-effect classification for Phase-0B."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


EPS = 1e-9


def pareto_frontier(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    if len({row["architecture_sha256"] for row in rows}) != len(rows):
        raise ValueError("Pareto inputs must be deduplicated by architecture SHA256")
    result = []
    for row in rows:
        physical, h8 = row["primary_physical_cost_um"], row["H8"]
        dominated = any((other["primary_physical_cost_um"] <= physical + EPS
                         and other["H8"] <= h8 + EPS
                         and (other["primary_physical_cost_um"] < physical - EPS
                              or other["H8"] < h8 - EPS)) for other in rows if other is not row)
        if not dominated:
            result.append(row)
    return sorted(result, key=lambda row: (row["primary_physical_cost_um"], row["H8"], row["architecture_sha256"]))


def classify_pair(rows: Sequence[dict[str, Any]], *, physical_penalty_min_pct: float = 10.0,
                  hotspot_improvement_min_pct: float = 5.0) -> dict[str, Any]:
    if len(rows) < 2:
        raise ValueError("Paired conflict requires at least two qualified architectures")
    hashes = [row["architecture_sha256"] for row in rows]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Architecture hashes must be unique within a physical pair")
    if any(row["primary_physical_cost_um"] <= 0 or row["H8"] <= 0 for row in rows):
        raise ValueError("Primary objectives must be positive")
    minimum_physical = min(row["primary_physical_cost_um"] for row in rows)
    minimum_h8 = min(row["H8"] for row in rows)
    physical_optima = [row for row in rows if abs(row["primary_physical_cost_um"] - minimum_physical) <= EPS]
    h8_optima = [row for row in rows if abs(row["H8"] - minimum_h8) <= EPS]
    physical_best = min(physical_optima, key=lambda row: (row["H8"], row["architecture_sha256"]))
    h8_best = min(h8_optima, key=lambda row: (row["primary_physical_cost_um"], row["architecture_sha256"]))
    overlap = {row["architecture_sha256"] for row in physical_optima} & {row["architecture_sha256"] for row in h8_optima}
    h8_gain = physical_best["H8"] - h8_best["H8"]
    physical_penalty = h8_best["primary_physical_cost_um"] - physical_best["primary_physical_cost_um"]
    h8_gain_pct = 100 * h8_gain / physical_best["H8"]
    physical_penalty_pct = 100 * physical_penalty / physical_best["primary_physical_cost_um"]
    strict = not bool(overlap)
    meaningful = strict and h8_gain_pct >= hotspot_improvement_min_pct and physical_penalty_pct >= physical_penalty_min_pct
    frontier = pareto_frontier(rows)
    joint_rows = [row for row in rows if row["method"] in ("J25", "J50", "J75")]
    singles = [row for row in rows if row["method"] in ("P", "A")]
    def meaningfully_dominates(joint: dict[str, Any], single: dict[str, Any]) -> bool:
        return (joint["primary_physical_cost_um"] <= single["primary_physical_cost_um"] + EPS
                and joint["H8"] <= single["H8"] + EPS
                and (100 * (single["primary_physical_cost_um"] - joint["primary_physical_cost_um"])
                     / single["primary_physical_cost_um"] >= physical_penalty_min_pct
                     or 100 * (single["H8"] - joint["H8"]) / single["H8"] >= hotspot_improvement_min_pct))
    joint_vs_p = any(meaningfully_dominates(joint, single)
                     for joint in joint_rows for single in singles if single["method"] == "P")
    joint_vs_a = any(meaningfully_dominates(joint, single)
                     for joint in joint_rows for single in singles if single["method"] == "A")
    joint_vs_both = any(all(meaningfully_dominates(joint, single) for single in singles)
                        for joint in joint_rows) if len(singles) == 2 else False
    return {
        "A_physical_optimum_also_minimizes_H8": any(row["architecture_sha256"] in overlap for row in physical_optima),
        "B_H8_optimum_also_minimizes_physical": any(row["architecture_sha256"] in overlap for row in h8_optima),
        "C_distinct_architectures_on_frontier": len(frontier) >= 2,
        "D_joint_meaningfully_dominates_single_objective": joint_vs_p or joint_vs_a,
        "D_joint_meaningfully_dominates_P": joint_vs_p,
        "D_joint_meaningfully_dominates_A": joint_vs_a,
        "D_joint_meaningfully_dominates_both": joint_vs_both,
        "strict_conflict": strict,
        "practically_meaningful_conflict": meaningful,
        "physical_optimum_method": physical_best["method"],
        "H8_optimum_method": h8_best["method"],
        "physical_optimum_architecture_sha256": physical_best["architecture_sha256"],
        "H8_optimum_architecture_sha256": h8_best["architecture_sha256"],
        "H8_absolute_improvement_vs_physical_optimum": h8_gain,
        "H8_percent_improvement_vs_physical_optimum": h8_gain_pct,
        "physical_absolute_penalty_um_for_H8_optimum": physical_penalty,
        "physical_percent_penalty_for_H8_optimum": physical_penalty_pct,
        "pareto_architecture_sha256": [row["architecture_sha256"] for row in frontier],
        "pareto_methods": [row["method"] for row in frontier],
        "qualified_architecture_count": len(rows),
    }


def paired_effect_summary(pairs: Sequence[dict[str, Any]], *, bootstrap_seed: int = 0) -> dict[str, Any]:
    if not pairs:
        return {"n_physical_seeds": 0, "bootstrap_median_ci95": None}
    def describe(key: str) -> dict[str, object]:
        values = np.asarray([pair[key] for pair in pairs], dtype=float)
        result: dict[str, object] = {
            "median": float(np.median(values)),
            "q1": float(np.percentile(values, 25)),
            "q3": float(np.percentile(values, 75)),
            "iqr": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "min": float(values.min()), "max": float(values.max()),
            "positive_direction_count": int((values > EPS).sum()),
        }
        if len(values) >= 5:
            rng = np.random.default_rng(bootstrap_seed)
            resamples = rng.choice(values, size=(10_000, len(values)), replace=True)
            medians = np.median(resamples, axis=1)
            result["bootstrap_median_ci95"] = [float(np.percentile(medians, 2.5)),
                                               float(np.percentile(medians, 97.5))]
            result["bootstrap_scope"] = "exploratory resampling of these fixed physical realizations; no population claim"
        else:
            result["bootstrap_median_ci95"] = None
        return result
    return {
        "n_physical_seeds": len(pairs),
        "H8_absolute_improvement": describe("H8_absolute_improvement_vs_physical_optimum"),
        "H8_percent_improvement": describe("H8_percent_improvement_vs_physical_optimum"),
        "physical_absolute_penalty_um": describe("physical_absolute_penalty_um_for_H8_optimum"),
        "physical_percent_penalty": describe("physical_percent_penalty_for_H8_optimum"),
        "strict_conflict_seed_count": sum(bool(pair["strict_conflict"]) for pair in pairs),
        "meaningful_conflict_seed_count": sum(bool(pair["practically_meaningful_conflict"]) for pair in pairs),
    }
