# Installation

Use Python 3.11+ in a fresh environment:

```sh
python -m venv .venv
# Linux/WSL: source .venv/bin/activate
# PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -e '.[optimizer,dev]'
```

Numba is required by optimizer/stateful evaluation. Windows supports portable numerical workflows/tests; physical adapters target Linux/WSL with OpenROAD's Python interface, ORFS, FAN_ATPG, Yosys and Icarus Verilog.

```sh
export PACT_DEPENDENCY_ROOT="$PWD/external"
export PACT_ORFS_ROOT="$PACT_DEPENDENCY_ROOT/OpenROAD-flow-scripts"
export PACT_FAN_ATPG_ROOT="$PACT_DEPENDENCY_ROOT/FAN_ATPG"
export PACT_EXPERIMENT_ROOT="$PWD/scratch"
```

Use a larger external volume for EDA outputs. Individual ORFS/FAN location overrides take precedence in dependency resolution. Scratch defaults to ignored `scratch/`.

Adapters use the current Python interpreter; set `PACT_PYTHON` when a separate qualified Python environment is required.

Recorded pins are ORFS `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`, FAN_ATPG `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, and native implementation OpenROAD `08f67ee5ecd14db5a42be8c610bbfd1ccf079299`. The original installed binary and source checkout differed; the binary revision defines B1 behavior. [Baseline provenance](benchmarks.md) records exact B2/B3T sources and repairs.

`python scripts/fetch_data.py --output external` fetches known pinned FAN/ORFS sources and recursive dependencies, refusing to replace existing destinations. It does not install compilers or run experiments. Build dependencies according to their pinned instructions; an arbitrary current OpenROAD binary is not the frozen benchmark backend.

`python -m pact.cli doctor` reports missing tools and configured source revisions. Missing EDA tools on a numerical-only host must not be relabeled as physical qualification.
