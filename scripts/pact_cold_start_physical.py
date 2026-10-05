#!/usr/bin/env python3
"""Qualify frozen prospective candidates through the common backend and FAN.

Only preselected architectures are implemented. Inputs are explicit bindings to
the unseen design's placed source, identity/workload, and qualified reference.
No historical P0, archive, per-design source mapping, or candidate reselection
is accessed. Earlier campaign evidence is read-only.
"""
import argparse
import gzip
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

from pact_generalization import ROOT, binding, now, read, sha, write
from pact_generalization_infrastructure import (
    FAN, FLOW, REPAIRED, execute, external_binding as _external_binding,
)
from pact_generalization_physical import LIB
from pact.scan.model import ScanArchitecture
from pact.integration.patterns import fan_workload, export_workload
from pact.integration.permutation import ScanPermutation
from pact.integration.replay import verify, write_recovered_fan
from pact.integration.qualification import simulate, compare_exports
from pact.test.pattern_parser import parse_fan_pat
from pact.phase0d.external import extract_structured_metrics

OUT = ROOT/'results/pact_cold_start_unseen_20261004'
RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cold_start_unseen_20261004')
STAGES = ('rewire', 'route', 'topology', 'functional_export', 'extraction', 'ATPG')


class ResourcePolicyError(RuntimeError):
    pass


def external_binding(path):
    return _external_binding(Path(path).resolve())


def bound_path(record):
    """Resolve and verify a data binding, including canonical repo URIs."""
    path = record['path']
    path = ROOT/path.removeprefix('repo://') if path.startswith('repo://') else Path(path)
    if not path.is_file() or sha(path) != record['sha256']:
        raise ValueError('Artifact binding mismatch: '+str(path))
    if 'bytes' in record and path.stat().st_size != record['bytes']:
        raise ValueError('Artifact byte size mismatch: '+str(path))
    return path


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError('Unsafe design/candidate artifact name')
    return value


def load_selection(selection_path, input_path=None):
    """Fail closed before routing; identity is entirely artifact-driven.

    Package fields follow ColdStartPACTInput: design, preparation binding,
    reference binding, and artifacts containing the selected architecture,
    identity/workload and complete reference fault export.
    """
    selection_path = Path(selection_path)
    selection = read(selection_path)
    design = safe_name(selection['design'])
    if input_path is None:
        pointer = selection.get('cold_start_input', selection.get('source_manifest'))
        if pointer is None:
            raise ValueError('Selection requires a bound cold_start_input package')
        input_path = bound_path(pointer)
    package = read(input_path)
    if package['design'] != design:
        raise ValueError('Input and selection design disagree')
    artifacts = package.get('artifacts', package)
    preparation = read(bound_path(package.get('preparation', artifacts.get('preparation'))))
    identity_binding = artifacts['identity_map']
    identity = read(bound_path(identity_binding))['records']
    reference = package.get('reference')
    if reference is not None and 'path' in reference:
        bound_path(reference)
        qualified = read(bound_path(artifacts['qualification']))
        if qualified['status'] != 'QUALIFIED':
            raise ValueError('Selected reference route is not qualified')
        reference = dict(status='QUALIFIED', method=package['reference_method'],
            architecture=artifacts['architecture'], architecture_hash=package['reference_architecture_hash'],
            provenance=artifacts['qualification'], correctness=dict(export=artifacts['reference_fault_export'],
                serial=artifacts['reference_serial']))
    elif reference is None:
        frozen = read(bound_path(package['reference_frozen']))
        reference = frozen.get('reference', frozen.get('selected_reference', frozen))
    if reference.get('status') != 'QUALIFIED':
        raise ValueError('External reference is not qualified')
    before = ScanArchitecture.from_json(bound_path(reference['architecture']))
    if before.sha256() != reference['architecture_hash']:
        raise ValueError('Reference architecture semantic hash mismatch')
    if len(before.chains) != 2 or any(len(c.cells) < 8 for c in before.chains):
        raise ValueError('Frozen K=2/minimum-eight-FF-per-chain contract failed')
    for name in ('source', 'patterns', 'source_placed_database', 'SDC', 'placed_def', 'config'):
        bound_path(preparation[name])
    for artifact_name, prep_name in (('patterns', 'patterns'), ('source_placed_database', 'source_placed_database'),
                                    ('SDC', 'SDC'), ('placement', 'placed_def')):
        if bound_path(artifacts[artifact_name]) != bound_path(preparation[prep_name]):
            raise ValueError('Cold-start/preparation source disagreement: '+artifact_name)
    bound_path(artifacts['source_netlist'])
    target = read(bound_path(reference['correctness']['export']))
    records = selection['records']
    if not 0 < len(records) <= 3:
        raise ValueError('Selection must freeze one to three candidates')
    names, hashes = set(), set()
    validated = []
    for row in records:
        name = safe_name(row['candidate'])
        after = ScanArchitecture.from_json(bound_path(row['architecture']))
        if row['architecture_hash'] != after.sha256():
            raise ValueError('Candidate architecture semantic hash mismatch')
        if row.get('reference_hash', row.get('parent_reference_hash')) != before.sha256():
            raise ValueError('Candidate does not bind frozen external reference')
        if name in names or after.sha256() in hashes:
            raise ValueError('Candidate names and architectures must be distinct')
        # Frozen chain identity, endpoint, FF-capacity, clock and placement gates.
        ScanPermutation(before, after)
        names.add(name)
        hashes.add(after.sha256())
        validated.append((row, after))
    return dict(design=design, selection=selection, selection_binding=external_binding(selection_path),
        package_binding=external_binding(input_path), artifacts=artifacts, preparation=preparation,
        identity_binding=identity_binding, identity=identity, reference=reference,
        before=before, target=target, validated=validated)


