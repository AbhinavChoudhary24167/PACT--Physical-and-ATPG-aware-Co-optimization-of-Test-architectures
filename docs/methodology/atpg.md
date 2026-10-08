# ATPG and test preservation

FAN_ATPG supplies stored load patterns and capture responses. PACT maps them through qualified FF identities into candidate SI-to-SO chain orders. Independent replay checks load/unload trajectories and FF transitions. Equal fault-coverage percentages alone do not prove equivalent test behavior.

`test/pattern_parser.py`, `test/shift_simulator.py` and `integration/patterns.py`, `permutation.py`, `replay.py`, `faults.py` bind workload, architecture and qualification. Stateful evaluation uses exact stored load/response trajectories rather than regenerating ATPG per order.

The end-to-end gate compares every collapsed target fault-class identity and weight for frozen references/selections. Individual uncollapsed class members are not enumerated. FAN construction/reporting repairs preserve the generation algorithm and original statistics; retain the exact patched revision, binary hash, testcase and original failure receipt.

Workload, benchmark identity, FF map, placement, seeds and backend must match a comparison's registration. A changed pattern set or fault universe defines a different experiment. See [upstream provenance](../upstream.md).
