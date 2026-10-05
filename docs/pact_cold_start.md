# Prospective cold-start PACT input contract

`ColdStartPACTInput` in `src/pact/optimizer/cold_start.py` loads a
`pact_cold_start_input_v1` JSON manifest. The design name is an artifact identity;
it does not select a Python lookup table. A new design is introduced by supplying
the bound artifacts described below. No historical P0, candidate archive,
previous PACT result, learned initialization or precursor search is required.

The minimal loader contract requires `schema`, `design`, `reference_method`,
`reference_architecture_hash` and seven bound artifacts: `architecture`,
`patterns`, `identity_map`, `placement`, `mapping`, `caps` and `topology`.
The low-level loader verifies those artifacts, supported method labels and the
architecture hash. A supported method label alone does not prove physical or
FAN qualification. The operational campaign preparation and physical handoff
add and verify the reference, qualification and source-preparation receipts
listed below before scientific search or implementation.

The sole initial architecture in this campaign is the external reference selected before search:
the minimum qualified routed scan cost among available B0/B1/B2/B3T methods.
The selection includes routing, extraction, exact scan topology, functional
connections and FF placement, nonnegative setup/hold WNS, DRC=0, serial replay
and the complete FAN collapsed correctness gate. The reference remains fixed
even if PACT performs poorly.

| Manifest field/artifact | Origin | Required use |
|---|---|---|
| `schema`, `design` | Automatically authored input manifest | Artifact discovery and identity |
| `reference_method`, `reference_architecture_hash`, `reference` | Qualified external-reference selection and its frozen receipt | Bind the sole initial architecture |
| `architecture` | External reference | Canonical physical FF inventory, placement, chain capacities, SI/SO endpoints and order |
| `patterns` | FAN ATPG on the mapped functional source | Complete binary PPI/PPO, functional input and response states |
| `identity_map` | Mapped source, placed netlist and FAN PPI identities | Exact ATPG-to-physical FF bijection and clock domains |
| `placement` | Frozen placed DEF | Fixed FF origins and deterministic qualified scan-port positions |
| `mapping`, `topology` | Exact reference ODB and frozen Liberty functions | Signal origins, source positions, cells/functions, graph and spatial bounds |
| `caps` | Exact reference SPEF ground capacitance plus Liberty sink pin loads | Electrical model input; activity columns are optional and unused for initialization |
| `source_placed_database`, `source_netlist`, `SDC`, `preparation` | Mapped/scan-capable source and common placement preparation | Rewire each candidate from the same one-chain placed source and apply the same backend |
| `qualification` | Qualified external-reference physical receipt | Bind the route, extraction and physical gates |
| `reference_fault_export`, `reference_serial` | Complete FAN export and serial replay of the reference workload | Downstream collapsed target/detected identity and weight comparison |
| `provenance` | Supporting artifact receipts | Optional explanatory lineage; never search state |

Every artifact is a path plus byte SHA256 binding. Relative paths resolve from
the manifest location; `repo://` paths resolve from the repository root. The
loader verifies required bindings before building the unchanged model layers:
v2 ATPG load/unload representation, candidate-sensitive physical/electrical
model, then bounded simultaneous-state propagation. It returns exactly one
labelled starting order, with the label taken from `reference_method`.
Architecture serialization/deserialization must preserve canonical content
and the semantic architecture SHA256.

The current execution contract is one clock domain, K=2, at least eight FFs per
chain, explicit qualified SI/SO endpoint aliases, complete binary FAN states,
and fixed FF placement/inventory and chain semantics. Unknown ATPG bits are
rejected rather than filled. Unsupported libraries/functions, missing source
identity/capacitance, invalid topology, or unqualified references are framework
blockers. Adding a manually authored per-design source lookup is not a remedy.

Search preserves the existing Stage-B evaluator, E/H4/H8 definitions, mutation
operators, archive/restart logic and balanced weights. The registered settings
are seed 11, epsilons 0.02/0.05/0.10, and a per-loop limit of
`300 * max(1, ceil(FF/600))` seconds. The independent solver-worker deadline is
`max(1800, 4*per_loop_seconds)`. Up to three distinct pre-route role champions
are frozen before any candidate implementation. Exact downstream activity
uses the common routed/extracted circuit and measured shift protocol; candidate
search metrics remain model estimates and are not substituted for those
measurements.

Each design is independent. Search, route and exact activity stages record
their own outcomes and resource limits. The common backend has a 1200-second
route deadline and two implementation cores; exact measurement has an
independent 1800-second deadline. The campaign preserves a 20 GiB free scratch
reserve. Runtime observations include concurrent work, so they do not establish
an isolated machine scaling law or a general FF-count cutoff.

`scripts/pact_cold_start_initialization_diagnostic.py` provides a loader-only
diagnostic for a supplied manifest. It freezes the input/source bindings before
execution, enforces one thread and an independent 1800-second limit, audits
reads and rejects historical experiment state, records exact architecture
roundtrip, the sole start label, model metadata and wall/CPU/RSS. It performs no
candidate evaluation, optimization, mutation, selection, routing or simulation.
Its receipts live in `scalability/*_initialization_diagnostic.json`; a PASS
establishes initialization, and does not establish search or physical/activity
qualification.

Historical `s5378`, `s9234` and `s15850` remain an immutable, separately labelled
qualified core. They serve only regression and semantic-equivalence checks.
Prospective outputs and failures remain in
`results/pact_cold_start_unseen_20261004/` without overwriting earlier campaigns.