def functional_export(design, candidate, architecture, source, placement, routed, folder):
    root = RUN/'physical_gates'/design/candidate
    actual = root/design/candidate
    actual.mkdir(parents=True, exist_ok=True)
    shutil.copy2(routed, actual/'routed.odb')
    row = dict(design=design, role=candidate, architecture=architecture,
        source_placed_database=source, inputs=dict(placement=placement))
    write(root/'manifest.json', dict(rows=[row], library=external_binding(LIB),
        created_utc=now(), purpose='EXACT_CANDIDATE_FUNCTIONAL_AND_FF_PLACEMENT_GATES'), immutable=True)
    env = dict(os.environ, PACT_PHYSICAL_EFFECT_OUT=str(root))
    execution = execute(['/usr/bin/openroad', '-exit', '-python',
        ROOT/'scripts/pact_generalization_export.py', actual], folder/'functional_export', timeout=1200, env=env)
    topology = read(actual/'topology_verification.json')
    function = read(actual/'functional_verification.json')
    if topology['status'] != 'PASS' or function['status'] != 'PASS' or function['FF_placement'] != 'exact':
        raise ValueError('Frozen functional/topology/FF-placement gate failed')
    for name in ('topology_verification.json', 'functional_verification.json'):
        shutil.copy2(actual/name, folder/name)
    return dict(execution=execution, functional=function,
        outputs={name: external_binding(actual/name) for name in (
            'topology_verification.json', 'functional_verification.json', 'net_mapping.json')})


