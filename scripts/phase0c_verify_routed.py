#!/usr/bin/env python3
"""Verify routed scan paths through transparent BUF_X*/CLKBUF_X* cells."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import odb

from pact.physical.phase0c_port_policy import frozen_def_ports


def verify(routed: Path, architecture: Path) -> dict:
    arch = json.loads(architecture.read_text(encoding="utf-8"))
    db = odb.dbDatabase.create()
    odb.read_db(db, str(routed))
    block = db.getChip().getBlock()
    design = architecture.parent.parent.parent.name
    seed_folder = architecture.parent.parent.name
    frozen_def = (Path(__file__).resolve().parents[1]
                  / f"artifacts/raw/phase0b/placements/{design}/{seed_folder}/placed.def")
    expected_ports, _ = frozen_def_ports(frozen_def, len(arch["chains"]))
    for name, expected in expected_ports.items():
        term = block.findBTerm(name)
        if term is None:
            raise ValueError(f"Missing routed port {name}")
        boxes = [box for pin in term.getBPins() for box in pin.getBoxes()]
        if len(boxes) != 1:
            raise ValueError(f"Expected one shape for routed port {name}")
        box = boxes[0]
        observed = ((box.xMin() + box.xMax()) // 2, (box.yMin() + box.yMax()) // 2)
        if observed != tuple(expected):
            raise ValueError(f"Port {name} center {observed} differs from fixed policy {expected}")
    ff = {inst.getName(): inst for inst in block.getInsts() if inst.getMaster().getName() == "SDFF_X1"}
    expected_names = {cell["name"] for cell in arch["cells"]}
    if set(ff) != expected_names:
        raise ValueError("Routed FF inventory differs from architecture")
    buffers = {}
    for inst in block.getInsts():
        if not inst.getMaster().getName().startswith(("BUF_X", "CLKBUF_X")):
            continue
        a, z = inst.findITerm("A").getNet(), inst.findITerm("Z").getNet()
        if a is not None and z is not None:
            buffers.setdefault(a.getName(), []).append((z.getName(), inst.getName()))

    def path(start, target):
        frontier = [(start.getName(), [])]
        visited = set()
        solutions = []
        while frontier:
            net, traversed = frontier.pop(0)
            if net in visited:
                continue
            visited.add(net)
            if net == target.getName():
                solutions.append((net, traversed))
                continue
            if len(traversed) < 8:
                frontier.extend((next_net, traversed + [buffer]) for next_net, buffer in buffers.get(net, []))
        if len(solutions) != 1:
            terms = lambda net: [(t.getInst().getName(), t.getInst().getMaster().getName(), t.getMTerm().getName()) for t in net.getITerms()]
            raise ValueError(f"Expected one transparent scan path from {start.getName()} to {target.getName()}; found {len(solutions)}; source_terms={terms(start)}; target_terms={terms(target)}")
        return solutions[0][1]

    def path_upper_bound(start, target, intermediates):
        path_nets = [start] + [block.findInst(buffer).findITerm("Z").getNet()
                               for buffer in intermediates]
        if path_nets[-1] != target:
            raise ValueError("Buffered scan path does not terminate at target net")
        return (sum(int(item.getWire().getLength()) for item in path_nets)
                / block.getDbUnitsPerMicron()
                if all(item.getWire() is not None for item in path_nets) else None)

    edges = []
    port_links = []
    exclusive = 0
    for ci, chain in enumerate(arch["chains"]):
        cells = chain["cells"]
        input_port = block.findBTerm("test_si" if ci == 0 else f"test_si_{ci}")
        output_port = block.findBTerm("test_so" if ci == 0 else f"test_so_{ci}")
        if input_port is None or output_port is None:
            raise ValueError("Scan port missing after route")
        input_target = ff[cells[0]].findITerm("SI").getNet()
        input_buffers = path(input_port.getNet(), input_target)
        port_links.append({"chain": ci, "kind": "SI_to_first_FF",
                           "net_length_upper_bound_um": path_upper_bound(
                               input_port.getNet(), input_target, input_buffers),
                           "transparent_buffers": input_buffers})
        for source, dest in zip(cells, cells[1:]):
            left = ff[source].findITerm("Q").getNet()
            right = ff[dest].findITerm("SI").getNet()
            intermediates = path(left, right)
            direct = left == right and not intermediates
            net = left if direct else right
            # Exact scan-only length requires the routed net to contain no
            # functional branches, port, or unaccounted buffer endpoint.
            terminals = {(t.getInst().getName(), t.getMTerm().getName()) for t in net.getITerms()}
            scan_only = direct and terminals == {(source, "Q"), (dest, "SI")} and not net.getBTerms()
            wire = net.getWire()
            length = int(wire.getLength()) / block.getDbUnitsPerMicron() if scan_only and wire else None
            upper = path_upper_bound(left, right, intermediates)
            exclusive += int(scan_only and length is not None)
            edges.append({"chain": ci, "source_ff": source, "dest_ff": dest,
                          "transparent_buffers": intermediates, "exclusive_scan_net": scan_only,
                          "exact_routed_length_um": length,
                          "net_length_upper_bound_um": upper})
        output_source = ff[cells[-1]].findITerm("Q").getNet()
        output_buffers = path(output_source, output_port.getNet())
        port_links.append({"chain": ci, "kind": "last_FF_to_SO",
                           "net_length_upper_bound_um": path_upper_bound(
                               output_source, output_port.getNet(), output_buffers),
                           "transparent_buffers": output_buffers})
    all_exclusive = exclusive == len(edges)
    bounded = [item["net_length_upper_bound_um"] for item in edges + port_links]
    return {"status": "PASS", "scan_ff_count": len(ff), "K": len(arch["chains"]),
            "scan_edges": len(edges), "exclusive_exact_edge_count": exclusive,
            "exact_internal_ff_scan_only_total_um": sum(edge["exact_routed_length_um"] for edge in edges) if all_exclusive else None,
            "exact_scan_only_total_um": None,
            "bounded_scan_path_link_count": sum(value is not None for value in bounded),
            "routed_full_scan_path_net_length_upper_bound_um": sum(bounded) if all(value is not None for value in bounded) else None,
            "all_chain_inputs_outputs_verified": True,
            "fixed_port_positions_verified": True,
            "port_centers_dbu": expected_ports, "edges": edges, "port_links": port_links}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--routed", type=Path, required=True)
    parser.add_argument("--architecture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.routed, args.architecture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "scan_ff_count", "K", "scan_edges", "exclusive_exact_edge_count")}))


if __name__ == "__main__":
    main()
