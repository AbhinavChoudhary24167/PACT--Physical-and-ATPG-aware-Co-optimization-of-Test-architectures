# Methodology

PACT keeps physical cost, total switching and local peaks separate. Legal transformations preserve FF bijection, clock domains and capacities. Fixed SI/SO endpoints must survive restitching, scan metadata and exported connectivity.

## Models and schedules

The working solver uses repaired M3 load and M5 HPWL costs. `phase2cr_loads` is authoritative for selected SO branch ownership, functional-plus-scan geometry/pin load and coefficient 0.103981. Its schedule carries loaded patterns from zero, uses 10×10 bins and 81 contained 2×2 windows, and excludes capture/final unload. These are not edge-Hamming costs.

The implementation-aware path uses stored FAN load/capture-response states and exact load/unload trajectories. QN is Q's complement. Candidate-stateful propagation evaluates simultaneous settled inputs through three nontransparent levels; BUF/INV do not consume depth. Unrepresented fanins and outputs beyond the bound are omitted and recorded as coverage limits.

E is the all-data sum of ground-plus-pin capacitance times transitions, in fF·transitions. Coupling is excluded from the primary metric. H4/H8 are maximum cycle/bin values on 4×4/8×8 source-localized grids. Each net's entire capacitance is assigned to its source; metal crossing bins is not distributed energy attribution. Zero-delay simulation does not establish watts, physical glitches or IR-drop.

## Physical qualification

Search wire is port-inclusive Manhattan scan HPWL. Measured routed scan cost is a connected scan-path net-length upper bound including functional branches on shared nets. It differs from total detailed-route wire and exact scan-only attribution.

Qualification requires FF membership once, SI/internal/fixed-SO traversal without cycles/forks/orphans, consistent metadata/exported Verilog, unchanged functional D/CK/Q/QN fanout as applicable, independent workload and FF-transition checks, zero detailed-route DRC and available nonnegative global-route setup/hold values. Global-route timing is not detailed-route signoff.

Stage B requires `W_proxy <= (1+epsilon)*W_proxy(reference)` before activity work. The reference minimizes measured routed scan cost among B2/B3T. Routed budget acceptance is checked independently after implementation. Dominance is reported for both Stage A's (wire,E,H8) and expanded (wire,E,H4,H8) coordinates against all qualified comparators.

Historical defects and negative gates remain in [history](history.md). Cleanup changes no scientific objectives or optimization parameters.
