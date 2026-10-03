#!/usr/bin/env python3
"""Seal a source-blocked recovery without crossing the external-build gate."""
import csv
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import tarfile
import xml.etree.ElementTree as ET

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, git, read, verify, write
from pact_oss_recovery import RECOVERY, DATA, MOUNT, require_prerequisites
from pact_oss_canonicalize import csv_write, validate_architecture
from pact.scan.model import ScanArchitecture

STAGE = RECOVERY / 'stage_a'
B2 = 'B2_openroad_10176'
B3 = 'B3_openroad_10666'


def child_rss(path):
    if not path.exists():
        return None
    match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', path.read_text())
    return int(match[1]) if match else None


def checked_binding(item):
    actual = binding(item['path'])
    if actual['sha256'] != item['sha256']:
        raise ValueError('Evidence changed: ' + item['path'])
    return actual


def check_build_evidence():
    from pact_oss_storage import ensure
    ensure()
    require_prerequisites()
    verify()
    builds = {}
    for name in (B2, B3):
        folder = RECOVERY / 'baselines' / name
        builds[name] = read(folder / 'build_result.json')
        pin = read(OUT / 'baselines' / name / 'source_pin.json')
        if builds[name]['commit'] != pin['commit']:
            raise ValueError('External source revision changed')
        checked_binding(builds[name]['build'])
        resolution = read(folder / 'cmake_resolved_dependencies.json')
        if resolution['status'] != 'PASS':
            raise ValueError('Actual CMake prerequisite resolution did not pass')
        checked_binding(resolution['actual_cmake_cache'])
        sources = read(folder / 'source_manifest.json')
        if sources['source_modifications']:
            raise ValueError('Pinned PR source was modified')
        for relative, expected in sources['pinned_source_blobs_checked'].items():
            path = MOUNT / name / 'source' / relative
            actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
            if actual != expected:
                raise ValueError('Pinned source changed: ' + name + '/' + relative)
    if builds[B2]['status'] != 'BUILT' or builds[B3]['status'] != 'COMPILATION_FAILED' or builds[B3]['binary'] is not None:
        raise ValueError('Observed source-blocked state is not present')
    checked_binding(builds[B2]['binary'])
    qualification = read(RECOVERY / 'baselines' / B2 / 'qualification.json')
    if qualification['status'] != 'PASS' or set(qualification['designs']) != set(DESIGNS):
        raise ValueError('B2 does not have all three canonical qualifications')
    if qualification['binary_sha256'] != builds[B2]['binary_sha256']:
        raise ValueError('B2 qualification used a different executable')
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    for design, item in qualification['designs'].items():
        checked_binding(item['proof'])
        checked_binding(item['canonical'])
        architecture = ScanArchitecture.from_json(Path(item['canonical']['path']))
        reference = ScanArchitecture.from_json(Path(frozen['frozen_inputs'][design]['B0_reference']['path']))
        validate_architecture(architecture, reference)
        if architecture.sha256() != item['architecture_hash']:
            raise ValueError('B2 canonical architecture identity changed')
    return builds, qualification


