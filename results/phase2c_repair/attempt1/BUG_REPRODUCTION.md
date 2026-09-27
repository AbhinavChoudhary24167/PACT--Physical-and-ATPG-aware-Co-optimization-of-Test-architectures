# Independent legacy-bug reproduction

Status: **PACT_PHASE2CR_BUG_REPRODUCED**. No corrected metric has been calculated.

The read-only `scripts/phase2cr_extract.py` regenerated all three historical
placed graphs from their frozen DEFs using the unchanged exporter and compared
them exactly with the hash-verified archived graphs. Endpoint identity came
independently from those DEFs, not from the routed load reference. Liberty was
hash-verified and parsed directly. Physical inventories were read only to audit
the selected owner. See `bug_reproduction.json` for paths, SHA256s and assertions.

For s5378/seed11/P (architecture SHA
`bf4923662baa3ce72543bd3ad5092fb514808ffe46ce23173d3c9695ff0c9486`), the
legacy graph retains `U_n1588gat/Q -> n1588gat -> output38/A -> output38/Z -> test_so`.
The architecture's final chain-0 FF is `U_n2121gat`; the frozen physical
inventory assigns the `output38` transparent branch to that FF. The actual
topology is `U_n2121gat/Q -> output38/A -> output38/Z -> test_so`.
The directly parsed BUF_X1/A Liberty capacitance is exactly 0.974659 fF.

## Responsible source statements

- `scripts/phase2b_extract.py`, `placed_graph`: `master.startswith(('BUF_X',
  'CLKBUF_X','INV_X'))` builds transparent A-to-Z/ZN traversal. The sink
  comprehension excludes only `(t.getInst().getName() in ff and
  t.getMTerm().getName()=='SI')`. Thus it retains `output38/A`.
  `if t.getName().startswith(('test_si','test_so')): continue` removes scan
  BTerm geometry, and `pending.extend(transparent.get(name,[]))` retains the branch.
- `src/pact/analysis/phase2b_loads.py`, `construct_weights`:
  `extra[tail].append(dict(xy=ports[so], master=None, pin=so))` adds a synthetic
  tail-to-port point. `all_sinks = sinks + [s for s in additions if
  s['master'] is not None]` gives it no pin capacitance. The unchanged original
  root and `pending.extend(graph['transparent'].get(netname, []))` still charge
  the real buffer pin and branch to the old owner.
- `scripts/phase0c_rewire_odb.py`, `rewire`: after walking chain 0,
  `out_buffer.findITerm("A").disconnect()` and
  `out_buffer.findITerm("A").connect(prior)` transfer the inherited branch to
  its selected final Q net. For chain > 0, `connect_port(... test_so_{ci}, prior,
  "OUTPUT", ...)` instead creates a direct port.

The reproduced mechanism matches the prior bug exactly. Phase-2C remains
**STOPPED_LEGACY_DEFINITION_BUG**. Historical definitions and evidence are untouched.
