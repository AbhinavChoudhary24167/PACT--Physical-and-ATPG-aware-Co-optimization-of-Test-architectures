# Phase-2C-R stop report

**Execution: PACT_PHASE2CR_TOPOLOGY_FAIL — required validation incomplete.**
**Scientific classification: not evaluated.**
**Engineering recommendation: MULTISEED_REPAIR_RERUN_BLOCKED.**

This is an audit-check failure, not demonstrated physical topology disagreement
or scientific invalidation. The representative witness asserted exact equality
between two floating-point reductions: 66.94999999999999 and 66.95. The difference
is approximately 1.42e-14 um. The user-required witness stop was retained rather
than changing the assertion and continuing. No corrected correlations, rankings,
architecture-level metric deltas or qualification claims were generated.

## Direct answers

1. **Mismatch reproduced?** Yes: PACT_PHASE2CR_BUG_REPRODUCED. All three historical
   placed graphs regenerated exactly; the s5378/P frozen witness matches.
2. **Legacy topology?** U_n1588gat/Q -> n1588gat -> output38/A -> output38/Z ->
   test_so remains under the old owner, plus synthetic selected-tail-to-SO geometry.
3. **Physical topology?** U_n2121gat/Q -> output38/A -> output38/Z -> test_so.
4. **Correction implemented?** New explicit placed endpoints, complete branch
   ownership transfer, real buffer-output port geometry, unique traversal and
   point-set HPWL; no change to historical functions.
5. **Historical preservation?** Yes. Final integrity checks verify all 534 frozen
   inputs/preserved files. Phase-2B/C results and user modifications are unchanged.
6. **All 21 topology checks pass?** Not established: the mandatory all-21 audit was
   not started after the representative numerical assertion. The representative
   topology-only diagnostic passes. This is not a 21/21 qualification.
7. **Representative transfer correct?** The topology diagnostic confirms
   output38 moves from U_n1588gat to U_n2121gat; the complete witness is unaccepted.
8. **BUF cap transferred once?** The representative topology diagnostic verifies
   exactly one 0.974659 fF transfer and preserved unrelated pin load.
9. **M5 recomputed from points?** Yes in the implementation and focused tests.
   The failed assertion concerns summation arithmetic in the audit only.
10. **Changed FF weights per architecture?** Not reported as qualified results;
    all-architecture diagnostic and score analysis was not completed.
11. **How much did M3 change?** Architecture scores not computed.
12. **How much did M5 change?** Architecture scores not computed. Diagnostic
    old-owner per-FF corrected HPWL is 5.910000000000003 um; selected-tail net
    terms are 34.699999999999996, 15.750000000000002 and 16.5 um. These are audit
    operands, not a qualified scientific measurement.
13. **Architecture rankings changed?** Not evaluated.
14. **Pair directions changed?** Not evaluated.
15. **M3 original gates on all designs?** Not evaluated.
16. **M5 original gates on all designs?** Not evaluated.
17. **Any original pass/fail conclusion changed?** No new conclusion issued;
    historical conclusions are preserved, not reaffirmed by this incomplete run.
18. **Minor, rank-significant or qualification-changing bug?** Undetermined.
    The small audit rounding difference says nothing about the legacy bug's impact.
19. **Multi-seed rerun justified?** Blocked pending witness, 21/21 topology,
    full regression and corrected seed-11 scientific evidence.
20. **Unvalidated?** Complete numerical witness, all-21 topology, corrected
    correlations and qualification, full regression; also all generalization,
    optimization, causal, power/energy and large-design claims.
21. **Exact classification?** PACT_PHASE2CR_TOPOLOGY_FAIL as an unsatisfied
    execution gate. No SEED11_REQUALIFIED/PARTIAL/INVALIDATED status is assigned.

## Tests and protocol accounting

Initial focused run: 14 passed, 0 failed, 0 skipped (6.53 s pytest summary).
No full regression was run after the stop. The initial integration test also
exercised corrected construction on the 21 inputs before the representative
witness; this was an ordering deviation. That call was removed, no architecture
scores/correlations were produced, and the edited test file has not been rerun.
See tests.json for environment, exact runtime, commands and setup failures.
The source implementation remains a candidate repair, not fully qualified code.

## Exact next experiment

First correct only the audit reduction to match the predictor's ordered
sequential addition, retaining this failed log. Re-run focused tests and the same
frozen s5378/P witness. Only after it passes, run all 21 topology gates, then
score the unchanged archived activity against corrected predictor weights and
reuse exact physical targets. Reuse Phase-2B statistics and the preregistered
gates, run isolated full regression and issue a seed-11 classification. Do not
launch any additional seed, route, ATPG, optimizer or Phase-2D work.

Phase-2C remains STOPPED_LEGACY_DEFINITION_BUG. No historical artifact was
overwritten, no routed quantity was used as a predictor feature, and no push occurred.