def route_candidate(context, row, architecture, folder):
    """Same placed source, port/rewiring policy, backend and RCX as references."""
    design, candidate = context['design'], row['candidate']
    if shutil.disk_usage(RUN).free < 20*1024**3:
        raise ResourcePolicyError('Registered minimum free scratch reserve is 20 GiB')
    prep = context['preparation']
    archpath = bound_path(row['architecture'])
    source = bound_path(prep['source_placed_database'])
    work = RUN/'orfs'
    variant_name = 'cold_start_'+candidate
    variant = work/f'results/nangate45/{design}/{variant_name}'
    logs = work/f'logs/nangate45/{design}/{variant_name}'
    variant.mkdir(parents=True, exist_ok=True)
    execute(['/usr/bin/openroad', '-python', '-no_init', '-exit', ROOT/'scripts/phase0c_rewire_odb.py',
        '--source', source, '--architecture', archpath, '--output', variant/'3_place.odb'],
        folder/'rewire', timeout=180)
    shutil.copy2(bound_path(prep['SDC']), variant/'3_place.sdc')
    routing = execute(['make', '-o', str(variant/'3_place.odb'), '-o', str(variant/'3_place.sdc'),
        f'DESIGN_CONFIG={bound_path(prep["config"])}', f'FLOW_VARIANT={variant_name}', f'WORK_HOME={work}',
        'GRT_SEED=11', 'NUM_CORES=2', 'OPENROAD_EXE=/usr/bin/openroad', 'YOSYS_EXE=/usr/bin/yosys', 'route'],
        folder/'route', FLOW, 1200)
    metrics = extract_structured_metrics(read(logs/'5_1_grt.json'), read(logs/'5_2_route.json'))
    proof = folder/'routed_verification.json'
    execute(['/usr/bin/openroad', '-python', '-no_init', '-exit', ROOT/'scripts/pact_generalization_routed.py',
        '--recognize-sized-scan', '--routed', variant/'5_2_route.odb', '--architecture', archpath,
        '--frozen-def', bound_path(prep['placed_def']), '--output', proof], folder/'topology', timeout=180)
    topology = read(proof)
    if topology['status'] != 'PASS':
        raise ValueError('Exact routed scan topology gate failed')
    if metrics['detailed_route_drc_errors'] != 0:
        raise ValueError('Detailed route DRC gate failed')
    if not all(math.isfinite(float(metrics[k])) and float(metrics[k]) >= 0 for k in ('setup_wns_ns', 'hold_wns_ns')):
        raise ValueError('Frozen nonnegative setup/hold WNS gate failed')
    exported = functional_export(design, candidate, row['architecture'], prep['source_placed_database'],
        prep['placed_def'], variant/'5_2_route.odb', folder)
    tcl = folder/'extract.tcl'
    tcl.write_text(f'''read_liberty {LIB}
read_db {variant}/5_2_route.odb
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {FLOW}/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {folder}/extracted.spef
exit
''')
    extraction = execute(['/usr/bin/openroad', '-no_init', '-exit', tcl], folder/'extraction', timeout=180)
    if not (folder/'extracted.spef').stat().st_size:
        raise ValueError('Empty SPEF')
    archive = folder/'5_2_route.odb.gz'
    with (variant/'5_2_route.odb').open('rb') as src, gzip.open(archive, 'wb') as dst:
        shutil.copyfileobj(src, dst)
    report = dict(status='PHYSICAL_GATES_PASS', design=design, candidate=candidate,
        architecture_sha256=architecture.sha256(), reference_hash=context['before'].sha256(),
        routed_scan_wirelength_um=topology['routed_full_scan_path_net_length_upper_bound_um'],
        DRC_errors=metrics['detailed_route_drc_errors'], structured_metrics=metrics,
        postroute_verification=topology, functional_verification=exported,
        route_wall_seconds=routing['wall_seconds'], extraction_wall_seconds=extraction['wall_seconds'],
        extraction=external_binding(folder/'extracted.spef'), archive=external_binding(archive),
        routed_odb_sha256=sha(variant/'5_2_route.odb'), selection=context['selection_binding'],
        source_placed_database=prep['source_placed_database'], created_utc=now(),
        gates=dict(rewire='PASS', topology='PASS', FF_inventory='PASS', FF_placement='PASS',
            functional_connections='PASS', routing='PASS', extraction='PASS', timing='PASS', DRC='PASS'),
        activity_status='PENDING', scientific_method_change=False)
    write(folder/'route_result.json', report, immutable=True)
    return report


def serial_and_fan(context, row, after, folder):
    before, prep = context['before'], context['preparation']
    fan, states = fan_workload(bound_path(prep['patterns']), context['identity'], before)
    permutation = ScanPermutation(before, after)
    permutation.to_json(folder/'permutation.json')
    original, remapped = export_workload(permutation, states)
    write(folder/'original_serial_workload.json', original, immutable=True)
    write(folder/'patterns_remapped.json', remapped, immutable=True)
    replay, recovered = verify(before, after, original, remapped, states)
    write(folder/'serial_replay.json', replay, immutable=True)
    if replay['status'] != 'PASS':
        raise ValueError('Independent serial replay failed')
    recovered_path = folder/'patterns_recovered.pat'
    write_recovered_fan(recovered_path, fan, context['identity'], recovered)
    if parse_fan_pat(recovered_path) != fan:
        raise ValueError('Reconstructed full FAN workload changed')
    exported = simulate(REPAIRED, FAN/'techlib/mod_nangate45.mdt', bound_path(prep['source']),
        recovered_path, folder/'fan', timeout=900)
    compared = compare_exports(context['target'], exported)
    write(folder/'test_correctness.json', compared, immutable=True)
    if compared['status'] != 'PASS':
        raise ValueError('Complete collapsed FAN target/detected identity/weight gate failed')
    result = dict(status='ATPG_GATES_PASS', design=context['design'], candidate=row['candidate'],
        architecture_hash=after.sha256(), reference_hash=before.sha256(),
        serial=external_binding(folder/'serial_replay.json'), faults=external_binding(folder/'test_correctness.json'),
        export=external_binding(folder/'fan/export.json'), statistics=exported['statistics'],
        selection=context['selection_binding'], workload=external_binding(folder/'patterns_remapped.json'),
        permutation=external_binding(folder/'permutation.json'), created_utc=now(),
        identity_scope=exported['identity_scope'], uncollapsed_member_identity_equivalence='NOT_ENUMERATED')
    write(folder/'atpg_result.json', result, immutable=True)
    return result


