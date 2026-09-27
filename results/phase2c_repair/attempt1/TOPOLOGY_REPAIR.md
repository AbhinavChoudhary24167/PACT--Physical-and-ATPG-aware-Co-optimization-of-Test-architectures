# Versioned topology repair (not fully qualified)

`phase2cr_loads` leaves the historical builder unchanged. The placed graph has
explicit scan_endpoints and scan_ports, exported read-only from the frozen DEF.
Architecture construction removes the unique inherited buffer sink and child
edge from the old Q net, appends them to the selected chain-0 tail Q net, and
places the SO port on the buffer output net. The same-owner case avoids a
remove/reinsert operation. Direct chain-1 semantics are preserved.

Unique transparent-net traversal recomputes HPWL from driver/sink/port points.
No M5 scalar subtraction is used. The fixed coefficient is 0.103981 fF/um.
Strict nested schema checks reject unknown/routed fields. The predictor accepts
only an architecture, placed graph and parsed Liberty loads. Routed evidence is
only read by the separate validation boundary. It is never passed to the builder.

Fourteen initial focused tests passed, including synthetic same-owner, changed
owner, functional fanout preservation, descendant branch transfer, direct chain-1,
nonlinear geometry and feature-leakage rejection. Historical archived weights
reproduced exactly for all 21. The representative topology diagnostic also passed.
The representative numerical audit assertion subsequently failed due to unequal
floating-point reductions. Full topology qualification and regression are not
complete; the implementation must not yet be treated as scientifically qualified.

Execution ordering note: the first focused integration test exercised corrected
per-FF construction for all 21 earlier than the requested witness ordering. That
call was removed. It produced no corrected architecture scores or correlations,
but this deviation is retained in tests.json; it is not presented as a gate pass.
