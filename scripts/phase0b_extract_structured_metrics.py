#!/usr/bin/env python3
"""Archive normalized physical metric families from OpenROAD JSON only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pact.physical.phase0b_structured_metrics import extract_structured_metrics


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    folder = ROOT / f"artifacts/raw/phase0b/physical/{args.design}/s{args.seed}/{args.method}"
    grt = json.loads((folder / "5_1_grt.json").read_text(encoding="utf-8"))
    drt = json.loads((folder / "5_2_route.json").read_text(encoding="utf-8"))
    metrics = extract_structured_metrics(grt, drt)
    metrics.update({"design": args.design, "physical_seed": args.seed, "method": args.method,
                    "structured_sources": [str((folder / name).relative_to(ROOT)).replace("\\", "/")
                                           for name in ("5_1_grt.json", "5_2_route.json")]})
    (folder / "structured_metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"drc": metrics["detailed_route_drc_errors"],
                      "congestion": metrics["congestion_classification"]}))


if __name__ == "__main__":
    main()
