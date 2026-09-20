"""Small, exact Pareto utilities for three-objective Phase-0D analysis."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence, TypeVar


ObjectiveVector = tuple[float, float, float]
T = TypeVar("T")


def _checked(point: Sequence[float]) -> ObjectiveVector:
    if len(point) != 3 or any(not math.isfinite(float(value)) for value in point):
        raise ValueError(f"Expected three finite objectives, got {point!r}")
    return tuple(float(value) for value in point)  # type: ignore[return-value]


def dominates(left: Sequence[float], right: Sequence[float]) -> bool:
    a, b = _checked(left), _checked(right)
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def nondominated(items: Iterable[T], key=lambda value: value) -> list[T]:
    values = list(items)
    points = [_checked(key(value)) for value in values]
    return [
        value for index, value in enumerate(values)
        if not any(dominates(other, points[index]) for other_index, other in enumerate(points) if other_index != index)
    ]


@dataclass(frozen=True)
class ObjectiveBounds:
    ideal: ObjectiveVector
    reference: ObjectiveVector

    def __post_init__(self) -> None:
        ideal, reference = _checked(self.ideal), _checked(self.reference)
        if any(low >= high for low, high in zip(ideal, reference)):
            raise ValueError("Every objective reference bound must exceed its ideal")

    def normalize(self, point: Sequence[float]) -> ObjectiveVector:
        checked = _checked(point)
        return tuple(
            (value - low) / (high - low)
            for value, low, high in zip(checked, self.ideal, self.reference)
        )  # type: ignore[return-value]


def freeze_bounds(portfolio: Iterable[Sequence[float]], margin_fraction: float = 0.25,
                  zero_range_fraction: float = 0.10) -> ObjectiveBounds:
    points = [_checked(point) for point in portfolio]
    if not points:
        raise ValueError("Cannot freeze objective bounds from an empty portfolio")
    ideal = tuple(min(point[index] for point in points) for index in range(3))
    nadir = tuple(max(point[index] for point in points) for index in range(3))
    reference = []
    for low, high in zip(ideal, nadir):
        span = high - low
        margin = margin_fraction * span if span > 0 else max(abs(high) * zero_range_fraction, 1.0)
        reference.append(high + margin)
    return ObjectiveBounds(_checked(ideal), _checked(reference))


def _dominated_area_2d(points: Iterable[tuple[float, float]], reference: tuple[float, float]) -> float:
    ref_y, ref_z = reference
    filtered = sorted((y, z) for y, z in points if y < ref_y and z < ref_z)
    if not filtered:
        return 0.0
    last_y = filtered[0][0]
    best_z = ref_z
    area = 0.0
    for y, z in filtered:
        if y > last_y:
            area += (y - last_y) * max(0.0, ref_z - best_z)
            last_y = y
        best_z = min(best_z, z)
    area += max(0.0, ref_y - last_y) * max(0.0, ref_z - best_z)
    return area


def hypervolume_3d(points: Iterable[Sequence[float]], reference: Sequence[float] = (1.0, 1.0, 1.0)) -> float:
    """Exact dominated hypervolume for minimization in three objectives."""
    ref = _checked(reference)
    front = nondominated(
        [_checked(point) for point in points if all(float(value) < limit for value, limit in zip(point, ref))]
    )
    if not front:
        return 0.0
    levels = sorted(set(point[0] for point in front))
    volume = 0.0
    active: list[ObjectiveVector] = []
    for index, level in enumerate(levels):
        active.extend(point for point in front if point[0] == level)
        next_level = levels[index + 1] if index + 1 < len(levels) else ref[0]
        if next_level > level:
            volume += (next_level - level) * _dominated_area_2d(
                ((point[1], point[2]) for point in active), (ref[1], ref[2])
            )
    return volume


def normalized_hypervolume(points: Iterable[Sequence[float]], bounds: ObjectiveBounds) -> float:
    return hypervolume_3d((bounds.normalize(point) for point in points))


def additive_epsilon_coverage(approximation: Iterable[Sequence[float]],
                              reference_front: Iterable[Sequence[float]]) -> float:
    """Return the additive epsilon needed for approximation to weakly cover the reference."""
    approx = [_checked(point) for point in approximation]
    reference = [_checked(point) for point in reference_front]
    if not approx or not reference:
        raise ValueError("Both fronts are required")
    return max(min(max(a - b for a, b in zip(candidate, target)) for candidate in approx)
               for target in reference)


def objective_regret(approximation: Iterable[Sequence[float]],
                     reference_front: Iterable[Sequence[float]]) -> ObjectiveVector:
    approx = [_checked(point) for point in approximation]
    reference = [_checked(point) for point in reference_front]
    if not approx or not reference:
        raise ValueError("Both fronts are required")
    return tuple(
        min(point[index] for point in approx) - min(point[index] for point in reference)
        for index in range(3)
    )  # type: ignore[return-value]
