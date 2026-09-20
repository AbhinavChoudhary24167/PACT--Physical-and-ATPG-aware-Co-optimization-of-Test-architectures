#!/usr/bin/env python3
"""Check Phase-0C report, figure hashes, frozen baseline, and regeneration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from phase0c_report import ROOT, main as regenerate


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    report = ROOT / "reports/PACT_PHASE0C_REPORT.md"
    original = sha(report)
    regenerate()
    if sha(report) != original:
        raise ValueError("Report regeneration changed its bytes")
    text = report.read_text(encoding="utf-8")
    analysis = json.loads((ROOT / "artifacts/derived/phase0c/gate_analysis.json").read_text())
    if text.rstrip().splitlines()[-1] != f"`{analysis['classification']}`":
        raise ValueError("Report classification does not match script")
    answers_text = text.split("## Answers to the 28 required questions", 1)[1]
    if len(re.findall(r"(?m)^\| (?:[1-9]|1[0-9]|2[0-8]) \|", answers_text)) != 28:
        raise ValueError("Missing required report answers")
    links = re.findall(r"\]\(([^)]+)\)", text)
    broken = [link for link in links if not link.startswith(("https://", "http://"))
              and not (report.parent / link).resolve().is_file()]
    if broken:
        raise ValueError(f"Broken report links: {broken}")
    figures = json.loads((ROOT / "reports/figures/phase0c/figures_manifest.json").read_text())
    if len(figures) < 17:
        raise ValueError(f"Required at least 17 final figures, found {len(figures)}")
    for figure in figures:
        if sha(ROOT / figure["figure"]) != figure["sha256"]:
            raise ValueError("Figure hash mismatch")
        for source in figure["sources"]:
            if sha(ROOT / source["path"]) != source["sha256"]:
                raise ValueError("Figure source changed since generation")
    execution = json.loads((ROOT / "artifacts/manifests/phase0c/campaign_execution.json").read_text())
    if execution.get("freeze_commit") is None or execution.get("planned_routes") != 375:
        raise ValueError("Final campaign manifest is missing its frozen 375-row identity")
    if not all((ROOT / path).is_file() and sha(ROOT / path) == expected
               for path, expected in execution.get("frozen_input_sha256", {}).items()):
        raise ValueError("Frozen final-campaign inputs changed")
    recovery = json.loads((ROOT / "artifacts/manifests/phase0c/campaign_recovery.json").read_text())
    if recovery.get("eligible_routes") != 348 or analysis.get("recovery", {}).get("errors"):
        raise ValueError("Disk-floor recovery ledger is incomplete or invalid")
    report_manifest = json.loads((ROOT / "artifacts/manifests/phase0c/report_manifest.json").read_text())
    if report_manifest["report_sha256"] != sha(report):
        raise ValueError("Report manifest hash mismatch")
    if any(analysis["gates"].get(f"C{i}", {}).get("status") not in
           ("PASS", "FAIL", "NOT QUALIFIED") for i in range(1, 10)):
        raise ValueError("Gate status missing or invalid")
    lines = (ROOT / "artifacts/manifests/phase0c/phase0b_pre_edit.sha256").read_text().splitlines()
    mismatches = [path for line in lines for expected, path in [line.split("  ", 1)]
                  if not (ROOT / path).is_file() or sha(ROOT / path) != expected]
    if mismatches:
        raise ValueError(f"Frozen Phase-0B evidence changed: {mismatches[:5]}")
    print(json.dumps({"classification": analysis["classification"], "answers": 28,
                      "figures": len(figures), "phase0b_hashes_verified": len(lines),
                      "freeze_commit": execution["freeze_commit"],
                      "recovery_freeze_commit": recovery["recovery_freeze_commit"],
                      "report_sha256": sha(report)}))


if __name__ == "__main__":
    main()
