# PACT Phase-0C disk-floor recovery addendum

The frozen Phase-0C campaign at commit `3e7b516a6a3b68950aad624b3474bf0c45b78b97` stopped after 3,353.453573 seconds because the workspace had less than the predeclared 512 MiB of free space. At that point 27 rows were `QUALIFIED`; the remaining 348 rows were recorded as `WORKSPACE_DISK_FLOOR_REACHED`. The preserved interrupted manifest has SHA-256 `5907a04fd4a1e23cd599e49918a3c191c327073d5d6cc1cae16f315af4ce2104`.

This addendum authorizes one recovery pass over exactly those 348 rows. It does not change the benchmark set, physical seeds, K values, methods, toolchain, routes, ports, objectives, analysis thresholds, per-route timeout, or disk floor. The recovery process keeps the original freeze commit in each route identity and uses a separate immutable recovery ledger.

The recovery cap is 68,647 seconds, calculated as the original 72,000-second cap minus the integer part of the interrupted session duration. A row already present in the recovery ledger is never attempted again. The final analysis is admissible only when the 27 original qualified rows and all 348 predeclared recovery rows form an exact, nonoverlapping 375-row union and every frozen input hash remains valid.

The interrupted manifest remains unchanged. Recovery eligibility depends only on the preexisting `WORKSPACE_DISK_FLOOR_REACHED` status and never on a measured physical or activity outcome.
