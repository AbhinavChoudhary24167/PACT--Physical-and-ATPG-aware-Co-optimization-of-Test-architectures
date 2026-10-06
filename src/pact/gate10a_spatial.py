"""Deterministic Gate 10A spatial summaries, without changing frozen H4/H8.

Activity is ground-plus-pin capacitance times measured load/unload transitions,
averaged over measured shift cycles. It is a locality proxy in fF transitions
per cycle, not watts. Static IR is a distinct temporal approximation.

Primary comparisons use the preregistered occupied powered-instance domain.
Every full-grid vector and missing bin is retained. Sparse/constant records do
not acquire invented zero measurements or a favorable primary statistic.
"""
from __future__ import annotations

import math
import json
from collections.abc import Iterable, Mapping, Sequence

import numpy as np

from pact.physical_effect import spatial_bin


RESOLUTIONS = (4, 8)
ACTIVITY_UNIT = "fF_transitions_per_shift_cycle"


def _number(value, label: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"Invalid {label}")
    return result


def grid_metadata(bounds_um: Sequence[float], resolution: int) -> dict:
    """Return the unchanged lower-left, row-major frozen die grid geometry."""
    if type(resolution) is not int or resolution not in RESOLUTIONS:
        raise ValueError("Gate 10A requires the frozen 4x4 or 8x8 grid")
    if len(bounds_um) != 4:
        raise ValueError("Four die bounds required")
    bounds = [_number(v, "die coordinate", nonnegative=False) for v in bounds_um]
    x0, y0, x1, y1 = bounds
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid die bounds")
    dx, dy = (x1 - x0) / resolution, (y1 - y0) / resolution
    cells = []
    for by in range(resolution):
        for bx in range(resolution):
            cells.append(dict(bin_id=by * resolution + bx, bx=bx, by=by,
                              bounds_um=[x0 + bx * dx, y0 + by * dy,
                                         x0 + (bx + 1) * dx, y0 + (by + 1) * dy]))
    return dict(resolution=resolution, bounds_um=bounds, bins=cells,
                ordering="by*resolution+bx; lower-left origin",
                boundary_rule="interior boundary enters upper index; outer maximum clamps to final index")


def _bin(row: Mapping, grid: Mapping) -> int:
    point = [_number(row[axis], axis, nonnegative=False) for axis in ("x_um", "y_um")]
    return spatial_bin(point, grid["bounds_um"], grid["resolution"])


def _identified(rows: Iterable[Mapping], id_key: str) -> list[Mapping]:
    rows = list(rows)
    identities = [row[id_key] for row in rows]
    if any(not isinstance(key, str) or not key for key in identities):
        raise ValueError("Every observation requires a nonempty string identity")
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate observation identity")
    return sorted(rows, key=lambda row: row[id_key])


def regional_activity(net_rows: Iterable[Mapping], bounds_um: Sequence[float],
                      shift_cycles: int, resolution: int) -> dict:
    """Reconstruct mean weighted activity from a complete Gate 09 net CSV.

    ``net_rows`` use net,x_um,y_um,transitions,ground_pin_ff CSV columns. A
    missing static net capacitance is excluded only when transitions is zero,
    mirroring the frozen analyzer. Switched missing capacitance is an error.
    This summary is additional Gate 10A evidence; H4/H8 remain the frozen
    maximum over cycle and bin, not the maximum of this averaged vector.
    """
    if type(shift_cycles) is not int or shift_cycles < 1:
        raise ValueError("Positive complete measured shift-cycle count required")
    grid = grid_metadata(bounds_um, resolution)
    weighted = [[] for _ in grid["bins"]]
    raw = [[] for _ in grid["bins"]]
    supports = [0] * resolution**2
    excluded = []
    rows = _identified(net_rows, "net")
    if not rows:
        raise ValueError("Complete activity inventory cannot be empty")
    for row in rows:
        bid = _bin(row, grid)
        transitions = _number(row["transitions"], "transition count")
        if not transitions.is_integer():
            raise ValueError("Transition counts must be integers")
        cap = row["ground_pin_ff"]
        if cap is None or cap == "":
            if transitions:
                raise ValueError("Switched net missing capacitance: " + row["net"])
            cap = 0.0
            excluded.append(row["net"])
        cap = _number(cap, "ground-plus-pin capacitance")
        weighted[bid].append(cap * transitions)
        raw[bid].append(int(transitions))
        supports[bid] += 1
    totals = [math.fsum(values) for values in weighted]
    if any(not math.isfinite(value) for value in totals):
        raise ValueError("Nonfinite regional activity product")
    return dict(grid=grid, values=[value / shift_cycles for value in totals],
                unit=ACTIVITY_UNIT, total_cap_ff_transitions=totals,
                total_transitions=[sum(values) for values in raw], support_counts=supports,
                shift_cycles=shift_cycles, missing_static_caps=excluded,
                scope="all_data; clocks and PG excluded by frozen net inventory",
                attribution="whole-net ground-plus-pin capacitance at source cell origin or input port center",
                temporal_population="all measured load and unload shift cycles; setup/capture excluded")


