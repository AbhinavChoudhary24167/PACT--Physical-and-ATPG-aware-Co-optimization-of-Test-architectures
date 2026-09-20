"""Bounded, deterministic, legal scan-architecture operators for Phase-0D."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Any, Mapping, Sequence

from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.phase0c import verify_parallel_schedule
from pact.scan.phase0c_interventions import edges
from pact.scan.validate import ScanConstraints, validate_scan


OPERATOR_NAMES = (
    "swap",
    "two_opt",
    "block_relocation",
    "cross_chain_move",
    "cross_chain_swap",
    "endpoint_reassignment",
    "cross_chain_block_move",
)


@dataclass(frozen=True)
class OperatorConstraints:
    minimum_chain_length: int = 8
    maximum_chain_length_difference: int = 2
    maximum_block_length: int = 4


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    legality: str
    generation_complexity: str
    neighborhood_size: str
    balance_effect: str
    changes_K: bool
    requires_SI_SO_recalculation: bool


def operator_catalog() -> dict[str, OperatorSpec]:
    return {
        "swap": OperatorSpec(
            "swap", "two distinct positions in one legal chain", "O(1) apply; O(B) bounded sampling",
            "sum_i binomial(n_i,2)", "none", False, True,
        ),
        "two_opt": OperatorSpec(
            "two_opt", "reverse a nontrivial inclusive segment in one chain", "O(segment length) apply; O(B) sampling",
            "sum_i binomial(n_i,2)", "none", False, True,
        ),
        "block_relocation": OperatorSpec(
            "block_relocation", "remove a bounded contiguous block and reinsert at a position that changes the chain",
            "O(n_i) apply; O(B) sampling", "O(sum_i n_i^2 * L), L is frozen maximum block length",
            "none", False, True,
        ),
        "cross_chain_move": OperatorSpec(
            "cross_chain_move", "move one FF between distinct chains while preserving minimum length and balance bound",
            "O(n_i+n_j) apply; O(B) sampling", "sum_(i!=j) n_i(n_j+1), before legality filtering",
            "changes two chain lengths by one", False, True,
        ),
        "cross_chain_swap": OperatorSpec(
            "cross_chain_swap", "exchange one FF in each of two distinct chains",
            "O(1) apply; O(B) sampling", "sum_(i<j) n_i*n_j", "none", False, True,
        ),
        "endpoint_reassignment": OperatorSpec(
            "endpoint_reassignment", "exchange an SI- or SO-adjacent FF with a nonidentical position in the same chain",
            "O(1) apply; O(B) sampling", "sum_i 2(n_i-1)", "none", False, True,
        ),
        "cross_chain_block_move": OperatorSpec(
            "cross_chain_block_move", "move a bounded contiguous block between chains while preserving minimum length and balance bound",
            "O(n_i+n_j) apply; O(B) sampling", "O(sum_(i!=j) n_i*n_j*L), before legality filtering",
            "changes two chain lengths by block length", False, True,
        ),
    }


def _validate_phase0d(arch: ScanArchitecture, constraints: OperatorConstraints) -> None:
    validate_scan(arch, ScanConstraints(min_chain_length=constraints.minimum_chain_length))
    lengths = [len(chain.cells) for chain in arch.chains]
    if max(lengths) - min(lengths) > constraints.maximum_chain_length_difference:
        raise ValueError(f"Chain balance bound exceeded: {lengths}")


def _checked_index(value: Any, size: int, label: str, allow_end: bool = False) -> int:
    index = int(value)
    upper = size if allow_end else size - 1
    if not 0 <= index <= upper:
        raise ValueError(f"Invalid {label}: {index}")
    return index


def _endpoint_cells(groups: Sequence[Sequence[str]]) -> set[str]:
    return {name for group in groups for name in (group[0], group[-1])}


def apply_operator(
    arch: ScanArchitecture,
    operation: Mapping[str, Any],
    constraints: OperatorConstraints = OperatorConstraints(),
) -> tuple[ScanArchitecture, dict[str, Any]]:
    """Apply one operation and return the child plus a complete legality record."""
    _validate_phase0d(arch, constraints)
    kind = str(operation.get("type"))
    if kind not in OPERATOR_NAMES:
        raise ValueError(f"Unknown Phase-0D operator: {kind}")
    groups = [list(chain.cells) for chain in arch.chains]
    before_groups = [group.copy() for group in groups]
    affected: list[str] = []

    if kind in {"swap", "two_opt", "block_relocation", "endpoint_reassignment"}:
        chain = _checked_index(operation.get("chain"), len(groups), "chain")
        group = groups[chain]
        if kind == "swap":
            left = _checked_index(operation.get("i"), len(group), "i")
            right = _checked_index(operation.get("j"), len(group), "j")
            if left == right:
                raise ValueError("Swap positions must differ")
            affected = [group[left], group[right]]
            group[left], group[right] = group[right], group[left]
        elif kind == "two_opt":
            left = _checked_index(operation.get("i"), len(group), "i")
            right = _checked_index(operation.get("j"), len(group), "j")
            if left >= right:
                raise ValueError("two_opt requires i < j")
            affected = group[left:right + 1].copy()
            group[left:right + 1] = reversed(group[left:right + 1])
        elif kind == "block_relocation":
            start = _checked_index(operation.get("start"), len(group), "start")
            length = int(operation.get("length"))
            if not 1 <= length <= constraints.maximum_block_length or start + length > len(group):
                raise ValueError("Invalid relocation block")
            block = group[start:start + length]
            del group[start:start + length]
            target = _checked_index(operation.get("to_index"), len(group), "to_index", allow_end=True)
            group[target:target] = block
            affected = block.copy()
        else:
            endpoint = str(operation.get("endpoint", "")).upper()
            if endpoint not in {"SI", "SO"}:
                raise ValueError("endpoint must be SI or SO")
            selected = 0 if endpoint == "SI" else len(group) - 1
            other = _checked_index(operation.get("index"), len(group), "index")
            if selected == other:
                raise ValueError("Endpoint reassignment must change the endpoint FF")
            affected = [group[selected], group[other]]
            group[selected], group[other] = group[other], group[selected]
    else:
        source = _checked_index(operation.get("from_chain"), len(groups), "from_chain")
        target_chain = _checked_index(operation.get("to_chain"), len(groups), "to_chain")
        if source == target_chain:
            raise ValueError("Cross-chain operation requires distinct chains")
        source_group, target_group = groups[source], groups[target_chain]
        if kind == "cross_chain_move":
            index = _checked_index(operation.get("index"), len(source_group), "index")
            target = _checked_index(operation.get("to_index"), len(target_group), "to_index", allow_end=True)
            affected = [source_group.pop(index)]
            target_group.insert(target, affected[0])
        elif kind == "cross_chain_swap":
            left = _checked_index(operation.get("from_index"), len(source_group), "from_index")
            right = _checked_index(operation.get("to_index"), len(target_group), "to_index")
            affected = [source_group[left], target_group[right]]
            source_group[left], target_group[right] = target_group[right], source_group[left]
        else:
            start = _checked_index(operation.get("start"), len(source_group), "start")
            length = int(operation.get("length"))
            if not 1 <= length <= constraints.maximum_block_length or start + length > len(source_group):
                raise ValueError("Invalid cross-chain block")
            target = _checked_index(operation.get("to_index"), len(target_group), "to_index", allow_end=True)
            block = source_group[start:start + length]
            del source_group[start:start + length]
            target_group[target:target] = block
            affected = block.copy()

    if groups == before_groups:
        raise ValueError("No-op intervention")
    child = ScanArchitecture(
        arch.cells,
        tuple(
            ScanChain(chain.chain_id, tuple(group), chain.scan_in, chain.scan_out)
            for chain, group in zip(arch.chains, groups)
        ),
    )
    _validate_phase0d(child, constraints)
    if child.sha256() == arch.sha256():
        raise ValueError("No-op intervention")
    removed, added = edges(arch) - edges(child), edges(child) - edges(arch)
    record = {
        "schema_version": "phase0d-operator-record-1",
        "type": kind,
        "operation": dict(operation),
        "affected_FFs": affected,
        "removed_edges": sorted(removed),
        "added_edges": sorted(added),
        "parent_sha256": arch.sha256(),
        "child_sha256": child.sha256(),
        "chain_lengths_before": [len(group) for group in before_groups],
        "chain_lengths_after": [len(group) for group in groups],
        "changes_K": False,
        "requires_SI_SO_recalculation": _endpoint_cells(before_groups) != _endpoint_cells(groups),
        "legal": True,
        "constraints": asdict(constraints),
    }
    return child, record


def _rng_for(arch: ScanArchitecture, operator: str, proposal_seed: int, round_index: int) -> random.Random:
    material = json.dumps(
        ["PACT_PHASE0D_PROPOSAL", arch.sha256(), operator, proposal_seed, round_index],
        separators=(",", ":"),
    )
    return random.Random(int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big"))


def _random_operation(arch: ScanArchitecture, operator: str, rng: random.Random,
                      constraints: OperatorConstraints) -> dict[str, Any]:
    lengths = [len(chain.cells) for chain in arch.chains]
    if operator in {"swap", "two_opt", "block_relocation", "endpoint_reassignment"}:
        chain = rng.randrange(len(lengths))
        length = lengths[chain]
        if operator == "swap":
            left, right = rng.sample(range(length), 2)
            return {"type": operator, "chain": chain, "i": left, "j": right}
        if operator == "two_opt":
            left, right = sorted(rng.sample(range(length), 2))
            return {"type": operator, "chain": chain, "i": left, "j": right}
        if operator == "block_relocation":
            block_length = rng.randint(1, min(constraints.maximum_block_length, length - 1))
            start = rng.randrange(length - block_length + 1)
            return {"type": operator, "chain": chain, "start": start, "length": block_length,
                    "to_index": rng.randrange(length - block_length + 1)}
        endpoint = rng.choice(("SI", "SO"))
        endpoint_index = 0 if endpoint == "SI" else length - 1
        choices = [index for index in range(length) if index != endpoint_index]
        return {"type": operator, "chain": chain, "endpoint": endpoint, "index": rng.choice(choices)}

    if len(lengths) < 2:
        raise ValueError(f"{operator} requires K >= 2")
    source, target = rng.sample(range(len(lengths)), 2)
    if operator == "cross_chain_move":
        return {"type": operator, "from_chain": source, "to_chain": target,
                "index": rng.randrange(lengths[source]), "to_index": rng.randrange(lengths[target] + 1)}
    if operator == "cross_chain_swap":
        return {"type": operator, "from_chain": source, "to_chain": target,
                "from_index": rng.randrange(lengths[source]), "to_index": rng.randrange(lengths[target])}
    block_length = rng.randint(1, min(constraints.maximum_block_length,
                                      lengths[source] - constraints.minimum_chain_length))
    return {"type": operator, "from_chain": source, "to_chain": target,
            "start": rng.randrange(lengths[source] - block_length + 1), "length": block_length,
            "to_index": rng.randrange(lengths[target] + 1)}


def sample_operations(
    arch: ScanArchitecture,
    count: int,
    proposal_seed: int,
    round_index: int = 0,
    operators: Sequence[str] = OPERATOR_NAMES,
    constraints: OperatorConstraints = OperatorConstraints(),
) -> list[dict[str, Any]]:
    """Sample at most ``count`` unique legal operations without enumerating neighborhoods."""
    _validate_phase0d(arch, constraints)
    if count < 0:
        raise ValueError("count must be nonnegative")
    names = tuple(name for name in operators if name in OPERATOR_NAMES)
    if len(names) != len(operators) or not names:
        raise ValueError("Unknown or empty operator selection")
    if len(arch.chains) < 2:
        names = tuple(name for name in names if not name.startswith("cross_chain"))
    results: list[dict[str, Any]] = []
    seen_children: set[str] = set()
    per_operator_attempts = max(64, count * 32)
    cursor = 0
    while len(results) < count and cursor < count * len(names) * 4 + len(names):
        operator = names[cursor % len(names)]
        rng = _rng_for(arch, operator, proposal_seed, round_index + cursor // len(names))
        for _ in range(per_operator_attempts):
            try:
                operation = _random_operation(arch, operator, rng, constraints)
                child, _ = apply_operator(arch, operation, constraints)
            except (ValueError, IndexError):
                continue
            if child.sha256() in seen_children:
                continue
            seen_children.add(child.sha256())
            results.append(operation)
            break
        cursor += 1
    if len(results) < count:
        raise ValueError(f"Only {len(results)} unique legal operations available for requested count {count}")
    return results


def structural_proof(
    parent: ScanArchitecture,
    child: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]] = (),
    constraints: OperatorConstraints = OperatorConstraints(),
) -> dict[str, Any]:
    """Prove invariant preservation and, when supplied, every frozen ATPG target."""
    _validate_phase0d(parent, constraints)
    _validate_phase0d(child, constraints)
    parent_cells = {cell.name: cell for cell in parent.cells}
    child_cells = {cell.name: cell for cell in child.cells}
    if parent_cells != child_cells:
        raise ValueError("FF identity or placement changed")
    if len(parent.chains) != len(child.chains):
        raise ValueError("K changed")
    if [(chain.chain_id, chain.scan_in, chain.scan_out) for chain in parent.chains] != [
        (chain.chain_id, chain.scan_in, chain.scan_out) for chain in child.chains
    ]:
        raise ValueError("SI/SO identities changed")
    for pattern in patterns:
        verify_parallel_schedule(child, pattern)
    proof = {
        "schema_version": "phase0d-structural-proof-1",
        "parent_sha256": parent.sha256(),
        "child_sha256": child.sha256(),
        "FF_inventory_verified": True,
        "FF_identity_and_placement_unchanged": True,
        "K_fixed": True,
        "SI_SO_identity_verified": True,
        "ATPG_patterns_verified": len(patterns),
        "exact_parallel_loading_verified": bool(patterns),
        "leading_padding_semantics": "tail-first target bits with fully clocked leading zero padding",
        "chain_lengths": [len(chain.cells) for chain in child.chains],
    }
    proof["proof_sha256"] = hashlib.sha256(
        json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return proof


def neighborhood_sizes(arch: ScanArchitecture, maximum_block_length: int = 4) -> dict[str, int]:
    """Return documented pre-legality neighborhood sizes without generating candidates."""
    lengths = [len(chain.cells) for chain in arch.chains]
    within_pairs = sum(math.comb(length, 2) for length in lengths)
    block_relocations = sum(
        sum((length - block + 1) * (length - block + 1) for block in range(1, min(maximum_block_length, length) + 1))
        for length in lengths
    )
    directed_pairs = [(left, right) for left in range(len(lengths)) for right in range(len(lengths)) if left != right]
    return {
        "swap": within_pairs,
        "two_opt": within_pairs,
        "block_relocation": block_relocations,
        "cross_chain_move": sum(lengths[left] * (lengths[right] + 1) for left, right in directed_pairs),
        "cross_chain_swap": sum(lengths[left] * lengths[right] for left in range(len(lengths)) for right in range(left + 1, len(lengths))),
        "endpoint_reassignment": sum(2 * (length - 1) for length in lengths),
        "cross_chain_block_move": sum(
            sum((lengths[left] - block + 1) * (lengths[right] + 1)
                for block in range(1, min(maximum_block_length, lengths[left]) + 1))
            for left, right in directed_pairs
        ),
    }
