"""Frozen solver -> scan implementation -> exact pattern replay orchestration."""
from pathlib import Path
import gzip
import shutil
import subprocess
import sys

from pact.scan.model import ScanArchitecture
from pact.physical.extract_placement import extract_def_scan_cells
from .permutation import ScanPermutation, file_hash, read, write
from .patterns import fan_workload, export_workload
from .replay import verify, write_recovered_fan
from .implementation import emit, port_bindings
from .faults import replay_faults


def frozen_inputs(root, paths):
    freeze_path = root/'results/phase2c_repair/freeze.json'
    freeze = read(freeze_path)
    verified = {}
    for path in paths:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        matches = [value for key, value in freeze['inputs'].items() if key.endswith('/'+relative)]
        if len(matches) != 1 or file_hash(path) != matches[0]:
            raise ValueError(f'Qualified input hash missing/changed: {relative}')
        verified[relative] = matches[0]
    return dict(freeze_sha256=file_hash(freeze_path), verified_inputs=verified)


def selected_result(run, before, design, count):
    result = read(run/'result.json')
    supplied = ScanArchitecture.from_json(run/'supplied.architecture.json')
    after = ScanArchitecture.from_json(run/'optimized.architecture.json')
    selected = result.get('selected')
    if not selected or selected['architecture_sha256'] != after.sha256():
        raise ValueError('Selected optimizer recommendation hash missing/changed')
    if supplied.sha256() != before.sha256():
        raise ValueError('Optimizer supplied topology differs from integration input')
    if (result['design'], result['pattern_count'], result['FF_count'], result['K']) != (design, count, len(before.cells), len(before.chains)):
        raise ValueError('Optimizer workload dimensions/design differ')
    limits, score = result['recommendation_constraints'], selected['metrics']
    if score['scan_hpwl_um'] > limits['wire_cap_um']+1e-7 or any(
        score[k] > limits[k+'_max']+1e-7 for k in ('M3_load_local', 'M5_hpwl_local')):
        raise ValueError('Saved selection violates its constrained recommendation policy')
    if abs(limits['wire_cap_um'] - result['physical_reference_um']*(1+result['config']['wire_allowance'])) > 1e-6:
        raise ValueError('Saved wire allowance provenance inconsistent')
    return after, result


def route_evidence(root, design, after):
    folder = root/f'reports/working_solver/routes/{design}/{after.sha256()}'
    report = folder/'route_result.json'
    archive = folder/'5_2_route.odb.gz'
    if not report.exists() or not archive.exists():
        return dict(status='NOT_RUN', reason='No matching retained route report/archive')
    row = read(report)
    if row['architecture_sha256'] != after.sha256() or file_hash(archive) != row['routed_odb_gzip_sha256']:
        raise ValueError('Route evidence hash mismatch')
    proof = row['postroute_verification']
    # Check every concrete internal edge as well as the architecture hash.
    expected = {(i,a,b) for i,c in enumerate(after.chains) for a,b in zip(c.cells,c.cells[1:])}
    observed = {(e['chain'],e['source_ff'],e['dest_ff']) for e in proof['edges']}
    if expected != observed or len(proof['edges']) != len(expected):
        raise ValueError('Routed order edges differ from emitted topology')
    if row['status'] != 'QUALIFIED' or row['DRC_errors'] != 0 or proof['status'] != 'PASS' or not proof['all_chain_inputs_outputs_verified']:
        raise ValueError('Matching route not qualified')
    return dict(status='PASS', reused=True, architecture_sha256=after.sha256(),
                exact_internal_edges_checked=len(expected), DRC_errors=0,
                report=str(report.relative_to(root)), report_sha256=file_hash(report),
                archive=str(archive.relative_to(root)), archive_sha256=file_hash(archive),
                endpoint_verification=True, scope='exact same selected order; archived routed ODB hash verified')


