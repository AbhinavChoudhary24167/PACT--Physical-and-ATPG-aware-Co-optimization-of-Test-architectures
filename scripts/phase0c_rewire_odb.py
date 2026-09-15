#!/usr/bin/env python3
"""Build one isolated multi-chain placed ODB from a frozen Phase-0B seed.

Only FF SI nets, the existing test_so buffer input, and new test ports change.
All functional instance nets and placements are compared before writing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import odb


def connect_port(block, name: str, net, io: str, location: tuple[int, int, int, int], layer):
    term = odb.dbBTerm.create(net, name)
    if term is None:
        raise ValueError(f"Could not create {name}")
    term.setIoType(io)
    pin = odb.dbBPin.create(term)
    pin.setPlacementStatus("PLACED")
    odb.dbBox.create(pin, layer, *location)
    return term


def edge_pin_centers(block, side: str, xlo: int, xhi: int) -> list[int]:
    """Existing edge-pin centers, excluding the test output being relocated."""
    centers = []
    for term in block.getBTerms():
        if term.getName() == "test_so":
            continue
        for pin in term.getBPins():
            for box in pin.getBoxes():
                on_side = box.xMin() < xlo + 1000 if side == "left" else box.xMax() > xhi - 1000
                if on_side:
                    centers.append((box.yMin() + box.yMax()) // 2)
    return centers


def free_track(nominal: int, existing: list[int], used: list[int], ylo: int, yhi: int) -> int:
    """Choose the nearest metal5 Y track with two-track clearance on this edge."""
    track_origin, track_step = 140, 560  # frozen Nangate45 DEF track grid, in DBU
    candidates = range(track_origin, yhi, track_step)
    legal = [y for y in candidates if ylo + 2000 <= y <= yhi - 2000
             and all(abs(y - other) >= 1120 for other in existing + used)]
    if not legal:
        raise ValueError("No open metal5 edge track for scan port")
    return min(legal, key=lambda y: (abs(y - nominal), y))


def fingerprint(block):
    return {inst.getName(): {
        "master": inst.getMaster().getName(), "location": inst.getLocation(),
        "orientation": inst.getOrient(),
        "functional_nets": {term.getMTerm().getName():
                            (term.getNet().getName() if term.getNet() else None)
                            for term in inst.getITerms()
                            if not (inst.getMaster().getName() == "SDFF_X1" and term.getMTerm().getName() == "SI")
                            and not (inst.getMaster().getName() == "BUF_X1" and term.getMTerm().getName() == "A"
                                     and any(t.getName() == "test_so" for t in term.getInst().findITerm("Z").getNet().getBTerms()))}
    } for inst in block.getInsts()}


def rewire(source: Path, architecture: Path, output: Path) -> dict:
    arch = json.loads(architecture.read_text(encoding="utf-8"))
    chains = [tuple(chain["cells"]) for chain in arch["chains"]]
    db = odb.dbDatabase.create()
    odb.read_db(db, str(source))
    block = db.getChip().getBlock()
    before = fingerprint(block)
    ff = {inst.getName(): inst for inst in block.getInsts() if inst.getMaster().getName() == "SDFF_X1"}
    requested = [name for chain in chains for name in chain]
    if len(requested) != len(ff) or set(requested) != set(ff):
        raise ValueError("FF inventory mismatch")
    input_port = block.findBTerm("test_si")
    output_port = block.findBTerm("test_so")
    if input_port is None or output_port is None:
        raise ValueError("Frozen test ports missing")
    baseline_roots = [inst for inst in ff.values() if inst.findITerm("SI").getNet() == input_port.getNet()]
    # The original input may pass through a BUF_X1. Identify the unique
    # original root as the SI net of the source-order first FF when needed.
    if len(baseline_roots) != 1:
        input_buffers = [inst for inst in block.getInsts() if inst.getMaster().getName() == "BUF_X1"
                         and inst.findITerm("A").getNet() == input_port.getNet()]
        roots = [inst.findITerm("Z").getNet() for inst in input_buffers]
        baseline_roots = [inst for inst in ff.values() if inst.findITerm("SI").getNet() in roots]
    if len(baseline_roots) != 1:
        raise ValueError("Original scan root is ambiguous")
    root_net = baseline_roots[0].findITerm("SI").getNet()
    output_buffers = [inst for inst in block.getInsts() if inst.getMaster().getName() == "BUF_X1"
                      and inst.findITerm("Z").getNet() == output_port.getNet()]
    if len(output_buffers) != 1:
        raise ValueError("Original test_so buffer ambiguous")
    out_buffer = output_buffers[0]
    for inst in ff.values():
        inst.findITerm("SI").disconnect()
    die = block.getDieArea()
    layer = db.getTech().findLayer("metal5")
    if layer is None:
        raise ValueError("metal5 not found for added port pins")
    xlo, ylo, xhi, yhi = die.xMin(), die.yMin(), die.xMax(), die.yMax()
    pin_size = 280
    # Every Phase-0C variant uses a deterministic, track-aligned edge-port
    # policy. Avoid the existing functional edge pins, which otherwise cause
    # stubborn metal5 DRC violations at K=4 and above.
    left_existing = edge_pin_centers(block, "left", xlo, xhi)
    right_existing = edge_pin_centers(block, "right", xlo, xhi)
    left_used: list[int] = []
    right_used: list[int] = []
    out_pins = list(output_port.getBPins())
    if len(out_pins) != 1 or len(list(out_pins[0].getBoxes())) != 1:
        raise ValueError("Expected one inherited test_so pin shape")
    for box in list(out_pins[0].getBoxes()):
        odb.dbBox.destroy(box)
    output_center = free_track((ylo + yhi) // 2, left_existing, left_used, ylo, yhi)
    left_used.append(output_center)
    odb.dbBox.create(out_pins[0], layer, xlo, output_center - pin_size // 2,
                     xlo + pin_size, output_center + pin_size // 2)
    for ci, chain in enumerate(chains):
        if ci == 0:
            prior = root_net
        else:
            prior = odb.dbNet.create(block, f"phase0c_scan_in_{ci}")
            if prior is None:
                raise ValueError("Could not create input net")
            nominal = ylo + (yhi - ylo) * (ci + 1) // (len(chains) + 1)
            center = free_track(nominal, right_existing, right_used, ylo, yhi)
            right_used.append(center)
            connect_port(block, f"test_si_{ci}", prior, "INPUT",
                         (xhi - pin_size, center - pin_size // 2,
                          xhi, center + pin_size // 2), layer)
        for name in chain:
            si = ff[name].findITerm("SI")
            si.connect(prior)
            prior = ff[name].findITerm("Q").getNet()
            if si.getNet() is None:
                raise AssertionError("SI disconnected after stitching")
        if ci == 0:
            out_buffer.findITerm("A").disconnect()
            out_buffer.findITerm("A").connect(prior)
        else:
            nominal = ylo + (yhi - ylo) * (ci + 1) // (len(chains) + 1)
            center = free_track(nominal, left_existing, left_used, ylo, yhi)
            left_used.append(center)
            connect_port(block, f"test_so_{ci}", prior, "OUTPUT",
                         (xlo, center - pin_size // 2,
                          xlo + pin_size, center + pin_size // 2), layer)
    if fingerprint(block) != before:
        raise AssertionError("Functional connection or placement changed")
    for ci, chain in enumerate(chains):
        expected = root_net if ci == 0 else block.findBTerm(f"test_si_{ci}").getNet()
        for name in chain:
            inst = ff[name]
            if inst.findITerm("SI").getNet() != expected:
                raise AssertionError("Stitched chain mismatch")
            expected = inst.findITerm("Q").getNet()
        observed = out_buffer.findITerm("A").getNet() if ci == 0 else block.findBTerm(f"test_so_{ci}").getNet()
        if observed != expected:
            raise AssertionError("Scan-out endpoint mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    odb.write_db(db, str(output))
    return {"status": "PASS", "source_odb": str(source), "architecture": str(architecture),
            "output_odb": str(output), "FF_count": len(ff), "K": len(chains),
            "functional_connections_placement_unchanged": True,
            "SI_SO_topology_verified": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--architecture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rewire(args.source, args.architecture, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
