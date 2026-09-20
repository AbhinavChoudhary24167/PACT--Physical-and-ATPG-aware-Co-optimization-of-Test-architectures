from __future__ import annotations

import pytest

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.scan.phase0d_operators import (
    OPERATOR_NAMES,
    OperatorConstraints,
    apply_operator,
    neighborhood_sizes,
    operator_catalog,
    sample_operations,
    structural_proof,
)


def balanced_arch() -> ScanArchitecture:
    names = tuple(f"f{i:02d}" for i in range(20))
    cells = tuple(ScanCell(name, float(i % 5), float(i // 5), "CK") for i, name in enumerate(names))
    return ScanArchitecture(cells, (
        ScanChain("C00", names[:10], "test_si_0", "test_so_0"),
        ScanChain("C01", names[10:], "test_si_1", "test_so_1"),
    ))


OPERATIONS = (
    {"type": "swap", "chain": 0, "i": 1, "j": 7},
    {"type": "two_opt", "chain": 0, "i": 2, "j": 6},
    {"type": "block_relocation", "chain": 0, "start": 2, "length": 3, "to_index": 6},
    {"type": "cross_chain_move", "from_chain": 0, "to_chain": 1, "index": 3, "to_index": 5},
    {"type": "cross_chain_swap", "from_chain": 0, "to_chain": 1, "from_index": 3, "to_index": 5},
    {"type": "endpoint_reassignment", "chain": 0, "endpoint": "SI", "index": 4},
    {"type": "cross_chain_block_move", "from_chain": 0, "to_chain": 1, "start": 3, "length": 1, "to_index": 5},
)


@pytest.mark.parametrize("operation", OPERATIONS, ids=[operation["type"] for operation in OPERATIONS])
def test_each_rich_operator_preserves_invariants(operation) -> None:
    parent = balanced_arch()
    child, record = apply_operator(parent, operation)
    assert record["legal"] is True
    assert record["changes_K"] is False
    assert record["child_sha256"] == child.sha256()
    assert record["removed_edges"] and record["added_edges"]
    assert sorted(name for chain in child.chains for name in chain.cells) == sorted(cell.name for cell in parent.cells)
    assert max(record["chain_lengths_after"]) - min(record["chain_lengths_after"]) <= 2


def test_operator_metadata_is_complete() -> None:
    catalog = operator_catalog()
    assert tuple(catalog) == OPERATOR_NAMES
    for spec in catalog.values():
        assert spec.legality and spec.generation_complexity and spec.neighborhood_size
        assert spec.changes_K is False


def test_sampling_is_bounded_unique_deterministic_and_covers_every_operator() -> None:
    arch = balanced_arch()
    first = sample_operations(arch, 14, proposal_seed=101)
    second = sample_operations(arch, 14, proposal_seed=101)
    assert first == second
    assert set(operation["type"] for operation in first) == set(OPERATOR_NAMES)
    children = [apply_operator(arch, operation)[0].sha256() for operation in first]
    assert len(children) == len(set(children)) == 14


def test_structural_proof_checks_exact_patterns() -> None:
    parent = balanced_arch()
    child, _ = apply_operator(parent, OPERATIONS[1])
    patterns = [
        {cell.name: (index + offset) % 2 for index, cell in enumerate(parent.cells)}
        for offset in range(2)
    ]
    proof = structural_proof(parent, child, patterns)
    assert proof["ATPG_patterns_verified"] == 2
    assert proof["exact_parallel_loading_verified"] is True
    assert len(proof["proof_sha256"]) == 64


def test_illegal_balance_and_no_op_are_rejected() -> None:
    parent = balanced_arch()
    constraints = OperatorConstraints(maximum_chain_length_difference=2)
    with pytest.raises(ValueError, match="balance"):
        apply_operator(parent, {"type": "cross_chain_block_move", "from_chain": 0, "to_chain": 1,
                                "start": 0, "length": 2, "to_index": 0}, constraints)
    with pytest.raises(ValueError, match="No-op"):
        apply_operator(parent, {"type": "block_relocation", "chain": 0,
                                "start": 2, "length": 2, "to_index": 2}, constraints)


def test_neighborhood_sizes_are_analytical_and_larger_than_sample() -> None:
    sizes = neighborhood_sizes(balanced_arch())
    assert all(sizes[name] > 14 for name in OPERATOR_NAMES)
