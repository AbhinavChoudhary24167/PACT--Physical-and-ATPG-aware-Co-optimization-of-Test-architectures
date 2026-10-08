# Environment and pinned tools

Python **3.11+** is the package contract. `pyproject.toml` declares NumPy≥1.24, pandas≥2.0, SciPy≥1.10, Matplotlib≥3.7, PyYAML≥6.0 and jsonschema≥4.0; optimizer usage adds Numba≥0.59 and development pytest≥8. These are compatibility bounds, not historical environment locks.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[optimizer,dev]'
PYTHONPATH=src:scripts:. python -m pytest -q
python scripts/verify_reproducibility.py
```

Numerical usage supports Windows (`.venv/Scripts/Activate.ps1`); the complete campaign/test harness uses Linux facilities such as `resource` and targets Linux/WSL. Exact reproduction uses the recorded interpreter/package/compiler/build receipts.

| Dependency | Recorded identity |
|---|---|
| Installed OpenROAD backend | `08f67ee5ecd14db5a42be8c610bbfd1ccf079299`, version `26Q2-1164-g08f67ee5ec` |
| Supporting OpenROAD source | `dc5eee77c45dba8e5ace2fc89c38c6d9a4ed6e0f`; differs from the binary |
| OpenSTA | Installed 3.1.0; embedded declared revision `76c4d6df3537ccce331b5caa812196c3330ba7c4` |
| ORFS | `5e8b1450d19263f797a27c4f371b9dd19f32a3aa` |
| FAN_ATPG base | `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, plus the registered construction/reporting repairs |
| Physical simulation/build | Qualified OpenROAD Python interface, FAN_ATPG, Yosys, Icarus Verilog, C/C++ compiler and exact submodule/build settings from receipts |
| Technology | Hash-bound Nangate45 library/LEF/RC/PDN inputs in manifests and Gate 10A provenance |

B2/B3T generation builds differ from the common backend; [baseline provenance](../benchmarks.md) defines their pins/repairs. A current checkout/compiler does not prove bit-identical execution. `scripts/fetch_data.py --output external` fetches pinned sources without replacing existing locations or inventing private-data URLs; follow the pinned build instructions and retained configuration.

Configure `PACT_DEPENDENCY_ROOT`, `PACT_ORFS_ROOT`, `PACT_FAN_ATPG_ROOT`, `PACT_EXPERIMENT_ROOT` and `PACT_PYTHON` as needed; `pact doctor` reports availability. Portable receipts use `repo://`, `dep://`, `run://`. Immutable historical raw paths/hashes remain provenance. Restore complete raw campaigns through `archives/MANIFEST.csv` before adapters need their contents. PACT's license does not grant new rights to external assets.
