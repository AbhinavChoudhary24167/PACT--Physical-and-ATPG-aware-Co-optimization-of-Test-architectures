#!/usr/bin/env python3
"""Generate the final Phase-0C figure set from machine-readable evidence."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pact.analysis.phase0c_activity import direct_sink_weights
from pact.physical.grid_metrics import placement_grid
from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.scan.phase0c import architecture_space_log10, parallel_schedule
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/figures/phase0c"
SOURCE_DATA = ROOT / "artifacts/derived/phase0c/figure_source_data.json"
COLORS = {"B0": "#4c78a8", "B1": "#72b7b2", "P": "#59a14f", "A": "#e15759",
          "J50": "#f28e2b", "T": "#b07aa1", "R": "#9c755f"}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def quantile(values, fraction):
    return float(np.quantile(np.asarray(values, dtype=float), fraction)) if values else None


def exact_weighted_cumulative(proxy: dict) -> list[list[float]]:
    """Replay a representative architecture and retain its cumulative weighted map."""
    design, seed = proxy["design"], proxy["physical_seed"]
    architecture = ScanArchitecture.from_json(ROOT / proxy["architecture_path"])
    placed = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.v"
    ff = {item.name: item for item in scan_ff_instances(placed)}
    weights = direct_sink_weights(placed, {name: item.q_net for name, item in ff.items()})
    identity = read(ROOT / f"artifacts/derived/{design}/ff_identity_map.json")["records"]
    patterns = map_ppi_patterns(parse_fan_pat(
        ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat"), identity)
    names = tuple(sorted(cell.name for cell in architecture.cells))
    index = {name: i for i, name in enumerate(names)}
    chains = [np.asarray([index[name] for name in chain.cells], dtype=np.int32)
              for chain in architecture.chains]
    grid = placement_grid(architecture.cells, 8)
    cell_by_name = {cell.name: cell for cell in architecture.cells}
    bins = [grid.bin_for(cell_by_name[name].x_um, cell_by_name[name].y_um) for name in names]
    weight_array = np.asarray([weights[name] for name in names], dtype=float)
    state = np.zeros(len(names), dtype=np.uint8)
    cumulative = np.zeros((8, 8), dtype=float)
    for pattern in patterns:
        for inputs in parallel_schedule(architecture, pattern):
            after = state.copy()
            for ci, chain in enumerate(chains):
                after[chain[1:]] = state[chain[:-1]]
                after[chain[0]] = inputs[ci]
            for position in np.flatnonzero(state ^ after):
                cumulative[bins[position]] += weight_array[position]
            state = after
    expected = float(proxy["activity"]["weighted_total"])
    if not np.isclose(float(cumulative.sum()), expected):
        raise AssertionError("Representative weighted map does not reproduce frozen weighted_total")
    return cumulative.tolist()


def collect() -> tuple[dict, list[Path]]:
    execution_path = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
    recovery_path = ROOT / "artifacts/manifests/phase0c/campaign_recovery.json"
    analysis_path = ROOT / "artifacts/derived/phase0c/gate_analysis.json"
    if not execution_path.is_file() or not recovery_path.is_file() or not analysis_path.is_file():
        raise ValueError("Original execution, recovery execution and gate analysis are required")
    execution, recovery_execution, analysis = read(execution_path), read(recovery_path), read(analysis_path)
    freeze = execution["freeze_commit"]
    proxy_paths = sorted((ROOT / "artifacts/derived/phase0c").glob("*/s*/k*/*.proxy.json"))
    route_paths = sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json"))
    proxy_by_key = {(p["design"], p["physical_seed"], p["K"], p["method"]): p
                    for p in map(read, proxy_paths)}
    rows, used_routes = [], []
    for path in route_paths:
        route = read(path)
        key = (route.get("design"), route.get("physical_seed"), route.get("K"), route.get("method"))
        proxy = proxy_by_key.get(key)
        if (not proxy or route.get("status") != "QUALIFIED" or route.get("DRC_errors") != 0
                or route.get("campaign_freeze_commit") != freeze
                or route.get("architecture_sha256") != proxy.get("architecture_sha256")):
            continue
        metrics = route["structured_metrics"]
        runtime_path = ROOT / f"artifacts/derived/phase0c/{key[0]}/s{key[1]}/k{key[2]}/{key[3]}.runtime.json"
        runtime = read(runtime_path)
        route_execution = path.parent / "route/execution.json"
        route_runtime = read(route_execution) if route_execution.is_file() else {}
        archive = ROOT / route["routed_odb_archive"]
        rows.append({
            "design": key[0], "seed": key[1], "K": key[2], "method": key[3],
            "run_id": proxy["run_id"], "architecture_sha256": proxy["architecture_sha256"],
            "physical_um": route["physical_primary_um"],
            "H_eff8": proxy["activity"]["grids"]["8"]["H_eff"],
            "H_density8": proxy["activity"]["grids"]["8"]["H_density"],
            "cumulative_toggle_map8": proxy["activity"]["grids"]["8"]["cumulative_bin_toggles"],
            "total_toggles": proxy["activity"]["total_shift_toggles"],
            "peak_toggles": proxy["activity"]["peak_simultaneous_toggles"],
            "p95_toggles": proxy["activity"]["p95_simultaneous_toggles"],
            "p99_toggles": proxy["activity"]["p99_simultaneous_toggles"],
            "chain_lengths": proxy["chain_statistics"]["chain_lengths"],
            "chain_imbalance": proxy["chain_statistics"]["normalized_imbalance"],
            "shift_cycles": proxy["chain_statistics"]["parallel_shift_cycles"],
            "setup_wns_ns": metrics["setup_wns_ns"], "hold_wns_ns": metrics["hold_wns_ns"],
            "global_route_usage_percent": metrics["congestion"]["total"]["usage_percent"],
            "global_route_overflow": metrics["congestion"]["total"]["total_overflow"],
            "detailed_route_wirelength_um": metrics["total_detailed_route_wirelength_um"],
            "detailed_route_vias": metrics["detailed_route_vias"],
            "routed_scan_path_upper_bound_um": route["routed_full_scan_path_net_length_upper_bound_um"],
            "generation_and_metrics_s": runtime["generation_verification_and_metrics_s"],
            "shift_activity_s": runtime["parallel_shift_activity_s"],
            "route_s": route_runtime.get("elapsed_s"), "odb_archive_bytes": archive.stat().st_size,
            "architecture_path": proxy["architecture_path"],
        })
        used_routes.append(path)
    if not rows:
        raise ValueError("No qualified frozen-campaign route/proxy joins")
    interventions_path = ROOT / "artifacts/derived/phase0c/intervention_dataset.jsonl"
    interventions = []
    if interventions_path.is_file():
        for line in interventions_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("screen_id") == "FROZEN_C7_LOCAL_SWAP":
                interventions.append(record)
    representatives, representative_sources = [], []
    for design in sorted({row["design"] for row in rows}):
        candidates = [row for row in rows if row["design"] == design and row["seed"] == 11
                      and row["K"] == 8 and row["method"] == "B0"]
        if candidates:
            row = candidates[0]
            representative_sources.extend([
                ROOT / row["architecture_path"],
                ROOT / f"artifacts/raw/phase0b/placements/{design}/s11/placed.v",
                ROOT / f"artifacts/derived/{design}/ff_identity_map.json",
                ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat",
            ])
            representatives.append({"design": design, "seed": 11, "K": 8, "method": "B0",
                                    "architecture": read(ROOT / row["architecture_path"]),
                                    "cumulative_toggle_map8": row["cumulative_toggle_map8"],
                                    "weighted_cumulative_toggle_map8": exact_weighted_cumulative(
                                        proxy_by_key[(design, 11, 8, "B0")])})
    data = {"schema_version": "phase0c-figure-source-1", "freeze_commit": freeze,
            "execution_status": execution["status"], "rows": rows,
            "recovery_execution_status": recovery_execution["status"],
            "complete_pair_descriptives": analysis["complete_pair_descriptives"],
            "descriptive_statistics": analysis["descriptive_statistics"],
            "interventions": interventions, "representatives": representatives,
            "gate_status": {name: gate["status"] for name, gate in analysis["gates"].items()},
            "classification": analysis["classification"]}
    architecture_paths = [ROOT / proxy["architecture_path"] for proxy in proxy_by_key.values()]
    source_paths = proxy_paths + architecture_paths + representative_sources + used_routes + [
        execution_path, recovery_path, analysis_path]
    if interventions_path.is_file():
        source_paths.append(interventions_path)
    data["raw_source_sha256"] = {
        path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(source_paths))}
    SOURCE_DATA.write_bytes((json.dumps(data, indent=2, sort_keys=True) + "\n").encode())
    return data, [SOURCE_DATA, Path(__file__).resolve()]


def pareto(rows):
    return [row for row in rows if not any(
        other is not row and other["physical_um"] <= row["physical_um"]
        and other["H_eff8"] <= row["H_eff8"]
        and (other["physical_um"] < row["physical_um"] or other["H_eff8"] < row["H_eff8"])
        for other in rows)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data, common_sources = collect()
    rows, pair_rows = data["rows"], data["complete_pair_descriptives"]
    methods = [method for method in ("B0", "B1", "P", "A", "J50", "T", "R")
               if any(row["method"] == method for row in rows)]
    designs = sorted({row["design"] for row in rows})
    manifest = []
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": .22,
                         "axes.spines.top": False, "axes.spines.right": False})

    def save(name: str, description: str):
        target = OUT / name
        plt.tight_layout()
        plt.savefig(target, dpi=170, metadata={"Software": "PACT Phase-0C"})
        plt.close()
        manifest.append({"figure": target.relative_to(ROOT).as_posix(), "sha256": digest(target),
                         "description": description,
                         "sources": [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p)}
                                     for p in common_sources]})

    fig, ax = plt.subplots(figsize=(8, 5))
    for method in methods:
        subset = [r for r in rows if r["method"] == method]
        ax.scatter([r["physical_um"] for r in subset], [r["H_eff8"] for r in subset],
                   s=22, alpha=.65, label=method, color=COLORS[method])
    ax.set(xlabel="Port-aware scan HPWL proxy (µm)", ylabel="H_eff8 (dimensionless)",
           title="Frozen campaign: physical cost versus effective switching")
    ax.legend(ncol=4)
    save("01_physical_vs_effective_activity.png", "All qualified frozen-campaign rows")

    fig, axes = plt.subplots(1, len(designs), figsize=(14, 4.2), squeeze=False)
    for ax, design in zip(axes[0], designs):
        subset = [r for r in rows if r["design"] == design and r["seed"] == 11 and r["K"] == 8]
        front = sorted(pareto(subset), key=lambda r: r["physical_um"])
        for row in subset:
            ax.scatter(row["physical_um"], row["H_eff8"], color=COLORS[row["method"]])
            ax.annotate(row["method"], (row["physical_um"], row["H_eff8"]), fontsize=7)
        ax.plot([r["physical_um"] for r in front], [r["H_eff8"] for r in front], color="black", lw=1)
        ax.set(title=f"{design}, seed 11, K=8", xlabel="HPWL proxy (µm)")
    axes[0][0].set_ylabel("H_eff8")
    save("02_pareto_frontier_by_design.png", "Representative paired Pareto front for each design")

    fig, axes = plt.subplots(1, len(data["representatives"]), figsize=(15, 4.5), squeeze=False)
    for ax, rep in zip(axes[0], data["representatives"]):
        cells = {cell["name"]: cell for cell in rep["architecture"]["cells"]}
        for ci, chain in enumerate(rep["architecture"]["chains"]):
            x = [cells[name]["x_um"] for name in chain["cells"]]
            y = [cells[name]["y_um"] for name in chain["cells"]]
            ax.plot(x, y, lw=.65, alpha=.8, label=f"C{ci}")
        ax.set(title=f"{rep['design']} K=8 B0", xlabel="x (µm)", ylabel="y (µm)", aspect="equal")
    save("03_multichain_scan_overlays.png", "Representative placed FF-origin chain overlays")

    fig, axes = plt.subplots(1, len(data["representatives"]), figsize=(14, 4.2), squeeze=False)
    for ax, rep in zip(axes[0], data["representatives"]):
        image = ax.imshow(rep["cumulative_toggle_map8"], origin="lower", cmap="magma")
        ax.set_title(f"{rep['design']} cumulative toggles")
        fig.colorbar(image, ax=ax, shrink=.72)
    save("04_activity_hotspot_maps.png", "Exact cumulative logical toggle maps for representative B0/K8 rows")

    fig, axes = plt.subplots(1, len(data["representatives"]), figsize=(14, 4.2), squeeze=False)
    for ax, rep in zip(axes[0], data["representatives"]):
        image = ax.imshow(rep["weighted_cumulative_toggle_map8"], origin="lower", cmap="viridis")
        ax.set_title(f"{rep['design']} weighted exposure")
        fig.colorbar(image, ax=ax, shrink=.72)
    save("05_effective_activity_maps.png", "Exact cumulative direct-sink-weighted logical toggle maps")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    values, labels = [], []
    for k in sorted({r["K"] for r in rows}):
        values.append([length for r in rows if r["K"] == k for length in r["chain_lengths"]])
        labels.append(f"K={k}")
    ax.boxplot(values, tick_labels=labels, showfliers=False)
    ax.set(ylabel="FFs per chain", title="Chain-length distributions across qualified rows")
    save("06_chain_length_distribution.png", "All chain lengths grouped by K")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    for mi, method in enumerate(methods):
        subset = [r for r in rows if r["method"] == method]
        axes[0].boxplot([r["setup_wns_ns"] for r in subset], positions=[mi], widths=.6)
        axes[1].boxplot([r["hold_wns_ns"] for r in subset], positions=[mi], widths=.6)
    for ax, title in zip(axes, ("Global-route setup WNS", "Global-route hold WNS")):
        ax.set_xticks(range(len(methods)), methods, rotation=35)
        ax.set_ylabel("ns")
        ax.set_title(title)
    save("07_timing_comparison.png", "Tool-reported global-route setup and hold WNS")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for design in designs:
        sequence = [quantile([r["shift_cycles"] for r in rows if r["design"] == design and r["K"] == k], .5)
                    for k in (1, 2, 4, 8)]
        ax.plot((1, 2, 4, 8), sequence, marker="o", label=design)
    ax.set(xlabel="K", ylabel="Parallel shift clocks (capture excluded)", title="Test-cycle scaling")
    ax.legend()
    save("08_test_cycle_comparison.png", "Median exact shift-clock counts by design and K")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    for method in methods:
        subset = [r for r in rows if r["method"] == method]
        axes[0].scatter([r["K"] for r in subset], [r["global_route_usage_percent"] for r in subset],
                        s=14, alpha=.45, color=COLORS[method], label=method)
        axes[1].scatter([r["K"] for r in subset], [r["global_route_overflow"] for r in subset],
                        s=14, alpha=.45, color=COLORS[method])
    axes[0].set(xlabel="K", ylabel="Total usage (%)", title="Initial global-route usage")
    axes[1].set(xlabel="K", ylabel="Total overflow", title="Initial global-route overflow")
    axes[0].legend(ncol=2)
    save("09_congestion_comparison.png", "Initial global-route resource use and overflow")

    fig, axes = plt.subplots(1, len(designs), figsize=(14, 4.2), squeeze=False)
    for ax, design in zip(axes[0], designs):
        for method in methods:
            subset = [r for r in rows if r["design"] == design and r["K"] == 8 and r["method"] == method]
            if subset:
                ax.plot([r["seed"] for r in subset], [r["physical_um"] for r in subset],
                        marker="o", ms=3, label=method, color=COLORS[method])
        ax.set(title=f"{design}, K=8", xlabel="Physical seed", ylabel="HPWL proxy (µm)")
    axes[0][-1].legend(fontsize=7)
    save("10_physical_seed_variability.png", "Paired physical-seed variability at K=8")

    interventions = data["interventions"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    physical_deltas = [[r["delta"]["scan_hpwl_proxy_um"] for r in interventions if r["design"] == design]
                       for design in designs]
    activity_deltas = [[r["delta"]["H_eff8_proxy"] for r in interventions if r["design"] == design]
                       for design in designs]
    if all(physical_deltas):
        axes[0].violinplot(physical_deltas, showmedians=True)
        axes[1].violinplot(activity_deltas, showmedians=True)
    for ax, label in zip(axes, ("Δ HPWL proxy (µm)", "Δ H_eff8")):
        ax.axhline(0, color="black", lw=.8)
        ax.set_xticks(range(1, len(designs) + 1), designs)
        ax.set_ylabel(label)
    axes[0].set_title("Fixed local-swap physical effects")
    axes[1].set_title("Fixed local-swap activity effects")
    save("11_intervention_delta_distributions.png", "Frozen C7 local-swap delta distributions")

    regret = data["descriptive_statistics"]["method_regret"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(methods))
    p = [regret.get(m, {}).get("physical_percent", {}).get("median", np.nan) for m in methods]
    a = [regret.get(m, {}).get("activity_percent", {}).get("median", np.nan) for m in methods]
    ax.bar(x - .2, p, .4, label="physical regret")
    ax.bar(x + .2, a, .4, label="activity regret")
    ax.set_xticks(x, methods)
    ax.set(ylabel="Median regret (%)", title="Deterministic heuristic regret")
    ax.legend()
    save("12_heuristic_regret.png", "Median paired regret from complete design-seed-K groups")

    columns = [("physical_um", "HPWL"), ("H_eff8", "H_eff8"), ("peak_toggles", "peak"),
               ("shift_cycles", "cycles"), ("setup_wns_ns", "setup WNS"),
               ("global_route_usage_percent", "GRT use")]
    matrix = np.asarray([[r[name] for name, _ in columns] for r in rows], dtype=float)
    ranks = np.apply_along_axis(lambda x: np.argsort(np.argsort(x)), 0, matrix)
    corr = np.corrcoef(ranks, rowvar=False)
    fig, ax = plt.subplots(figsize=(6.3, 5.2))
    image = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(columns)), [label for _, label in columns], rotation=35, ha="right")
    ax.set_yticks(range(len(columns)), [label for _, label in columns])
    for i in range(len(columns)):
        for j in range(len(columns)):
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, shrink=.8)
    ax.set_title("Objective rank-correlation matrix")
    save("13_objective_correlation_matrix.png", "Descriptive rank correlations over qualified rows")

    counts = data["descriptive_statistics"]["pareto_membership_counts"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(methods, [counts.get(method, 0) for method in methods], color=[COLORS[m] for m in methods])
    ax.set(ylabel="Complete-pair Pareto memberships", title="Pareto membership frequency")
    save("14_pareto_membership_frequency.png", "Frequency across complete design-seed-K groups")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for design in designs:
        design_rows = [r for r in rows if r["design"] == design]
        pbase = quantile([r["physical_um"] for r in design_rows], .5)
        abase = quantile([r["H_eff8"] for r in design_rows], .5)
        axes[0].plot(methods, [quantile([r["physical_um"] / pbase for r in design_rows if r["method"] == m], .5)
                               for m in methods], marker="o", label=design)
        axes[1].plot(methods, [quantile([r["H_eff8"] / abase for r in design_rows if r["method"] == m], .5)
                               for m in methods], marker="o", label=design)
    axes[0].set(ylabel="Median / design median", title="Normalized physical cost")
    axes[1].set(ylabel="Median / design median", title="Normalized effective activity")
    for ax in axes:
        ax.tick_params(axis="x", rotation=35)
        ax.legend()
    save("15_cross_design_aggregate.png", "Within-design normalized aggregate by method")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    for field, label, marker in (("physical_penalty_percent", "Physical penalty", "o"),
                                 ("H_eff_gain_percent", "H_eff gain", "s")):
        medians = [quantile([r[field] for r in pair_rows if r["K"] == k], .5) for k in (1, 2, 4, 8)]
        ax.plot((1, 2, 4, 8), medians, marker=marker, label=label)
    ax.axhline(10, color="gray", ls="--", lw=.8, label="10% physical gate")
    ax.axhline(5, color="gray", ls=":", lw=.8, label="5% activity gate")
    ax.set(xlabel="K", ylabel="Median paired difference (%)", title="Trade-off strength versus K")
    ax.legend()
    save("16_tradeoff_change_vs_k.png", "Median paired optimum differences by K")

    benchmark_path = ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json"
    benchmark = read(benchmark_path)
    common_sources.append(benchmark_path)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for design in benchmark["designs"]:
        n = design["scan_ff_count"]
        ax.plot((1, 2, 4, 8), [architecture_space_log10(n, k) for k in (1, 2, 4, 8)],
                marker="o", label=f"{design['design']} ({n} FFs)")
    ax.axhline(100, color="black", ls="--", lw=.8, label="C8 threshold")
    ax.set(xlabel="K", ylabel="log10 legal ordered-chain architectures",
           title="Combinatorial search-space scaling")
    ax.legend()
    save("17_search_space_scaling.png", "N! × binomial(N−1,K−1) architecture count")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for position, design in enumerate(designs):
        subset = [r for r in rows if r["design"] == design and r["route_s"] is not None]
        axes[0].boxplot([r["route_s"] for r in subset], positions=[position], widths=.55)
        axes[1].boxplot([r["odb_archive_bytes"] / 1048576 for r in subset],
                        positions=[position], widths=.55)
    for ax, title, ylabel in zip(axes, ("OpenROAD route runtime", "Compressed routed ODB storage"),
                                 ("seconds", "MiB per row")):
        ax.set_xticks(range(len(designs)), designs)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
    save("18_runtime_and_storage_scaling.png", "Recorded final route time and archive storage")

    manifest_path = OUT / "figures_manifest.json"
    manifest_path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"figures": len(manifest), "manifest": str(manifest_path),
                      "source_data": str(SOURCE_DATA)}))


if __name__ == "__main__":
    main()
