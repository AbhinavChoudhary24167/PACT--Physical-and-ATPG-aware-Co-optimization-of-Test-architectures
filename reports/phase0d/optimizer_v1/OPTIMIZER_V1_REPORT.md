# PACT Optimizer v1 Report

**Decision:** `PACT_OPTIMIZER_V1_PROXY_ADVANCE`

**Routed decision:** `PACT_OPTIMIZER_V1_ROUTE_QUALIFIED`

**Frozen prior decisions:** `PACT_PHASE0C_LEARNING_GATE_FAIL` and
`PILOT_COMPLETE_NO_ROUTE_QUALIFIED`

## Result

The bounded s5378/seed11/K2 experiment proposed
24 architectures and performed
24 unique exact proxy
evaluations, including 0 verified cache reuses.
Search wall time was 61.313000 seconds; accumulated new
proxy computation was 39.971490 seconds.

### Reused Phase-0C proxy Pareto front

| Method | Architecture | HPWL proxy (µm) | Exact H_eff8 |
|---|---|---:|---:|
| P | `bf4923662baa` | 1380.830000 | 63.333333 |
| T | `37deaa7b3eee` | 1421.170000 | 62.333333 |
| J50 | `9c54b48f2ab8` | 2634.750000 | 61.666667 |
| A | `16904eaa0db2` | 6850.210000 | 60.500000 |

### New PACT points on the combined proxy Pareto front

| Source | Architecture | HPWL proxy (µm) | Exact H_eff8 |
|---|---|---:|---:|
| segment+physical_best | `44b1a2ab5a1e` | 1180.750000 | 64.833333 |
| region+physical_best | `0348f2cc6b9d` | 1305.770000 | 62.833333 |
| cross_chain+physical_best | `a78c6ce1a5a1` | 1306.550000 | 62.666667 |
| hotspot+physical_best | `75ea663523d9` | 1319.110000 | 60.833333 |
| segment+physical_best | `1f1a3a458946` | 2157.810000 | 59.000000 |

New nondominated point found: **yes**.

## Runtime accounting erratum

The completed pilot is not rewritten. Its STATUS elapsed field measured the
current/finalization process invocation, while its summed proxy times measured
unique cached artifacts created across earlier invocations. Optimizer v1 records
process invocation (61.313000 s), cumulative search wall
time (61.313000 s), accumulated new-proxy computation
(39.971490 s), and route time (78.069737 s) separately.

## Selective routing

Selected candidates: 1. Observed route results: 1.
No Phase-0C route was rerun. Routing is skipped when the new combined-front set
is empty; otherwise only the balanced representative and optional activity
extreme are eligible.

## Interpretation and next step

The optimizer extended the reused proxy front. The scientifically justified next step is selective route qualification of the saved shortlist, without scaling the campaign.

ML was not introduced.

## Routed qualification evidence

- architecture: `1f1a3a458946abcf31aa53a2375266a8629ed0ac0079ec7c20ecf47cc1e2e685`
- status: `QUALIFIED`; detailed-route DRC errors: 0
- full-netlist detailed-route wirelength: 26982 µm
- detailed-route vias: 13469
- global-route setup/hold WNS: 9.08672 / 0.00273018 ns
- initial global-route utilization/overflow: 23.81% / 0
- route wall time: 78.069737 s
- compressed routed ODB: 564115 bytes
- structural reconstruction: `PASS`; 177 scan edges verified
- routed full scan-path upper bound: 5494.14 µm
