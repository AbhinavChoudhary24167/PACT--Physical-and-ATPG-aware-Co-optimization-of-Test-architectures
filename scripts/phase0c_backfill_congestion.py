#!/usr/bin/env python3
"""Add parsed GRT congestion to qualification records without losing originals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from pact.physical.phase0c_congestion import parse_grt_congestion


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    updated = 0
    unavailable = 0
    for metrics_path in sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json")):
        record = json.loads(metrics_path.read_text(encoding="utf-8"))
        stdout_path = metrics_path.parent / "route/stdout.log"
        if not stdout_path.is_file():
            unavailable += 1
            continue
        parsed = parse_grt_congestion(stdout_path.read_text(encoding="utf-8", errors="replace"))
        if parsed is None:
            unavailable += 1
            continue
        parsed["source_stdout_sha256"] = hashlib.sha256(stdout_path.read_bytes()).hexdigest()
        metrics = record["structured_metrics"]
        if metrics.get("congestion") == parsed:
            continue
        backup = metrics_path.parent / "route_metrics_pre_congestion.json"
        if not backup.exists():
            shutil.copy2(metrics_path, backup)
        metrics["congestion"] = parsed
        metrics["global_route_overflow"] = parsed["total"]["total_overflow"]
        metrics["layer_utilization"] = {name: layer["usage_percent"]
                                        for name, layer in parsed["layers"].items()}
        metrics["congestion_classification"] = "QUALIFIED_INITIAL_GLOBAL_ROUTE_REPORT"
        metrics_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        updated += 1
    print(json.dumps({"updated": updated, "unavailable": unavailable}))


if __name__ == "__main__":
    main()
