# Development and tests

Install `.[optimizer,dev]`, then run `python -m pytest -q`. Tests cover scan/identity/pattern contracts, exact activity references, mutation/rollback, stateful logic/geometry, Stage-B feasibility, integration replay and baseline/receipt qualification. Phase-named tests protect shared current behavior rather than complete historical campaigns.

| Layer | Command / scope |
|---|---|
| Unit | `python -m pytest -q`; constructed numerical/structural fixtures |
| Small integration | Same suite; CLI/file export/workload replay and physical/benchmark adapters |
| Research regression | `python scripts/verify_reproducibility.py`; saved portable bundles/orders/hashes |
| Physical smoke | Explicit inputs with `pact-integrate`/OpenDB adapters in qualified Linux/WSL; independently verify topology/exported connectivity before routing |

Physical tools/inputs are outside numerical CI. An external-evidence test skips only when its explicit artifacts are absent; a skip is not physical validation.

Obsolete H_eff8 Optimizer-v1/v2/v2.1/v2.2/v2.3 modules/runners and paired tests are removed. Maintained implementation-aware v2 classes are a separate current dependency. The retired suite's undeclared threadpoolctl dependency is not imposed on the current product.

Evaluator changes require independent full-reference and rollback checks. A scalar score or proxy gate does not replace measured qualification. Store generated outputs in ignored scratch or configured experiment storage, and publish hashes/configuration/summary tables for research changes.
