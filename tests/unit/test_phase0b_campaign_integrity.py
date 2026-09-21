"""Regression gates for physical-seed propagation and paired evidence identity."""
from __future__ import annotations

import pytest
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scripts.phase0b_analyze import (CONFIG_SHA256, SEED_METHOD_SHA256,
                                    evidence_matches_pair, plan_matches_contract)
from scripts.phase0b_stage_seed_audit import seed_arguments_match
from scripts.phase0b_pipeline import placement_fingerprint, route_make_command
import phase0b_pipeline


def test_route_seed_is_propagated_to_variant_and_global_router():
    command = route_make_command("s5378", 17, "J50")
    assert "FLOW_VARIANT=phase0b_s17_J50" in command
    assert "GRT_SEED=17" in command
    assert command.count("-o") == 2
    assert all("phase0b_s17_J50" in command[i + 1]
               for i, value in enumerate(command) if value == "-o")
    assert seed_arguments_match(command, 17, "J50", "global_route")
    assert not seed_arguments_match(command, 19, "J50", "global_route")
    with pytest.raises(ValueError, match="Unregistered"):
        route_make_command("s5378", 999, "P")


def test_placement_fingerprint_detects_physical_change_not_dict_order():
    first = {"a": ("SDFF_X1", "100", "200", "N"),
             "b": ("BUF_X1", "300", "400", "N")}
    reordered = {"b": first["b"], "a": first["a"]}
    moved = {**first, "a": ("SDFF_X1", "101", "200", "N")}
    assert placement_fingerprint(first) == placement_fingerprint(reordered)
    assert placement_fingerprint(first) != placement_fingerprint(moved)


def test_placement_seed_audit_rejects_mismatched_variant():
    command = ["env", "PACT_PHASE0B_PHYSICAL_SEED=17",
               "PACT_PHASE0B_PLACED_ODB=/flow/phase0b_s19_B0/3_place.odb"]
    assert not seed_arguments_match(command, 17, "B0", "placement_perturbation")
    command[2] = "PACT_PHASE0B_PLACED_ODB=/flow/phase0b_s17_B0/3_place.odb"
    assert seed_arguments_match(command, 17, "B0", "placement_perturbation")


def test_seed_qualification_always_uses_full_predeclared_set(tmp_path, monkeypatch):
    monkeypatch.setattr(phase0b_pipeline, "ROOT", tmp_path)
    for seed in phase0b_pipeline.PHYSICAL_SEEDS:
        folder = tmp_path / f"artifacts/raw/phase0b/placements/tiny/s{seed}"
        folder.mkdir(parents=True)
        (folder / "placed.def").write_text(
            f"COMPONENTS 1 ;\n- f0 SDFF_X1 + PLACED ( {seed} 200 ) N ;\nEND COMPONENTS\n")
    phase0b_pipeline.qualify_seeds("tiny")
    result = json.loads((tmp_path / "artifacts/derived/phase0b/tiny/physical_seed_qualification.json").read_text())
    assert result["requested_seeds"] == [11, 13, 17, 19, 23]
    assert result["completed_physical_seeds"] == 5
    assert result["all_completed_placements_distinct"]


def test_paired_evidence_rejects_wrong_seed_method_or_architecture():
    verification = {"status": "PASS", "design": "s5378", "physical_seed": 11, "method": "P",
                    "architecture_sha256": "abc"}
    metrics = {"design": "s5378", "physical_seed": 11, "method": "P"}
    route = {"design": "s5378", "physical_seed": 11, "method": "P",
             "architecture_sha256": "abc"}
    assert evidence_matches_pair("s5378", 11, "P", "abc", verification, metrics, route)
    assert not evidence_matches_pair("s5378", 13, "P", "abc", verification, metrics, route)
    assert not evidence_matches_pair("s5378", 11, "A", "abc", verification, metrics, route)
    assert not evidence_matches_pair("s5378", 11, "P", "other", verification, metrics, route)


def test_pair_plan_requires_frozen_contract_hashes_and_row_identity():
    plan = {"design": "s5378", "physical_seed": 11,
            "phase0b_config_sha256": CONFIG_SHA256,
            "seed_method_sha256": SEED_METHOD_SHA256,
            "rows": [{"design": "s5378", "physical_seed": 11}]}
    assert plan_matches_contract(plan, "s5378", 11)
    assert not plan_matches_contract(plan, "s5378", 13)
    assert not plan_matches_contract({**plan, "phase0b_config_sha256": "changed"}, "s5378", 11)
    assert not plan_matches_contract({**plan, "rows": [{"design": "s9234", "physical_seed": 11}]}, "s5378", 11)
