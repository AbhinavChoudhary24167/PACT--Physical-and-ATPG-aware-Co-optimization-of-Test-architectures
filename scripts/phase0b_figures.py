#!/usr/bin/env python3
"""Rebuild Phase-0B figures solely from recorded JSON architectures and metrics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/figures/phase0b"
METHODS = ("B0", "B1", "P", "S", "A", "J25", "J50", "J75", "Rstar")
COLORS = dict(zip(METHODS, plt.cm.tab10.colors[:len(METHODS)]))
SEED_MARKERS = {11: "o", 13: "s", 17: "^", 19: "D", 23: "P"}


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def no_data(ax, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True,
            transform=ax.transAxes, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])


def save(fig, path: Path, inputs: list[Path], manifest: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    manifest.append({"figure": str(path.relative_to(ROOT)).replace("\\", "/"),
                     "inputs": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in inputs if p.is_file()]})


def pair_plan(design: str, seed: int) -> tuple[dict | None, Path]:
    path = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/plan.json"
    return read(path), path


def per_design(design: str, analysis: dict, manifest: list[dict]) -> None:
    folder = OUT / design
    pairs = [p for p in analysis["pairs"] if p["design"] == design]
    inputs = [ROOT / "artifacts/derived/phase0b/conflict_analysis.json"] + [ROOT / f"artifacts/derived/phase0b/{design}/s{p['physical_seed']}/plan.json"
              for p in pairs if p["qualified_rows"]]
    rows = [(p, row) for p in pairs for row in p["qualified_rows"]]
    x_label = "Scan HPWL proxy (µm)" if not any(p.get("primary_physical_metric", "").startswith("qualified") for p in pairs) else "Qualified routed scan-only length (µm)"

    fig, ax = plt.subplots(figsize=(7, 5))
    for p, row in rows:
        ax.scatter(row["primary_physical_cost_um"], row["H8"],
                   c=[COLORS[row["method"]]], marker=SEED_MARKERS[p["physical_seed"]],
                   s=62, alpha=0.8, edgecolor="black", linewidth=0.25)
    if not rows:
        no_data(ax, "No qualified routed architecture yet")
    else:
        methods_present = [m for m in METHODS if any(r["method"] == m for _, r in rows)]
        seeds_present = sorted({p["physical_seed"] for p, _ in rows})
        method_legend = ax.legend(
            [Line2D([], [], marker="o", linestyle="", markerfacecolor=COLORS[m],
                    markeredgecolor="none", label=m) for m in methods_present],
            methods_present, title="Architecture", fontsize=7, title_fontsize=8,
            loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=min(6, len(methods_present)))
        ax.add_artist(method_legend)
        ax.legend([Line2D([], [], marker=SEED_MARKERS[s], linestyle="", color="black", label=str(s))
                   for s in seeds_present], [str(s) for s in seeds_present],
                  title="Physical seed", fontsize=7, title_fontsize=8,
                  loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=len(seeds_present))
    ax.set(xlabel=x_label, ylabel="Exact shift H8 (8×8 distance-weighted hotspot)",
           title=f"{design}: physical metric vs H8")
    ax.grid(alpha=0.2)
    save(fig, folder / "physical_vs_H8.png", inputs, manifest)

    fig, ax = plt.subplots(figsize=(7, 5))
    for p in pairs:
        frontier = [r for r in p["qualified_rows"] if r["architecture_sha256"] in p.get("pareto_architecture_sha256", [])]
        if frontier:
            frontier.sort(key=lambda r: r["primary_physical_cost_um"])
            ax.plot([r["primary_physical_cost_um"] for r in frontier],
                    [r["H8"] for r in frontier], "o-", lw=1.2,
                    label=f"physical seed {p['physical_seed']}")
    if not any(p.get("pareto_methods") for p in pairs):
        no_data(ax, "No qualified paired Pareto set yet")
    else:
        ax.legend(fontsize=8)
    ax.set(xlabel=x_label, ylabel="H8", title=f"{design}: paired Pareto frontiers")
    ax.grid(alpha=0.2)
    save(fig, folder / "pareto_frontier.png", inputs, manifest)

    representative = next((p for p in pairs if p["qualified_rows"]), None)
    seed = representative["physical_seed"] if representative else 11
    plan, plan_path = pair_plan(design, seed)
    fig, axes = plt.subplots(2, 2, figsize=(10, 9), sharex=True, sharey=True)
    overlay_inputs = [plan_path]
    for ax, method in zip(axes.flat, ("B0", "P", "A", "Rstar")):
        arch_path = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/{method}.architecture.json"
        if arch_path.is_file():
            arch = ScanArchitecture.from_json(arch_path)
            cell = {c.name: c for c in arch.cells}
            ordered = [cell[name] for name in arch.chains[0].cells]
            ax.plot([c.x_um for c in ordered], [c.y_um for c in ordered],
                    lw=0.4, color=COLORS[method], alpha=0.7)
            ax.scatter([c.x_um for c in ordered], [c.y_um for c in ordered],
                       s=3, color="black", alpha=0.5)
            overlay_inputs.append(arch_path)
        else:
            no_data(ax, "Architecture unavailable")
        ax.set_title(method)
        ax.set_aspect("equal", adjustable="box")
    fig.suptitle(f"{design}, physical seed {seed}: scan order overlays (placed FF locations)")
    fig.supxlabel("x (µm)")
    fig.supylabel("y (µm)")
    save(fig, folder / "scan_chain_overlays.png", overlay_inputs, manifest)

    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    for ax, method in zip(axes.flat, ("B0", "P", "A", "Rstar")):
        row = next((r for r in plan["rows"] if r["method"] == method), None) if plan else None
        if row:
            grid = np.asarray(row["shift_activity"]["spatial_by_grid"]["8"]["cumulative_bin_toggles"])
            im = ax.imshow(grid, origin="lower", cmap="magma", interpolation="nearest")
            fig.colorbar(im, ax=ax, shrink=0.72, label="Cumulative bin toggles")
        else:
            no_data(ax, "Activity unavailable")
        ax.set_title(method)
    fig.suptitle(f"{design}, physical seed {seed}: exact serial-shift 8×8 activity")
    save(fig, folder / "activity_heatmaps.png", [plan_path], manifest)

    fig, ax = plt.subplots(figsize=(7, 4))
    available_congestion = [(p, r) for p, r in rows if r["congestion"] is not None]
    if available_congestion:
        labels = [f"{r['method']}/{p['physical_seed']}" for p, r in available_congestion]
        ax.bar(labels, [r["congestion"] for _, r in available_congestion])
        ax.tick_params(axis="x", rotation=75)
        ax.set_ylabel("Structured global-route congestion")
    else:
        no_data(ax, "Structured global-route congestion is unavailable\nfor the qualified runs shown in this campaign" if rows else "No qualified routes yet")
    ax.set_title(f"{design}: routed congestion comparison")
    save(fig, folder / "congestion_comparison.png", inputs, manifest)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    complete = [p for p in pairs if p["complete"] and "H8_percent_improvement_vs_physical_optimum" in p]
    if complete:
        seeds = [p["physical_seed"] for p in complete]
        axes[0].scatter(seeds, [p["H8_percent_improvement_vs_physical_optimum"] for p in complete], s=58)
        axes[1].scatter(seeds, [p["physical_percent_penalty_for_H8_optimum"] for p in complete],
                        s=58, color="tab:orange")
        axes[0].axhline(5, color="grey", linestyle="--", linewidth=0.8,
                        label="predeclared 5% threshold")
        axes[1].axhline(10, color="grey", linestyle="--", linewidth=0.8,
                        label="predeclared 10% threshold")
        for ax in axes:
            ax.set_xticks(seeds)
            ax.grid(alpha=0.2)
            ax.legend(fontsize=7)
    else:
        for ax in axes:
            no_data(ax, "No complete qualified pairs yet")
    axes[0].set(ylabel="H8 improvement (%)", xlabel="Physical seed")
    axes[1].set(ylabel="Physical penalty (%)", xlabel="Physical seed")
    fig.suptitle(f"{design}: paired physical-seed variability")
    save(fig, folder / "physical_seed_variability.png", inputs, manifest)

    fig, ax = plt.subplots(figsize=(7, 4))
    exact = [(p, r) for p, r in rows if r["routed_scan_net_only_length_um"] is not None]
    if exact:
        labels = [f"{r['method']}/{p['physical_seed']}" for p, r in exact]
        ax.bar(labels, [r["routed_scan_net_only_length_um"] for _, r in exact])
        ax.tick_params(axis="x", rotation=75)
        ax.set_ylabel("Qualified routed scan-only length (µm)")
    else:
        no_data(ax, "Exact scan-only routed length unavailable:\nscan edges share functional nets" if rows else "No routed extraction yet")
    ax.set_title(f"{design}: routed scan-only length comparison")
    save(fig, folder / "routed_scan_length_comparison.png", inputs, manifest)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    if rows:
        labels = [f"{r['method']}/{p['physical_seed']}" for p, r in rows]
        axes[0].bar(np.arange(len(rows)), [r["setup_wns_ns"] for _, r in rows])
        axes[1].bar(np.arange(len(rows)), [r["hold_wns_ns"] for _, r in rows])
        for ax in axes:
            ax.set_xticks(np.arange(len(rows)), labels, rotation=75, fontsize=6)
            ax.set_ylabel("WNS (ns), global-route stage")
    else:
        for ax in axes:
            no_data(ax, "No structured timing yet")
    axes[0].set_title("Setup")
    axes[1].set_title("Hold")
    fig.suptitle(f"{design}: comparable-stage timing")
    save(fig, folder / "timing_comparison.png", inputs, manifest)


def aggregate(analysis: dict, manifest: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for design, summary in analysis["design_summaries"].items():
        pairs = [p for p in analysis["pairs"] if p["design"] == design and p["complete"]]
        if pairs:
            axes[0].scatter([p["physical_percent_penalty_for_H8_optimum"] for p in pairs],
                            [p["H8_percent_improvement_vs_physical_optimum"] for p in pairs],
                            label=design)
        axes[1].bar(design, summary["completed_physical_seeds"], label=design)
    axes[0].axvline(10, ls="--", color="grey", lw=0.8)
    axes[0].axhline(5, ls="--", color="grey", lw=0.8)
    axes[0].set(xlabel="Physical penalty of H8 optimum (%)", ylabel="H8 improvement (%)",
                title="Paired effects; dashed lines are predeclared thresholds")
    if any(p["complete"] for p in analysis["pairs"]):
        axes[0].legend()
    else:
        no_data(axes[0], "No complete pairs yet")
    axes[1].set(ylim=(0, 5.5), ylabel="Complete physical seeds (of 5)",
                title="Campaign coverage")
    fig.suptitle("Phase-0B cross-design evidence")
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.19, top=0.76, wspace=0.30)
    save(fig, OUT / "aggregate_cross_design.png",
         [ROOT / "artifacts/derived/phase0b/conflict_analysis.json"], manifest)


def main() -> None:
    analysis_path = ROOT / "artifacts/derived/phase0b/conflict_analysis.json"
    analysis = read(analysis_path)
    if analysis is None:
        raise SystemExit("Run scripts/phase0b_analyze.py first")
    manifest: list[dict] = []
    for design in analysis["design_summaries"]:
        per_design(design, analysis, manifest)
    aggregate(analysis, manifest)
    (OUT / "figures_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8")
    print(f"Generated {len(manifest)} figures")


if __name__ == "__main__":
    main()
