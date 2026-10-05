# Gate 9 prospective benchmark

Both large unseen designs completed end to end, and the measured results support scientific entry into a broader scaling campaign. The next campaign is prepared; no Gate 9 reference simulation or search has run. Heavy launch remains held until storage and reference-admission gates pass.

The prospective intake uses sequential optimized designs from the [official PoliTo ITC'99 collection](https://github.com/cad-polito-it/I99T), licensed under EUPL-1.2. Cite Corno, Sonza Reorda and Squillero, *RT-Level ITC 99 Benchmarks and First ATPG Results*, DOI 10.1109/54.867894 when using this collection.

| Design | Source assignments, including DFFs | Source FFs | Family role |
|---|---:|---:|---|
| b14_opt | 5592 | 245 | Base family |
| b15_opt | 7471 | 449 | Base family |
| b17_opt | 24171 | 1414 | Composition scaling stress |
| b18_opt | 73183 | 3270 | Composition scaling stress |

These are unmapped sequential BENCH source counts, not admitted technology-mapped counts. b17 derives from b15; b18 combines b14 and b17. Report all four rows while grouping generalization by the two base families. Related copies are not independent generalization samples. No combinational variants or outcome-dependent substitutions are permitted.

Run order is source compatibility admission, complete external-reference physical/FAN/activity qualification, reference freeze, three cold-search lanes, candidate freeze, physical/topology/routing/DRC/timing, FAN, exact compact activity, then measured comparison. An unsupported import is an admission blocker rather than a PACT scientific failure.

Retain K=2, seed=11, epsilon 0.02/0.05/0.10, 900 seconds per mutation loop and 7200 seconds per search worker. Keep the existing objectives, operators, acceptance, reference-selection rule, primary/secondary role order, maximum three pre-route candidates, FAN workload and E/H4/H8 definitions. No per-design rescue or retuning is allowed.

Use one heavy CPU worker. Admission requires at least 6 GiB of system-volume headroom and the existing 20 GiB scratch reserve plus a margin of at least 5 GiB. Raise the required margin from measured reference/package/trace dimensions for larger designs. Never reduce the floor to launch; no GPU or distributed execution is introduced.

Measure mapped gate/FF/chain counts, patterns, shift cycles, activity nets, exact evaluations, mutation throughput, runtimes, peak RSS, compressed trace bytes, routed scan wirelength, setup/hold timing, DRC, fault coverage and E/H4/H8. Retain missing measurements as pending with a reason.

Report candidate qualification rate against all preselected candidates and design completion/useful-result rates against the full preregistered cohort. Also show the admitted-design denominator. Preserve failed and blocked rows, primary outcomes, all secondary outcomes and every regression.
