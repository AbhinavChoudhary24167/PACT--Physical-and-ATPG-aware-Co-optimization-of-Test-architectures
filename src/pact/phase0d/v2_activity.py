"""Exact tiled H_eff8 evaluation for Optimizer-v2.2.

The authoritative activity field is separable by scan chain before the final
spatial maximum. V2.2 therefore persists only the summed global field ``E``.
For a local move it reconstructs the old and new fields of the affected chains
in bounded pattern tiles, applies their exact difference to ``E`` only after a
candidate is accepted, and reduces tile results in deterministic index order.

``RetainedIncrementalHEff8`` is the frozen v2.1 implementation. It remains
available for qualification and equivalence benchmarks; production uses the
tiled backend below.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Callable, Iterator, Mapping, Sequence, TypeVar

import numpy as np
from scipy.linalg import toeplitz
from scipy.ndimage import convolve
from threadpoolctl import threadpool_limits

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
    """Persistent v2.2 state: one exact global pattern/cycle/bin field."""

    longest_chain: int
    global_field: np.ndarray
    value: float


@dataclass(frozen=True)
class HEffCandidate:
    """A scalar evaluation plus enough immutable data to commit it exactly."""

    value: float
    before_orders: tuple[tuple[int, tuple[int, ...]], ...]
    after_orders: tuple[tuple[int, tuple[int, ...]], ...]
    full_orders: tuple[tuple[int, ...], ...] | None = None


@dataclass
class RetainedHEffState:
    """Frozen v2.1 state retained only for comparison measurements."""

    longest_chain: int
    chain_fields: list[np.ndarray]
    global_field: np.ndarray
    value: float


@dataclass
class RetainedHEffCandidate:
    value: float
    delta_field: np.ndarray | None
    replacements: dict[int, np.ndarray]
    full_state: RetainedHEffState | None = None


class _HEffInputs:
    """Validated immutable arrays shared by both exact backends."""

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
        """Frozen v2.1 whole-pattern implementation."""
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


class RetainedIncrementalHEff8(_HEffInputs):
    """Unchanged per-chain-retained v2.1 backend for baseline comparisons."""

    def __init__(self, architecture: ScanArchitecture,
                 patterns: Sequence[Mapping[str, int]], weights: Mapping[str, int]) -> None:
        super().__init__(architecture, patterns, weights)
        self.full_seconds = 0.0
        self.incremental_seconds = 0.0
        self.accept_seconds = 0.0
        self.peak_transient_tile_bytes = 0

    def full_state(self, orders: Sequence[Sequence[int]]) -> RetainedHEffState:
        started = time.perf_counter()
        self.full_evaluations += 1
        longest = max(map(len, orders))
        fields = [self._chain_field(order, longest) for order in orders]
        global_field = np.zeros_like(fields[0])
        for field in fields:
            global_field += field
        state = RetainedHEffState(
            longest, fields, global_field, float(global_field.max(initial=0.0))
        )
        self.full_seconds += time.perf_counter() - started
        return state

    def evaluate(self, state: RetainedHEffState,
                 before_orders: Mapping[int, Sequence[int]],
                 after_orders: Mapping[int, Sequence[int]], chain_lengths: Sequence[int],
                 all_orders: Sequence[Sequence[int]] | None = None) -> RetainedHEffCandidate:
        started = time.perf_counter()
        new_longest = max(map(int, chain_lengths))
        if new_longest != state.longest_chain:
            if all_orders is None:
                raise ValueError("All chain orders are required when Lmax changes")
            full = self.full_state(all_orders)
            candidate = RetainedHEffCandidate(full.value, None, {}, full)
            return candidate
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
        for start in range(0, len(delta), 256):
            stop = min(len(delta), start + 256)
            peak = max(
                peak,
                float(np.max(state.global_field[start:stop] + delta[start:stop], initial=0.0)),
            )
        candidate = RetainedHEffCandidate(peak, delta, replacements)
        self.incremental_seconds += time.perf_counter() - started
        return candidate

    def accept(self, state: RetainedHEffState,
               candidate: RetainedHEffCandidate) -> RetainedHEffState:
        started = time.perf_counter()
        if candidate.full_state is not None:
            self.accept_seconds += time.perf_counter() - started
            return candidate.full_state
        if candidate.delta_field is None:
            raise AssertionError("Incremental candidate lacks a delta field")
        state.global_field += candidate.delta_field
        for chain, field in candidate.replacements.items():
            state.chain_fields[chain] = field
        state.value = candidate.value
        self.accept_seconds += time.perf_counter() - started
        return state

    @staticmethod
    def memory_bytes(state: RetainedHEffState) -> int:
        return int(state.global_field.nbytes + sum(field.nbytes for field in state.chain_fields))

    @staticmethod
    def persistent_global_bytes(state: RetainedHEffState) -> int:
        return int(state.global_field.nbytes)

    @staticmethod
    def persistent_per_chain_bytes(state: RetainedHEffState) -> int:
        return int(sum(field.nbytes for field in state.chain_fields))

    @property
    def exact_seconds(self) -> float:
        return self.full_seconds + self.incremental_seconds + self.accept_seconds


_T = TypeVar("_T")


class IncrementalHEff8(_HEffInputs):
    """Exact global-only H_eff8 backend with deterministic pattern tiling."""

    def __init__(self, architecture: ScanArchitecture,
                 patterns: Sequence[Mapping[str, int]], weights: Mapping[str, int], *,
                 tile_patterns: int = 8, workers: int = 1,
                 parallel_backend: str = "thread") -> None:
        super().__init__(architecture, patterns, weights)
        if tile_patterns < 1:
            raise ValueError("tile_patterns must be positive")
        if workers < 1:
            raise ValueError("workers must be positive")
        if parallel_backend not in {"sequential", "thread"}:
            raise ValueError("H_eff8 backend must be sequential or thread")
        self.tile_patterns = int(tile_patterns)
        self.workers = int(workers)
        self.parallel_backend = parallel_backend
        self.full_seconds = 0.0
        self.incremental_seconds = 0.0
        self.accept_seconds = 0.0
        self.peak_transient_tile_bytes = 0

    def _tiles(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (start, min(self.pattern_count, start + self.tile_patterns))
            for start in range(0, self.pattern_count, self.tile_patterns)
        )

    def _ordered_tile_results(self, function: Callable[[int, int], _T]) -> Iterator[_T]:
        """Yield bounded results in strict tile-index order."""
        tiles = self._tiles()
        if self.workers == 1 or self.parallel_backend == "sequential" or len(tiles) == 1:
            with threadpool_limits(limits=1, user_api="blas"):
                for start, stop in tiles:
                    yield function(start, stop)
            return
        with threadpool_limits(limits=1, user_api="blas"):
            with ThreadPoolExecutor(max_workers=min(self.workers, len(tiles))) as executor:
                # Submit at most W tiles at once. This prevents completed ndarray
                # results from accumulating to a second O(P*L*64) field.
                for offset in range(0, len(tiles), self.workers):
                    batch = tiles[offset:offset + self.workers]
                    futures = [executor.submit(function, start, stop) for start, stop in batch]
                    for future in futures:
                        yield future.result()

    def _note_transient(self, longest: int, length: int, pattern_rows: int,
                        *, fields: int = 1) -> None:
        # raw + convolved/output fields, mapping, and one pattern's Toeplitz
        # before/toggle pair. Parallel workers hold at most one such tile each.
        per_worker = (
            fields * 2 * pattern_rows * longest * 64 * np.dtype(np.float64).itemsize
            + length * 64 * np.dtype(np.float64).itemsize
            + 2 * longest * length * np.dtype(np.uint8).itemsize
        )
        concurrent = min(self.workers, max(1, len(self._tiles())))
        self.peak_transient_tile_bytes = max(
            self.peak_transient_tile_bytes, int(per_worker * concurrent)
        )

    def _chain_tile(self, order: Sequence[int], longest: int,
                    pattern_start: int, pattern_stop: int) -> np.ndarray:
        """Return one chain's exact field for a contiguous pattern tile."""
        ordered = np.asarray(order, dtype=np.int32)
        length = len(ordered)
        if length < 1 or length > longest:
            raise ValueError("Invalid chain length")
        pattern_rows = pattern_stop - pattern_start
        raw = np.zeros((pattern_rows * longest, 64), dtype=np.float64)
        ordered_bins = self.bins[ordered]
        ordered_weights = self.weights[ordered]
        bin_mapping = np.zeros((length, 64), dtype=np.float64)
        bin_mapping[np.arange(length), ordered_bins] = ordered_weights
        padding = longest - length
        self._note_transient(longest, length, pattern_rows)
        row = 0
        for pattern_index in range(pattern_start, pattern_stop):
            initial = (
                np.zeros(length, dtype=np.uint8)
                if pattern_index == 0
                else self.patterns[pattern_index - 1, ordered]
            )
            target = self.patterns[pattern_index, ordered]
            stream = np.zeros(longest, dtype=np.uint8)
            stream[padding:] = target[::-1]
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
                raise AssertionError("Tiled chain simulation did not load target")
        return convolve(
            raw.reshape(pattern_rows * longest, 8, 8), self.kernel,
            mode="constant", cval=0.0,
        ).reshape(pattern_rows * longest, 64)

    def _full_tile(self, orders: Sequence[Sequence[int]], longest: int,
                   pattern_start: int, pattern_stop: int) -> np.ndarray:
        rows = (pattern_stop - pattern_start) * longest
        field = np.zeros((rows, 64), dtype=np.float64)
        for order in orders:
            self._note_transient(longest, len(order), pattern_stop - pattern_start,
                                 fields=2)
            field += self._chain_tile(order, longest, pattern_start, pattern_stop)
        return field

    def _delta_tile(self, state: HEffState,
                    before_items: tuple[tuple[int, tuple[int, ...]], ...],
                    after_items: tuple[tuple[int, tuple[int, ...]], ...],
                    pattern_start: int, pattern_stop: int) -> tuple[float, np.ndarray]:
        row_start = pattern_start * state.longest_chain
        row_stop = pattern_stop * state.longest_chain
        delta = np.zeros((row_stop - row_start, 64), dtype=np.float64)
        before = dict(before_items)
        for chain, after_order in after_items:
            old_order = before[chain]
            if old_order == after_order:
                continue
            self._note_transient(
                state.longest_chain,
                max(len(old_order), len(after_order)),
                pattern_stop - pattern_start,
                fields=2,
            )
            new_field = self._chain_tile(
                after_order, state.longest_chain, pattern_start, pattern_stop
            )
            old_field = self._chain_tile(
                old_order, state.longest_chain, pattern_start, pattern_stop
            )
            delta += new_field - old_field
        candidate_tile = state.global_field[row_start:row_stop] + delta
        return float(candidate_tile.max(initial=0.0)), delta

    def full_state(self, orders: Sequence[Sequence[int]]) -> HEffState:
        started = time.perf_counter()
        self.full_evaluations += 1
        frozen_orders = tuple(tuple(map(int, order)) for order in orders)
        longest = max(map(len, frozen_orders))
        global_field = np.empty((self.pattern_count * longest, 64), dtype=np.float64)

        def work(start: int, stop: int) -> np.ndarray:
            return self._full_tile(frozen_orders, longest, start, stop)

        for (pattern_start, pattern_stop), field in zip(
            self._tiles(), self._ordered_tile_results(work)
        ):
            row_start = pattern_start * longest
            row_stop = pattern_stop * longest
            global_field[row_start:row_stop] = field
        state = HEffState(longest, global_field, float(global_field.max(initial=0.0)))
        self.full_seconds += time.perf_counter() - started
        return state

    def evaluate(self, state: HEffState, before_orders: Mapping[int, Sequence[int]],
                 after_orders: Mapping[int, Sequence[int]], chain_lengths: Sequence[int],
                 all_orders: Sequence[Sequence[int]] | None = None) -> HEffCandidate:
        started = time.perf_counter()
        new_longest = max(map(int, chain_lengths))
        before_items = tuple(
            (int(chain), tuple(map(int, before_orders[chain]))) for chain in after_orders
        )
        after_items = tuple(
            (int(chain), tuple(map(int, order))) for chain, order in after_orders.items()
        )
        if new_longest != state.longest_chain:
            if all_orders is None:
                raise ValueError("All chain orders are required when Lmax changes")
            frozen_orders = tuple(tuple(map(int, order)) for order in all_orders)
            # Compute only the scalar during candidate evaluation. A new E is
            # materialized only if the search accepts this Lmax-changing move.
            peaks = self._ordered_tile_results(
                lambda start, stop: float(
                    self._full_tile(frozen_orders, new_longest, start, stop).max(initial=0.0)
                )
            )
            candidate = HEffCandidate(max(peaks, default=0.0), before_items, after_items,
                                      frozen_orders)
            self.full_evaluations += 1
        else:
            self.incremental_evaluations += 1
            peaks = self._ordered_tile_results(
                lambda start, stop: self._delta_tile(
                    state, before_items, after_items, start, stop
                )[0]
            )
            candidate = HEffCandidate(max(peaks, default=0.0), before_items, after_items)
        self.incremental_seconds += time.perf_counter() - started
        return candidate

    def accept(self, state: HEffState, candidate: HEffCandidate) -> HEffState:
        """Commit in fixed tile order; rejected candidates never mutate state."""
        started = time.perf_counter()
        if candidate.full_orders is not None:
            replacement = self.full_state(candidate.full_orders)
            # full_state is a commit recomputation, not another search-budget
            # evaluation; keep the public scientific counter unchanged.
            self.full_evaluations -= 1
            return replacement

        def work(start: int, stop: int) -> np.ndarray:
            return self._delta_tile(
                state, candidate.before_orders, candidate.after_orders, start, stop
            )[1]

        for (pattern_start, pattern_stop), delta in zip(
            self._tiles(), self._ordered_tile_results(work)
        ):
            row_start = pattern_start * state.longest_chain
            row_stop = pattern_stop * state.longest_chain
            state.global_field[row_start:row_stop] += delta
        state.value = candidate.value
        self.accept_seconds += time.perf_counter() - started
        return state

    @staticmethod
    def memory_bytes(state: HEffState) -> int:
        return int(state.global_field.nbytes)

    @staticmethod
    def persistent_global_bytes(state: HEffState) -> int:
        return int(state.global_field.nbytes)

    @staticmethod
    def persistent_per_chain_bytes(state: HEffState) -> int:
        return 0

    @property
    def exact_seconds(self) -> float:
        return self.full_seconds + self.incremental_seconds + self.accept_seconds