def powered_domain(instance_rows: Iterable[Mapping], bounds_um: Sequence[float], resolution: int) -> dict:
    """Freeze the primary bin population using explicit instance role flags.

    Rows have ``id,x_um,y_um,powered,physical_only``. The caller must derive
    flags from Liberty/database evidence; an omitted flag is not inferred.
    """
    grid = grid_metadata(bounds_um, resolution)
    supports = [0] * resolution**2
    for row in _identified(instance_rows, "id"):
        if type(row["powered"]) is not bool or type(row["physical_only"]) is not bool:
            raise ValueError("Explicit Boolean powered and physical_only flags required")
        bid = _bin(row, grid)
        if row["powered"] and not row["physical_only"]:
            supports[bid] += 1
    return dict(bin_ids=[bid for bid, count in enumerate(supports) if count],
                occupied_mask=[bool(count) for count in supports], support_counts=supports,
                definition="bins with non-physical-only Liberty-powered instance origins")


def aggregate_points(points: Iterable[Mapping], bounds_um: Sequence[float], resolution: int,
                     *, reduction: str, unit: str, complete_inventory: bool = True) -> dict:
    """Aggregate already-normalized observations by frozen region.

    Points use ``id,x_um,y_um,value``. ``sum`` is for an exhaustive per-instance
    power inventory in W; ``maximum`` is for static IR drop in V. Sum over an
    empty but complete region is zero. Maximum over an empty region is missing.
    Missing observations make their bin unavailable; an incomplete inventory
    makes all bins unavailable, while finite diagnostic aggregates are retained.
    """
    if (reduction, unit) not in (("sum", "W"), ("maximum", "V")):
        raise ValueError("Registered aggregation is power sum W or IR maximum V")
    if type(complete_inventory) is not bool:
        raise ValueError("Explicit complete-inventory flag required")
    grid = grid_metadata(bounds_um, resolution)
    members = [[] for _ in grid["bins"]]
    support = [0] * resolution**2
    missing = [0] * resolution**2
    for row in _identified(points, "id"):
        bid = _bin(row, grid)
        support[bid] += 1
        if row["value"] is None or row["value"] == "":
            missing[bid] += 1
        else:
            members[bid].append(_number(row["value"], unit))
    diagnostic = [(math.fsum(values) if reduction == "sum" else max(values) if values else None)
                  for values in members]
    if any(value is not None and not math.isfinite(value) for value in diagnostic):
        raise ValueError("Nonfinite regional aggregate")
    values = [value if complete_inventory and not missing[bid] else None
              for bid, value in enumerate(diagnostic)]
    return dict(grid=grid, values=values, unit=unit, reduction=reduction,
                support_counts=support, missing_observation_counts=missing,
                complete_inventory=complete_inventory, diagnostic_finite_aggregates=diagnostic,
                missing_bin_ids=[bid for bid, value in enumerate(values) if value is None])


def crosscheck_source_origins(net_rows: Iterable[Mapping], instance_rows: Iterable[Mapping],
                             *, tolerance_um: float = 1e-9) -> dict:
    """Verify activity and power share source-cell origins; ports stay explicit."""
    tolerance_um = _number(tolerance_um, "coordinate tolerance")
    instances = {row["id"]: row for row in _identified(instance_rows, "id")}
    checked, ports = 0, []
    for row in _identified(net_rows, "net"):
        source = row["source"]
        if source.startswith("PORT/"):
            ports.append(row["net"])
            continue
        if "/" not in source:
            raise ValueError("Invalid activity source identity: " + source)
        origin = instances.get(source.rsplit("/", 1)[0])
        if origin is None:
            raise ValueError("Activity source missing from instance inventory: " + source)
        for axis in ("x_um", "y_um"):
            actual = _number(row[axis], axis, nonnegative=False)
            expected = _number(origin[axis], axis, nonnegative=False)
            if abs(actual - expected) > tolerance_um:
                raise ValueError("Activity/power source-origin mismatch: " + source)
        checked += 1
    return dict(status="PASS", checked_source_nets=checked, external_input_nets=ports,
                tolerance_um=tolerance_um, ports="activity at input BTerm center; no internal-cell power source")


