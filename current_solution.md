# Current optimizer architecture

The public model is `ScanArchitecture`: fixed placed FF records and ordered,
named SI-to-SO chains. v1 constructs and destroys/repairs entire architectures.
v2 uses integer predecessor/successor arrays, reversible patches, cKDTree
neighbors, bounded epsilon/crowding Pareto admission, and bounded seen caches.
v2.1 shares constructor features; v2.2 tiles exact H_eff8 by pattern; v2.3 runs
independent process lanes with periodic archive merging. These optimize
port-aware Manhattan scan HPWL and H_eff8, not the subsequently qualified M3/M5.

## Reusable components

Canonical scan serialization/validation, FAN pattern/identity mapping, placed
graphs, Liberty pin parsing, port policy, deterministic baselines P/A/J50/T,
Pareto concepts, and bounded OpenROAD rewire/route/structural verification.
`phase2cr_loads` is the repaired M3/M5 authority: architecture-dependent
functional-plus-scan source HPWL/pin capacitance, complete inherited SO branch
transfer, and CAP_PER_UM=0.103981. `phase2b_scoring` defines total and local
activity: carry-loaded patterns from zero, 10×10 fixed bins, 81 contained 2×2
windows, no capture or final unload. M3/M5 are not edge Hamming proxies.
Existing route-qualified architectures and route metrics can be reused by
exact architecture identity. Historical evidence stays untouched.

## Known bottlenecks

v2 patches copy affected complete chain orders even for swaps. Tiled H_eff8
rebuilds old/new affected-chain Toeplitz waveforms and computes accepted deltas
again. Construction/admission repeatedly traverse, serialize or copy chains.
v2.3 reports the numerical activity kernel as the dominant remaining cost.
The later event evaluator is slower than packed evaluation on real dense
activity (reported packed/event ratios 0.235–0.301); it is not a suitable
drop-in acceleration. Sparse bounded-prefix results are not full-load scaling.

## Major algorithmic limitations

Sparse physical neighbors alone do not make exact activity scalable. A changed
target bit propagates throughout a loaded chain, so activity is not a sum of
fixed independent edge costs. Full-load work depends on pattern count P and
maximum chain length L as well as N. Whole-chain waveforms can require quadratic
work for fixed small K. Earlier objectives do not include repaired M3/M5.
Strict time limits cannot interrupt one unbounded constructor/evaluator.
Strong P/A/J50 baselines and routed proxy mismatch must remain visible.
