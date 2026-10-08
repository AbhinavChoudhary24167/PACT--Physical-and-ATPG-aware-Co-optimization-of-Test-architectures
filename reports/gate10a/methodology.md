# Gate 10A methodology

The binding prospective definitions are in [preregistration.md](preregistration.md)
and [protocol.json](protocol.json). This file provides an execution crosswalk;
implementation diagnostics and outcomes belong in separate immutable receipts.

1. Anchor final Gate 09 receipts to published Git objects and recursively verify
   selected source, topology, architecture, placement, workload, routed ODB,
   SPEF, net mapping and exact transition-count evidence by historical hashes.
2. Stream the qualified compact counts and reconstruct per-net transition totals
   and ground-plus-pin capacitance from qualified SPEF/mapping. This is derived
   reanalysis, not a simulation or new Gate 09 result.
3. Read the original ODB/Liberty/SDC/SPEF into the hash-matched OpenROAD binary.
   Annotate data rates and the fixed clock/control assumptions. Retain complete
   annotation inventories and per-instance power in SI units.
4. Derive fixed top-stripe endpoint sources; verify identical original PDN
   geometry within each design. Solve static VDD power-grid voltage using the
   estimated instance total-power loads and preserve segment-current reports.
5. Qualify the representative repeated nominal and activity-scaling controls.
   Admit each selected architecture independently under the fixed qualification
   and resource checks. No optimization, search or backend rerun is performed.
6. Aggregate complete machine records to original H4/H8 regions and report both
   preregistered correlations and deterministic hotspot overlap. Keep averaged
   activity correspondence separate from cycle-resolved peak-map evidence.
7. Apply frozen materiality and classification rules, preserve every admissible
   outcome and hold, generate full-precision tables and a conservative report,
   and save an unposted OpenROAD discussion response.

The primary physical response is static VDD supply drop under an activity-derived
power approximation at 100 MHz and 1.1 V. Non-clock duty=0.5 is assumed because
qualified retained counts contain no state occupancy. Thermal is not evaluated.
Segment current is not current density unless qualified conductor cross-section
data exists. Raw solver reports and complete spatial vectors accompany summaries.
