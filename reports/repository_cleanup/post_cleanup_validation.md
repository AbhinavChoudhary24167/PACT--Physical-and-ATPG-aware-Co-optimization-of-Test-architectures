# Post-cleanup validation

## Environment and build

Numerical verification used a Python 3.12 virtual environment created during cleanup, moved outside the nested checkout to ../.pact-validation-env. Dependencies were resolved using pip, then the renamed pact package was rebuilt/reinstalled editable. The initial retired project name pact-phase0 was also present as editable metadata in this validation environment; fresh-archive checks explicitly put archive/src first and verify the loaded package location. No ignored Linux binary/environment copy supplies numerical imports. The native Git submodule command could not run because this installation lacks its shell helper utilities; the index contains no submodule gitlinks.

```powershell
python -m venv .cleanup-venv
# Initial dependency resolution, then final renamed editable build:
../.pact-validation-env/Scripts/python.exe -m pip install -e '.[optimizer,dev]' --no-deps
../.pact-validation-env/Scripts/python.exe -m pip check
```

Dependency resolution and editable build passed; pip check reports No broken requirements found. Installed numerical versions include NumPy 2.5.3, Numba 0.68.0, llvmlite 0.50.0, pandas 3.0.6, SciPy 1.18.1, pytest 9.1.1. This verifies an editable checkout build, not a separately published wheel or EDA toolchain rebuild.

## Tests and tool checks

```powershell
../.pact-validation-env/Scripts/python.exe -m pytest -q --junitxml=reports/repository_cleanup/post_cleanup_tests.xml
../.pact-validation-env/Scripts/pact-optimize.exe --help
../.pact-validation-env/Scripts/pact-integrate.exe --help
../.pact-validation-env/Scripts/python.exe -m pact.optimizer.cli --synthetic 64 --chains 2 --time-budget 1 --output scratch/cleanup_smoke_final
../.pact-validation-env/Scripts/pact.exe validate-scan --architecture scratch/cleanup_smoke_final/optimized.architecture.json
../.pact-validation-env/Scripts/python.exe -m pact.integration.cli --design s5378 --optimizer-run reports/working_solver/final/s5378 --output scratch/cleanup_integration_final
../.pact-validation-env/Scripts/python.exe scripts/verify_reproducibility.py
../.pact-validation-env/Scripts/python.exe scripts/fetch_data.py --help
../.pact-validation-env/Scripts/python.exe scripts/pact_stage_b_search.py --help
```

The suite passed 382 tests and skipped one optional historical external-Liberty/weight gate in 24.037 seconds. Baseline excluding the five retired optimizer test files passed 384 and skipped one. Three tests depending on the obsolete 375-route funnel were removed; one portable-environment regression was added. All small integration tests execute in this same suite; there is no separate tests/integration directory. JUnit receipts are retained.

Optimizer smoke: WORKING_SOLVER, 64 FFs/K=2, 2,324 evaluations, 1.0042663 seconds, peak RSS 120,619,008 bytes. Selected hash 9a443c60c021d7d47fc69f32646a06e2402cc8df7499b1f5457dbb83332781a4. Topology validation passed 64 cells/two chains. This synthetic invocation tests the tool; it is not a new scientific search/campaign.

Qualified-input s5378 integration emits the scan-only handoff, passes permutation, load and unload replay with zero mismatches and checks 20,943 FF states over 117 patterns/179 FFs/K=2. Its overall status is honestly BLOCKED because route reuse and FAN replay were not run; the cleaned checkout has no retained routed ODB archive. No physical/fault-equivalence pass is inferred.

Saved replay validates the three Stage-B bundles, nine starts and nine selected architectures against independent reference scores. All nine selections match saved proxy wire/E/H8/H4 at rtol=1e-9/atol=1e-6; every order is legal. Final retained original-input checksums and the neutral Stage-A export are checked independently. Export rows/retained columns must equal the original result CSVs, including negative/dominated outcomes. The replay does not recreate routed measurements. No Stage-B search, routing, extraction or activity campaign was run during cleanup.

Three placed DEF fixtures were exported from existing frozen ODBs and exactly match their original frozen hashes; no placement was regenerated. The minimal P rewired fixture was exported from its existing database. Three graph files and 22 other retained text inputs were restored from exact original Git blobs to undo checkout line-ending conversion; their frozen SHA256 and parsed data are verified in graph_line_ending_repair.json. Input values and model/methodology did not change. All 657 originally tracked retained inputs were compared with baseline Git blobs; 674 final hash bindings, including new minimal fixtures/active summaries, were also checked against staged Git blobs. Hash-bound inputs use -text attributes, including saved FAN scripts, so new archives/clones retain those bytes. The Windows optimizer RSS call received explicit pointer argument types after the CLI smoke exposed a handle-conversion failure.

## Fresh source archive

An archive of the source/documentation commit is extracted outside the nested checkout without ignored caches, external dependencies, generated outputs or active untracked work. The existing freshly resolved numerical environment runs it with archive/src first. The loaded pact.__file__ must be inside the archive. Archive tests: 382 passed, 1 skipped; 0 failures/0 errors. Exact source revision and commands are recorded in fresh_checkout_validation.json. This validates fresh source/fixtures rather than another network installation of the same dependency versions.

## Gates and physical limits

| Gate | Outcome |
|---|---|
| G1 imports/build | PASS: editable package build, pip check and CLI imports |
| G2 unit regressions | PASS: 382 passed; explicit optional external-evidence skip |
| G3 small integration | PASS: suite plus real s5378 serialization/permutation/replay/handoff; full physical/FAN stage unexecuted |
| G4 representative tool invocation | PASS: 64-FF synthetic optimizer and topology check |
| G5 current benchmark inputs | PASS: three portable models/starts, nine selections and frozen definitions/results parse/replay |
| G6 documentation commands | PASS: quick-start smoke, CLI/help signatures, local canonical links and Python 3.11 grammar; physical/search commands documented, not launched |
| G7 tracked hygiene | PASS: no tracked dependency/build/environment/ODB/SPEF/GDS/compiled output; explicit minimal DEF/V/FAN fixtures remain |
| G8 active path defaults | PASS: configurable dependency/Python/scratch roots; only deliberate legacy relocation patterns remain; historical immutable receipts retain original captured paths |
| G9 size reduction | PASS for tracked checkout; local ignored cleanup remains pending review |
| G10 scientific/docs state | PASS: actual Stage-A completion and later Stage-B outcome/limitations reflected |

Native Windows doctor exits 1 because OpenROAD/KLayout and configured FAN/ORFS repositories are unavailable in that environment. WSL OpenROAD/FAN availability was read; exporting saved DEF/V fixtures succeeded. Full external physical build/routing/FAN integration was not executed. A further WSL Liberty-copy check could not obtain escalation review because the automatic reviewer reached its usage quota. No review rejection was bypassed.

Local recursive removal of ignored environment/dependency folders was rejected by automatic approval review as risking untracked scripts/user work. Their exact remaining inventory is local_cleanup_pending.json. These folders are excluded from the committed checkout and fresh archive, but local-storage cleanup remains incomplete. Full physical data distribution remains an explicit reproducibility limitation; the history plan requires archiving required data before removing its historical originals.