def measurement_row(context, row, route, correctness, folder):
    prep = context['preparation']
    source_netlist = context['artifacts'].get('source_netlist')
    if source_netlist is None:
        raise ValueError('Cold-start package requires an explicit source_netlist binding')
    bound_path(source_netlist)
    result = dict(design=context['design'], role=row['candidate'], architecture=external_binding(bound_path(row['architecture'])),
        architecture_sha256=row['architecture_hash'], routed_archive=route['archive'],
        source_placed_database=external_binding(bound_path(prep['source_placed_database'])),
        source_netlist=external_binding(bound_path(source_netlist)),
        SDC=external_binding(bound_path(prep['SDC'])), qualification=external_binding(folder/'route_result.json'),
        prior_integration=correctness['serial'], workload=correctness['workload'],
        inputs=dict(patterns=external_binding(bound_path(prep['patterns'])),
            identity_map=external_binding(bound_path(context['identity_binding'])),
            placement=external_binding(bound_path(prep['placed_def']))),
        selection=context['selection_binding'], reference_hash=context['before'].sha256(),
        chain_lengths=[len(c.cells) for c in ScanArchitecture.from_json(bound_path(row['architecture'])).chains])
    write(folder/'measurement_row.json', result, immutable=True)
    return result


def copy_compact(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.glob('*.json'):
        shutil.copy2(path, destination/path.name)
    for stage in STAGES:
        if (source/stage/'execution.json').exists():
            target = destination/stage
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source/stage/'execution.json', target/'execution.json')
    if (source/'fan/execution.json').exists():
        target = destination/'fan'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/'fan/execution.json', target/'execution.json')


