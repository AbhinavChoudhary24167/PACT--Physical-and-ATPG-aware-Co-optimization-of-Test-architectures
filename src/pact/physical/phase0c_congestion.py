"""Parse the OpenROAD GRT-0096 per-layer congestion table from saved stdout."""
from __future__ import annotations

import re


ROW = re.compile(r"^\s*(metal\d+|Total)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+"
                 r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*$")


def parse_grt_congestion(stdout: str) -> dict | None:
    marker = "[INFO GRT-0096] Final congestion report:"
    if stdout.count(marker) != 1:
        return None
    lines = stdout.split(marker, 1)[1].splitlines()
    rows = {}
    for line in lines:
        found = ROW.match(line)
        if found:
            layer, resource, demand, usage, horizontal, vertical, total = found.groups()
            rows[layer] = {
                "resource": int(resource), "demand": int(demand),
                "usage_percent": float(usage),
                "max_horizontal_overflow": int(horizontal),
                "max_vertical_overflow": int(vertical),
                "total_overflow": int(total),
            }
            if layer == "Total":
                break
    if "Total" not in rows or not any(name.startswith("metal") for name in rows):
        return None
    total = rows.pop("Total")
    if sum(row["resource"] for row in rows.values()) != total["resource"]:
        raise ValueError("GRT layer resource sum differs from reported total")
    if sum(row["demand"] for row in rows.values()) != total["demand"]:
        raise ValueError("GRT layer demand sum differs from reported total")
    return {"stage": "initial_global_route_before_incremental_repairs",
            "layers": rows, "total": total,
            "quantity_type": "reported routing resource/demand and overflow, not detailed-route congestion"}
