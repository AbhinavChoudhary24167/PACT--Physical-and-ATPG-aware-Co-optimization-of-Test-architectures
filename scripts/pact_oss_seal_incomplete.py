#!/usr/bin/env python3
"""Seal a factual incomplete Stage A after an observed baseline build failure."""
from pact.environment import python_executable
from pact.experiment_storage import experiment_root
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, git, read, verify, write
from pact_oss_canonicalize import csv_write


def resource_rss(path):
    match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', path.read_text())
    return int(match[1]) / 1024 if match else ''


def markdown(path, text):
    if path.exists():
        raise ValueError('Refusing to overwrite sealed report: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n')


def main():
    block = read(OUT / 'baselines/B2_openroad_10176/build_status.json')
    if block['status'] != 'CONFIGURATION_FAILED' or block['configuration']['returncode'] == 0:
        raise ValueError('Incomplete classification requires an observed failed build gate')
    verify()
    versions = read(OUT / 'protocol/tool_versions.json')
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    index = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    selected = [r for r in index if r['selected'] == 'True']
    suite = ET.parse(OUT / 'stage_a/protocol_tests.xml').getroot().find('testsuite')
    if int(suite.attrib['failures']) or int(suite.attrib['errors']):
        raise ValueError('Protocol/P0 regression suite failed')
    status = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                  stage_a='PACT_STAGE_A_INCOMPLETE', scientific='PACT_BENCHMARK_INCONCLUSIVE',
                  P0_commit=frozen['commit'], OSS_benchmark_complete=False,
                  P1_model_complete=False, post_improvement_benchmark_complete=False,
                  Stage_B='NOT_STARTED_STAGE_A_STOP_CONDITION', Stage_C='NOT_STARTED_STAGE_A_STOP_CONDITION',
                  stop_condition='Requested OpenROAD baseline not reproduced: exact PR #10176 failed CMake configuration in the current qualified environment',
                  observed_blockers=['SWIG_EXECUTABLE and SWIG_DIR missing; source requires SWIG >=4.3', 'TCL_HEADER-NOTFOUND'],
                  build_evidence=binding(OUT / 'baselines/B2_openroad_10176/build_status.json'),
                  qualification=dict(P0_frozen_bindings=454, canonical_architectures=len(index), FF_manifest_rows=7328,
                                     selected_P0_architectures=sum(r['method'] == 'P0' for r in selected),
                                     native_K2_designs=list(DESIGNS), unit_tests_passed=int(suite.attrib['tests'])),
                  new_routes=0, new_extractions=0, new_simulations=0, new_ATPG_runs=0,
                  implemented_comparison='UNAVAILABLE; no measured OSS/P0 comparison or external Pareto conclusion',
                  next_milestone='Provision an isolated reproducible build toolchain for the pinned PRs, then complete and seal the unchanged Stage-A benchmark before P1')
    write(OUT / 'stage_a/status.json', status)
    algorithms = dict(
        B0=dict(behavior='Existing seed-11 K=2 contiguous supplied-order reference; not the original K=1 physical chain'),
        B1=dict(commit=versions['baselines']['B1_openroad_native']['commit'],
                commands='set_dft_config -max_chains 2 -max_length ceil(FF/2) -clock_mixing no_mix; report_dft_plan -verbose; execute_dft_plan',
                behavior='Native clock-domain buckets and per-chain nearest-neighbor FF-origin ordering; scan_opt is not invoked',
                source='src/dft/src/architect/ScanArchitectHeuristic.cpp and Opt.cpp in source_pin.json'),
        B2=dict(commit=versions['baselines']['B2_openroad_10176']['commit'], commands='execute_dft_plan; scan_opt (planned, not executed)',
                behavior='Nearest-neighbor native seed followed by endpoint-inclusive symmetric FF-origin Manhattan 2-Opt; restitch and write DFT information',
                parameters=dict(max_2opt_iterations=30), reproduction='CONFIGURATION_FAILED; no generated B2 architecture'),
        B3=dict(commit=versions['baselines']['B3_openroad_10666']['commit'], commands='execute_dft_plan; scan_opt (planned, not executed)',
                behavior='Same-clock/edge capacity-aware farthest-point seeded K-means repartitioning, nearest-neighbor seed, asymmetric scan-pin 2-Opt and direction-preserving 3-Opt; restitch ODB',
                parameters=dict(kmeans_iterations=100, capacity='original maximum chain bit count', candidate_neighbors=50,
                                candidate_overquery=100, local_search='strict improvement until no improvement'),
                objective_note='Per-chain local search uses internal directed scan-pin Manhattan distances; it does not include external SI/SO endpoint costs',
                reproduction='Source pinned and inspected; full build not attempted after B2 stop condition'),
        P0=dict(commit=frozen['commit'], model='candidate_stateful_depth3_frozen', production_changed=False,
                search='Reuse existing frozen retained archive and exact recorded budgets', selection='Predeclared predicted-only physical/H8 extrema and balanced minimax normalized regret'),
        P1=dict(model='candidate_stateful_adaptive', implementation='NOT_STARTED'))
    write(OUT / 'protocol/algorithm_audit.json', algorithms)
    quality = {}
    for design in DESIGNS:
        files = {name: binding(ROOT / 'artifacts/raw/tool_qualification/fan_atpg' / f'{design}.{name}.log')
                 for name in ('atpg', 'fsim')}
        text = Path(files['fsim']['path']).read_text()
        retained = [line.strip() for line in text.splitlines() if re.search(r'fault coverage|detected faults|detected fault|faults detected', line, re.I)]
        quality[design] = dict(logs=files, original_report_lines=retained, patterns=frozen['frozen_inputs'][design]['patterns'],
                               interpretation='Stored original FAN evidence retained; no new candidate fault simulation or identity-set comparison',
                               fault_set_equivalent=None)
    write(OUT / 'stage_a/test_quality_evidence.json', quality)
    metric_fields = ['design', 'method', 'architecture_hash', 'roles', 'representative', 'benchmark_status',
                     'routed_scan_path_cost', 'measured_E', 'measured_H4', 'measured_H8', 'measured_peak_bin',
                     'measured_peak_cycle', 'top_N_bins', 'DRC', 'scan_topology_correct', 'FF_identity_correct',
                     'functional_sanity', 'setup', 'hold', 'WNS', 'TNS', 'fault_coverage', 'detected_fault_count',
                     'fault_set_equivalent_if_available', 'implementation_runtime', 'peak_RSS']
    implementation = []
    for row in selected:
        result = {k: row.get(k, '') for k in metric_fields}
        result['benchmark_status'] = 'NOT_IMPORTED_OR_PERFORMED_AFTER_BASELINE_BUILD_GATE'
        implementation.append(result)
    for design in DESIGNS:
        for method in ('B2', 'B3'):
            row = dict.fromkeys(metric_fields, '')
            row.update(design=design, method=method, representative=True,
                       benchmark_status='CONFIGURATION_FAILED' if method == 'B2' else 'NOT_BUILT_AFTER_STOP_CONDITION')
            implementation.append(row)
    csv_write(OUT / 'stage_a/implemented_metrics.csv', metric_fields, implementation)
    pareto_fields = ['design', 'method', 'architecture_hash', 'representative', 'nondominated', 'dominated_by', 'unique_frontier_contribution', 'status']
    pareto = [dict(design=r['design'], method=r['method'], architecture_hash=r['architecture_hash'], representative=r['representative'],
                   nondominated='', dominated_by='', unique_frontier_contribution='', status='NOT_EVALUATED_IMPLEMENTED_METRICS_UNAVAILABLE') for r in implementation]
    csv_write(OUT / 'stage_a/pareto_front.csv', pareto_fields, pareto)
    comparison = []
    for design in DESIGNS:
        for method in ('B0', 'B1', 'B2', 'B3', 'P0'):
            points = [r for r in selected if r['design'] == design and r['method'] == method]
            comparison.append(dict(design=design, method=method, retained_selected_points=len(points),
                                   method_representative=next((r['architecture_hash'] for r in points if r['representative'] == 'True'), ''),
                                   generation_status='CANONICAL_QUALIFIED' if points else ('CONFIGURATION_FAILED' if method == 'B2' else 'NOT_BUILT'),
                                   implemented_comparison='NOT_ASSESSABLE', A1='NOT_ASSESSABLE', A2='NOT_ASSESSABLE',
                                   A3='NOT_ASSESSABLE', A4='NOT_ASSESSABLE', A5='NOT_ASSESSABLE'))
    csv_write(OUT / 'stage_a/method_comparison.csv', list(comparison[0]), comparison)
    runtime = []
    summary = read(ROOT / 'results/pact_candidate_stateful/summary.json')
    for design in DESIGNS:
        folder = OUT / 'baselines/B1_openroad_native' / design
        successful = [p for p in folder.glob('native*.execution.json') if read(p)['returncode'] == 0]
        if len(successful) != 1:
            raise ValueError('Native success evidence ambiguous')
        path = successful[0]
        result = read(path)
        resource = path.with_name(path.name.replace('.execution.json', '.resource.txt'))
        runtime.append(dict(design=design, method='B1', phase='generator_command_including_IO', seconds=result['seconds'],
                            peak_RSS_MiB=resource_rss(resource), evaluations='', source=str(path), reused=False))
        previous = summary['designs'][design]
        runtime.append(dict(design=design, method='P0', phase='historical_search_command_including_initialization_and_checks',
                            seconds=previous['total_seconds'], peak_RSS_MiB=previous['peak_RSS_MiB'],
                            evaluations=previous['evaluations'], source='results/pact_candidate_stateful/summary.json', reused=True))
    runtime.append(dict(design='all', method='B2', phase='failed_build_configuration', seconds=block['configuration']['seconds'],
                        peak_RSS_MiB=resource_rss(OUT / 'baselines/B2_openroad_10176/configure.resource.txt'), evaluations='',
                        source='baselines/B2_openroad_10176/build_status.json', reused=False))
    csv_write(OUT / 'stage_a/runtime.csv', list(runtime[0]), runtime)
    master_fields = ['design', 'method', 'architecture_hash', 'roles', 'representative', 'benchmark_status',
                     'pre_route_scan_hpwl', 'port_inclusive_scan_hpwl', 'routed_scan_path_cost', 'predicted_E', 'predicted_H8',
                     'measured_E', 'measured_H4', 'measured_H8', 'measured_peak_bin', 'measured_peak_cycle',
                     'DRC', 'setup', 'hold', 'WNS', 'TNS', 'fault_coverage', 'detected_fault_count',
                     'fault_set_equivalent_if_available', 'optimizer_runtime', 'implementation_runtime', 'peak_RSS']
    pre = {r['architecture_hash']: r for r in csv.DictReader((OUT / 'stage_a/pre_route_metrics.csv').open())}
    master = []
    for row in implementation:
        result = {k: row.get(k, '') for k in master_fields}
        p = pre.get(row['architecture_hash'], {})
        result.update(pre_route_scan_hpwl=p.get('scan_hpwl_um', ''), port_inclusive_scan_hpwl=p.get('port_inclusive_scan_hpwl_um', ''),
                      predicted_E=p.get('predicted_E', ''), predicted_H8=p.get('predicted_H8', ''))
        if row['method'] == 'P0':
            result['optimizer_runtime'] = summary['designs'][row['design']]['total_seconds']
            result['peak_RSS'] = summary['designs'][row['design']]['peak_RSS_MiB']
        master.append(result)
    for design in DESIGNS:
        result = dict.fromkeys(master_fields, '')
        result.update(design=design, method='P1', benchmark_status='NOT_STARTED_STAGE_A_INCOMPLETE', representative=True)
        master.append(result)
    csv_write(OUT / 'final/master_comparison.csv', master_fields, master)
    design_summary = [dict(design=d, stage_a=status['stage_a'], P0_vs_OSS='UNAVAILABLE', P1_vs_P0='NOT_STARTED',
                           P1_vs_OSS='NOT_STARTED', implemented_E_delta='', implemented_H8_delta='', physical_cost_delta='',
                           prediction_delta='', frontier_contribution='UNKNOWN', next_gate='Reproduce pinned B2/B3 binaries') for d in DESIGNS]
    csv_write(OUT / 'final/per_design_summary.csv', list(design_summary[0]), design_summary)
    csv_write(OUT / 'final/pareto_summary.csv', pareto_fields, pareto)
    markdown(OUT / 'baselines/B0_reference/README.md', '# B0 reference\n\nThe already established seed-11 K=2 B0 canonical architectures are copied under `../../stage_a/canonical`. '
             'This is the supplied-order contiguous K=2 reference, rather than the original physical K=1 chain. Canonical hashes are preserved. '
             'Implementation evidence is not imported into the incomplete comparison.\n')
    markdown(OUT / 'baselines/B2_openroad_10176/README.md', '# Pinned 2-Opt baseline\n\n'
             f'Exact head: `{block["commit"]}`. The full archive and exact recursive submodules are in D: scratch storage and indexed in build_sources.json. '
             'DFT source bytes match the commit-addressed Git blob audit. Release configuration used GCC 13.3.0, CMake 3.28.3, GUI/GPU/tests disabled, Python enabled and LTO disabled. '
             'Configuration failed because SWIG >=4.3 is absent; Tcl headers are also missing. No binary or B2 architecture was produced. '
             'Source-archive VCS warnings are retained; they do not substitute for the explicit immutable source hashes. This is an environment/build qualification failure, not evidence that the algorithm is defective or impossible to build elsewhere.\n')
    markdown(OUT / 'baselines/B3_openroad_10666/README.md', '# Pinned primary external baseline\n\n'
             f'Exact head: `{versions["baselines"]["B3_openroad_10666"]["commit"]}`. See source_pin.json and algorithm_audit.json for immutable source hashes and actual behavior. '
             'The source was acquired and inspected. Its full build and architecture generation were not attempted after the B2 reproduction stop condition. '
             'No weaker algorithm or reimplementation was substituted.\n')
    markdown(OUT / 'baselines/B1_openroad_native/README.md', '# Native OpenROAD baseline\n\n'
             f'Installed binary source revision: `{versions["baselines"]["B1_openroad_native"]["commit"]}`. '
             'All three designs pass actual execute_dft_plan K=2 ordering qualification, exact FF inventory and unchanged FF masters/placement/functional D/CK nets. '
             'No scan_replace was needed because the common placed database already contains SDFF_X1. SI/SO paths were independently traced in the generated ODB. '
             'The regenerated historical test_cell-only Liberty exactly matches its prior hash; downstream Liberty remains original. '
             'Port names are translated before STA initialization, preserving endpoint shapes and avoiding stale STA port caches. '
             'PACT logical chain-0 endpoint aliases are recorded separately. Four s5378 adapter attempts are retained: missing historical Liberty copy, unsupported setName API, '
             'a stale-port-cache SIGSEGV after renaming an already initialized STA database, and the successful corrected adapter. '
             'The last successful attempt and the two other successful designs have executed-source snapshots. The failed first two attempts have logs but no source snapshots. '
             'No native route, extraction, workload replay or implemented activity measurement has been performed.\n')
    markdown(OUT / 'README.md', '# Controlled PACT / OSS campaign\n\n'
             '**Stage A: PACT_STAGE_A_INCOMPLETE. Scientific result: PACT_BENCHMARK_INCONCLUSIVE.**\n\n'
             'P0 is frozen at 9d9103027918b1d4af2b209e6d36133ad82d4a4e. Native K=2 ordering qualifies on all three designs. '
             'The exact PR #10176 build fails configuration on missing SWIG >=4.3 and Tcl development headers. '
             'The requested baseline-reproduction stop condition is active. Stages B and C are not started.\n\n'
             'Read [Stage A](stage_a/README.md) and the [report](final/FINAL_REPORT.md). '
             'The 24 canonical architectures, 7 selected P0 points and protocol tests are preserved. No new routes, extraction, simulation or ATPG runs occurred. '
             'Blank implemented values mean unavailable, not zero, and historical measurements have not been relabeled as OSS comparisons.\n')
    markdown(OUT / 'stage_a/README.md', '# Stage A incomplete seal\n\n'
             '**Classification: PACT_STAGE_A_INCOMPLETE.**\n\n'
             'The independent-variable contract, immutable P0 source/input hashes, exact OSS source revisions, native DFT commands and generated FF ordering are recorded. '
             'All 454 frozen evidence bindings pass. The manifest contains 24 canonical architectures and 7,328 ordered-FF records, including the complete retained P0 archives; '
             'seven distinct P0 points are selected using the predeclared predicted-only policy. B0 and B1 each supply one solution per design.\n\n'
             'The full PR #10176 source and its five recursive submodules were acquired, and DFT source equivalence passed. '
             'Release CMake configuration failed on missing SWIG >=4.3; TCL_HEADER-NOTFOUND is also reported. '
             'A valid exact baseline executable therefore remains unavailable in the current environment. '
             'Under the user’s explicit stop rule, no route or model change follows this failure. This incomplete seal does not satisfy the Stage-B engineering gate.\n\n'
             'Implemented metrics, Pareto membership and A1–A5 are unavailable. The tables retain explicit statuses and empty measurements. '
             'Saved P0 predictions are diagnostics; B0/B1 rescoring was not performed after the pending baseline build gate. '
             'The complete archive includes points without imported implemented evidence; a complete implemented Pareto claim is not made.\n\n'
             f'Tests: `PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 {python_executable()} '
             '-m pytest -q tests/unit/test_oss_benchmark.py tests/unit/test_candidate_stateful.py --junitxml=results/pact_oss_benchmark/stage_a/protocol_tests.xml`: **16 passed**. '
             'These include deterministic selection, unit scaling, measurement independence, rejection of FF/placement/K/capacity/endpoint confounders, '
             'and all six existing stateful correctness/rollback/search tests. Native qualification is additional executed tool evidence.\n\n'
             'Original FAN fault-coverage/detected-count report lines and log hashes are retained in test_quality_evidence.json. '
             'No candidate fault-identity equivalence has passed. Original README/planning/fault-identity/H8 diagnosis edits remain outside the milestone commit. '
             'The stage seal commit is identified by the subsequent commit receipt and final response.\n')
    pins = versions['baselines']
    report = f'''# Controlled PACT research campaign: incomplete at Stage A

**Engineering: PACT_STAGE_A_INCOMPLETE. Scientific: PACT_BENCHMARK_INCONCLUSIVE.**

## 1. What was benchmarked?

Prepared designs: s5378, s9234 and s15850, existing qualified seed-11 Nangate45 placement, K=2 and existing FAN patterns. Architecture generation was qualified for B0, B1 and the frozen P0 archive. The implemented head-to-head benchmark was not reached.

| Method | Exact revision | Status |
|---|---|---|
| P0 | `{frozen['commit']}` | Frozen candidate_stateful depth=3; complete saved archive retained |
| B1 native | `{pins['B1_openroad_native']['commit']}` | Actual execute_dft_plan ordering qualifies for all three designs |
| B2 PR #10176 | `{pins['B2_openroad_10176']['commit']}` | Full source/submodules acquired; CMake configuration fails |
| B3 PR #10666 | `{pins['B3_openroad_10666']['commit']}` | Immutable source acquired and inspected; build/generation not attempted after stop |
| B0 | Existing reference architecture hashes in architecture_manifest.csv | Canonical supplied-order K=2 control retained |

ORFS commit: `{versions['ORFS_commit']}`. Fixed implementation OpenROAD: `{versions['implementation_openroad_version']}`, binary SHA256 `{versions['implementation_binary_sha256']}`. Its local source checkout was a different revision, so native semantics were inspected using source acquired at the binary revision instead. B2 merge-base: `{pins['B2_openroad_10176']['base_revision']}`. B3 merge-base: `{pins['B3_openroad_10666']['base_revision']}`.

The exact commands, algorithm parameters, configurations, source Git blobs, source SHA256s, architecture identities and native endpoint translations are in protocol/ and baselines/. B2 uses native NN initialization and endpoint-inclusive FF-origin Manhattan 2-Opt, default 30 iterations. B3 uses capacity-aware same-domain K-means (100 iterations maximum), NN, directed scan-pin 2-Opt with reversal correction and direction-preserving 3-Opt over 50 nearest candidates; its local-search cost excludes external endpoints. This description comes from the pinned implementation, not only the PR summary.

## 2. Was the comparison fair?

The contract freezes mapped design, exact FF inventory/coordinates, technology, original Liberty/LEF infrastructure, clocks/constraints, K, placement/seed, FAN pattern hashes, load/capture/unload cycles, routing/extraction/measurement scripts, H4/H8 grids, source attribution and timing methodology. Source/input/evidence verification passes 454 bindings. No production model or optimizer file changed. No placement, routing-method, K, seed, workload or measurement change was made.

Documented generator adapter exceptions: the byte-identical historical test_cell-only Liberty annotation provides missing native DFT metadata without changing functional/timing/C data; indexed native chain-0 ports are translated before STA initialization with endpoint geometry preserved; logical PACT test_si_0/test_so_0 map to physical test_si/test_so in the common adapter. FF membership/order is preserved by translation. Native K=2 lengths are 90/89, 106/105 and 267/267, preserving the maximum-chain workload cycle count. No K=1 native order was split and passed off as native K=2.

There is no fair **implemented** comparison yet, because the requested B2 binary has not been reproduced. No backend was substituted to manufacture a comparison.

## 3. How did P0 compare with OpenROAD?

Unknown. Pre-route scan-edge HPWL and saved P0 E/H4/H8 predictions are diagnostics only. There are no implemented B1/B2/B3 measurements in this campaign. A1–A5 are not assessable; historical PACT measurements have not been relabeled as external-baseline evidence.

## 4. What was wrong with P0?

The existing, hashed H8 root-cause result identifies fixed-depth spatial coverage omissions interacting with candidate-specific extracted ground capacitance. Of 37 problematic saved comparisons, 27 first recover ordering after omitted-net substitution and 10 after capacitance substitution. Coverage of represented measured E is about 83–84%, 72–74% and 69–70% for s5378/s9234/s15850. These are existing diagnosis results, not a repeated root-cause study. They justify the planned adaptive stateful coverage mechanism, while retaining ground-C limitations.

## 5. What changed in P1?

Nothing. P1 implementation has not started. Adaptive stateful cone expansion remains the sole authorized Stage-B mechanism once Stage A is successfully completed and sealed. P0 depth=3 and all optimizer semantics remain unchanged. An incomplete Stage-A seal does not open Stage B.

## 6. Did P1 improve prediction?

Not evaluated. P1 scores, reference/incremental correctness, coverage accounting and historical prediction deltas do not exist. No new expansion rule or threshold was fitted using measured labels.

## 7. Did P1 improve actual implemented outcomes?

Not evaluated. New routes: **0**. New extraction, simulation and ATPG runs: **0**. E/H4/H8 measurements and implemented deltas are blank, not zero. E retains units fF·transitions; H4/H8 retain fF·transitions per bin/cycle. These are C×N switching metrics, not measured power or Joules.

## 8. How does P1 compare with P0?

Unavailable for physical cost, E, H8, runtime, memory and architecture selection. The complete P0 retained archive is copied canonically (18 archive points across designs, plus 6 B0/B1 controls). Predicted-only selection retains seven distinct P0 points. Balanced minimax normalized regret is the method representative; physical and H8 extrema are also retained with SHA tie breaks and deduplication. Multiple PACT points versus single OSS solutions are explicit. Full archive points without imported implementation evidence are not treated as implemented frontier points.

## 9. How does P1 compare with OpenROAD?

Unavailable against B1, B2 and primary B3. B2 failed configuration on missing SWIG >=4.3; Tcl headers are also absent. CMake logged source-archive VCS warnings, while immutable main/submodule commits and hashes are independently recorded. This is a build-environment qualification failure, not proof of an algorithm defect or impossibility of building elsewhere. B3 source inspection passed; its full build was not attempted after the stop condition. Neither baseline is replaced by a Python implementation or a floating branch.

## 10. Does PACT add an external Pareto point?

Unknown. The required three-dimensional implemented space (routed full scan-path wire upper bound, measured E, measured H8) is not populated. No architecture is labeled dominated/nondominated, and no unique external frontier contribution is claimed. No weighted score or post-outcome tolerance was introduced.

## 11. What did adaptive expansion cost?

Not implemented, so P1 graph growth, throughput, rollback cost, runtime and peak RSS are unmeasured. runtime.csv retains the historical frozen P0 command times and RSS (397/203/53 mutation evaluations), actual native generator-command time/RSS and the failed build-configuration resource record. The failed B2 configuration took {block['configuration']['seconds']:.3f} seconds. These phases are not interchangeable search-performance measurements.

## 12. What remains unresolved?

Immediate gate: build the exact pinned B2/B3 revisions in an isolated toolchain and qualify canonical K=2 architectures before implementing/measuring them under the original backend. SWIG >=4.3 and Tcl development headers are demonstrably missing; subsequent build prerequisites remain unchecked. Original source archives and submodule data remain on D: for reproducible recovery. Failed native adapter attempts and their corrections are retained; successful qualified attempts have executed-source snapshots.

Fault coverage/detected-count source evidence is retained with hashes; candidate fault identity-set equivalence is not established. Glitch/delay-aware activity, distributed power density, IR-drop, larger designs, additional K/placements and technology generalization remain outside this controlled campaign. None was introduced as a fallback.

Validation executed: 10 new protocol tests and 6 existing candidate_stateful tests, **16 passed**; native actual DFT/FF/placement/capacity/SI/SO qualification for all three designs; canonical 24-architecture legality and exact inventory/coordinate/endpoint checks; 454 frozen source/input/historical-evidence bindings checked. No P1 test is claimed.

## 13. What is the next scientifically justified milestone?

**Provision an isolated reproducible build toolchain for the two pinned PRs, then complete and seal this unchanged Stage-A benchmark before P1.** Keep the captured revisions, protocol, canonical P0 selection, placement, workload and physical backend fixed.

Commit boundary: this incomplete Stage-A seal is committed separately. Stage-B/model and Stage-C commits do not exist. The exact seal SHA is recorded in the subsequent commit receipt and final response; it cannot be embedded in the same commit that creates it. Initial user README/planning/fault-identity/H8 evidence edits are preserved and excluded from the milestone commit. Final Git status is recorded in the commit receipt.
'''
    markdown(OUT / 'final/FINAL_REPORT.md', report)
    write(OUT / 'stage_a/git_status_before_seal.json', dict(status=git('status', '--short'),
                                                         pending_milestone_paths='results/pact_oss_benchmark, scripts/pact_oss_*.py, tests/unit/test_oss_benchmark.py',
                                                         initial_status=frozen['initial_git_status']))
    artifacts = {p.relative_to(ROOT).as_posix(): binding(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    sources = {p.relative_to(ROOT).as_posix(): binding(p) for p in sorted((ROOT / 'scripts').glob('pact_oss_*.py'))}
    sources['tests/unit/test_oss_benchmark.py'] = binding(ROOT / 'tests/unit/test_oss_benchmark.py')
    write(OUT / 'stage_a/evidence_manifest.json', dict(timestamp=status['timestamp'], repository_commit_at_execution=frozen['commit'],
                                                     classification=status['stage_a'], artifacts=artifacts, benchmark_sources=sources,
                                                     freeze=binding(OUT / 'stage_a/P0_FREEZE.json'),
                                                     self_hash_policy='Manifest excludes itself; later commit receipt is additive and separately Git-tracked'))
    print('SEALED', status['stage_a'], status['scientific'], 'tests', suite.attrib['tests'], 'new routes 0', flush=True)


if __name__ == '__main__':
    main()