def _average_ranks(values: Sequence[float]) -> np.ndarray:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = np.empty(len(values), dtype=float)
    first = 0
    while first < len(order):
        last = first + 1
        while last < len(order) and values[order[last]] == values[order[first]]:
            last += 1
        ranks[order[first:last]] = (first + 1 + last) / 2.0
        first = last
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    # Scaling before centering avoids overflow for otherwise finite vectors.
    x, y = np.asarray(left, float), np.asarray(right, float)
    x = x / (float(np.max(np.abs(x))) or 1.0)
    y = y / (float(np.max(np.abs(y))) or 1.0)
    x, y = x - x.mean(), y - y.mean()
    value = np.dot(x, y) / math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    return max(-1.0, min(1.0, float(value)))


def _comparison(left: Sequence[float], right: Sequence[float], bids: Sequence[int]) -> dict:
    result = dict(n_bins=len(bids), bin_ids=list(bids), pearson_r=None, spearman_rho=None,
                  hotspot_iou=None, hotspot_k=None, activity_hotspot_bins=[], physical_hotspot_bins=[])
    if len(bids) < 3:
        return dict(result, status="UNAVAILABLE", reason="fewer_than_three_bins")
    if len(set(left)) == 1 or len(set(right)) == 1:
        return dict(result, status="UNAVAILABLE", reason="constant_vector")
    k = math.ceil(len(bids) / 4)
    top_x = sorted(range(len(bids)), key=lambda index: (-left[index], bids[index]))[:k]
    top_y = sorted(range(len(bids)), key=lambda index: (-right[index], bids[index]))[:k]
    sx, sy = {bids[index] for index in top_x}, {bids[index] for index in top_y}
    result.update(status="AVAILABLE", reason=None, pearson_r=_pearson(left, right),
                  spearman_rho=_pearson(_average_ranks(left), _average_ranks(right)),
                  hotspot_iou=len(sx & sy) / len(sx | sy), hotspot_k=k,
                  activity_hotspot_bins=[bids[index] for index in top_x],
                  physical_hotspot_bins=[bids[index] for index in top_y])
    return result


def compare_regions(activity_vector: Sequence[float | None], physical_vector: Sequence[float | None],
                    domain_bins: Sequence[int]) -> dict:
    """Both primary correlations and fixed top-quartile IoU, no selection.

    Domain bins must be frozen from non-physical powered instance occupancy,
    independently of outcomes. An unavailable primary is not rescued by the
    separately labeled finite-subset diagnostic. Ties use average ranks for
    Spearman and lowest bin IDs at the hotspot cutoff. Constant-vector hotspot
    comparisons are unavailable even though a deterministic tie order exists.
    """
    if len(activity_vector) not in (16, 64) or len(physical_vector) != len(activity_vector):
        raise ValueError("Complete matching 4x4/8x8 vectors required")
    bids = list(domain_bins)
    if any(type(bid) is not int or bid < 0 or bid >= len(activity_vector) for bid in bids):
        raise ValueError("Invalid domain bin")
    if len(set(bids)) != len(bids):
        raise ValueError("Duplicate domain bin")
    bids.sort()
    x = [None if value is None else _number(value, "activity vector") for value in activity_vector]
    y = [None if value is None else _number(value, "physical vector") for value in physical_vector]
    finite = [bid for bid in bids if x[bid] is not None and y[bid] is not None]
    missing = [bid for bid in bids if bid not in finite]
    if missing:
        primary = dict(status="UNAVAILABLE", reason="missing_occupied_domain_measurements",
                       n_bins=len(bids), bin_ids=bids, pearson_r=None, spearman_rho=None,
                       hotspot_iou=None, hotspot_k=None, activity_hotspot_bins=[], physical_hotspot_bins=[])
    else:
        primary = _comparison([x[bid] for bid in bids], [y[bid] for bid in bids], bids)
    return dict(primary=primary,
                diagnostic_pairwise_finite=_comparison([x[bid] for bid in finite], [y[bid] for bid in finite], finite),
                activity_vector=x, physical_vector=y, domain_bins=bids, missing_domain_bins=missing,
                statistic_policy="both Pearson and average-tie-rank Spearman; no best-statistic selection",
                hotspot_policy="top ceil(occupied-domain bins/4); descending value, ascending bin ID; IoU")


