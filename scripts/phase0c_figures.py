#!/usr/bin/env python3
"""Reproducible qualification-only figures from machine-readable Phase-0C rows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pact.scan.phase0c import architecture_space_log10


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/figures/phase0c"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = sorted((ROOT / "artifacts/derived/phase0c/s5378/s11").glob("k*/*.proxy.json"))
    rows = [json.loads(path.read_text()) for path in inputs]
    if not rows:
        raise ValueError("No machine-readable qualification rows")
    methods = sorted({r["method"] for r in rows})
    manifest = []

    def save(name: str, source_paths: list[Path], description: str):
        target = OUT / name
        plt.tight_layout()
        plt.savefig(target, dpi=160, metadata={"Software": "PACT Phase-0C matplotlib"})
        plt.close()
        manifest.append({"figure": str(target.relative_to(ROOT)).replace("\\", "/"),
                         "sha256": digest(target), "description": description,
                         "sources": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                                      "sha256": digest(path)} for path in source_paths]})

    fig, ax = plt.subplots(figsize=(7, 4))
    b0 = sorted((r for r in rows if r["method"] == "B0"), key=lambda r: r["K"])
    ax.plot([r["K"] for r in b0], [r["chain_statistics"]["parallel_shift_cycles"] for r in b0], marker="o")
    ax.set(xlabel="Number of parallel chains K", ylabel="Approximate parallel shift clocks",
           title="s5378 seed 11: frozen 117 patterns; capture excluded")
    ax.grid(alpha=.25)
    save("qualification_shift_cycles.png", inputs, "Logical test-cycle cost, one design and physical seed")

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in methods:
        seq = sorted((r for r in rows if r["method"] == method), key=lambda r: r["K"])
        ax.plot([r["K"] for r in seq], [r["activity"]["grids"]["8"]["H_eff"] for r in seq],
                marker="o", label=method)
    ax.set(xlabel="K", ylabel="H_eff8, dimensionless proxy", title="Qualification only: effective switching by K")
    ax.legend(ncol=3, fontsize=8)
    ax.grid(alpha=.25)
    save("qualification_effective_activity_by_k.png", inputs, "Fanout-weighted activity proxy, not current or power")

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in methods:
        seq = [r for r in rows if r["method"] == method]
        ax.scatter([r["scan_geometry"]["total_scan_hpwl_um"] for r in seq],
                   [r["activity"]["grids"]["8"]["H_eff"] for r in seq], label=method)
    ax.set(xlabel="Port-aware scan FF-origin HPWL proxy (µm)", ylabel="H_eff8, dimensionless proxy",
           title="Qualification only: no routed Pareto claim")
    ax.legend(ncol=3, fontsize=8)
    ax.grid(alpha=.25)
    save("qualification_proxy_tradeoff.png", inputs, "Paired geometry/activity proxies; no physical conflict gate")

    dataset = ROOT / "artifacts/derived/phase0c/intervention_dataset.jsonl"
    if dataset.is_file():
        interventions = [json.loads(line) for line in dataset.read_text().splitlines()]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.axhline(0, color="gray", lw=.8)
        ax.axvline(0, color="gray", lw=.8)
        for method in sorted({r["parent_method"] for r in interventions}):
            seq = [r for r in interventions if r["parent_method"] == method]
            ax.scatter([r["delta"]["scan_hpwl_proxy_um"] for r in seq],
                       [r["delta"]["H_eff8_proxy"] for r in seq], label=method)
        ax.set(xlabel="Δ scan HPWL proxy (µm)", ylabel="Δ H_eff8 proxy",
               title="Legal local interventions; no routed effect")
        ax.legend()
        ax.grid(alpha=.25)
        save("qualification_intervention_deltas.png", [dataset], "Proxy-only local intervention deltas")

    bench = ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json"
    designs = json.loads(bench.read_text())["designs"]
    fig, ax = plt.subplots(figsize=(7, 4))
    for row in designs:
        n = row["scan_ff_count"]
        ax.plot([1, 2, 4, 8], [architecture_space_log10(n, k) for k in (1, 2, 4, 8)],
                marker="o", label=f"{row['design']} ({n} FFs)")
    ax.set(xlabel="K", ylabel="log10 legal labelled ordered architectures",
           title="Combinatorial space, before physical legality constraints")
    ax.legend()
    ax.grid(alpha=.25)
    save("qualification_search_space.png", [bench], "Theoretical labelled ordered-chain count")

    (OUT / "figures_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"figures": len(manifest), "manifest": str(OUT / "figures_manifest.json")}))


if __name__ == "__main__":
    main()
