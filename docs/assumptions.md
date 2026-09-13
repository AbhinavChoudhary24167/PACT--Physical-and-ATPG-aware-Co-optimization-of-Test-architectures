# Assumptions and scope

- One functional clock and fixed scan FF identities are the initial scope.
- ATPG pattern values are logical FF target states, independent of scan order. Unmapped or unknown values are rejected for shift analysis.
- Manhattan scan-edge length is a geometric estimate. Routed length is a separate physical metric.
- Spatial toggle metrics are activity proxies, not dynamic IR drop or signoff power.
- Native OpenROAD ordering is only reported when extracted from actual stitched connectivity.
