"""Render Gate 10A figures from sealed CSV/JSON; no metric redefinition."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/gate10a"
FIG = OUT / "figures"


def bind(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def verified(item):
    raw_path = item["path"]
    path = ROOT / (raw_path[7:] if raw_path.startswith("repo://") else raw_path)
    observed = bind(path)
    if any(observed[key] != item[key] for key in ("bytes", "sha256")):
        raise ValueError("Figure input binding failed: " + str(path))
    return path


def save(fig, name):
    paths = []
    for suffix in ("png", "pdf"):
        path = FIG / f"{name}.{suffix}"
        if path.exists():
            raise ValueError("Preserve existing figure: " + str(path))
        fig.savefig(path, dpi=180, facecolor="white", bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def architecture_plot(rows):
    if any(row["status"] != "QUALIFIED" for row in rows):
        raise ValueError("Incomplete architecture comparison")
    labels = [row["design"].replace("_opt", "") + " " + row["candidate"] for row in rows]
    colors = ["#6e7887" if row["comparison_role"] == "control" else "#2164a8" for row in rows]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.8), sharey=True, layout="constrained")
    fields = [("delta_H8_fraction", "H8 reduction (%)", 100),
              ("delta_worst_ir_v", "Worst static VDD drop reduction (µV)", 1e6),
              ("delta_dynamic_power_fraction", "Dynamic power reduction (%)", 100)]
    for ax, (field, title, scale) in zip(axes, fields):
        values = [-float(row[field]) * scale for row in rows]
        ax.barh(np.arange(len(rows)), values, color=colors, height=0.65)
        ax.axvline(0, color="#343a40", linewidth=0.7)
        ax.grid(axis="x", alpha=0.2)
        ax.set_axisbelow(True)
        ax.set_xlabel(title, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(np.arange(len(rows)), labels)
    axes[0].invert_yaxis()
    axes[1].axvline(100, color="#a33a36", linestyle="--", linewidth=0.9, label="100 µV absolute criterion")
    axes[1].legend(fontsize=7, loc="lower right")
    fig.suptitle("Frozen PACT activity gains and measured physical response", fontsize=13)
    fig.supxlabel("Positive = reduction relative to b14 B3T or b15 B2. Gray = B5 control. Static, averaged-load model.\nMateriality additionally requires p99 improvement, relative thresholds and power/current guardrails.", fontsize=9)
    return save(fig, "activity_and_physical_response")


def spatial_plot(summary):
    lookup = {(row["design"], row["architecture"]): row for row in summary["architectures"]}
    keys = [("b14_opt", "B3T"), ("b14_opt", "CS_C1"), ("b15_opt", "B2"), ("b15_opt", "CS_C1")]
    vectors, inputs = [], []
    for key in keys:
        path = verified(lookup[key]["spatial_vectors"])
        inputs.append(path)
        vectors.append(json.loads(path.read_text())["grids"]["8"])
    fields = [("secondary_peak_cycle_activity", "Peak-cycle activity", "fF transitions", 1),
              ("activity", "Mean activity per shift", "fF transitions / shift", 1),
              ("static_vdd_drop", "Static VDD drop", "mV", 1000)]
    fig, axes = plt.subplots(4, 3, figsize=(11, 13), layout="constrained")
    for row_index, (key, grid) in enumerate(zip(keys, vectors)):
        for col, (field, title, unit, scale) in enumerate(fields):
            ax = axes[row_index, col]
            data = np.array([np.nan if value is None else value * scale for value in grid[field]["values"]]).reshape(8, 8)
            domain = set(grid["domain"]["bin_ids"])
            data = np.where(np.array([i in domain for i in range(64)]).reshape(8, 8), data, np.nan)
            paired = vectors[2 * (row_index // 2):2 * (row_index // 2) + 2]
            vmax = max(value * scale for other in paired for index, value in enumerate(other[field]["values"])
                       if index in other["domain"]["bin_ids"] and value is not None)
            bins = grid[field]["grid"]["bins"]
            extent = [bins[0]["bounds_um"][0], bins[-1]["bounds_um"][2], bins[0]["bounds_um"][1], bins[-1]["bounds_um"][3]]
            cmap = plt.get_cmap("magma").copy()
            cmap.set_bad("#e8e8e8")
            im = ax.imshow(data, origin="lower", interpolation="nearest", extent=extent, vmin=0, vmax=vmax, cmap=cmap)
            ax.set_title(f"{key[0]} {key[1]} — {title}", fontsize=9)
            ax.set_xlabel("x (µm)", fontsize=8)
            ax.set_ylabel("y (µm)", fontsize=8)
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label=unit)
    fig.suptitle("Frozen 8×8 maps: activity and static voltage drop", fontsize=14)
    fig.supxlabel("Same scales within each design pair. Gray = excluded unoccupied bin. Regional peaks can occur on different cycles.", fontsize=9)
    return save(fig, "primary_spatial_maps"), inputs


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "machine_summary.json"
    comparison_path = OUT / "final_comparison.csv"
    summary = json.loads(summary_path.read_text())
    if summary["qualification_errors"]:
        raise ValueError("Figures require complete qualified evidence")
    with comparison_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    outputs = architecture_plot(rows)
    spatial_outputs, vectors = spatial_plot(summary)
    outputs += spatial_outputs
    receipt = {"schema": "pact_gate10a_figure_derivation_v1", "status": "PASS", "source": bind(Path(__file__)),
               "inputs": [bind(path) for path in [summary_path, comparison_path, *vectors]], "outputs": [bind(path) for path in outputs],
               "matplotlib": matplotlib.__version__, "numpy": np.__version__,
               "interpretation": "Presentation only; signed reductions preserve existing full-precision metrics. Spatial plots use the preregistered occupied-bin domain and common scales within each design pair."}
    with (OUT / "control/figure_derivation.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "outputs": [bind(path) for path in outputs]}))


if __name__ == "__main__":
    main()