def run(args, root):
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory is nonempty; preserve prior evidence and choose a new run')
    design = args.design
    base = root/f'artifacts/derived/phase0c/{design}/s11/k2/B0.architecture.json'
    topology = (args.scan_topology or base).resolve()
    placement = (args.placement or root/f'artifacts/raw/phase0b/placements/{design}/s11/placed.def').resolve()
    patterns = (args.patterns or root/f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat').resolve()
    identity_path = (args.identity_map or root/f'artifacts/derived/{design}/ff_identity_map.json').resolve()
    before = ScanArchitecture.from_json(topology)
    # Validate before parsing or invoking any external tool.
    ScanPermutation(before, before)
    coordinates = extract_def_scan_cells(placement, [c.name for c in before.cells], before.cells[0].clock_domain)
    if {c.name:c for c in coordinates} != {c.name:c for c in before.cells}:
        raise ValueError('Placed DEF and topology FF coordinates differ')
    identity = read(identity_path)['records']
    fan, rows = fan_workload(patterns, identity, before)
    inputs = dict(topology=topology, placement=placement, patterns=patterns, identity_map=identity_path)
    if args.adapter == 'qualified':
        graph = root/f'results/phase2c_repair/{design}.placed_graph.json'
        qualification = frozen_inputs(root, [placement, patterns, identity_path, graph])
        if ScanArchitecture.from_json(base).sha256() != before.sha256():
            raise ValueError('Qualified integration requires the original B0 topology')
        baseline_route = read(root/f'artifacts/raw/phase0c/physical/{design}/s11/k2/B0/route_metrics.json')
        if baseline_route['architecture_sha256'] != before.sha256() or baseline_route['status'] != 'QUALIFIED':
            raise ValueError('Input B0 topology does not match qualified route identity')
        qualification['input_B0_route_architecture_sha256'] = baseline_route['architecture_sha256']
        if args.fan_root:
            netlist = root/f'artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v'
            evidence = read(identity_path)['evidence']
            if evidence.get(netlist.relative_to(root).as_posix()) != file_hash(netlist):
                raise ValueError('FAN functional netlist differs from identity-map provenance')
    else:
        qualification = dict(scope='explicit generic inputs; input provenance must bind the solver run')
    output.mkdir(parents=True)
    optimizer_run = args.optimizer_run
    if optimizer_run is None:
        optimizer_run = output/'optimizer'
        command = [sys.executable, str(root/'scripts/pact_optimize.py'), '--output', str(optimizer_run),
                   '--time-budget', str(args.time_limit), '--chains', str(len(before.chains)),
                   '--wire-allowance', str(args.wire_allowance)]
        if args.solver_input:
            bundle = read(args.solver_input)
            bundled = ScanArchitecture.from_json(args.solver_input.resolve().parent/bundle['architecture'])
            expected = [{n:int(b) for n,b in r['load_state'].items()} for r in rows]
            if bundled.sha256() != before.sha256() or bundle['patterns'] != expected:
                raise ValueError('Solver bundle differs from integration workload')
            command += ['--input', str(args.solver_input)]
            design = args.solver_input.stem
        elif args.adapter == 'qualified':
            command += ['--design', design]
        else:
            raise ValueError('Generic fresh solve requires --solver-input')
        if args.liberty:
            command += ['--liberty', str(args.liberty)]
        subprocess.run(command, check=True)
        write(optimizer_run/'integration_inputs.json', {k:file_hash(p) for k,p in inputs.items()})
    optimizer_run = optimizer_run.resolve()
    binding = optimizer_run/'integration_inputs.json'
    if binding.exists():
        if read(binding) != {k:file_hash(p) for k,p in inputs.items()}:
            raise ValueError('Optimizer input provenance hashes differ')
    elif args.adapter != 'qualified' or optimizer_run != (root/f'reports/working_solver/final/{design}').resolve():
        raise ValueError('Reused solver run lacks input-hash binding; only qualified historical final runs may use frozen evidence')
    after, result = selected_result(optimizer_run, before, design, len(rows))
    permutation = ScanPermutation(before, after)
    before.to_json(output/'scan_topology_before.json')
    after.to_json(output/'scan_topology_after.json')
    permutation.to_json(output/'scan_permutation.json')
    original, remapped = export_workload(permutation, rows)
    for workload, arch in ((original,before),(remapped,after)):
        workload.update(primary_input_order=list(fan.primary_inputs), primary_output_order=list(fan.primary_outputs),
                        pseudo_primary_order=list(fan.pseudo_primary_inputs),
                        logical_to_physical_ports=port_bindings(arch,args.adapter),
                        clock_domain=before.cells[0].clock_domain)
    write(output/'patterns_original.json', original)
    write(output/'patterns_remapped.json', remapped)
    # Read exported files back; replay tests exactly what consumers receive.
    proof, recovered = verify(before, after, read(output/'patterns_original.json'), read(output/'patterns_remapped.json'), rows)
    write(output/'replay_report.json', proof)
    if proof['status'] != 'PASS':
        raise ValueError('PACT_END_TO_END_PATTERN_MAPPING_FAIL')
    write_recovered_fan(output/'patterns_recovered.pat', fan, identity, recovered)
    emit(output, permutation, root, args.adapter)
    physical = route_evidence(root, args.design, after) if args.adapter == 'qualified' else dict(status='NOT_RUN')
    write(output/'physical_handoff.json', physical)
    if args.source_odb:
        subprocess.run([args.openroad, '-python', '-no_init', '-exit', str(output/'implementation_patch.py'),
                        '--repository', str(root), '--source', str(args.source_odb.resolve()),
                        '--output', str(output/'implementation.odb')], check=True, timeout=args.tool_timeout)
        applied = read(output/'implementation_applied.json')
        if applied['status'] != 'PASS' or not applied['functional_connections_placement_unchanged']:
            raise ValueError('PACT_END_TO_END_IMPLEMENTATION_FAIL')
        physical['patch_application'] = 'PASS'
        physical['status'] = 'PASS'
        write(output/'physical_handoff.json', physical)
        with (output/'implementation.odb').open('rb') as src, gzip.open(output/'implementation.odb.gz','wb') as dst:
            shutil.copyfileobj(src,dst)
    fault = dict(status='NOT_RUN', reason='Supply --fan-root to replay the existing FAN toolchain')
    if args.fan_root:
        fault = replay_faults(args.fan_root.resolve(), args.design, patterns, output/'patterns_recovered.pat',
                             root/f'artifacts/raw/tool_qualification/fan_atpg/benchmarks/{args.design}.v',
                             output/'fault_replay', args.tool_timeout)
    status = 'PASS' if physical['status'] == 'PASS' and fault['status'] != 'FAIL' else ('FAIL' if fault['status'] == 'FAIL' else 'BLOCKED')
    summary = dict(design=args.design, FF_count=len(before.cells), patterns=len(rows), K=len(before.chains),
                   permutation_valid='PASS', load_replay=proof['load_replay'], unload_replay=proof['unload_replay'],
                   fault_equivalence=fault, implementation_emitted='PASS', physical_flow_consumable=physical['status'],
                   overall=status, classification=f'PACT_END_TO_END_{args.design.upper()}_PASS' if status == 'PASS' else status,
                   mismatches=proof['mismatches'], FF_states_checked=proof['FF_states_checked'])
    write(output/'summary.json', summary)
    input_files = dict(inputs, optimizer_result=optimizer_run/'result.json',
                       optimizer_selected=optimizer_run/'optimized.architecture.json',
                       optimizer_supplied=optimizer_run/'supplied.architecture.json')
    write(output/'manifest.json', dict(schema='pact_end_to_end_manifest_v1',
          input_files={k:dict(path=str(p), sha256=file_hash(p)) for k,p in input_files.items()},
          qualification=qualification, input_topology_sha256=before.sha256(),
          selected_architecture_sha256=after.sha256(), solver_config=result['config'],
          solver_reused=args.optimizer_run is not None,
          integration_code={p.relative_to(root).as_posix():file_hash(p) for p in sorted((root/'src/pact/integration').glob('*.py'))},
          artifacts={p.relative_to(output).as_posix():file_hash(p) for p in sorted(output.rglob('*')) if p.is_file() and p.suffix != '.odb'}))
    return summary
