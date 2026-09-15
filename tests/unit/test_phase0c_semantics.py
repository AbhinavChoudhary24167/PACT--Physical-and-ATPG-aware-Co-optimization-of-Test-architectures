from __future__ import annotations

import pytest

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.scan.phase0c import (architecture_space_log10, chain_statistics,
                                generate_architecture, parallel_schedule,
                                verify_parallel_schedule)
from pact.analysis.phase0c_activity import parallel_activity_metrics
from pact.scan.phase0c_interventions import apply_intervention, sampled_local_swaps


def fixture():
    names = tuple(f"f{i:02d}" for i in range(17))
    cells = tuple(ScanCell(name, float(i % 5), float(i // 5), "CK") for i, name in enumerate(names))
    base = ScanArchitecture(cells, (ScanChain("source", names),))
    patterns = [{name: (i + p) % 2 for i, name in enumerate(names)} for p in range(3)]
    return base, patterns


@pytest.mark.parametrize("method", ["B0", "P", "A", "J25", "J50", "J75", "T", "R"])
def test_deterministic_balanced_architectures(method):
    base, patterns = fixture()
    a = generate_architecture(base, 2, method, patterns)
    b = generate_architecture(base, 2, method, patterns)
    assert a.sha256() == b.sha256()
    assert sorted(chain_statistics(a, len(patterns))["chain_lengths"]) == [8, 9]
    assert set(name for chain in a.chains for name in chain.cells) == {cell.name for cell in base.cells}


def test_short_chain_is_clocked_during_padding_and_exact_loaded():
    base, patterns = fixture()
    arch = generate_architecture(base, 2, "B0", patterns)
    schedule = parallel_schedule(arch, patterns[0])
    assert len(schedule) == 9
    assert schedule[0][1] == 0
    initial = {name: 1 for name in patterns[0]}
    proof = verify_parallel_schedule(arch, patterns[0], initial)
    assert proof["clock_count"] == 9
    assert proof["scan_out"][1][:8] == [1] * 8
    assert proof["loaded_state_exact"] and proof["scan_out_traversal_exact"]
    assert chain_statistics(arch, len(patterns))["parallel_shift_cycles"] == 27


def test_exact_activity_has_expected_cycle_count():
    base, patterns = fixture()
    arch = generate_architecture(base, 2, "P", patterns)
    weights = {cell.name: 1 for cell in arch.cells}
    metrics = parallel_activity_metrics(arch, patterns, weights, (8,))
    assert metrics["parallel_shift_clock_count"] == 27
    assert metrics["total_shift_toggles"] > 0
    assert metrics["weighted_total"] == metrics["total_shift_toggles"]


def test_invalid_target_and_space_count():
    base, patterns = fixture()
    arch = generate_architecture(base, 2, "B0", patterns)
    with pytest.raises(ValueError):
        parallel_schedule(arch, {"f00": 1})
    assert architecture_space_log10(17, 2) > architecture_space_log10(17, 1)


@pytest.mark.parametrize("operation", [
    {"type": "swap", "chain": 0, "i": 0, "j": 1},
    {"type": "segment_reversal", "chain": 0, "i": 1, "j": 4},
    {"type": "two_opt", "chain": 0, "i": 1, "j": 4},
    {"type": "relocate", "chain": 0, "to_chain": 1, "i": 0, "to_index": 0},
    {"type": "chain_rebalance", "chain": 0, "to_chain": 1, "i": 0, "to_index": 0},
    {"type": "cross_chain_exchange", "chain": 0, "other_chain": 1, "i": 0, "j": 0},
])
def test_intervention_legality_and_hashing(operation):
    base, patterns = fixture()
    arch = generate_architecture(base, 2, "B0", patterns)
    child, record = apply_intervention(arch, operation)
    assert record["legal"]
    assert record["parent_sha256"] == arch.sha256()
    assert record["child_sha256"] == child.sha256()
    assert record["added_edges"] and record["removed_edges"]
    assert set(name for chain in child.chains for name in chain.cells) == {c.name for c in base.cells}


def test_sampled_local_swap_proposals_are_unique_deterministic_and_legal():
    base, patterns = fixture()
    arch = generate_architecture(base, 2, "P", patterns)
    first = sampled_local_swaps(arch, 10)
    assert first == sampled_local_swaps(arch, 10)
    assert len({(item["chain"], item["i"], item["j"]) for item in first}) == 10
    for operation in first:
        child, record = apply_intervention(arch, operation)
        assert child.sha256() == record["child_sha256"]
