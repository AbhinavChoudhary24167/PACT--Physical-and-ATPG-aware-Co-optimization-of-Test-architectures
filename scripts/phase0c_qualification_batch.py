#!/usr/bin/env python3
"""Run the one-design/one-seed qualification matrix with one campaign deadline."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from phase0c_run_route import ROOT, route_one


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", default="s5378")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--cap-s", type=int, default=3600)
    args = parser.parse_args()
    campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text())
    if args.design not in campaign["designs"] or args.seed not in campaign["physical_seeds"]:
        raise ValueError("Unregistered design or seed")
    matrix = [(k, method) for k in campaign["K_values"]
              for method in campaign["route_families_each_K"]]
    matrix.insert(len(campaign["route_families_each_K"]), (1, campaign["native_B1_k1_method"]))
    target = ROOT / f"artifacts/derived/phase0c/{args.design}/s{args.seed}/qualification_batch.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    prior = json.loads(target.read_text()) if target.exists() else {"runs": {}}
    runs = prior["runs"]
    deadline = time.monotonic() + args.cap_s
    for k, method in matrix:
        left = int(deadline - time.monotonic())
        key = f"k{k}/{method}"
        if left <= 0:
            runs[key] = {"status": "CAMPAIGN_CAP_REACHED", "timestamp_utc": datetime.now(timezone.utc).isoformat()}
            break
        try:
            result = route_one(args.design, args.seed, k, method, left)
            label = result["status"]
        except Exception as exc:
            label = "DRIVER_EXCEPTION"
            result = {"status": label, "exception": repr(exc)}
        runs[key] = {"status": label, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "remaining_campaign_s": max(0, int(deadline - time.monotonic())),
                     "detail": result if label != "QUALIFIED" else
                     {"DRC_errors": result["DRC_errors"], "physical_primary_um": result["physical_primary_um"]}}
        target.write_text(json.dumps({"schema_version": "phase0c-qualification-batch-1",
                                      "design": args.design, "physical_seed": args.seed,
                                      "planned": len(matrix), "runs": runs}, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"K": k, "method": method, "status": label,
                          "remaining_campaign_s": runs[key]["remaining_campaign_s"]}), flush=True)
    print(json.dumps({"planned": len(matrix), "recorded": len(runs),
                      "qualified": sum(r["status"] == "QUALIFIED" for r in runs.values())}))


if __name__ == "__main__":
    main()
