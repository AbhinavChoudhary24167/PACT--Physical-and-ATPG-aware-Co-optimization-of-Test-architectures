"""Exact chain-incremental H_eff8 evaluation for Optimizer-v2.

H_eff8 is not a local edge sum. A local order change can alter every cycle at
every FF in an affected chain. It is nevertheless separable by chain before the
final spatial maximum: scan chains shift independently, spatial accumulation
and convolution are linear, and every pattern finishes at the architecture-
independent ATPG target state. V2 therefore recomputes complete affected-chain
cycle/bin fields and updates the retained global field exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy.ndimage import convolve
from scipy.linalg import toeplitz

from pact.physical.grid_metrics import placement_grid
from pact.scan.model import ScanArchitecture


def _kernel() -> np.ndarray:
    kernel = np.zeros((1, 3, 3), dtype=np.float64)
    for row in range(-1, 2):
        for col in range(-1, 2):
            kernel[0, row + 1, col + 1] = 1.0 / (1 + abs(row) + abs(col))
    return kernel


@dataclass
class HEffState:
    longest_chain: int
    chain_fields: list[np.ndarray]
    global_field: np.ndarray
    value: float


@dataclass
class HEffCandidate:
    value: float
    delta_field: np.ndarray | None
    replacements: dict[int, np.ndarray]
    full_state: HEffState | None = None


class IncrementalHEff8:
    """Authoritative H_eff8 evaluator with exact affected-chain updates."""

    def __init__(self, architecture: ScanArchitecture,
                 patterns: Sequence[Mapping[str, int]], weights: Mapping[str, int]) -> None:
        self.names = tuple(cell.name for cell in architecture.cells)
        self.index = {name: index for index, name in enumerate(self.names)}
        if not patterns:
            raise ValueError("At least one ATPG pattern is required")
        if set(weights) != set(self.names):
            raise ValueError("Weight and FF sets differ")
        self.patterns = np.asarray(
            [[int(pattern[name]) for name in self.names] for pattern in patterns], dtype=np.uint8
        )
        if np.any((self.patterns != 0) & (self.patterns != 1)):
            raise ValueError("Patterns must be binary")
        self.weights = np.asarray([weights[name] for name in self.names], dtype=np.float64)
        if np.any(self.weights < 1):
            raise ValueError("Positive direct-sink weights are required")
        grid = placement_grid(architecture.cells, 8)
        self.bins = np.asarray(
            [np.ravel_multi_index(grid.bin_for(cell.x_um, cell.y_um), (8, 8))
             for cell in architecture.cells],
            dtype=np.int32,
        )
        self.kernel = _kernel()
        self.incremental_evaluations = 0
        self.full_evaluations = 0

    @property
    def pattern_count(self) -> int:
        return int(self.patterns.shape[0])

    def _chain_field(self, order: Sequence[int], longest: int) -> np.ndarray:
        """Return this chain's exact convolved weighted field for every cycle."""
        ordered = np.asarray(order, dtype=np.int32)
        length = len(ordered)
        if length < 1 or length > longest:
            raise ValueError("Invalid chain length")
        total_cycles = self.pattern_count * longest
        raw = np.zeros((total_cycles, 64), dtype=np.float64)
        ordered_bins = self.bins[ordered]
        ordered_weights = self.weights[ordered]
        bin_mapping = np.zeros((length, 64), dtype=np.float64)
        bin_mapping[np.arange(length), ordered_bins] = ordered_weights
        row = 0
        padding = longest - length
        initial = np.zeros(length, dtype=np.uint8)
        for pattern in self.patterns:
            target = pattern[ordered]
            stream = np.zeros(longest, dtype=np.uint8)
            stream[padding:] = target[::-1]
            # before[t,j] is initial[j-t] for j>=t and stream[t-j-1]
            # otherwise. This is exactly a Toeplitz matrix, avoiding a Python
            # loop over every shift cycle while preserving the recurrence.
            first_column = np.concatenate((initial[:1], stream[:-1]))
            before = toeplitz(first_column, initial).astype(np.uint8, copy=False)
            toggles = np.empty_like(before)
            toggles[:, 0] = before[:, 0] ^ stream
            if length > 1:
                toggles[:, 1:] = before[:, 1:] ^ before[:, :-1]
            raw[row:row + longest] = toggles @ bin_mapping
            row += longest
            final = np.concatenate((stream[-min(longest, length):][::-1], initial))[:length]
            if not np.array_equal(final, target):
                raise AssertionError("Incremental chain simulation did not load target")
            initial = target
        return convolve(raw.reshape(total_cycles, 8, 8), self.kernel,
                        mode="constant", cval=0.0).reshape(total_cycles, 64)

    def full_state(self, orders: Sequence[Sequence[int]]) -> HEffState:
        self.full_evaluations += 1
        longest = max(map(len, orders))
        fields = [self._chain_field(order, longest) for order in orders]
        global_field = np.zeros_like(fields[0])
        for field in fields:
            global_field += field
        return HEffState(longest, fields, global_field, float(global_field.max(initial=0.0)))

    def evaluate(self, state: HEffState, before_orders: Mapping[int, Sequence[int]],
                 after_orders: Mapping[int, Sequence[int]], chain_lengths: Sequence[int],
                 all_orders: Sequence[Sequence[int]] | None = None) -> HEffCandidate:
        new_longest = max(map(int, chain_lengths))
        if new_longest != state.longest_chain:
            # Leading-zero alignment changed for every chain; exact global
            # reevaluation is required and explicitly counted.
            if all_orders is None:
                raise ValueError("All chain orders are required when Lmax changes")
            full = self.full_state(all_orders)
            return HEffCandidate(full.value, None, {}, full)
        self.incremental_evaluations += 1
        delta = np.zeros_like(state.global_field)
        replacements: dict[int, np.ndarray] = {}
        for chain, after in after_orders.items():
            if tuple(before_orders[chain]) == tuple(after):
                continue
            field = self._chain_field(after, state.longest_chain)
            replacements[int(chain)] = field
            delta += field - state.chain_fields[int(chain)]
        peak = 0.0
        # Avoid allocating another complete T x 64 candidate field merely to
        # compute a scalar global maximum.
        for start in range(0, len(delta), 256):
            stop = min(len(delta), start + 256)
            peak = max(peak, float(np.max(state.global_field[start:stop] + delta[start:stop], initial=0.0)))
        return HEffCandidate(peak, delta, replacements)

    @staticmethod
    def accept(state: HEffState, candidate: HEffCandidate) -> HEffState:
        if candidate.full_state is not None:
            return candidate.full_state
        if candidate.delta_field is None:
            raise AssertionError("Incremental candidate lacks a delta field")
        state.global_field += candidate.delta_field
        for chain, field in candidate.replacements.items():
            state.chain_fields[chain] = field
        state.value = candidate.value
        return state

    @staticmethod
    def memory_bytes(state: HEffState) -> int:
        return int(state.global_field.nbytes + sum(field.nbytes for field in state.chain_fields))
