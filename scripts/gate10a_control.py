"""Gate 10A admission and immutable control records; no optimization policy."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from pact_experiment_receipts import atomic_write, now, resources

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/gate10a"


def binding(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def preflight() -> None:
    parent = "53ebab37fd76970d7c5e676b0caec13c7c16296e"
    initial = "e5dbf26721f3e0e17aac9d3569691b322969b4c0"
    if git("diff", initial, parent):
        raise ValueError("Published parent differs from initially audited tree")
    record = {
        "schema": "pact_gate10a_preflight_v1", "created_utc": now(),
        "campaign": "PACT_GATE10A_PRACTICAL_IMPACT_VALIDATION",
        "initial_head": initial, "initial_git_status_porcelain": "",
        "initial_cleanliness_observation": "First repository git status --short returned no entries",
        "published_parent": parent, "published_parent_tree": git("rev-parse", parent + "^{tree}"),
        "initial_and_published_trees_identical": True,
        "branch": git("branch", "--show-current"),
        "request": binding(Path("C:/Users/Abhinav/.codex/attachments/5e8c8ca0-4317-4108-94ca-2a41e6e1be39/Pasted text.txt")),
        "host": {"platform": platform.platform(), "python": sys.version, "executable": sys.executable},
        "resources": resources({"workspace": ROOT, "retained_experiments": "D:/", "preserved_cache": "F:/"}),
        "initial_command_observations": [
            {"command": "Get-Content pasted request; rg --files -g AGENTS.md; git status --short at workspace parent", "result": "Request read; parent is not Git repository; nested PACT checkout located"},
            {"command": "git -C PACT status --short; git log -5 --oneline; git remote -v", "result": "Clean Gate09 branch at initial_head; origin identified"},
            {"command": "wsl --list --quiet", "result": "Sandbox E_ACCESSDENIED; read-only escalation assigned to tool audit lane"},
            {"command": "git switch -c development/gate10a-practical-impact-validation; git merge --ff-only origin/main", "result": "Branch created, fast-forwarded to identical published parent tree"},
        ],
        "scientific_execution_started": False,
        "receipt_timing": "Control record created after initial discovery; initial commands are recorded retrospectively, with no fabricated execution timestamps",
    }
    atomic_write(OUT / "control/preflight.json", record, immutable=True)


def seal_preregistration() -> None:
    head = git("rev-parse", "HEAD")
    files = ["preregistration.md", "methodology.md", "selected_architectures.json",
             "artifact_reuse_manifest.json", "tool_provenance.json", "protocol.json"]
    entries = [binding(OUT / name) for name in files]
    for name in files:
        if git("diff", "HEAD", "--", str(OUT / name)):
            raise ValueError("Preregistration file differs from committed version: " + name)
        subprocess.check_call(["git", "ls-files", "--error-unmatch", str(OUT / name)], cwd=ROOT,
                              stdout=subprocess.DEVNULL)
    atomic_write(OUT / "control/preregistration_commit.json", {
        "schema": "pact_gate10a_preregistration_commit_v1", "created_utc": now(),
        "commit": head, "files": entries, "scientific_execution_started": False,
    }, immutable=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["preflight", "seal-preregistration"])
    args = parser.parse_args()
    {"preflight": preflight, "seal-preregistration": seal_preregistration}[args.action]()
