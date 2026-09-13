"""Headless, evidence-linked static Phase-0 figures."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pact.scan.model import ScanArchitecture
from .aggregate import hotspot


def _label(row: dict[str, Any]) -> str:
    return f"{row['method']} (seed {row['seed']})" if row["method"] == "random" else row["method"]


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _bar(rows: list[dict[str, Any]], values: list[float], title: str, x_label: str, path: Path) -> None:
    order = np.argsort(values)
    fig, ax = plt.subplots(figsize=(9, max(4, len(rows) * 0.37 + 1)))
    ax.barh(np.arange(len(rows)), [values[i] for i in order], color="#2474a6")
    ax.set_yticks(np.arange(len(rows)), [_label(rows[i]) for i in order])
    ax.set_xlabel(x_label)
    ax.set_title(title)
    _save(fig, path)


def _no_data(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    _save(fig, path)


def plot_results(records: list[dict[str, Any]], root: Path, output: Path) -> list[Path]:
    """Generate required plots; missing physical metrics receive labeled no-data panels."""
    output.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    fig, ax = plt.subplots(figsize=(10, 6))
    # Alpha endpoints duplicate the activity-only and nearest architectures.
    unique = {row["architecture_sha256"]: row for row in reversed(records)}
    categories = {
        "supplied_fan": ("Supplied FAN", "#2563a6", "s"),
        "nearest_neighbor": ("Nearest neighbor", "#d1493f", "D"),
        "serpentine": ("Serpentine", "#238b45", "o"),
        "activity_only": ("Activity only", "#8c42a3", "P"),
        "random": ("Random", "#6b7280", "o"),
        "physical_activity": ("Physical + activity", "#e39a20", "^"),
    }
    labeled: set[str] = set()
    for row in unique.values():
        category = "physical_activity" if row["method"].startswith("physical_activity") else row["method"]
        name, color, marker = categories[category]
        ax.scatter(row["scan"]["total_hpwl_um"], hotspot(row), s=46, color=color,
                   marker=marker, label=name if name not in labeled else None)
        labeled.add(name)
        if row["method"] in {"supplied_fan", "nearest_neighbor", "activity_only"}:
            ax.annotate(name, (row["scan"]["total_hpwl_um"], hotspot(row)),
                        xytext=(8, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Estimated scan HPWL (µm)")
    ax.set_ylabel("Distance-weighted hotspot, 8×8 (toggle density proxy)")
    ax.set_title("Fixed-placement scan wirelength vs ATPG shift-activity hotspot")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    path = output / "scan_wirelength_vs_hotspot_activity.png"
    _save(fig, path); created.append(path)

    path = output / "scan_wirelength_by_method.png"
    _bar(records, [float(row["scan"]["total_hpwl_um"]) for row in records],
         "Estimated scan HPWL by method", "µm", path)
    created.append(path)
    path = output / "peak_local_activity_by_method.png"
    _bar(records, [float(row["test"]["peak_local_activity"]) for row in records],
         "Peak 8×8-bin shift toggles by method", "toggles / bin / clock", path)
    created.append(path)

    physical = [row for row in records if row["physical"]["wns_ns"] is not None]
    path = output / "timing_delta_by_method.png"
    if physical:
        baseline = next((row for row in physical if row["method"] == "supplied_fan"), physical[0])
        _bar(physical, [float(row["physical"]["wns_ns"]) - float(baseline["physical"]["wns_ns"]) for row in physical],
             "Global-route setup worst-slack delta vs supplied order", "ns", path)
    else:
        _no_data(path, "Timing delta", "No paired routed timing evidence")
    created.append(path)
    path = output / "congestion_delta_by_method.png"
    congestion = [row for row in records if row["physical"]["congestion_metric"] is not None]
    if congestion:
        baseline = congestion[0]
        _bar(congestion, [float(row["physical"]["congestion_metric"]) - float(baseline["physical"]["congestion_metric"]) for row in congestion],
             "Congestion delta vs supplied order", "reported units", path)
    else:
        _no_data(path, "Congestion delta", "No structured congestion metric available in this ORFS run")
    created.append(path)

    for row in records:
        arch_ref = next(ref for ref in row["evidence"] if ref.endswith(".architecture.json"))
        arch = ScanArchitecture.from_json(root / arch_ref)
        label = re.sub(r"[^A-Za-z0-9_]+", "_", _label(row))
        spatial_ref = next(ref for ref in row["evidence"] if ref.endswith(".spatial.json"))
        matrix = np.asarray(json.loads((root / spatial_ref).read_text(encoding="utf-8"))["8"]["cumulative_bin_toggles"])
        fig, ax = plt.subplots(figsize=(5, 4))
        image = ax.imshow(matrix, origin="lower", cmap="magma")
        fig.colorbar(image, ax=ax, label="cumulative toggles")
        ax.set_xlabel("X bin"); ax.set_ylabel("Y bin")
        ax.set_title(f"Shift activity: {_label(row)}")
        path = output / f"activity_heatmap_{label}.png"
        _save(fig, path); created.append(path)

        cells = {cell.name: cell for cell in arch.cells}
        fig, ax = plt.subplots(figsize=(7, 6))
        for chain in arch.chains:
            xs = [cells[name].x_um for name in chain.cells]
            ys = [cells[name].y_um for name in chain.cells]
            ax.plot(xs, ys, linewidth=0.55, alpha=0.65, label=chain.chain_id)
            ax.scatter(xs, ys, s=4)
        ax.set_xlabel("X (µm)"); ax.set_ylabel("Y (µm)")
        ax.set_title(f"Placed scan chain: {_label(row)}")
        ax.set_aspect("equal", adjustable="box")
        if len(arch.chains) > 1:
            ax.legend(fontsize=7)
        path = output / f"placement_scan_overlay_{label}.png"
        _save(fig, path); created.append(path)
    return created
