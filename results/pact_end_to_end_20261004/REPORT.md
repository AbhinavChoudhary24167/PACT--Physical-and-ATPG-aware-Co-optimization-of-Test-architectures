PACT_END_TO_END_SOLUTION_QUALIFIED

References are frozen by minimum qualified routed scan cost among B0/B1/B2/B3T before this gate. All nine prior Stage-B selections are retained; the optimizer, objective, seeds, workload and common backend are unchanged. Saved search/physical runs are reused with verified input/output hashes, exact routed edges, extraction and simulation proofs.

| Design | Method | Routed scan WL (µm) | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS (ns) | DRC | Fault coverage % | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s5378 | B2 | 4882.830 | 0.0000 | 19523343.212 | 0.0000 | 446.23105 | 0.0000 | 187.25777 | 0.0000 | 9.08788 | 0 | 96.041279 | QUALIFIED |
| s5378 | s5378_C1 | 4899.280 | 0.3369 | 18913553.093 | -3.1234 | 404.20548 | -9.4179 | 166.60606 | -11.0285 | 9.08575 | 0 | 96.041279 | QUALIFIED |
| s5378 | s5378_C2 | 5159.585 | 5.6679 | 18218623.503 | -6.6829 | 409.56072 | -8.2178 | 174.38007 | -6.8770 | 9.08663 | 0 | 96.041279 | QUALIFIED |
| s5378 | s5378_C3 | 5074.960 | 3.9348 | 19218672.616 | -1.5605 | 383.08508 | -14.1510 | 183.61355 | -1.9461 | 9.08726 | 0 | 96.041279 | QUALIFIED |
| s9234 | B3T | 10505.275 | 0.0000 | 39816702.111 | 0.0000 | 537.13614 | 0.0000 | 195.57764 | 0.0000 | 8.74941 | 0 | 94.142996 | QUALIFIED |
| s9234 | s9234_C1 | 10696.095 | 1.8164 | 38556259.567 | -3.1656 | 463.14322 | -13.7755 | 191.87925 | -1.8910 | 8.75119 | 0 | 94.142996 | QUALIFIED |
| s9234 | s9234_C2 | 10643.935 | 1.3199 | 38153295.476 | -4.1777 | 507.83279 | -5.4555 | 192.35797 | -1.6462 | 8.74961 | 0 | 94.142996 | QUALIFIED |
| s9234 | s9234_C3 | 10653.995 | 1.4157 | 38762209.820 | -2.6484 | 485.46609 | -9.6195 | 190.51088 | -2.5907 | 8.74898 | 0 | 94.142996 | QUALIFIED |
| s15850 | B2 | 23958.435 | 0.0000 | 158251697.846 | 0.0000 | 680.24193 | 0.0000 | 279.57368 | 0.0000 | 8.13162 | 0 | 94.617879 | QUALIFIED |
| s15850 | s15850_C1 | 24208.690 | 1.0445 | 158127855.196 | -0.0783 | 699.96965 | 2.9001 | 276.18001 | -1.2139 | 8.13166 | 0 | 94.617879 | QUALIFIED |
| s15850 | s15850_C2 | 24210.015 | 1.0501 | 157217009.226 | -0.6538 | 653.25134 | -3.9678 | 278.59896 | -0.3486 | 8.13180 | 0 | 94.617879 | QUALIFIED |
| s15850 | s15850_C3 | 24191.395 | 0.9724 | 158202517.693 | -0.0311 | 700.55294 | 2.9859 | 278.08832 | -0.5313 | 8.13186 | 0 | 94.617879 | QUALIFIED |

E is extracted ground-plus-pin C×transitions in fF·transitions. H4/H8 are the frozen maximum source-bin/cycle metrics. Routed scan WL includes shared functional branches and is an upper bound, not exact scan-only attribution. WNS is the existing global-route setup value; hold WNS/TNS are in the canonical dataset. Detailed-route DRC is zero. No signoff timing, watts or IR-drop claim is made.

FAN correctness uses the original functional circuit/library after independent serial recovery for each exact selected architecture. Complete collapsed target universes, equivalence weights and detected class identities match the frozen reference; all simulated pattern counts and weighted full/detected counts agree. The original extraction premarks some CK/SE/SI faults detected, and that semantics is preserved. Individual uncollapsed class-member identities are not enumerated and are not claimed equivalent.

The reporting-only FAN repair is isolated on fix/report-fault-scan-identities, based on 26b2b36c0e9db11a4b6d9e759df6e44357121f39. It preserves extraction and simulation statistics on all three frozen workloads. See upstream_repair/qualification.json and reporter.patch.

Searches: seed 11, K=2, epsilons 0.02/0.05/0.10, 300 seconds per mutation loop, 20,000 evaluations, 2,000 stagnation attempts, 16 neighbors, segment 8, archive 16, 150-attempt lane restarts and existing balanced weights (1,1,1). There are 4869 exact candidate evaluations across the nine saved runs. Complete configuration, source, parent/reference hashes, selection roles and runtimes are in selected_candidates.json and canonical_results.json. No search or route was repeated for this sealing task.

The balanced C1 selections improve E/H4/H8 for s5378 and s9234 with routed wire costs. s15850 C1 regresses H4; its retained best_E C2 improves all three activity coordinates. All s9234 selections remain dominated on the original wire/E/H8 Stage-A front, while the frozen four-coordinate analysis retains H4 tradeoffs. All nine outcomes are reported; no baseline or objective was changed to make them positive.

The primary representative is the existing pre-route balanced C1 for every design (primary_comparison.csv); it is not reselected using measured values. The s15850 C2 endpoint remains a reported alternative from the original best_E lane.

Repository start: main at de833ef018703d26dd1e6e1fd1e4a103dc8dc41e, clean native working tree. PACT work branch: qualify/end-to-end-20261004. Separate FAN repair branch: fix/report-fault-scan-identities at 05ac6173535418711b60ee22df391da7a4a82252. The ending PACT SHA is reported in the completion message because the result commit cannot include its own SHA.

Changed source: scripts/pact_end_to_end.py, scripts/verify_end_to_end.py, src/pact/integration/qualification.py and tests/unit/test_end_to_end_qualification.py; documentation: README.md, docs/research_status.md and docs/end_to_end_qualification.md; new receipts/results are under results/pact_end_to_end_20261004/. Existing qualified outputs and the scientific optimizer remain unchanged.

Validation for this task: 33 focused integration/correctness regressions passed; the standalone FAN full/state-filtered reporting regression passed; all three repaired-vs-original FAN workload statistics matched; final independent verification checked all 12 records. Earlier new-gate path/schema failures are retained in qualification_attempts/ and triggered no search, routing or scientific-method changes.

Remaining implementation blockers for this three-design milestone: none. Broader scaling, hotspot prediction reliability, full uncollapsed member enumeration and signoff analyses remain outside this result.
