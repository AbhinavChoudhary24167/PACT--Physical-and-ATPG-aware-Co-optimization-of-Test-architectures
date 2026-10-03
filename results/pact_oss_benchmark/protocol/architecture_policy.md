# Predeclared architecture selection

B0 is the already established seed-11 K=2 contiguous supplied-order reference. B1/B2/B3 each contribute their actual single generated solution. No K=1 native order may be split and presented as native K=2.

P0 reuses the complete frozen candidate_stateful search archive. For P0 and future P1, retain the minimum predicted wire point, minimum predicted H8 point, and the point minimizing the maximum normalized regret across predicted wire, E and H8. Regret uses each retained archive dimension’s min/max; a zero range contributes zero. Break ties by full canonical SHA256, deduplicate, and use balanced as the method representative. Archive membership and selection precede new routes. Preserve all archive points for a complete predicted frontier; only implemented points can enter an implemented frontier, and unimplemented archive points must remain explicit. PACT supplies multiple solutions; OSS methods supply one.

Stage C fixes mutation evaluations to the recorded P0 count per design, uses identical starts and seed, and records wall time and memory. No coefficients, topology thresholds, selection policy or budgets may be chosen using Stage-A or Stage-C H8 labels.
