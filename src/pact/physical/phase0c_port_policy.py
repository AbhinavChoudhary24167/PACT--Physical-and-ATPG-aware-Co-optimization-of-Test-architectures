"""Frozen Nangate45 Phase-0C edge-port policy, in integer DEF database units."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


PIN_SIZE_DBU = 280
TRACK_Y_ORIGIN_DBU = 140
TRACK_Y_STEP_DBU = 560
EDGE_MARGIN_DBU = 2000
MIN_PORT_SEPARATION_DBU = 1120


def free_track(nominal: int, existing: list[int], used: list[int],
               ylo: int, yhi: int) -> int:
    candidates = range(TRACK_Y_ORIGIN_DBU, yhi, TRACK_Y_STEP_DBU)
    legal = [y for y in candidates if ylo + EDGE_MARGIN_DBU <= y <= yhi - EDGE_MARGIN_DBU
             and all(abs(y - other) >= MIN_PORT_SEPARATION_DBU for other in existing + used)]
    if not legal:
        raise ValueError("No open metal5 edge track for scan port")
    return min(legal, key=lambda y: (abs(y - nominal), y))


def port_centers(die: tuple[int, int, int, int],
                 existing_pins: list[tuple[str, int, int]], k: int) -> dict[str, tuple[int, int]]:
    if k < 1:
        raise ValueError("K must be positive")
    xlo, ylo, xhi, yhi = die
    test_si = [position for name, *position in existing_pins if name == "test_si"]
    if len(test_si) != 1:
        raise ValueError("Expected exactly one frozen test_si pin")
    left_existing = [y for name, x, y in existing_pins
                     if name != "test_so" and x < xlo + 1000]
    right_existing = [y for name, x, y in existing_pins
                      if name != "test_so" and x > xhi - 1000]
    left_used: list[int] = []
    right_used: list[int] = []
    output_y = free_track((ylo + yhi) // 2, left_existing, left_used, ylo, yhi)
    left_used.append(output_y)
    result = {"test_si": tuple(test_si[0]),
              "test_so": (xlo + PIN_SIZE_DBU // 2, output_y)}
    for ci in range(1, k):
        nominal = ylo + (yhi - ylo) * (ci + 1) // (k + 1)
        input_y = free_track(nominal, right_existing, right_used, ylo, yhi)
        right_used.append(input_y)
        output_y = free_track(nominal, left_existing, left_used, ylo, yhi)
        left_used.append(output_y)
        result[f"test_si_{ci}"] = (xhi - PIN_SIZE_DBU // 2, input_y)
        result[f"test_so_{ci}"] = (xlo + PIN_SIZE_DBU // 2, output_y)
    return result


@lru_cache(maxsize=128)
def frozen_def_ports(path: Path, k: int) -> tuple[dict[str, tuple[int, int]], int]:
    text = path.read_text(encoding="utf-8")
    units = re.search(r"UNITS DISTANCE MICRONS (\d+)\s*;", text)
    die = re.search(r"DIEAREA \( (\d+) (\d+) \) \( (\d+) (\d+) \)\s*;", text)
    if not units or not die:
        raise ValueError("Frozen DEF units or die area missing")
    start = text.index("PINS ")
    end = text.index("END PINS", start)
    pin_block = text[start:end]
    pins = []
    for entry in re.finditer(r"(?m)^\s*- (\S+) \+ NET .*?(?=^\s*- |^END PINS|\Z)", pin_block,
                             re.MULTILINE | re.DOTALL):
        placed = re.search(r"\+ (?:PLACED|FIXED) \( (\d+) (\d+) \)", entry.group(0))
        if placed:
            pins.append((entry.group(1), int(placed.group(1)), int(placed.group(2))))
    return port_centers(tuple(map(int, die.groups())), pins, k), int(units.group(1))
