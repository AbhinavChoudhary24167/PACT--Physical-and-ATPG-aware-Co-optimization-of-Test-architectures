# Troubleshooting

| Symptom | Remedy |
|---|---|
| `numba` missing | Install `.[optimizer,dev]`; exact historical execution may use its recorded `.optimizer-deps` |
| Full Windows tests import `resource` | Use Linux/WSL for the complete campaign harness; numerical usage remains supported on Windows |
| Test helper import fails | Run at repository root with `PYTHONPATH=src:scripts:.` and the qualified interpreter |
| Output already exists | Choose a fresh directory; preserve interrupted/frozen attempts |
| Doctor reports missing EDA | Supply the exact backend, FAN, simulator, library and frozen inputs for physical qualification |
| Binary/source pins disagree | Recorded binary hash/revision defines execution; source checkout alone is insufficient |
| Scan identity/endpoint/export fails | Inspect qualified connectivity/identity/alias repairs rather than weakening correctness gates |
| FAN construction/reporting differs | Use campaign-specific repairs and fault-class identities, not coverage percentage alone |
| Historical raw input missing | Restore the complete indexed archive with its original relative layout and verify hashes |
| WSL `HCS_E_HYPERV_NOT_INSTALLED` | Restore host virtualization/Virtual Machine Platform support; keep distribution files untouched |

Generated caches/builds can be rebuilt. Frozen scientific inputs/results and unique source cannot be silently substituted. See [environment](reproduction/environment.md), [upstream](upstream.md) and [retention inventory](../cleanup/PACT_STORAGE_INVENTORY.md).
