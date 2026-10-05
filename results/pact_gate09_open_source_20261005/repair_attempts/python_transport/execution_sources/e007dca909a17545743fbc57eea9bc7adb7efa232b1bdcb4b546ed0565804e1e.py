#!/usr/bin/env python3
"""Gate-09 campaign adapters; frozen scientific modules are never edited.

One registered architecture per heuristic; frozen role selection for PACT.
Only prospective paths and the already preregistered 900s budget are adapted.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src'), str(ROOT / '.optimizer-deps')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
import pact_gate09_measure as measure
from pact_experiment_receipts import atomic_write


def stamp():
    return datetime.now(timezone.utc).isoformat()


def require_exact_reference(meta, design):
    selected = admission.read(meta / f'baselines/{design}_selected.json')
    method = selected['method']
    result_path = meta / f'activity/GATE09_PRIMARY/{design}/{method}/normal/result.json'
    result = admission.read(result_path)
    worker = admission.read(meta / f'workers/{design}/measure_run_{method}.lifecycle.json')
    if (worker['state'] != 'COMPLETED' or worker['status'] != 'QUALIFIED' or
            admission.verify(worker['receipt'])['status'] != 'PASS' or
            result['status'] != 'QUALIFIED' or not result['complete'] or
            result['architecture_sha256'] != selected['architecture_hash']):
        raise ValueError('Complete qualified exact external reference required before Gate-09 optimization')
    folder = admission.resolve(result['output_folder'])
    cross = admission.read(folder / 'FF_transition_crosscheck.json')
    summary = admission.read(folder / 'activity_summary.json')
    if cross['status'] != 'PASS' or not summary['activity_trace']['complete']:
        raise ValueError('Complete independent FF replay and exact trace required')
    for value in (result['manifest'], selected['architecture'], selected['provenance']):
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Qualified external reference binding changed')
    return selected, result_path, folder


def freeze(meta, raw, design, protocol):
    selected, exact_path, folder = require_exact_reference(meta, design)
    # These are the versioned configurations, not reconstructed defaults.
    from pact.optimizer.stage_b import Config
    import numpy, scipy, numba, llvmlite
    configs = protocol['fixed_method']['configurations']
    for c in configs:
        expected = asdict(Config(epsilon=c['epsilon'], seconds=900,
            max_evaluations=20000, stagnation_attempts=2000))
        expected['weights'] = list(expected['weights'])
        if expected != c:
            raise ValueError('Frozen solver defaults do not equal the preregistered Gate-09 configuration')
    gate_path = meta / f'admission/{design}_complete.json'
    atomic_write(gate_path, dict(schema='pact_gate09_reference_admission_v1', design=design,
        created_utc=stamp(), status='PACT_GATE09_ADMISSION_COMPLETE',
        physical=admission.binding(meta / f'physical/{design}/presearch_qualification.json'),
        reference=admission.binding(meta / f'baselines/{design}_selected.json'),
        exact=admission.binding(exact_path), FF_crosscheck=admission.binding(folder / 'FF_transition_crosscheck.json'),
        exact_summary=admission.binding(folder / 'activity_summary.json'),
        capacity=measure.capacity(protocol), PACT_search_started=False), immutable=True)
    definitions = references.BASE_META / 'manifests/competitive_method_definitions.json'
    if not definitions.exists():
        atomic_write(definitions, dict(schema='pact_gate09_competitor_freeze_v1', frozen_utc=stamp(),
            protocol=admission.binding(admission.INTAKE),
            frozen_before_B4_B5_generation=True, frozen_before_PACT_search=True,
            scope='All preregistered cohort designs; no per-design weights or tuning',
            methods=dict(
                B0=dict(algorithm='Supplied source scan order split contiguously into balanced K=2 capacities; common original control',
                    source='src/pact/scan/phase0c.py:generate_architecture(B0)', parameters=dict(K=2)),
                B1=dict(algorithm='Native placed-cell greedy nearest neighbor; Boost Geometry Cartesian nearest uses Euclidean ranking; start minimizes x+y Manhattan distance to origin; no endpoint-inclusive local refinement',
                    source_SHA='08f67ee5ecd14db5a42be8c610bbfd1ccf079299', terminology='OPENROAD_UPSTREAM',
                    audit=admission.binding(references.BASE_META / 'dependency_probes/B1_pinned_Opt.cpp'),
                    source_url='https://github.com/The-OpenROAD-Project/OpenROAD/blob/08f67ee5ecd14db5a42be8c610bbfd1ccf079299/src/dft/src/architect/Opt.cpp'),
                B2=dict(algorithm='Established native FF-origin nearest neighbor followed by endpoint-inclusive symmetric Manhattan 2-opt, maximum 30 iterations',
                    source_SHA='6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf', terminology='OPEN_SOURCE_PINNED'),
                B3T=dict(algorithm='Qualified patched OpenROAD K-means partition plus directed scan-pin Manhattan nearest neighbor and strict improving 2-opt/3-opt; external endpoints excluded by optimizer and included by common qualification',
                    source_SHA='5c3751171685d507939ee7064a67feec786e5219', terminology='OPENROAD_QUALIFIED_PATCHED',
                    parameters=dict(kmeans_iterations=100, neighbor_count=50, overquery=100, capacity='ceil(FF/K)')),
                B4=dict(algorithm='Existing phase0c A: global greedy balanced chain extensions minimizing mean load-PPI bit disagreement over the identical frozen FAN patterns; activity proxy, not exact E',
                    implementation='src/pact/scan/phase0c.py:generate_architecture(A)',
                    parameters=dict(alpha_physical=0.0, beta_activity=1.0, K=2),
                    starts='Alphabetical names at indices j*N//K', ties='(cost, chain_index, cell_name)'),
                B5=dict(algorithm='Existing phase0c J50: global greedy balanced extensions of 0.5 normalized FF-origin Manhattan distance + 0.5 mean load-PPI disagreement',
                    implementation='src/pact/scan/phase0c.py:generate_architecture(J50)',
                    parameters=dict(alpha_physical=0.5, beta_activity=0.5, K=2),
                    normalization='distance / (x-span + y-span), or denominator 1 when zero',
                    starts='x/y/name sorted names at indices j*N//K', ties='(cost, chain_index, cell_name)'),
                B6=dict(status='NO_ADMITTED_DIRECT_COMPARATOR', discovery=admission.binding(references.BASE_META / 'optional_competitor_discovery.json'))),
            heuristic_source=admission.binding(ROOT / 'src/pact/scan/phase0c.py'),
            PACT=protocol['fixed_method'], seed_policy='Primary 11 only', CPU_only=True,
            budget_bridge='Only frozen search seconds expression and its runtime-policy text changed to the already versioned 900s per loop; solver/evaluator/selection unchanged',
            candidate_limits=dict(B4=1, B5=1, PACT_maximum_new=3),
            resource_policy=protocol['resource_policy'], scientific_method_changes=0,
            numerical_runtime={m.__name__: dict(version=m.__version__, module=admission.binding(m.__file__))
                for m in (numpy, scipy, numba, llvmlite)}), immutable=True)
    else:
        data = admission.read(definitions)
        if data['protocol']['sha256'] != admission.digest(admission.INTAKE):
            raise ValueError('Campaign protocol changed after competitor freeze')
    return gate_path


def generate(meta, raw, design):
    require_exact_reference(meta, design)
    definitions = references.BASE_META / 'manifests/competitive_method_definitions.json'
    if not definitions.exists():
        raise ValueError('Freeze competitors before generating B4/B5')
    from pact.scan.model import ScanArchitecture, ScanChain
    from pact.scan.phase0c import generate_architecture
    from pact.test.pattern_parser import parse_fan_pat, map_ppi_patterns
    prep = admission.read(meta / f'physical/{design}/preparation.json')
    refs = admission.read(meta / f'baselines/{design}_references.json')['records']
    b0 = next(r for r in refs if r['method'] == 'B0')
    base = ScanArchitecture.from_json(Path(b0['architecture']['path']))
    identity_path = raw / f'baselines/{design}/ff_identity_map.json'
    identity = admission.read(identity_path)['records']
    patterns = map_ppi_patterns(parse_fan_pat(Path(prep['patterns']['path'])), identity)
    rows = []
    for method, family in (('B4', 'A'), ('B5', 'J50')):
        began = time.perf_counter()
        generated = generate_architecture(base, 2, family, patterns, architecture_seed=101)
        # Carry the existing B0 endpoint spellings; no placement or metric changes.
        arch = ScanArchitecture(base.cells, tuple(ScanChain(c.chain_id, g.cells, c.scan_in, c.scan_out)
            for c, g in zip(base.chains, generated.chains)))
        path = raw / f'baselines/{design}/{method}/architecture.json'
        if path.exists():
            raise ValueError('Preserve previously generated baseline')
        arch.to_json(path)
        rows.append(dict(design=design, method=method, generator_status='PASS', status='GENERATED_PENDING_ROUTE',
            architecture=admission.binding(path), architecture_hash=arch.sha256(), chain_count=2,
            generation_wall_seconds=time.perf_counter()-began,
            source_revision=admission.digest(ROOT / 'src/pact/scan/phase0c.py'),
            algorithm_family=family, source=admission.binding(ROOT / 'src/pact/scan/phase0c.py'),
            FF_count=len(arch.cells), chain_lengths=[len(c.cells) for c in arch.chains],
            identity_map=admission.binding(identity_path), patterns=prep['patterns'],
            definitions=admission.binding(definitions), architecture_candidates_generated=1,
            candidate_routes_before_selection=0, frozen_utc=stamp()))
    atomic_write(meta / f'baselines/{design}_heuristics_preselected.json', dict(design=design,
        frozen_utc=stamp(), records=rows, final_results_read=0, PACT_search_started=False), immutable=True)


def route(meta, raw, design, method, physical):
    from pact.scan.model import ScanArchitecture
    require_exact_reference(meta, design)
    if method in ('B4', 'B5'):
        selection = meta / f'baselines/{design}_heuristics_preselected.json'
        row = next(r for r in admission.read(selection)['records'] if r['method'] == method)
    else:
        selection = meta / f'selections/{design}/preselected_candidates.json'
        row = next(r for r in admission.read(selection)['records'] if r['candidate'] == method)
        row = dict(row, method=method, generator_status='PASS', source_revision='71b059d9d1a00735d79b6a428693eaba549a5f33')
    path = admission.resolve(row['architecture']['path'])
    if admission.verify(row['architecture'])['status'] != 'PASS':
        raise ValueError('Preselected architecture changed')
    arch = ScanArchitecture.from_json(path)
    if arch.sha256() != row['architecture_hash']:
        raise ValueError('Preselection canonical hash changed')
    prep = admission.read(meta / f'physical/{design}/preparation.json')
    identity = admission.read(raw / f'baselines/{design}/ff_identity_map.json')['records']
    retained = admission.read(meta / f'workers/{design}/retained_reference_qualification.json')
    original = admission.read(retained['retained_original_fault_export']['path'])
    result = dict(row, status='FAILED', preselection=admission.binding(selection))
    try:
        report = physical.route(design, method, path, prep)
        correctness = physical.serial_correctness(design, arch, identity,
            Path(prep['patterns']['path']), original, physical.baseline_folder(design) / method / 'correctness',
            Path(prep['source']['path']))
        result.update(status='QUALIFIED', routed_scan_wirelength_um=report['routed_scan_wirelength_um'],
            timing=report['structured_metrics'], DRC=report['DRC_errors'], correctness=correctness,
            provenance=admission.binding(physical.baseline_folder(design) / method / 'physical/route_result.json'))
    except Exception as error:
        result.update(failure_class='COMMON_PHYSICAL_OR_ATPG_QUALIFICATION_FAIL', error=str(error),
                      traceback=traceback.format_exc())
    atomic_write(meta / f'baselines/{design}_{method}.json', result, immutable=True)
    if result['status'] != 'QUALIFIED':
        raise ValueError(result['failure_class'] + ': ' + result['error'])


def prepare_input(meta, raw, design, physical):
    selected, exact_path, exact_folder = require_exact_reference(meta, design)
    from pact.optimizer.cold_start import ColdStartPACTInput
    from pact.scan.model import ScanArchitecture
    prep = admission.read(meta / f'physical/{design}/preparation.json')
    export_prep = admission.read(meta / f'measurements/{design}/{selected["method"]}/preparation.json')
    export = Path(export_prep['folder'])
    input_root = raw / f'inputs/{design}'
    if input_root.exists():
        raise ValueError('Preserve prospective PACT input')
    input_root.mkdir(parents=True)
    for src, name in ((export / 'net_mapping.json', 'net_mapping.json'),
                      (export / 'routed.odb', 'routed.odb'),
                      (exact_folder / 'net_activity_capacitance.csv', 'net_activity_capacitance.csv')):
        shutil.copyfile(src, input_root / name)
    physical.execute(['/usr/bin/openroad', '-no_init', '-exit', '-python',
        ROOT / 'scripts/pact_cold_start_export.py', input_root, input_root / 'topology.json'],
        input_root / 'topology_export', timeout=1200)
    frozen_ref = meta / f'references/{design}/reference_frozen.json'
    atomic_write(frozen_ref, dict(selected, created_utc=stamp(), cold_start_initial_architecture=True,
        exact_qualification=admission.binding(exact_path)), immutable=True)
    artifacts = dict(architecture=selected['architecture'], patterns=prep['patterns'],
        identity_map=admission.binding(raw / f'baselines/{design}/ff_identity_map.json'), placement=prep['placed_def'],
        mapping=admission.binding(input_root / 'net_mapping.json'),
        caps=admission.binding(input_root / 'net_activity_capacitance.csv'),
        topology=admission.binding(input_root / 'topology.json'),
        source_placed_database=prep['source_placed_database'], SDC=prep['SDC'],
        source_netlist=admission.binding(Path(prep['patterns']['path']).parent / 'compatible.v'),
        qualification=selected['provenance'], reference_fault_export=selected['correctness']['export'],
        reference_serial=selected['correctness']['serial'])
    manifest = meta / f'inputs/{design}/cold_start_input.json'
    atomic_write(manifest, dict(schema='pact_cold_start_input_v1', design=design, created_utc=stamp(),
        reference_method=selected['method'], reference_architecture_hash=selected['architecture_hash'],
        reference=admission.binding(frozen_ref), preparation=admission.binding(meta / f'physical/{design}/preparation.json'),
        artifacts=artifacts, FF_count=len(ScanArchitecture.from_json(Path(artifacts['architecture']['path'])).cells),
        K=2, ATPG_pattern_count=selected['correctness']['statistics']['patterns'],
        target_fault_count=selected['correctness']['statistics']['total'], historical_state_required=False,
        provenance=dict(exact=admission.binding(exact_path), input_adaptation_only=True,
            competitor_outcomes_used_for_initialization=False,
            reference_selection='Frozen minimum-qualified-routed-WL B0/B1/B2/B3T only')), immutable=True)
    ColdStartPACTInput.from_manifest(manifest)


def budget_adapter(search_function):
    source = inspect.getsource(search_function)
    old = "seconds=300*max(1,math.ceil(contract_data['FF_count']/600))"
    text = "runtime_policy='300*max(1,ceil(FF/600)) seconds per unchanged mutation loop'"
    if source.count(old) != 1 or source.count(text) != 1:
        raise ValueError('Frozen budget bridge no longer matches; no implicit method rewrite')
    return source.replace(old, 'seconds=900', 1).replace(text,
        "runtime_policy='Preregistered Gate-09 900 seconds per unchanged mutation loop'", 1)


def search_child(meta, raw, design):
    # Read only PACT input and frozen configuration, never baseline outcome tables.
    import pact_cold_start as cold
    from pact.optimizer import cpu_incremental, cpu_reference
    cold.OUT, cold.RUN = meta, raw
    adapted = budget_adapter(cold.search)
    namespace = dict(cold.__dict__)
    exec(compile(adapted, '<Gate09-preregistered-budget-adapter>', 'exec'), namespace)
    namespace['search'](design, state_type=cpu_incremental.State, reference_evaluator=cpu_reference.reference)


def search(meta, raw, design, protocol):
    # Primary competitor runs must all have terminal, preserved outcomes first.
    for method in ('B0', 'B1', 'B2', 'B3T', 'B4', 'B5'):
        physical_path = meta / f'baselines/{design}_{method}.json'
        if method in ('B4', 'B5') and admission.read(physical_path)['status'] != 'QUALIFIED':
            continue
        state = admission.read(meta / f'workers/{design}/measure_run_{method}.lifecycle.json')
        if state['state'] not in ('COMPLETED', 'FAILED'):
            raise ValueError('Competitor execution remains active')
    import pact_cold_start as cold
    adapter_path = meta / f'execution_sources/{design}_registered_search_adapter.py'
    atomic_write(meta / f'searches/{design}/budget_bridge.json', dict(created_utc=stamp(),
        source=admission.binding(ROOT / 'scripts/pact_cold_start.py'),
        preregistration=admission.binding(admission.INTAKE),
        changes=['seconds expression: 300*max(1,ceil(FF/600)) -> 900', 'runtime policy receipt text'],
        evaluator='Frozen qualified CPU incremental State; independent cpu_reference.reference',
        worker_ceiling_seconds=7200, solver_parameters_changed=False), immutable=True)
    adapter_path.parent.mkdir(parents=True, exist_ok=True)
    adapter_path.write_text(budget_adapter(cold.search))
    from pact_cold_start_measure import execute_stage
    gate = admission.read(meta / f'measurements/{design}/B3T/preparation.json')
    measure.capacity(protocol, gate['dimensions'], gate['retained_bytes'])
    execute_stage([sys.executable, Path(__file__), 'search-child', '--design', design,
        '--meta', meta, '--raw', raw], raw / f'search_worker/{design}', 'search', time.perf_counter()+7200)
    selected = admission.read(meta / f'selections/{design}/preselected_candidates.json')
    if len(selected['records']) > 3 or selected['candidate_routes_before_selection'] != 0:
        raise ValueError('Frozen preselection invariant failed')


def worker(args):
    began = time.perf_counter()
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    name = args.action + ('_' + args.method if args.method else '')
    if args.execution_id:
        if not args.execution_id.replace('_', '').isalnum():
            raise ValueError('Unsafe explicit execution identifier')
        name += '_' + args.execution_id
    result_path = meta / f'workers/{args.design}/campaign_{name}.json'
    state_path = result_path.with_suffix('.lifecycle.json')
    if result_path.exists() or state_path.exists():
        raise ValueError('Preserve started/completed campaign action; no implicit replay')
    snapshot = meta / f'execution_sources/{admission.digest(Path(__file__))}.py'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot.exists():
        snapshot.write_bytes(Path(__file__).read_bytes())
    record = dict(schema='pact_gate09_campaign_worker_v1', action=args.action, method=args.method,
        design=args.design, execution_id=args.execution_id, created_utc=stamp(), PID=os.getpid(),
        Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        code_commit=admission.command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])['stdout'],
        harness=admission.binding(snapshot), source_admission=admission.binding(args.source_admission),
        dependency_repair=admission.binding(args.dependency_repair), CPU_only=True, scientific_method_changes=0)
    atomic_write(state_path, dict(record, state='REGISTERED'), immutable=True)
    atomic_write(result_path.with_name(result_path.stem+'.registered.json'), dict(record, state='REGISTERED'), immutable=True)
    try:
        os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps', 'src', 'scripts'))
        design, source, protocol, infrastructure, physical, repair = references.configure(
            args.source_admission, args.attempt, args.dependency_repair)
        if design != args.design:
            raise ValueError('Admitted design identity mismatch')
        admission_path = meta / f'admission/{design}_complete.json'
        if args.action != 'freeze' and admission.read(admission_path)['status'] != 'PACT_GATE09_ADMISSION_COMPLETE':
            raise ValueError('Reference admission must complete first')
        atomic_write(state_path, dict(record, state='STARTED'))
        atomic_write(result_path.with_name(result_path.stem+'.started.json'), dict(record, state='STARTED'), immutable=True)
        if args.action == 'freeze':
            freeze(meta, raw, design, protocol)
        elif args.action == 'generate':
            generate(meta, raw, design)
        elif args.action == 'route':
            prepared = admission.read(meta / f'measurements/{design}/B3T/preparation.json')
            record['capacity'] = measure.capacity(protocol, prepared['dimensions'], prepared['retained_bytes'])
            route(meta, raw, design, args.method, physical)
        elif args.action == 'input':
            prepare_input(meta, raw, design, physical)
        elif args.action == 'search':
            search(meta, raw, design, protocol)
        record.update(status='PASS', completed=True)
    except Exception as error:
        record.update(status='PACT_GATE09_CAMPAIGN_STAGE_BLOCKED', completed=False,
            error=str(error), traceback=traceback.format_exc())
    usage, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    record.update(completed_utc=stamp(), wall_seconds=time.perf_counter()-began,
        CPU_seconds=usage.ru_utime+usage.ru_stime, children_CPU_seconds=children.ru_utime+children.ru_stime,
        peak_RSS_KiB=usage.ru_maxrss, child_peak_RSS_KiB=children.ru_maxrss)
    atomic_write(result_path, record, immutable=True)
    atomic_write(state_path, dict(record, state='COMPLETED' if record['completed'] else 'FAILED'))
    print('GATE09_CAMPAIGN', args.action, args.design, args.method, record['status'], record.get('error', ''), flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'generate', 'route', 'input', 'search', 'search-child'))
    parser.add_argument('--design', required=True)
    parser.add_argument('--method', choices=('B4', 'B5', 'CS_C1', 'CS_C2', 'CS_C3'))
    parser.add_argument('--source-admission', type=Path)
    parser.add_argument('--attempt')
    parser.add_argument('--dependency-repair', type=Path)
    parser.add_argument('--meta', type=Path)
    parser.add_argument('--raw', type=Path)
    parser.add_argument('--execution-id', help='Explicit preserved recovery attempt; never implicit replay')
    args = parser.parse_args()
    if args.action == 'search-child':
        search_child(args.meta, args.raw, args.design)
    else:
        if not all((args.source_admission, args.attempt, args.dependency_repair)) or (args.action == 'route' and not args.method):
            parser.error('Admitted source, repair namespace/certificate and route method are required')
        result = worker(args)
        raise SystemExit(0 if result['completed'] else 2)
