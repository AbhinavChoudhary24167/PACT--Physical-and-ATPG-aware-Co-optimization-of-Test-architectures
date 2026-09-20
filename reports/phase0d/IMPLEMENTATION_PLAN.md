# PACT Phase-0D implementation and staged-execution plan

## Completed in the pilot stage

1. Preserve Phase-0C at commit `06d97d82263b3671d8a56c9e6ed104cf88d40266` and hash its evidence and upstream dependencies.
2. Freeze a pilot contract before evaluating Phase-0D children.
3. Implement bounded swap, 2-opt, block relocation, cross-chain move, cross-chain swap, endpoint reassignment, and cross-chain block move operators.
4. Implement structural/ATPG validation, qualified Phase-0C proxy reuse, Pareto filtering, deterministic caches, manifests, status files, timeout and disk guards.
5. Implement equal-budget greedy-best, greedy-first, beam, and simulated-annealing baselines.
6. Execute the s5378/seed-11/K=2 pilot and calculate runtime/storage projection.

## Pilot-driven staging decision

The naive primary matrix at B=128 and R=8 projects to 30,720 proxy evaluations and 1,920 new routes. The measured proxy time and recorded median Phase-0C route time imply approximately 252,571 serial seconds (about 70 hours), so the full matrix must not be launched.

The next contract should freeze a reduced sequence before execution:

1. Cross-design screen: all three designs, seed 11, K in {2, 8}, all four optimizers, total B=32 per optimizer/context, no routing until proxy qualification.
2. Stop with a negative gate result if no richer operator or search produces a new nondominated child on at least two designs.
3. If the screen qualifies, replicate only qualifying operators/optimizers on predeclared seeds 17 and 23, retaining the same pairing unit (design x physical seed x K).
4. Route only a small, predeclared proxy-nondominated shortlist; retain Phase-0C routes as existing baseline evidence and count only Phase-0D routes as new compute.
5. Freeze exact D1-D9 thresholds, normalization bounds, context count, and route budget before this reduced campaign begins.

The reduced runner must remain resumable and should execute as a persistent background campaign if its post-screen projection exceeds 45 minutes. No final Phase-0D decision is permitted from the pilot alone.
