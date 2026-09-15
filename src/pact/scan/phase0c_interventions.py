"""Legal, hash-addressable local scan interventions."""
from __future__ import annotations

import hashlib

from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan


def edges(arch: ScanArchitecture) -> set[tuple[str, str]]:
    return {(left, right) for chain in arch.chains
            for left, right in zip((f"SI:{chain.chain_id}",) + chain.cells,
                                   chain.cells + (f"SO:{chain.chain_id}",))}


def sampled_local_swaps(arch: ScanArchitecture, count: int,
                        proposal_seed: int = 101) -> list[dict]:
    """Fixed position-pair proposals, independent of physical-seed randomness."""
    candidates = []
    for ci, chain in enumerate(arch.chains):
        n = len(chain.cells)
        radius = max(2, n // 10)
        for i in range(n):
            for j in range(i + 1, min(n, i + radius + 1)):
                operation = {"type": "swap", "chain": ci, "i": i, "j": j}
                label = f"phase0c-{proposal_seed}-swap-{ci}-{i}-{j}"
                candidates.append((hashlib.sha256(label.encode()).digest(), operation))
    candidates.sort(key=lambda item: item[0])
    if len(candidates) < count:
        raise ValueError("Not enough distinct legal local swaps")
    return [operation for _, operation in candidates[:count]]


def apply_intervention(arch: ScanArchitecture, operation: dict) -> tuple[ScanArchitecture, dict]:
    validate_scan(arch)
    kind = operation["type"]
    groups = [list(chain.cells) for chain in arch.chains]
    c = int(operation.get("chain", 0))
    affected: list[str]
    if not 0 <= c < len(groups):
        raise ValueError("Invalid chain index")
    if kind == "swap":
        i, j = int(operation["i"]), int(operation["j"])
        affected = [groups[c][i], groups[c][j]]
        groups[c][i], groups[c][j] = groups[c][j], groups[c][i]
    elif kind in ("segment_reversal", "two_opt"):
        i, j = int(operation["i"]), int(operation["j"])
        if not 0 <= i < j < len(groups[c]):
            raise ValueError("Invalid reversal segment")
        affected = groups[c][i:j + 1].copy()
        groups[c][i:j + 1] = reversed(groups[c][i:j + 1])
    elif kind in ("relocate", "chain_rebalance"):
        other = int(operation["to_chain"])
        if other == c or not 0 <= other < len(groups) or len(groups[c]) <= 1:
            raise ValueError("Invalid relocation")
        i, j = int(operation["i"]), int(operation["to_index"])
        if kind == "chain_rebalance" and len(groups[c]) <= len(groups[other]):
            raise ValueError("Rebalance must move from longer to shorter chain")
        name = groups[c].pop(i)
        groups[other].insert(j, name)
        affected = [name]
    elif kind == "cross_chain_exchange":
        other = int(operation["other_chain"])
        if other == c or not 0 <= other < len(groups):
            raise ValueError("Invalid exchange")
        i, j = int(operation["i"]), int(operation["j"])
        affected = [groups[c][i], groups[other][j]]
        groups[c][i], groups[other][j] = groups[other][j], groups[c][i]
    else:
        raise ValueError(f"Unknown intervention: {kind}")
    child = ScanArchitecture(arch.cells, tuple(ScanChain(chain.chain_id, tuple(group), chain.scan_in, chain.scan_out)
                                              for chain, group in zip(arch.chains, groups)))
    validate_scan(child)
    if child.sha256() == arch.sha256():
        raise ValueError("No-op intervention")
    removed, added = edges(arch) - edges(child), edges(child) - edges(arch)
    return child, {"type": kind, "operation": operation,
                   "affected_FFs": affected,
                   "removed_edges": sorted(removed), "added_edges": sorted(added),
                   "parent_sha256": arch.sha256(), "child_sha256": child.sha256(),
                   "legal": True}
