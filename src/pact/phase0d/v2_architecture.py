"""Mutable integer scan architecture for sparse, reversible local search.

The public repository format remains :class:`ScanArchitecture`.  This module is
an inner-loop representation: one predecessor and successor slot per FF, one
chain-id slot per FF, and O(K) endpoint arrays.  Local moves modify only touched
slots and return a transaction that can be rolled back without copying N FFs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Iterable, Sequence

import numpy as np

from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan


NONE = -1
INPUT = -1
OUTPUT = -2
MASK64 = (1 << 64) - 1
Arc = tuple[int, int, int]


def _mix64(value: int) -> int:
    """Deterministic SplitMix64 finalizer used for an incremental 128-bit key."""
    value &= MASK64
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & MASK64
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & MASK64
    return value ^ (value >> 31)


def _arc_token(arc: Arc) -> int:
    chain, left, right = arc
    packed = ((chain + 1) * 0x9E3779B185EBCA87
              ^ (left + 3) * 0xC2B2AE3D27D4EB4F
              ^ (right + 5) * 0x165667B19E3779F9)
    low = _mix64(packed)
    high = _mix64(packed ^ 0xD6E8FEB86659FD93)
    return low | (high << 64)


@dataclass
class ArchitecturePatch:
    """Undo log and exact changed-arc description for one local move."""

    kind: str
    affected_chains: tuple[int, ...]
    before_orders: dict[int, tuple[int, ...]]
    hash_before: int
    changes: list[tuple[str, int, int]] = field(default_factory=list)
    changed_slots: set[tuple[str, int]] = field(default_factory=set)
    removed_arcs: tuple[Arc, ...] = ()
    added_arcs: tuple[Arc, ...] = ()
    physical_delta: float = 0.0
    hash_after: int = 0


class MutableScanArchitecture:
    """Integer linked-chain representation with transactional local moves.

    Lookup of predecessor, successor and chain membership is O(1). Relocation
    and adjacent/non-adjacent swaps are O(1); reversal and segment exchange are
    O(segment length), because explicit links and chain membership are updated.
    Reconstruction and a full validity check are O(N). The incremental key is
    O(number of changed directed arcs); the canonical boundary SHA remains O(N).
    """

    def __init__(
        self,
        base: ScanArchitecture,
        names: tuple[str, ...],
        predecessor: np.ndarray,
        successor: np.ndarray,
        chain_of: np.ndarray,
        heads: np.ndarray,
        tails: np.ndarray,
        lengths: np.ndarray,
    ) -> None:
        self.base = base
        self.names = names
        self.index = {name: index for index, name in enumerate(names)}
        self.predecessor = np.asarray(predecessor, dtype=np.int32)
        self.successor = np.asarray(successor, dtype=np.int32)
        self.chain_of = np.asarray(chain_of, dtype=np.int32)
        self.heads = np.asarray(heads, dtype=np.int32)
        self.tails = np.asarray(tails, dtype=np.int32)
        self.lengths = np.asarray(lengths, dtype=np.int32)
        self.architecture_key = self._full_key()

    @classmethod
    def from_scan_architecture(cls, architecture: ScanArchitecture) -> "MutableScanArchitecture":
        validate_scan(architecture)
        names = tuple(cell.name for cell in architecture.cells)
        index = {name: i for i, name in enumerate(names)}
        n, k = len(names), len(architecture.chains)
        predecessor = np.full(n, NONE, dtype=np.int32)
        successor = np.full(n, NONE, dtype=np.int32)
        chain_of = np.full(n, NONE, dtype=np.int32)
        heads = np.full(k, NONE, dtype=np.int32)
        tails = np.full(k, NONE, dtype=np.int32)
        lengths = np.zeros(k, dtype=np.int32)
        for ci, chain in enumerate(architecture.chains):
            order = [index[name] for name in chain.cells]
            heads[ci], tails[ci], lengths[ci] = order[0], order[-1], len(order)
            for position, node in enumerate(order):
                chain_of[node] = ci
                predecessor[node] = order[position - 1] if position else NONE
                successor[node] = order[position + 1] if position + 1 < len(order) else NONE
        return cls(architecture, names, predecessor, successor, chain_of, heads, tails, lengths)

    @classmethod
    def from_orders(cls, base: ScanArchitecture, orders: Sequence[Sequence[int]]) -> "MutableScanArchitecture":
        names = tuple(cell.name for cell in base.cells)
        flat = [int(node) for order in orders for node in order]
        if len(orders) != len(base.chains) or sorted(flat) != list(range(len(names))):
            raise ValueError("Orders must contain every FF exactly once in exactly K nonempty chains")
        if any(not order for order in orders):
            raise ValueError("Empty scan chains are not supported")
        n, k = len(names), len(orders)
        predecessor = np.full(n, NONE, dtype=np.int32)
        successor = np.full(n, NONE, dtype=np.int32)
        chain_of = np.full(n, NONE, dtype=np.int32)
        heads = np.empty(k, dtype=np.int32)
        tails = np.empty(k, dtype=np.int32)
        lengths = np.empty(k, dtype=np.int32)
        for ci, raw in enumerate(orders):
            order = [int(node) for node in raw]
            heads[ci], tails[ci], lengths[ci] = order[0], order[-1], len(order)
            for position, node in enumerate(order):
                chain_of[node] = ci
                predecessor[node] = order[position - 1] if position else NONE
                successor[node] = order[position + 1] if position + 1 < len(order) else NONE
        return cls(base, names, predecessor, successor, chain_of, heads, tails, lengths)

    @property
    def cell_count(self) -> int:
        return len(self.names)

    @property
    def chain_count(self) -> int:
        return len(self.heads)

    def order(self, chain: int) -> tuple[int, ...]:
        result: list[int] = []
        node = int(self.heads[chain])
        while node != NONE:
            result.append(node)
            node = int(self.successor[node])
            if len(result) > self.cell_count:
                raise AssertionError("Cycle in scan-chain links")
        if len(result) != int(self.lengths[chain]):
            raise AssertionError("Chain length metadata mismatch")
        return tuple(result)

    def orders(self) -> tuple[tuple[int, ...], ...]:
        return tuple(self.order(chain) for chain in range(self.chain_count))

    def to_scan_architecture(self) -> ScanArchitecture:
        chains = tuple(
            ScanChain(
                meta.chain_id,
                tuple(self.names[node] for node in self.order(ci)),
                meta.scan_in,
                meta.scan_out,
            )
            for ci, meta in enumerate(self.base.chains)
        )
        result = ScanArchitecture(self.base.cells, chains)
        validate_scan(result)
        return result

    def canonical_digest(self) -> str:
        """Compact exact digest of chain order, without serializing cell metadata."""
        digest = hashlib.sha256()
        for ci in range(self.chain_count):
            digest.update(ci.to_bytes(4, "little"))
            for node in self.order(ci):
                digest.update(node.to_bytes(4, "little"))
            digest.update(b"\xff\xff\xff\xff")
        return digest.hexdigest()

    def _arcs_for_chain(self, chain: int) -> Iterable[Arc]:
        node = int(self.heads[chain])
        yield chain, INPUT, node
        while int(self.successor[node]) != NONE:
            nxt = int(self.successor[node])
            yield chain, node, nxt
            node = nxt
        yield chain, node, OUTPUT

    def all_arcs(self) -> tuple[Arc, ...]:
        return tuple(arc for chain in range(self.chain_count) for arc in self._arcs_for_chain(chain))

    def _full_key(self) -> int:
        result = 0
        for arc in self.all_arcs():
            result ^= _arc_token(arc)
        return result

    def _incident_arcs(self, nodes: Iterable[int]) -> set[Arc]:
        result: set[Arc] = set()
        for raw in nodes:
            node = int(raw)
            if node < 0:
                continue
            chain = int(self.chain_of[node])
            if chain < 0:
                continue
            predecessor = int(self.predecessor[node])
            successor = int(self.successor[node])
            result.add((chain, predecessor if predecessor != NONE else INPUT, node))
            result.add((chain, node, successor if successor != NONE else OUTPUT))
        return result

    def _write(self, patch: ArchitecturePatch, array_name: str, index: int, value: int) -> None:
        array = getattr(self, array_name)
        key = (array_name, int(index))
        if key not in patch.changed_slots:
            patch.changed_slots.add(key)
            patch.changes.append((array_name, int(index), int(array[index])))
        array[index] = value

    def _new_patch(self, kind: str, chains: Iterable[int]) -> ArchitecturePatch:
        affected = tuple(sorted(set(map(int, chains))))
        return ArchitecturePatch(
            kind=kind,
            affected_chains=affected,
            before_orders={chain: self.order(chain) for chain in affected},
            hash_before=self.architecture_key,
        )

    def _finish_patch(self, patch: ArchitecturePatch, before_arcs: set[Arc], nodes: set[int], physical) -> ArchitecturePatch:
        # Compare the same endpoint set before and after. ``nodes`` already
        # includes every moved item and its boundary neighbors; expanding only
        # after mutation would spuriously classify unrelated outer arcs as new.
        after_arcs = self._incident_arcs(nodes)
        removed = tuple(sorted(before_arcs - after_arcs))
        added = tuple(sorted(after_arcs - before_arcs))
        patch.removed_arcs, patch.added_arcs = removed, added
        patch.physical_delta = (
            sum(physical.arc_cost(arc) for arc in added)
            - sum(physical.arc_cost(arc) for arc in removed)
        )
        key = patch.hash_before
        for arc in removed:
            key ^= _arc_token(arc)
        for arc in added:
            key ^= _arc_token(arc)
        patch.hash_after = key
        self.architecture_key = key
        return patch

    def rollback(self, patch: ArchitecturePatch) -> None:
        for array_name, index, old_value in reversed(patch.changes):
            getattr(self, array_name)[index] = old_value
        self.architecture_key = patch.hash_before

    def _seed_with_neighbors(self, nodes: Iterable[int]) -> set[int]:
        result = {int(node) for node in nodes if int(node) >= 0}
        for node in tuple(result):
            result.add(int(self.predecessor[node]))
            result.add(int(self.successor[node]))
        return result

    def relocate(self, node: int, target_chain: int, after: int, physical) -> ArchitecturePatch:
        """Move one FF after ``after``; NONE denotes the target chain head."""
        node, target_chain, after = int(node), int(target_chain), int(after)
        source = int(self.chain_of[node])
        if not 0 <= target_chain < self.chain_count:
            raise ValueError("Invalid target chain")
        if after != NONE and int(self.chain_of[after]) != target_chain:
            raise ValueError("Insertion anchor is not in the target chain")
        if node == after or (source == target_chain and int(self.predecessor[node]) == after):
            raise ValueError("No-op relocation")
        old_pre, old_next = int(self.predecessor[node]), int(self.successor[node])
        target_next = int(self.heads[target_chain]) if after == NONE else int(self.successor[after])
        nodes = self._seed_with_neighbors((node, old_pre, old_next, after, target_next))
        before_arcs = self._incident_arcs(nodes)
        patch = self._new_patch("relocate" if source == target_chain else "migration", (source, target_chain))

        if old_pre == NONE:
            self._write(patch, "heads", source, old_next)
        else:
            self._write(patch, "successor", old_pre, old_next)
        if old_next == NONE:
            self._write(patch, "tails", source, old_pre)
        else:
            self._write(patch, "predecessor", old_next, old_pre)
        self._write(patch, "lengths", source, int(self.lengths[source]) - 1)

        # The anchor may have been followed by the relocated node.
        if source == target_chain and after != NONE:
            target_next = int(self.successor[after])
        elif source == target_chain and after == NONE:
            target_next = int(self.heads[target_chain])
        if after == NONE:
            self._write(patch, "heads", target_chain, node)
        else:
            self._write(patch, "successor", after, node)
        self._write(patch, "predecessor", node, after)
        self._write(patch, "successor", node, target_next)
        if target_next == NONE:
            self._write(patch, "tails", target_chain, node)
        else:
            self._write(patch, "predecessor", target_next, node)
        self._write(patch, "chain_of", node, target_chain)
        self._write(patch, "lengths", target_chain, int(self.lengths[target_chain]) + 1)
        return self._finish_patch(patch, before_arcs, nodes, physical)

    def swap(self, first: int, second: int, physical) -> ArchitecturePatch:
        first, second = int(first), int(second)
        if first == second:
            raise ValueError("Swap requires distinct FFs")
        first_chain, second_chain = int(self.chain_of[first]), int(self.chain_of[second])
        pf, nf = int(self.predecessor[first]), int(self.successor[first])
        ps, ns = int(self.predecessor[second]), int(self.successor[second])
        nodes = self._seed_with_neighbors((first, second, pf, nf, ps, ns))
        before_arcs = self._incident_arcs(nodes)
        patch = self._new_patch("swap" if first_chain == second_chain else "cross_chain_swap",
                                (first_chain, second_chain))

        if nf == second and first_chain == second_chain:
            self._swap_adjacent(first, second, first_chain, patch)
        elif ns == first and first_chain == second_chain:
            self._swap_adjacent(second, first, first_chain, patch)
        else:
            if pf == NONE:
                self._write(patch, "heads", first_chain, second)
            else:
                self._write(patch, "successor", pf, second)
            if nf == NONE:
                self._write(patch, "tails", first_chain, second)
            else:
                self._write(patch, "predecessor", nf, second)
            if ps == NONE:
                self._write(patch, "heads", second_chain, first)
            else:
                self._write(patch, "successor", ps, first)
            if ns == NONE:
                self._write(patch, "tails", second_chain, first)
            else:
                self._write(patch, "predecessor", ns, first)
            self._write(patch, "predecessor", second, pf)
            self._write(patch, "successor", second, nf)
            self._write(patch, "predecessor", first, ps)
            self._write(patch, "successor", first, ns)
            if first_chain != second_chain:
                self._write(patch, "chain_of", first, second_chain)
                self._write(patch, "chain_of", second, first_chain)
        return self._finish_patch(patch, before_arcs, nodes, physical)

    def _swap_adjacent(self, left: int, right: int, chain: int, patch: ArchitecturePatch) -> None:
        before, after = int(self.predecessor[left]), int(self.successor[right])
        if before == NONE:
            self._write(patch, "heads", chain, right)
        else:
            self._write(patch, "successor", before, right)
        self._write(patch, "predecessor", right, before)
        self._write(patch, "successor", right, left)
        self._write(patch, "predecessor", left, right)
        self._write(patch, "successor", left, after)
        if after == NONE:
            self._write(patch, "tails", chain, left)
        else:
            self._write(patch, "predecessor", after, left)

    def reverse_segment(self, first: int, last: int, physical, maximum_length: int | None = None) -> ArchitecturePatch:
        first, last = int(first), int(last)
        chain = int(self.chain_of[first])
        if int(self.chain_of[last]) != chain or first == last:
            raise ValueError("Reversal endpoints must be distinct and in one chain")
        segment: list[int] = []
        node = first
        while node != NONE:
            segment.append(node)
            if node == last:
                break
            if maximum_length is not None and len(segment) >= maximum_length:
                raise ValueError("Reversal exceeds maximum segment length")
            node = int(self.successor[node])
        if not segment or segment[-1] != last:
            raise ValueError("Reversal endpoints are not in forward order")
        before, after = int(self.predecessor[first]), int(self.successor[last])
        nodes = self._seed_with_neighbors((*segment, before, after))
        before_arcs = self._incident_arcs(nodes)
        patch = self._new_patch("two_opt", (chain,))
        old_links = [(int(self.predecessor[item]), int(self.successor[item])) for item in segment]
        for item, (old_pre, old_succ) in zip(segment, old_links):
            self._write(patch, "predecessor", item, old_succ)
            self._write(patch, "successor", item, old_pre)
        if before == NONE:
            self._write(patch, "heads", chain, last)
        else:
            self._write(patch, "successor", before, last)
        self._write(patch, "predecessor", last, before)
        if after == NONE:
            self._write(patch, "tails", chain, first)
        else:
            self._write(patch, "predecessor", after, first)
        self._write(patch, "successor", first, after)
        return self._finish_patch(patch, before_arcs, nodes, physical)

    def exchange_segments(self, first_a: int, last_a: int, first_b: int, last_b: int,
                          physical, maximum_length: int | None = None) -> ArchitecturePatch:
        segment_a = self._forward_segment(first_a, last_a, maximum_length)
        segment_b = self._forward_segment(first_b, last_b, maximum_length)
        chain_a, chain_b = int(self.chain_of[first_a]), int(self.chain_of[first_b])
        if chain_a == chain_b:
            raise ValueError("Segment exchange requires different chains")
        pa, na = int(self.predecessor[first_a]), int(self.successor[last_a])
        pb, nb = int(self.predecessor[first_b]), int(self.successor[last_b])
        nodes = self._seed_with_neighbors((*segment_a, *segment_b, pa, na, pb, nb))
        before_arcs = self._incident_arcs(nodes)
        patch = self._new_patch("segment_exchange", (chain_a, chain_b))

        self._connect_segment(patch, chain_a, pa, first_b, last_b, na)
        self._connect_segment(patch, chain_b, pb, first_a, last_a, nb)
        for node in segment_a:
            self._write(patch, "chain_of", node, chain_b)
        for node in segment_b:
            self._write(patch, "chain_of", node, chain_a)
        self._write(patch, "lengths", chain_a,
                    int(self.lengths[chain_a]) - len(segment_a) + len(segment_b))
        self._write(patch, "lengths", chain_b,
                    int(self.lengths[chain_b]) - len(segment_b) + len(segment_a))
        return self._finish_patch(patch, before_arcs, nodes, physical)

    def _forward_segment(self, first: int, last: int, maximum_length: int | None) -> list[int]:
        first, last = int(first), int(last)
        chain = int(self.chain_of[first])
        if int(self.chain_of[last]) != chain:
            raise ValueError("Segment endpoints differ in chain")
        result = []
        node = first
        while node != NONE:
            result.append(node)
            if node == last:
                return result
            if maximum_length is not None and len(result) >= maximum_length:
                break
            node = int(self.successor[node])
        raise ValueError("Invalid forward segment")

    def _connect_segment(self, patch: ArchitecturePatch, chain: int, before: int,
                         first: int, last: int, after: int) -> None:
        if before == NONE:
            self._write(patch, "heads", chain, first)
        else:
            self._write(patch, "successor", before, first)
        self._write(patch, "predecessor", first, before)
        if after == NONE:
            self._write(patch, "tails", chain, last)
        else:
            self._write(patch, "predecessor", after, last)
        self._write(patch, "successor", last, after)

    def validate_internal(self) -> None:
        """O(N) integrity check intended for tests and accepted snapshots."""
        seen: list[int] = []
        for chain in range(self.chain_count):
            order = self.order(chain)
            if order[0] != int(self.heads[chain]) or order[-1] != int(self.tails[chain]):
                raise AssertionError("Endpoint mismatch")
            previous = NONE
            for node in order:
                if int(self.predecessor[node]) != previous or int(self.chain_of[node]) != chain:
                    raise AssertionError("Broken predecessor or chain membership")
                previous = node
            seen.extend(order)
        if sorted(seen) != list(range(self.cell_count)):
            raise AssertionError("Duplicate or missing FF")
        if self._full_key() != self.architecture_key:
            raise AssertionError("Incremental architecture key mismatch")


@dataclass(frozen=True)
class ArchitectureSnapshot:
    """A capped-archive snapshot; copies occur only for retained candidates."""

    orders: tuple[tuple[int, ...], ...]
    architecture_key: int

    @classmethod
    def capture(cls, architecture: MutableScanArchitecture) -> "ArchitectureSnapshot":
        return cls(architecture.orders(), architecture.architecture_key)

    def restore(self, base: ScanArchitecture) -> MutableScanArchitecture:
        result = MutableScanArchitecture.from_orders(base, self.orders)
        if result.architecture_key != self.architecture_key:
            raise AssertionError("Snapshot key mismatch")
        return result