def power_points(power_rows: Iterable[Mapping]) -> dict:
    """Normalize the per-instance W export without choosing a power statistic.

    Rows use instance,x_um,y_um,internal_w,switching_w,leakage_w,total_w.
    The primary dynamic value is internal plus switching, with both retained
    separately. Empty values remain missing. Total is the source-reported
    total, not a substituted value calculated from other fields.
    """
    components = ("internal_w", "switching_w", "leakage_w", "total_w")
    result = {component: [] for component in (*components, "dynamic_w")}
    for row in _identified(power_rows, "instance"):
        point = dict(id=row["instance"],
                     x_um=_number(row["x_um"], "x_um", nonnegative=False),
                     y_um=_number(row["y_um"], "y_um", nonnegative=False))
        values = {component: None if row[component] is None or row[component] == ""
                  else _number(row[component], component) for component in components}
        values["dynamic_w"] = (None if values["internal_w"] is None or values["switching_w"] is None
                               else math.fsum((values["internal_w"], values["switching_w"])))
        for component, value in values.items():
            if value is not None and not math.isfinite(value):
                raise ValueError("Nonfinite dynamic power")
            result[component].append(dict(point, value=value))
    return result


def ir_terminal_points(voltage_rows: Iterable[Mapping], instance_rows: Iterable[Mapping],
                       *, supply_voltage_v: float) -> list[dict]:
    """Map PDNSim terminal voltages to matching instance origins for comparison.

    Raw columns are Instance,Terminal,Layer,X location,Y location,Voltage, in
    um and V. Raw terminal coordinates and voltages remain in returned points.
    IR drop is the registered supply minus voltage. This samples connected
    instance-terminal PDN nodes, not every conductor point or transient droop.
    Unknown instance identity, duplicate observations, or voltage above the
    selected supply fails qualification instead of silently removing evidence.
    """
    supply = _number(supply_voltage_v, "supply voltage V")
    if supply == 0:
        raise ValueError("Positive registered supply voltage required")
    instances = {row["id"]: row for row in _identified(instance_rows, "id")}
    points = []
    for row in voltage_rows:
        name = row["Instance"]
        origin = instances.get(name)
        if origin is None:
            raise ValueError("PDNSim terminal instance missing from inventory: " + name)
        tx, ty = [_number(row[axis], axis, nonnegative=False) for axis in ("X location", "Y location")]
        voltage = None if row["Voltage"] is None or row["Voltage"] == "" else _number(row["Voltage"], "Voltage")
        drop = None if voltage is None else supply - voltage
        if drop is not None and drop < 0:
            raise ValueError("PDNSim voltage exceeds registered supply")
        identity = json.dumps([name, row["Terminal"], row["Layer"], tx, ty], separators=(",", ":"))
        points.append(dict(id=identity, instance=name, terminal=row["Terminal"], layer=row["Layer"],
                           x_um=_number(origin["x_um"], "instance x_um", nonnegative=False),
                           y_um=_number(origin["y_um"], "instance y_um", nonnegative=False),
                           terminal_x_um=tx, terminal_y_um=ty, voltage_v=voltage,
                           supply_voltage_v=supply, value=drop))
    return list(_identified(points, "id"))


def current_density(current_a: float, width_um: float | None, thickness_um: float | None) -> dict:
    """Convert branch current using known metal cross-section; never node area.

    Signed currents are converted to magnitude. Width and thickness must be
    independently known. A current value alone remains current and supplies
    no current-density or electromigration/signoff result.
    """
    current = _number(current_a, "current A", nonnegative=False)
    if width_um is None or thickness_um is None:
        return dict(status="NOT_EVALUATED", reason="missing_metal_cross_section", current_a=current,
                    density_a_per_um2=None, density_a_per_cm2=None)
    width = _number(width_um, "metal width um")
    thickness = _number(thickness_um, "metal thickness um")
    if width == 0 or thickness == 0:
        raise ValueError("Positive metal cross-section dimensions required")
    density = abs(current) / (width * thickness)
    if not math.isfinite(density) or not math.isfinite(density * 1e8):
        raise ValueError("Nonfinite current density")
    return dict(status="AVAILABLE", reason=None, current_a=current, width_um=width,
                thickness_um=thickness, density_a_per_um2=density, density_a_per_cm2=density * 1e8,
                interpretation="branch-current magnitude divided by metal cross-section; no EM threshold applied")
