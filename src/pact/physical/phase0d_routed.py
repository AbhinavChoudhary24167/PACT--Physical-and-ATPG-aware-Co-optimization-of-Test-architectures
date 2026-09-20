"""Post-route Phase-0D topology and scan-path evidence."""
from __future__ import annotations

import json
from pathlib import Path

from pact.physical.phase0c_port_policy import frozen_def_ports


def verify_routed(routed: Path, architecture: Path, frozen_def: Path) -> dict:
    """Verify routed chains through transparent buffers using an explicit frozen DEF."""
    try:
        import odb
    except ImportError as error:  # pragma: no cover - OpenROAD supplies this module
        raise RuntimeError("OpenROAD odb Python module is required") from error
    arch = json.loads(architecture.read_text(encoding="utf-8"))
    db = odb.dbDatabase.create()
    odb.read_db(db, str(routed))
    block = db.getChip().getBlock()
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
    if set(ff) != {cell["name"] for cell in arch["cells"]}:
        raise ValueError("Routed FF inventory differs from architecture")
    buffers: dict[str, list[tuple[str, str]]] = {}
    for inst in block.getInsts():
        if not inst.getMaster().getName().startswith(("BUF_X", "CLKBUF_X")):
            continue
        source, target = inst.findITerm("A").getNet(), inst.findITerm("Z").getNet()
        if source is not None and target is not None:
            buffers.setdefault(source.getName(), []).append((target.getName(), inst.getName()))

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
            raise ValueError(f"Expected one transparent scan path; found {len(solutions)}")
        return solutions[0][1]

    def path_upper_bound(start, target, intermediates):
        path_nets = [start] + [block.findInst(buffer).findITerm("Z").getNet() for buffer in intermediates]
        if path_nets[-1] != target:
            raise ValueError("Buffered scan path does not terminate at target net")
        return (sum(int(item.getWire().getLength()) for item in path_nets) / block.getDbUnitsPerMicron()
                if all(item.getWire() is not None for item in path_nets) else None)

    edges = []
    port_links = []
    exclusive = 0
    for chain_index, chain in enumerate(arch["chains"]):
        cells = chain["cells"]
        input_port = block.findBTerm("test_si" if chain_index == 0 else f"test_si_{chain_index}")
        output_port = block.findBTerm("test_so" if chain_index == 0 else f"test_so_{chain_index}")
        if input_port is None or output_port is None:
            raise ValueError("Scan port missing after route")
        input_target = ff[cells[0]].findITerm("SI").getNet()
        input_buffers = path(input_port.getNet(), input_target)
        port_links.append({
            "chain": chain_index, "kind": "SI_to_first_FF",
            "net_length_upper_bound_um": path_upper_bound(input_port.getNet(), input_target, input_buffers),
            "transparent_buffers": input_buffers,
        })
        for source_name, target_name in zip(cells, cells[1:]):
            source = ff[source_name].findITerm("Q").getNet()
            target = ff[target_name].findITerm("SI").getNet()
            intermediates = path(source, target)
            direct = source == target and not intermediates
            net = source if direct else target
            terminals = {(term.getInst().getName(), term.getMTerm().getName()) for term in net.getITerms()}
            scan_only = direct and terminals == {(source_name, "Q"), (target_name, "SI")} and not net.getBTerms()
            wire = net.getWire()
            exact = int(wire.getLength()) / block.getDbUnitsPerMicron() if scan_only and wire else None
            upper = path_upper_bound(source, target, intermediates)
            exclusive += int(scan_only and exact is not None)
            edges.append({
                "chain": chain_index, "source_ff": source_name, "dest_ff": target_name,
                "transparent_buffers": intermediates, "exclusive_scan_net": scan_only,
                "exact_routed_length_um": exact, "net_length_upper_bound_um": upper,
            })
        output_source = ff[cells[-1]].findITerm("Q").getNet()
        output_buffers = path(output_source, output_port.getNet())
        port_links.append({
            "chain": chain_index, "kind": "last_FF_to_SO",
            "net_length_upper_bound_um": path_upper_bound(output_source, output_port.getNet(), output_buffers),
            "transparent_buffers": output_buffers,
        })
    bounded = [item["net_length_upper_bound_um"] for item in edges + port_links]
    all_exclusive = exclusive == len(edges)
    return {
        "status": "PASS", "scan_ff_count": len(ff), "K": len(arch["chains"]),
        "scan_edges": len(edges), "exclusive_exact_edge_count": exclusive,
        "exact_internal_ff_scan_only_total_um": (
            sum(edge["exact_routed_length_um"] for edge in edges) if all_exclusive else None),
        "exact_scan_only_total_um": None,
        "bounded_scan_path_link_count": sum(value is not None for value in bounded),
        "routed_full_scan_path_net_length_upper_bound_um": (
            sum(bounded) if all(value is not None for value in bounded) else None),
        "all_chain_inputs_outputs_verified": True,
        "fixed_port_positions_verified": True,
        "port_centers_dbu": expected_ports,
        "edges": edges,
        "port_links": port_links,
    }
