#!/usr/bin/env python3
"""Read routed OpenDB Q/SI nets through numeric Python dbWire bindings."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import odb


def main() -> None:
    routed = Path(os.environ["PACT_PHASE0B_ROUTED_ODB"])
    ordered = json.loads(Path(os.environ["PACT_PHASE0B_ORDER_JSON"]).read_text(encoding="utf-8"))
    target = Path(os.environ["PACT_PHASE0B_SCAN_ROUTE_TSV"])
    db = odb.dbDatabase.create()
    odb.read_db(db, str(routed))
    block = db.getChip().getBlock()
    dbu = block.getDbUnitsPerMicron()
    transparent_buffers = {}
    for inst in block.getInsts():
        if inst.getMaster().getName() != "BUF_X1":
            continue
        input_term, output_term = inst.findITerm("A"), inst.findITerm("Z")
        if input_term is None or output_term is None or input_term.getNet() is None or output_term.getNet() is None:
            continue
        key = (input_term.getNet().getName(), output_term.getNet().getName())
        transparent_buffers.setdefault(key, []).append(inst.getName())
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("source_ff", "dest_ff", "q_net", "si_net", "connected",
                         "routed_nonvia_dbu", "iterm_count", "bterm_count", "dbu_per_um",
                         "via_transparent_buffer", "buffer_instance", "buffered_full_net_upper_dbu"))
        for source, dest in zip(ordered, ordered[1:]):
            a, b = block.findInst(source), block.findInst(dest)
            if a is None or b is None:
                raise ValueError("Routed scan FF missing")
            q, si = a.findITerm("Q"), b.findITerm("SI")
            if q is None or si is None or q.getNet() is None or si.getNet() is None:
                raise ValueError("Routed scan Q/SI term missing or disconnected")
            qnet, sinet = q.getNet(), si.getNet()
            wire = sinet.getWire()
            length = int(wire.getLength()) if wire is not None else -1
            buffers = transparent_buffers.get((qnet.getName(), sinet.getName()), [])
            if qnet.getName() != sinet.getName() and len(buffers) > 1:
                raise ValueError("Ambiguous transparent scan-edge buffers")
            qwire = qnet.getWire()
            buffered_upper = (int(qwire.getLength()) + length
                              if buffers and qwire is not None and length >= 0 else -1)
            writer.writerow((source, dest, qnet.getName(), sinet.getName(),
                             int(qnet.getName() == sinet.getName()), length,
                             len(sinet.getITerms()), len(sinet.getBTerms()), dbu,
                             int(bool(buffers) and qnet.getName() != sinet.getName()),
                             buffers[0] if buffers else "", buffered_upper))
    print(f"OPENDB_SCAN_EDGES {len(ordered) - 1} DBU_PER_UM {dbu}")


if __name__ == "__main__":
    main()
