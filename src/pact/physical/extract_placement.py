"""Strict extraction of named FF coordinates from DEF placement."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from pact.scan.model import ScanCell


def extract_def_scan_cells(path: Path, ff_names: Iterable[str], clock_domain: str) -> tuple[ScanCell, ...]:
    """Read DEF component centers in microns for an exact FF identity set.

    This parser uses DEF component origins. A future OpenDB extraction should
    resolve pin locations and orientation for routed scan-wire estimates.
    """
    text = path.read_text(encoding="utf-8")
    units_match = re.search(r"\bUNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", text, re.IGNORECASE)
    if not units_match:
        raise ValueError("DEF units missing")
    dbu = int(units_match.group(1))
    if dbu <= 0:
        raise ValueError("Invalid DEF DBU")
    section = re.search(r"\bCOMPONENTS\s+\d+\s*;(.*?)\bEND\s+COMPONENTS\b", text, re.IGNORECASE | re.DOTALL)
    if not section:
        raise ValueError("DEF COMPONENTS section missing")
    requested = set(ff_names)
    if not requested:
        raise ValueError("FF identity set is empty")
    found: dict[str, ScanCell] = {}
    for match in re.finditer(r"(?:^|\n)\s*-\s+(\S+)\s+\S+(.*?)\s*;", section.group(1), re.DOTALL):
        name, body = match.group(1), match.group(2)
        if name not in requested:
            continue
        if name in found:
            raise ValueError(f"Duplicate DEF component {name}")
        placement = re.search(r"\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", body, re.IGNORECASE)
        if not placement:
            raise ValueError(f"FF {name} lacks PLACED/FIXED DEF coordinates")
        found[name] = ScanCell(name, int(placement.group(1)) / dbu, int(placement.group(2)) / dbu, clock_domain)
    if set(found) != requested:
        raise ValueError(f"FFs absent from DEF: {sorted(requested - set(found))}")
    return tuple(found[name] for name in sorted(found))
