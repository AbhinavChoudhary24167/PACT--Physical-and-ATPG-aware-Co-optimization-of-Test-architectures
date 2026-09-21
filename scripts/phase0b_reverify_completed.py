#!/usr/bin/env python3
"""Add explicit pair identity to completed scan verification records."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from phase0b_run_command import run


ROOT = Path(__file__).resolve().parents[1]
VENV = Path("/root/pact-deps/pact-venv/bin/python")


def main() -> None:
    for design in ("s5378", "s9234", "s15850"):
        for seed in (11, 13, 17, 19, 23):
            folder = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
            plan_path = folder / "plan.json"
            if not plan_path.is_file():
                continue
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            # Only revise already completed physical pairs; never race a live route.
            methods = plan["distinct_route_canonical_methods"]
            if not all((ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}/{m}/scan_route_metrics.json").is_file()
                       for m in methods):
                continue
            for method in methods:
                target = folder / f"{method}.rewire_verification.json"
                old = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
                if old and all(old.get(key) == value for key, value in
                               (("design", design), ("physical_seed", seed), ("method", method))):
                    continue
                if old:
                    archive = folder / f"{method}.rewire_verification.pre_pair_identity.json"
                    if not archive.exists():
                        shutil.copy2(target, archive)
                script = "phase0b_verify_baseline.py" if method == "B0" else "phase0b_verify_rewire.py"
                command = [str(VENV), str(ROOT / "scripts" / script),
                           "--design", design, "--seed", str(seed)]
                if method != "B0":
                    command += ["--method", method]
                result = run(command, ROOT / f"artifacts/raw/phase0b/runs/{design}/s{seed}/{method}_verify_pair_identity",
                             ROOT, 180, [target])
                if result["exit_code"] != 0 or result["timed_out"]:
                    raise RuntimeError(f"Reverification failed for {design} s{seed} {method}")
                print(f"REVERIFIED {design} s{seed} {method}", flush=True)


if __name__ == "__main__":
    main()
