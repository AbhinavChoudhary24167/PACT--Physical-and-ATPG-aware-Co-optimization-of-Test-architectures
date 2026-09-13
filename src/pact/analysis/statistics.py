"""Small-sample descriptive statistics without significance theater."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.stats import t


def describe(values: Sequence[float]) -> dict[str, float | int | list[float] | None]:
    """Report sample size, central tendency, spread, range, and t-based CI."""
    data = np.asarray(values, dtype=float)
    if len(data) == 0 or not np.isfinite(data).all():
        raise ValueError("Statistics require nonempty finite measurements")
    mean = float(data.mean())
    std = float(data.std(ddof=1)) if len(data) > 1 else 0.0
    half_width = float(t.ppf(0.975, len(data) - 1) * std / np.sqrt(len(data))) if len(data) > 1 else None
    return {
        "n": len(data), "mean": mean, "median": float(np.median(data)),
        "std": std, "min": float(data.min()), "max": float(data.max()),
        "ci95": [mean - half_width, mean + half_width] if half_width is not None else None,
    }
