#!/usr/bin/env python3
"""Check report links, decision consistency, figures, and frozen Phase-0 hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/PHASE0B_CONFLICT_ESTABLISHMENT_REPORT.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    text = REPORT.read_text(encoding="utf-8")
    analysis = json.loads((ROOT / "artifacts/derived/phase0b/conflict_analysis.json").read_text())
    if args.require_complete:
        config = json.loads((ROOT / "config/phase0b_campaign.json").read_text(encoding="utf-8"))
        expected = {(design, seed) for design in config["designs_predeclared"]
                    for seed in config["physical_seeds"]}
        pairs = analysis["pairs"]
        observed = {(pair["design"], pair["physical_seed"]) for pair in pairs}
        if (len(pairs) != len(expected) or observed != expected
                or not all(pair["complete"] and not pair["excluded_methods"]
                           and len(pair["qualified_rows"]) == len(pair["requested_routed_methods"])
                           for pair in pairs)
                or any(not summary["distinct_placement_qualification"]
                       for summary in analysis["design_summaries"].values())
                or analysis["completed_design_seed_pairs"] != len(expected)
                or analysis["classification"].startswith("PACT_PHASE0B_INCOMPLETE")):
            raise ValueError("Predeclared campaign is not fully qualified")
    if text.rstrip().splitlines()[-1] != f"`{analysis['classification']}`":
        raise ValueError("Report final classification differs from analysis")
    if any(f"| {number}." not in text for number in range(1, 15)):
        raise ValueError("Report omits a required decision answer")
    broken = []
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("https://", "http://")):
            continue
        if not (REPORT.parent / target).resolve().is_file():
            broken.append(target)
    if broken:
        raise ValueError(f"Broken local report links: {broken}")
    figures = json.loads((ROOT / "reports/figures/phase0b/figures_manifest.json").read_text())
    if len(figures) != 25 or any(not (ROOT / row["figure"]).is_file() for row in figures):
        raise ValueError("Required 24 design and one aggregate figures are missing")
    frozen = ROOT / "artifacts/manifests/phase0_evidence.sha256"
    checks = []
    for line in frozen.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        checks.append((ROOT / relative).is_file() and sha256(ROOT / relative) == expected)
    if len(checks) != 447 or not all(checks):
        raise ValueError("Frozen Phase-0 evidence changed")
    print(json.dumps({"report_links": len(re.findall(r"\]\(([^)]+)\)", text)),
                      "figures": len(figures), "phase0_evidence_checks": len(checks),
                      "classification": analysis["classification"]}))


if __name__ == "__main__":
    main()