def diagnosis():
    folder = RECOVERY / 'baselines' / B3
    source = MOUNT / B3 / 'source'
    log = (folder / 'build.log').read_text()
    errors = [line for line in log.splitlines() if 'error:' in line]
    if len(errors) != 2 or not all(name in log for name in ('getLibertyScanIn', 'getLibertyScanOut')):
        raise ValueError('Observed diagnostics differ from the audited source defect')
    files = ('src/dft/src/cells/OneBitScanCell.cpp', 'src/dft/src/cells/OneBitScanCell.hh',
             'src/dft/src/cells/ScanCell.hh', 'src/dbSta/include/db_sta/dbNetwork.hh')
    archive = read(folder / 'build_sources.json')['main_archive']
    checked_binding(archive)
    # Independently compare the affected translation unit and declaration headers
    # with the exact immutable main archive, including headers outside the DFT pin.
    archive_matches = {}
    with tarfile.open(archive['path']) as stream:
        for member in stream:
            relative = '/'.join(Path(member.name).parts[1:])
            if relative in files:
                archived = stream.extractfile(member).read()
                if hashlib.sha256(archived).hexdigest() != binding(source / relative)['sha256']:
                    raise ValueError('Diagnostic source differs from the exact archive')
                archive_matches[relative] = binding(source / relative)
    if set(archive_matches) != set(files):
        raise ValueError('Diagnostic archive headers were not all verified')
    copies = {}
    for relative in files:
        target = folder / 'diagnostics' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
        copies[relative] = binding(target)
    for filename in ('flags.make', 'build.make'):
        path = MOUNT / B3 / 'build/src/dft/src/cells/CMakeFiles/dft_cells_lib.dir' / filename
        target = folder / 'diagnostics' / filename
        shutil.copy2(path, target)
        copies[filename] = binding(target)
    unit = (source / files[0]).read_text().splitlines()
    if 'findITerm(getLibertyScanIn(test_cell_))' not in unit[105] or 'findITerm(getLibertyScanOut(test_cell_))' not in unit[110]:
        raise ValueError('Pinned failing call sites differ')
    header = (source / files[3]).read_text().splitlines()
    if 'getLibertyScanIn' not in header[435] or 'getLibertyScanOut' not in header[436]:
        raise ValueError('Pinned member declaration locations differ')
    record = dict(status='SOURCE_PATCH_REQUIRED_STOPPED', source_commit=read(folder / 'build_result.json')['commit'],
        build_exit_code=read(folder / 'build.execution.json')['returncode'], compiler_errors=errors,
        source_locations=[dict(path=files[0], line=106, call=unit[105].strip()), dict(path=files[0], line=111, call=unit[110].strip())],
        member_declarations=dict(path=files[3], lines=[436, 437], receiver='sta::dbNetwork / db_network_'),
        diagnosis='The two location accessors call dbNetwork member APIs as unqualified functions; those functions are neither OneBitScanCell nor ScanCell members. The same translation unit uses db_network_-> correctly elsewhere.',
        required_change='A PR source change supplying the db_network_ receiver at both failing calls, or equivalent source injection. Neither is applied.',
        missing_package=False, source_patch_applied=False, build_retry_after_source_defect=False,
        compiled_command_qualification='UNAVAILABLE_NO_EXECUTABLE', architecture_generation='NOT_STARTED',
        optimizer_static_library_compiled=True, partial_library_is_not_baseline_reproduction=True,
        exact_archive_verified_sources=archive_matches, diagnostic_snapshots=copies,
        build_log=binding(folder / 'build.log'), build_execution=binding(folder / 'build.execution.json'))
    write(folder / 'compilation_blocker.json', record)
    write(folder / 'qualification.json', dict(status='NOT_GENERATED_BUILD_FAILURE', source_commit=record['source_commit'],
        binary_sha256=None, designs={d:dict(status='NOT_GENERATED_SOURCE_PATCH_STOP', chain_lengths=None) for d in DESIGNS},
        compiled_behavior_verified=False, blocker=binding(folder / 'compilation_blocker.json')))
    return record


def unit_tests():
    files = ('protocol_tests.xml', 'pareto_tests.xml', 'result_join_tests.xml', 'result_join_tests_final.xml',
             'scientific_question_tests.xml', 'scientific_question_tests_final.xml')
    records, distinct = {}, set()
    for filename in files:
        root = ET.parse(RECOVERY / filename).getroot()
        suite = root.find('testsuite')
        records[filename] = {key:int(suite.attrib.get(key, '0')) for key in ('tests', 'failures', 'errors', 'skipped')}
        if records[filename]['failures'] or records[filename]['errors'] or records[filename]['skipped']:
            raise ValueError('Relevant unit suite did not pass completely')
        for case in root.iter('testcase'):
            distinct.add((case.attrib.get('classname'), case.attrib['name']))
    return dict(suites=records, distinct_passed=len(distinct), distinct_failed=0,
                executions=sum(row['tests'] for row in records.values()), unrelated_suites=0)


