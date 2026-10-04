# End-to-end qualification

The sealed current result is `PACT_END_TO_END_SOLUTION_QUALIFIED` for s5378, s9234 and s15850, using the existing Stage-B method. [The report](../results/pact_end_to_end_20261004/REPORT.md) retains all nine candidates and their negative outcomes. [The canonical dataset](../results/pact_end_to_end_20261004/canonical_results.json) contains exact identities, configuration, predictions, measured values, fault counts, gates and provenance. [The immutable references](../results/pact_end_to_end_20261004/frozen_baselines.json) select B2/B3T/B2 by minimum qualified routed scan cost.

This qualification reuses the executed searches and exact routed/extracted implementations after checking their hashes and conditions. It adds independent serial replay and FAN stuck-at simulation for each reference and selected order. It does not repeat the search, routing or historical matrices.

```sh
python scripts/verify_end_to_end.py
```

This verifies the delivered architectures, complete fault-class exports, recovered functional workloads, measured-value preservation and deltas without EDA tools. Full physical source data remain in the original experiment store; a fresh physical campaign requires the hash-bound inputs described in [reproducibility](reproducibility.md).

Apply the retained `upstream_repair/reporter.patch` to an isolated checkout of FAN commit `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, retain a separate repair branch and build with its existing Makefile. Use the `qualify-reporter` action first to compare the repaired executable with the original qualified FAN binary on the three unchanged workloads. Then execute the reusable gate with the same arguments and action `qualify`:

```sh
python scripts/pact_end_to_end.py qualify \
  --campaign "$PACT_EXPERIMENT_ROOT/results/stage_b_20261004" \
  --experiments "$PACT_EXPERIMENT_ROOT" \
  --dependencies "$PACT_DEPENDENCY_ROOT" \
  --fan-root /path/to/qualified/FAN_ATPG-report-repair
```

The repair's standalone `report_fault_scan.py` regression accepts executable, library, netlist and pattern paths and verifies complete and state-filtered exports. No `run_atpg` command is invoked by these gates.

The gate fails on changed references, solver source, architecture/parent identities, routed edges, physical conditions, extraction/simulation bindings, pattern counts, fault universe weights or detected identities. Previous gate attempts remain recorded. The reporting repair and standalone regression are retained under `results/pact_end_to_end_20261004/upstream_repair/`; the original qualified FAN binary is unchanged.

Fault identity PASS means complete equality of FAN's collapsed SAF target classes and equivalence multiplicities on the same original functional circuit/library. FAN does not enumerate individual members of those equivalence classes; full uncollapsed member identity equivalence is explicitly unclaimed. Some test-control faults are premarked DT by the original extractor, and that existing semantics is preserved. WNS remains global-route timing, and switching measures remain extracted capacitance-times-transitions proxies.
