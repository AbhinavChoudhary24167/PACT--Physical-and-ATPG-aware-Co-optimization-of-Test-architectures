# Objectives, schedules and qualification

PACT evaluates a vector of physical/activity coordinates. Legal candidates preserve FF membership, chain capacities, clock domains and endpoints. `K` is chain count; a seed identifies a registered realization.

The numerical solver uses repaired **M3** activity and **M5** scan HPWL. `analysis/phase2cr_loads.py` defines SO-branch ownership, functional-plus-scan geometry/pin load and coefficient 0.103981. Its schedule carries patterns from zero, uses 10×10 bins and 81 contained 2×2 windows, and excludes capture/final unload. It is distinct from the implementation-aware E/H4/H8 schedule.

| Metric | Definition and boundary |
|---|---|
| `W_proxy` / HPWL | Port-inclusive Manhattan scan-wire predictor |
| Routed scan WL | Connected scan-path net-length upper bound, including functional branches on shared nets; differs from total route wire and exact scan-only attribution |
| `E` | Sum of `(ground + pin capacitance) × data transitions`, fF·transitions; coupling excluded from the primary metric |
| `H4`, `H8` | Maximum across cycle/bin on 4×4/8×8 grids; a net's entire capacitance is attributed to its source |
| `epsilon` | Relative budget: `W_proxy(candidate) ≤ (1 + epsilon) W_proxy(reference)` |
| Static VDD drop | Frozen mean-current resistive solve, separately measured from the switching proxies |

Source localization does not distribute activity along metal crossing bins. Zero-delay trajectories omit physical glitches. Stage B chooses the qualified B2/B3T reference with lowest measured routed cost, screens proxy feasibility first and independently checks the routed budget. Separate E/H4/H8/balanced winners and both `(wire,E,H8)` and `(wire,E,H4,H8)` fronts remain reported.

Topology, serial replay, functional connectivity, fault-class identity/weights, DRC and available timing are qualification gates. Nonnegative global-route timing is not detailed-route signoff. Proxy improvement cannot replace a gate or establish material power/IR benefit. See [negative results](../experiments/negative_results.md).