def seal():
    builds, qualification = check_build_evidence()
    if (DATA / 'stage_a').exists() and any((DATA / 'stage_a').rglob('*')):
        raise ValueError('Physical work exists beyond the stopped build gate')
    from pact_oss_verify import audit as original_audit
    original_audit()
    blocker = diagnosis()
    tests = unit_tests()
    original = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    known = original.copy()
    for design, item in qualification['designs'].items():
        known.append(dict(design=design, method='B2', architecture_hash=item['architecture_hash'],
            architecture_path=item['canonical']['path'], roles='single_solution', selected='True', representative='True',
            status='CANONICAL_QUALIFIED', FF_count=sum(item['chain_lengths']), K=2, predicted_E='', predicted_H8='', predicted_H4=''))
    csv_write(STAGE / 'architecture_index.csv', list(known[0]), known)
    ff_rows = list(csv.DictReader((OUT / 'stage_a/architecture_manifest.csv').open()))
    for row in csv.DictReader((RECOVERY / 'baselines' / B2 / 'architecture_manifest.csv').open()):
        ff_rows.append(dict(row, roles='single_solution', selected='True', representative='True'))
    csv_write(STAGE / 'architecture_manifest.csv', list(ff_rows[0]), ff_rows)
    metrics = []
    for row in known:
        if row['selected'] == 'True':
            metrics.append(dict(design=row['design'], method=row['method'], architecture_hash=row['architecture_hash'],
                roles=row['roles'], representative=row['representative'],
                status='NOT_IMPORTED_OR_PERFORMED_AFTER_B3_SOURCE_STOP', routed_scan_path_cost_um=None,
                measured_E=None, measured_H4=None, measured_H8=None, Pareto='UNASSESSABLE'))
    for design in DESIGNS:
        metrics.append(dict(design=design, method='B3', architecture_hash=None, roles='single_solution', representative='True',
            status='NO_EXECUTABLE_OR_ARCHITECTURE_SOURCE_PATCH_STOP', routed_scan_path_cost_um=None,
            measured_E=None, measured_H4=None, measured_H8=None, Pareto='UNASSESSABLE'))
    csv_write(STAGE / 'implemented_metrics.csv', list(metrics[0]), metrics)
    csv_write(STAGE / 'method_comparison.csv', list(metrics[0]), [r for r in metrics if r['representative']=='True'])
    csv_write(STAGE / 'pareto_front.csv', list(metrics[0]), metrics)
    # Retain the prior pre-route diagnostics, explicitly identifying their scope.
    shutil.copy2(OUT / 'stage_a/pre_route_metrics.csv', STAGE / 'pre_route_metrics.csv')
    runtime = []
    for name in (B2, B3):
        folder = RECOVERY / 'baselines' / name
        for label in (('configure', 'build', 'build_resume1') if name == B2 else ('configure', 'build')):
            receipt = read(folder / (label + '.execution.json'))
            runtime.append(dict(method=name[:2], design='all', stage=label, elapsed_seconds=receipt['elapsed_seconds'],
                exit_code=receipt['returncode'], peak_RSS_kbytes=child_rss(folder / (label + '.container.resource.txt')),
                RSS_scope='Maximum child process, not summed concurrent RSS; unknown if no inner time receipt',
                source=str(folder / (label + '.execution.json'))))
    for design in DESIGNS:
        receipt = read(RECOVERY / 'baselines' / B2 / design / 'generate.execution.json')
        runtime.append(dict(method='B2', design=design, stage='architecture_generation', elapsed_seconds=receipt['elapsed_seconds'],
            exit_code=receipt['returncode'], peak_RSS_kbytes=child_rss(RECOVERY / 'baselines' / B2 / design / 'generator.resource.txt'),
            RSS_scope='Maximum child process, not summed concurrent RSS; unknown if no inner time receipt',
            source=str(RECOVERY / 'baselines' / B2 / design / 'generate.execution.json')))
    csv_write(STAGE / 'runtime.csv', list(runtime[0]), runtime)
    status = dict(timestamp=datetime.now(timezone.utc).isoformat(), stage_a='PACT_STAGE_A_INCOMPLETE',
        scientific='PACT_BENCHMARK_INCONCLUSIVE', OSS_benchmark_complete=False,
        stop_condition='Exact pinned B3 requires a PR source API repair to compile; user forbids source patches and requires stopping.',
        blocker=binding(RECOVERY / 'baselines' / B3 / 'compilation_blocker.json'),
        B2='BUILT_AND_ALL_THREE_CANONICAL_ARCHITECTURES_QUALIFIED', B3='COMPILATION_FAILED_SOURCE_PATCH_REQUIRED',
        B3_binary_sha256=None, new_routes=0, new_extractions=0, new_simulations=0, new_ATPG_runs=0,
        new_placement_runs=0, new_rootcause_runs=0, new_architecture_generations=3,
        P0_commit=read(OUT / 'stage_a/P0_FREEZE.json')['commit'], P0_model_changed=False,
        P0_search_rerun=False, P0_selection_changed=False, B1_regenerated=False,
        qualified_canonical_architectures=len(known), ordered_FF_records=len(ff_rows),
        selected_method_records=len(metrics), pre_route_scope='Original 24-architecture diagnostics copied without rescoring; B2 metrics not evaluated after B3 source stop.',
        tests=tests, original_integrity=dict(frozen_bindings=454, sealed_bindings=122, canonical_architectures=24, status='PASS'),
        Stage_B='NOT_STARTED_STAGE_A_STOP_CONDITION', Stage_C='NOT_STARTED_STAGE_A_STOP_CONDITION',
        Stage_B_scientific_prerequisite_satisfied=False, Stage_B_execution_authorized_by_this_task=False,
        fixed_backend=binding('/usr/bin/openroad'), original_incomplete_seal=binding(OUT / 'stage_a/evidence_manifest.json'),
        original_P0_selection=binding(OUT / 'stage_a/P0_SELECTION.json'),
        Git_HEAD_before_commit=git('rev-parse', 'HEAD'), Git_status_before_commit=git('status', '--short'))
    write(STAGE / 'status.json', status)
    lengths = '\n'.join('| '+d+' | '+ '/'.join(map(str,qualification['designs'][d]['chain_lengths']))+' | PASS | unavailable |' for d in DESIGNS)
    report = f'''# Stage-A recovery stopped on exact B3 source defect

**PACT_STAGE_A_INCOMPLETE**. Scientific classification: **PACT_BENCHMARK_INCONCLUSIVE**.

B2 was reproduced and qualified. Exact B3 compilation failed because its two scan-pin location accessors call `sta::dbNetwork` member APIs without an object receiver. The user's explicit stop rule applies to any PR source change needed to compile. No PR source change, source-injecting compiler workaround, subsequent build retry or downstream experiment was performed.

## Builds and isolated environment

| Method | Exact source revision | Build status | Binary SHA256 |
| --- | --- | --- | --- |
| B2 | `{builds[B2]['commit']}` | BUILT | `{builds[B2]['binary_sha256']}` |
| B3 | `{builds[B3]['commit']}` | COMPILATION_FAILED | unavailable; no executable |

B2 binary: `{builds[B2]['binary']['path']}`. Immutable image: `openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`, Ubuntu 22.04.5 amd64. Dedicated D:-backed ext4 build prefixes; repository read-only in network-disabled containers. GCC/G++ 11.4.0 and CMake 3.31.9. Both actual CMakeCache files resolve SWIG 4.3.0 at `/usr/local/bin/swig`, data `/usr/local/share/swig/4.3.0`; Tcl header `/usr/include/tcl8.6/tcl.h`, include `/usr/include/tcl8.6`, library `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`, and interpreter `/usr/bin/tclsh`. Header and linked-library runtime both 8.6.12, independently compiled/linked/loaded before B2 configuration. Exact path/hash/version receipts are in each baseline's `cmake_resolved_dependencies.json` and `toolchain/qualification.json`. A working interpreter alone was not accepted. See [dependency audit](../protocol/build_environment_audit.md).

B2's successful resumed build took 5213.271 seconds, after an intentionally interrupted 1005.735-second storage attempt; maximum child RSS was 2,096,392 kbytes. B3 configure passed in 16.209 seconds; compilation failed after 4178.934 seconds, exit 2, maximum child RSS 2,095,732 kbytes. Complete commands, logs, resource receipts, exact submodule commits and archive hashes remain preserved. The qualified WSL OpenROAD/ORFS/PACT environment was not replaced. Storage relocation and nonfatal Boost/BZip2/GPU-banner warnings are documented in the audit.

## Exact blocker

`src/dft/src/cells/OneBitScanCell.cpp:106`: `getLibertyScanIn` undeclared. Line 111: `getLibertyScanOut` undeclared. `src/dbSta/include/db_sta/dbNetwork.hh:436–437` declares these as members; the header is already included. The same translation unit correctly calls these APIs through `db_network_->` elsewhere. The affected sources and headers match the exact pinned archive. These are source name-lookup errors, with no missing-package remedy. The optimizer static library compiled, but that does not reproduce an executable or qualify behavior. Full diagnostic snapshots and compiler rule/flags are in `baselines/{B3}/diagnostics/`; structured evidence is in `compilation_blocker.json`.

## Architecture qualification

B2's compiled Tcl command probe and linked optimizer symbols passed. Actual `execute_dft_plan; scan_opt` runs use native NN and endpoint-inclusive FF-origin Manhattan 2-Opt, maximum 30 iterations. All three outputs preserve exact expected FFs, K=2, domains, capacity, SI/SO legality, canonical assignment/order and endpoint geometry. B3 compiled-command verification and generation remain unavailable.

| Design | B2 chain lengths | B2 qualification | B3 chain lengths / qualification |
| --- | --- | --- | --- |
{lengths}

Full B2 architecture hashes and 924 ordered FF identities are in `baselines/{B2}/qualification.json` and `architecture_manifest.csv`. The partial Stage-A inventory records 27 qualified canonical architectures and 8,252 FF rows: the original 24 plus three B2 outputs. B0/B1 and the complete P0 archive and seven predeclared selected P0 identities remain unchanged. B1 was not regenerated. P0 remains `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3. No prediction rescoring or selection change occurred.

## Physical/activity outcomes and scientific questions

New physical implementations: **0**. New routing/extraction/simulation/ATPG/placement/root-cause runs: **0**. The common backend remains `/usr/bin/openroad`, revision `08f67ee5ecd14db5a42be8c610bbfd1ccf079299`, version `26Q2-1164-g08f67ee5ec`, SHA256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`; ORFS remains `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`. Existing physical evidence was not imported past the mandatory B3 gate. New physical qualification outcomes are unavailable.

| Design | Methods | Routed cost (µm) | E (fF·transitions) | H4/H8 (fF·transitions per bin/cycle) |
| --- | --- | --- | --- | --- |
| s5378 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |
| s9234 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |
| s15850 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |

All 19 selected method records retain unknown measurements in `stage_a/implemented_metrics.csv`; representative and Pareto tables explicitly mark them unassessable. Pre-route metrics retain only the original diagnostics, with their source scope recorded in status. P0 versus B0/B1/B2/B3, external Pareto membership and A1–A5 are **unassessed**. No P0 external advantage/disadvantage, B3 dominance, wire/activity relationship or A5 selection-miss conclusion can be drawn from this incomplete campaign.

## Validation, evidence and Git

Relevant unit tests: **{tests['distinct_passed']} distinct passed, 0 failed** ({tests['executions']} executions including reruns; no unrelated suites). The tests cover the existing protocol and candidate_stateful model, actual build-resolution parsing, exact Pareto dominance, missing/failed-measurement handling and scientific comparison scope. Separate integrations: three saved-B1 endpoint checks and three actual B2 architecture qualifications passed. Independent SWIG/Tcl C and generated-module compile/link/load probes passed. B3 has zero architecture qualifications. Original integrity checks passed for 454 frozen bindings, 122 sealed bindings and 24 canonical architectures. Failed prerequisite-package and endpoint-adapter attempts remain preserved alongside their corrected successful proofs.

The new evidence manifest binds compact artifacts, executed source snapshots, exact source archives, B2 binary and raw generator/prerequisite files; the previous incomplete seal remains untouched. Prepared downstream helpers were not executed and cannot bypass the qualification gate. A separate diagnostic/recovery commit is permitted because this attempt adds durable reproducibility infrastructure. Its SHA and final Git status will be recorded in a commit receipt. Existing user README/planning/fault-identity/H8 edits are excluded.

Stage B's scientific prerequisite is **not satisfied**. Stage B/P1 and Stage C remain unstarted. The remaining blocker is the exact pinned B3 source defect. Continuing requires a separately authorized change to the source-repair/pinning constraint, with explicit provenance and scientific review; this recovery stops here.
'''
    (RECOVERY / 'FINAL_REPORT.md').write_text(report)
    (STAGE / 'README.md').write_text('# Source-blocked recovery seal\n\n'
        'Classification: `PACT_STAGE_A_INCOMPLETE`; scientific: `PACT_BENCHMARK_INCONCLUSIVE`. '
        'See [report](../FINAL_REPORT.md). The exact B3 source requires a forbidden compile repair. '
        'Architecture inventory is partial (27 qualified architectures); B3 is absent. '
        'All physical/activity outcomes remain unknown. No Stage-B/P1 work occurred.\n')
    external = {'B2_binary': builds[B2]['binary']}
    for name, archive_file in ((B2, OUT / 'baselines' / B2 / 'build_sources.json'),
                               (B3, RECOVERY / 'baselines' / B3 / 'build_sources.json')):
        archives = read(archive_file)
        for item in [archives['main_archive']] + [row['archive'] for row in archives['submodules']]:
            external[name + '/archive/' + Path(item['path']).name] = checked_binding(item)
    for path in sorted(DATA.rglob('*')):
        if path.is_file() and path.name != 'build-storage.ext4':
            external['recovery_raw/' + str(path.relative_to(DATA))] = binding(path)
    for name in (B2, B3):
        source = read(RECOVERY / 'baselines' / name / 'source_manifest.json')
        for relative in source['pinned_source_blobs_checked']:
            path = MOUNT / name / 'source' / relative
            if not path.is_symlink():
                external[name + '/source/' + relative] = binding(path)
    external.update({'B3_diagnostic/' + key: item for key,item in blocker['exact_archive_verified_sources'].items()})
    artifacts = {str(path.relative_to(RECOVERY)):binding(path) for path in sorted(RECOVERY.rglob('*')) if path.is_file()}
    artifacts['../protocol/build_environment_audit.md'] = binding(OUT / 'protocol/build_environment_audit.md')
    sources = {str(path.relative_to(ROOT)):binding(path) for path in sorted((ROOT / 'scripts').glob('pact_oss_*.py'))}
    sources.update({str(path.relative_to(ROOT)):binding(path) for path in sorted((ROOT / 'tests/unit').glob('test_oss_*.py'))})
    write(STAGE / 'evidence_manifest.json', dict(timestamp=datetime.now(timezone.utc).isoformat(), status='SEALED_INCOMPLETE',
        artifacts=artifacts, benchmark_sources=sources, external_artifacts=external,
        original_incomplete_seal=status['original_incomplete_seal'], classification=status['stage_a'],
        Stage_B=status['Stage_B'], storage='Authorized D: data; file-level bindings exclude the mutable build filesystem image'))
    print('RECOVERY_SOURCE_BLOCK_SEALED', len(artifacts), len(sources), len(external), tests, flush=True)


if __name__ == '__main__':
    seal()
