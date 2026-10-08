# Post-merge large unseen campaign

The historical qualified implementation merged through PR #3 at
`084db2f9e164b7757597fec1eec73d9c4049a9a4`. That campaign used
`development/large-unseen-gate9-20261005`, compact receipts in
`results/pact_large_unseen_gate9_20261005/`, and raw artifacts in the matching
configured `PACT_EXPERIMENT_ROOT/results/` namespace. Its original host paths
remain in immutable execution receipts; current status is in
[research status](research_status.md).

`pact_large_unseen.py register` binds the merged parent, executable sources,
tools, frozen reference inputs and original configuration. Searches retain
K=2, seed 11, all three epsilon lanes and 900-second mutation loops. The
7200-second search worker ceiling remains separate from the mutation budget.
The prior interrupted s38584 run is hash-bound evidence and supplies no start.

The wrapper observes the existing optimizer call and receipt writes; its
arguments, model, reference replay, acceptance and candidate ordering remain
unchanged. Atomic lane states and immutable events record registration, start,
checkpoints and completion. Completed lanes bind a complete search receipt.
The Linux supervisor records child exit, CPU/RSS, ceilings and kernel evidence.
The Windows supervisor additionally records the WSL exit, host resources and
Linux boot IDs, preserving an explicit interruption if a Linux worker vanishes.
Signal 9 alone does not establish OOM.

The Windows controller serially searches both designs, freezes at most three
candidates each, then runs the existing physical/FAN/compact-activity chain.
Qualification routing uses a configurable receipt location to keep the new
campaign separate. No scientific definitions or gates change.

Storage registration requires six GiB free on C: and 25 GiB on D:. D: includes
the established 20-GiB workflow reserve plus five GiB for six compact traces,
observed physical/ATPG/routing packages and a safety allowance. Windows needs
only compact metadata; simulation, routing, count scratch and caches use D:.
The existing WSL backing disk and eight-GiB swap reside on F:.
