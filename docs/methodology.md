# Methodology

The fixed experimental object is the synthesized combinational logic, FF set, placement, platform, clock, and ATPG test set. An architecture changes only legal scan SI/SO connectivity. Every generated architecture is validated and SHA256-hashed over canonical JSON.

The activity simulator serially shifts each desired logical FF state into its chain from scan-in to scan-out. A shift cycle records toggles for every cell. Initial state is explicitly all-zero unless a verified previous capture state is available; this assumption must be reported. For parallel chains, a pattern consumes the maximum chain length in clocks and shorter chains do not toggle after their load completes.

Geometric scan length is the sum of Manhattan distances between adjacent placed cells in each chain. It excludes ports unless explicit endpoint coordinates are supplied. Spatial activity uses fixed placement bounds and nonoverlapping grid bins. Local density is toggles divided by the number of FFs in the bin; empty bins have zero density. Gini is computed over per-bin cumulative toggles. None of these values is an IR-drop measurement.

The distance-weighted hotspot is the maximum over shift clocks and bins of the sum of local bin densities within Manhattan radius one, with each contributing bin weighted by `1 / (1 + Manhattan bin distance)`. Out-of-die bins contribute zero. Per-cycle and per-bin percentiles include unoccupied bins as zeros. Placement extraction currently uses DEF component origins, not scan-pin coordinates; this limitation is tracked in the report.

The success gate requires independently qualified OpenROAD DFT and FAN_ATPG tools, an unambiguous ATPG-to-physical FF map, real ATPG patterns, at least two nontrivial designs or multiple physical seeds, and a fully rerun physical implementation with only scan ordering varied. Missing gates force a partial or not-established classification.
