"""Deterministic instrumentation shared by the v2 and v2.1 constructors."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConstructorStats:
    """Work counters for one complete multi-lane constructor invocation."""

    mode: str
    total_seconds: float = 0.0
    lane_seconds: dict[str, float] = field(default_factory=dict)
    insertion_candidates_generated: int = 0
    insertion_candidates_scored: int = 0
    head_candidates_scored: int = 0
    physical_delta_computations: int = 0
    activity_heuristic_computations: int = 0
    activity_heuristic_lookups: int = 0
    full_chain_traversals: int = 0
    frontier_rebuilds: int = 0
    frontier_refreshes: int = 0
    heap_rebuilds: int = 0
    candidates_discarded: int = 0
    candidates_invalidated: int = 0
    candidates_refreshed: int = 0
    stale_candidates_rejected: int = 0
    repeated_equivalent_candidate_evaluations_across_lanes: int = 0
    shared_candidate_feature_hits: int = 0
    candidate_feature_computations: int = 0
    candidate_feature_cache_resets: int = 0
    exhausted_frontier_fallbacks: int = 0
    accepted_insertions: int = 0
    maximum_frontier_entries: int = 0
    maximum_heap_entries: int = 0
    maximum_candidate_feature_cache_entries: int = 0
    maximum_activity_cache_entries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