def qualify(selection_path, input_path=None, *, stop_on_correctness_failure=False):
    context = load_selection(selection_path, input_path)
    design = context['design']
    write(OUT/f'physical/{design}/selection_snapshot.json', dict(
        created_utc=now(), selection=context['selection_binding'], input=context['package_binding'],
        records=[dict(candidate=r['candidate'], architecture_hash=a.sha256(), architecture=r['architecture'])
            for r, a in context['validated']], all_candidates_frozen_before_any_candidate_routing=True,
        executed_sources={name: binding(ROOT/name) for name in (
            'scripts/pact_cold_start_physical.py', 'scripts/phase0c_rewire_odb.py',
            'scripts/pact_generalization_routed.py', 'scripts/pact_generalization_scan_masters.py',
            'scripts/pact_generalization_export.py', 'scripts/physical_effect_export.py',
            'src/pact/integration/permutation.py', 'src/pact/integration/patterns.py',
            'src/pact/integration/replay.py', 'src/pact/integration/qualification.py')},
        tools=dict(OpenROAD=external_binding('/usr/bin/openroad'), FAN=external_binding(REPAIRED)),
        technology=dict(library=external_binding(LIB),
            extraction_rules=external_binding(FLOW/'platforms/nangate45/rcx_patterns.rules'),
            FAN_library=external_binding(FAN/'techlib/mod_nangate45.mdt'))), immutable=True)
    physical, atpg, final = [], [], []
    for row, after in context['validated']:
        candidate = row['candidate']
        pf = RUN/'physical'/design/candidate
        af = RUN/'atpg'/design/candidate
        pf.mkdir(parents=True, exist_ok=True)
        af.mkdir(parents=True, exist_ok=True)
        result = dict(design=design, candidate=candidate, architecture_hash=after.sha256(),
            selection=context['selection_binding'], input=context['package_binding'], created_utc=now(), status='PENDING')
        result['started_utc'] = result['created_utc']
        stage = 'PACT_PHYSICAL_FAILURE'
        try:
            routed = route_candidate(context, row, after, pf)
            physical.append(routed)
            stage = 'PACT_TEST_CORRECTNESS_FAILURE'
            correctness = serial_and_fan(context, row, after, af)
            atpg.append(correctness)
            measurement = measurement_row(context, row, routed, correctness, pf)
            result.update(status='PHYSICAL_AND_ATPG_PASS_ACTIVITY_PENDING', physical=external_binding(pf/'route_result.json'),
                atpg=external_binding(af/'atpg_result.json'), measurement_row=external_binding(pf/'measurement_row.json'))
        except Exception as error:
            # Frozen FAN simulate() raises before writing its receipt on a
            # timeout; retain its captured bytes and the observed limit here.
            if isinstance(error, subprocess.TimeoutExpired):
                fan_folder = af/'fan'
                fan_folder.mkdir(parents=True, exist_ok=True)
                for name, content in (('stdout.txt', error.stdout), ('stderr.txt', error.stderr)):
                    data = content or b''
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    (fan_folder/name).write_bytes(data)
                write(fan_folder/'execution.json', dict(command=list(map(str, error.cmd)),
                    exit_code=None, timed_out=True, timeout_seconds=error.timeout,
                    timestamp_utc=now(), stdout=external_binding(fan_folder/'stdout.txt'),
                    stderr=external_binding(fan_folder/'stderr.txt')), immutable=True)
            executions = {}
            for physical_stage in STAGES:
                receipt = pf/physical_stage/'execution.json'
                if receipt.exists():
                    executions[physical_stage] = read(receipt)
            fan_execution = af/'fan/execution.json'
            if fan_execution.exists():
                executions['FAN'] = read(fan_execution)
            limited = isinstance(error, (ResourcePolicyError, subprocess.TimeoutExpired)) or any(
                r.get('timed_out') or r.get('exit_code') in (-9, 137) for r in executions.values())
            result.update(status=stage, failure_class='RESOURCE_LIMIT' if limited else stage, completed_utc=now(),
                executions=executions, error=str(error), traceback=traceback.format_exc())
            result['scientific_stop'] = bool(stop_on_correctness_failure and not limited
                and str(error) not in ('Detailed route DRC gate failed',
                    'Frozen nonnegative setup/hold WNS gate failed'))
            write(OUT/f'failures/{design}_{candidate}_qualification.json', result, immutable=True)
            if not any(r['candidate']==candidate for r in physical):
                physical.append(dict(result))
            elif not any(r['candidate']==candidate for r in atpg):
                atpg.append(dict(result))
        result.setdefault('completed_utc', now())
        write(pf/'qualification_pending_activity.json', result, immutable=True)
        copy_compact(pf, OUT/f'physical/{design}/{candidate}')
        copy_compact(af, OUT/f'atpg/{design}/{candidate}')
        final.append(result)
        print('CANDIDATE_QUALIFICATION', design, candidate, result['status'], flush=True)
        if result.get('scientific_stop'):
            break
    common = dict(design=design, selection=context['selection_binding'], input=context['package_binding'], created_utc=now())
    write(OUT/f'physical/{design}/physical_results.json', dict(common, records=physical), immutable=True)
    write(OUT/f'atpg/{design}/atpg_results.json', dict(common, records=atpg), immutable=True)
    write(OUT/f'physical/{design}/qualification_pending_activity.json', dict(common, records=final), immutable=True)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    args = parser.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps', PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1', PATH='/usr/bin:'+os.environ['PATH'])
    if sha('/usr/bin/openroad') != read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json')['implementation_binary_sha256']:
        raise ValueError('Frozen implementation OpenROAD changed')
    if sha(REPAIRED) != read(ROOT/'results/pact_end_to_end_20261004/upstream_repair/qualification.json')['repaired_executable_sha256']:
        raise ValueError('Qualified FAN executable changed')
    qualify(args.selection, args.input)


if __name__ == '__main__':
    main()
