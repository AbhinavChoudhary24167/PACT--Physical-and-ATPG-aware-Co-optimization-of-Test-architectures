#!/usr/bin/env python3
"""Exact independently bounded cold-start candidate activity measurement.

Input is an artifact-bound measurement row, without any per-design lookup or
historical P0 state. Each invocation is an independent experimental unit.
"""
import argparse
import gzip
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact_generalization import now, read, sha, write
from pact_generalization_infrastructure import external_binding
from pact.scan.model import ScanArchitecture
from pact.integration.patterns import fan_workload, serialize

RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cold_start_unseen_20261004')
OUT = ROOT / 'results/pact_cold_start_unseen_20261004'
FLOW = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
LIB = FLOW / 'platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib'
CELLS = Path('/root/pact-deps/FAN_ATPG/techlib/NangateOpenCellLibrary.v')
RULES = FLOW / 'platforms/nangate45/rcx_patterns.rules'


def validate_row(row):
    for name in ('design', 'role'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', row[name]):
            raise ValueError('Unsafe measurement identifier: ' + name)
    for name in ('architecture', 'routed_archive', 'source_placed_database', 'source_netlist', 'SDC', 'qualification', 'prior_integration'):
        item = row[name]
        if sha(item['path']) != item['sha256']:
            raise ValueError('Hash mismatch: ' + name)
    for name in ('patterns', 'identity_map', 'placement'):
        item = row['inputs'][name]
        if sha(item['path']) != item['sha256']:
            raise ValueError('Hash mismatch: inputs/' + name)
    arch = ScanArchitecture.from_json(Path(row['architecture']['path']))
    if row.get('architecture_sha256', arch.sha256()) != arch.sha256():
        raise ValueError('Architecture semantic hash mismatch')
    if len(arch.chains) != 2:
        raise ValueError('Frozen measurement requires K=2')
    return arch


def prepare_row(row, root=None):
    row = dict(row)
    arch = validate_row(row)
    root = Path(root) if root is not None else RUN / 'activity' / row['design'] / row['role']
    if (root / 'manifest.json').exists():
        raise ValueError('Preserve existing measurement: ' + str(root))
    folder = root / row['design'] / row['role']
    folder.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 20 * 1024**3:
        raise RuntimeError('Registered minimum20GiB scratch reserve unavailable for independent exact measurement')
    _, states = fan_workload(Path(row['inputs']['patterns']['path']), read(row['inputs']['identity_map']['path'])['records'], arch)
    workload = dict(architecture_sha256=arch.sha256(), cycles=max(len(c.cells) for c in arch.chains),
        patterns=[dict(pattern=s['pattern'], source_fields=s['source_fields'], load=serialize(arch, s['load_state']),
            unload=serialize(arch, s['response_state'], response=True)) for s in states])
    write(folder / 'workload.json', workload, immutable=True)
    row.update(architecture_sha256=arch.sha256(), workload=external_binding(folder / 'workload.json'),
        patterns=len(states), chain_lengths=[len(c.cells) for c in arch.chains],
        shift_cycles=2 * len(states) * workload['cycles'])
    sources = {name: external_binding(ROOT / name) for name in (
        'scripts/physical_effect.py', 'scripts/physical_effect_export.py', 'src/pact/physical_effect.py',
        'scripts/pact_generalization_export.py', 'scripts/pact_generalization_routed.py',
        'scripts/pact_generalization_scan_masters.py', 'scripts/pact_cold_start_measure.py',
        'scripts/pact_cold_start_measure_analyze.py')}
    write(root / 'manifest.json', dict(schema='pact_cold_start_exact_activity_v1', rows=[row], created_utc=now(),
        library=external_binding(LIB), simulation_cells=external_binding(CELLS), extraction_rules=external_binding(RULES),
        executed_sources=sources,
        tools={name: external_binding('/usr/bin/' + name) for name in ('openroad', 'iverilog', 'vvp')},
        python_runtime=dict(executable=external_binding(sys.executable), version=sys.version),
        deadline_seconds=1800, initialization_inputs='artifact row only; no historical P0/archive',
        measurement_semantics='Frozen OpenRCX ground+Liberty pin C*N; all_data E, source-attributed H4/H8; exact Icarus functional scan replay'), immutable=True)
    return root, folder


def execute_stage(command, folder, name, deadline):
    """Linux wait4 captures CPU/RSS even when the independent deadline expires."""
    receipt = folder / (name + '.execution.json')
    if receipt.exists():
        raise ValueError('Preserve prior stage: ' + str(receipt))
    began = time.perf_counter()
    with (folder / (name + '.log')).open('w') as output:
        process = subprocess.Popen(list(map(str, command)), cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True)
        timed_out = False
        sent = None
        while True:
            pid, status, resources = os.wait4(process.pid, os.WNOHANG)
            if pid:
                code = os.waitstatus_to_exitcode(status)
                process.returncode = code
                break
            clock = time.perf_counter()
            if clock >= deadline and sent is None:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                sent = clock
            elif sent is not None and clock - sent >= 5:
                os.killpg(process.pid, signal.SIGKILL)
            time.sleep(.02)
    record = dict(command=list(map(str, command)), cwd=str(ROOT), returncode=code, timed_out=timed_out,
        wall_seconds=time.perf_counter() - began, CPU_user_seconds=resources.ru_utime,
        CPU_system_seconds=resources.ru_stime, CPU_seconds=resources.ru_utime + resources.ru_stime,
        peak_RSS_KiB=resources.ru_maxrss, major_page_faults=resources.ru_majflt,
        timestamp_utc=now(), resources_scope='wait4 child and child-waited descendants; RSS is maximum, not a summed tree value',
        log=external_binding(folder / (name + '.log')))
    write(receipt, record, immutable=True)
    print('MEASUREMENT_STAGE', name, code, round(record['wall_seconds'], 3), flush=True)
    if code or timed_out:
        raise RuntimeError('Measurement stage failed: ' + str(receipt))
    return record


def measure_prepared(root, folder, timeout_seconds=1800):
    """Invoke the unmodified frozen stimulus/export/metric semantics."""
    os.environ.update(PACT_PHYSICAL_EFFECT_OUT=str(root), PACT_DEPENDENCY_ROOT='/root/pact-deps',
        PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
        NUMBA_NUM_THREADS='1', PATH='/usr/bin:' + os.environ['PATH'])
    import physical_effect as frozen
    frozen.OUT = root
    manifest = read(root / 'manifest.json')
    row = manifest['rows'][0]
    for source in manifest['executed_sources'].values():
        if sha(source['path']) != source['sha256']:
            raise ValueError('Executed source binding changed')
    for name in ('library', 'simulation_cells', 'extraction_rules'):
        frozen.check_binding(manifest[name])
    for item in manifest['tools'].values():
        frozen.check_binding(item)
    frozen.check_binding(manifest['python_runtime']['executable'])
    if sha('/usr/bin/openroad') != read(ROOT / 'results/pact_oss_benchmark/protocol/tool_versions.json')['implementation_binary_sha256']:
        raise ValueError('Frozen common-backend OpenROAD executable changed')
    validate_row(row)
    import resource
    began = time.perf_counter()
    launcher_before = resource.getrusage(resource.RUSAGE_SELF)
    deadline = began + timeout_seconds
    result = dict(design=row['design'], role=row['role'], architecture_sha256=row['architecture_sha256'],
        status='PENDING', manifest=external_binding(root / 'manifest.json'), created_utc=now(),
        independent_design_policy=True, timeout_seconds=timeout_seconds)
    try:
        with gzip.open(row['routed_archive']['path'], 'rb') as src, (folder / 'routed.odb').open('wb') as dst:
            shutil.copyfileobj(src, dst)
        expected = read(row['qualification']['path']).get('routed_odb_sha256')
        if expected and sha(folder / 'routed.odb') != expected:
            raise ValueError('Routed archive uncompressed hash mismatch')
        execute_stage(['/usr/bin/openroad', '-python', '-no_init', '-exit', ROOT / 'scripts/pact_generalization_export.py', folder], folder, 'export', deadline)
        tcl = f'''read_liberty {LIB}
read_db {folder / 'routed.odb'}
write_verilog {folder / 'routed_raw.v'}
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {RULES} -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {folder / 'extracted.spef'}
exit
'''
        (folder / 'extract.tcl').write_text(tcl)
        execute_stage(['/usr/bin/openroad', '-no_init', '-exit', folder / 'extract.tcl'], folder, 'extract', deadline)
        mapping = read(folder / 'net_mapping.json')
        frozen.repair_input_aliases(folder, mapping)
        frozen.stimulus(row, folder, mapping)
        write(folder / 'simulation_manifest.json', dict(inputs={p: external_binding(folder / p) for p in (
            'routed.odb', 'routed.v', 'routed_raw.v', 'stimulus.v', 'net_mapping.json', 'cycles.json', 'extracted.spef', 'workload.json')},
            cells=external_binding(CELLS), architecture_sha256=row['architecture_sha256'],
            simulation='Icarus -g2012 -DTETRAMAX (vendor functional mode); specify disabled; zero delay; no SDF'), immutable=True)
        execute_stage(['/usr/bin/iverilog', '-g2012', '-DTETRAMAX', '-s', 'tb', '-o', folder / 'simulation.vvp',
            folder / 'stimulus.v', folder / 'routed.v', CELLS], folder, 'compile', deadline)
        execute_stage(['/usr/bin/vvp', folder / 'simulation.vvp'], folder, 'simulate', deadline)
        # Analysis runs in a separate worker under the remaining per-design
        # budget, so parsing/reduction cannot bypass the registered deadline.
        execute_stage([sys.executable, ROOT / 'scripts/pact_cold_start_measure.py', '--analyze-folder', folder], folder, 'analyze', deadline)
        for name in ('topology_verification.json', 'functional_verification.json', 'FF_transition_crosscheck.json'):
            if read(folder / name)['status'] != 'PASS':
                raise ValueError('Exact gate failed: ' + name)
        summary = read(folder / 'activity_summary.json')
        data = summary['scopes']['all_data']
        result.update(status='QUALIFIED', E=data['cap_weighted_ff_transitions']['total'],
            H4=data['grids']['4']['cap_peak_per_cycle']['maximum'], H8=data['grids']['8']['cap_peak_per_cycle']['maximum'],
            summary=external_binding(folder / 'activity_summary.json'), FF_transitions=external_binding(folder / 'FF_transition_crosscheck.json'),
            metric_scope='all_data', VCD_complete=True)
    except Exception as error:
        stages = [read(p) for p in folder.glob('*.execution.json')]
        resource_failure = any(r.get('timed_out') or r.get('returncode') in (-9, 137) for r in stages)
        simulation_complete = any(r.get('returncode') == 0 and not r.get('timed_out') and
            Path(r['command'][0]).name == 'vvp' for r in stages)
        result.update(status='FAILED', failure_class='RESOURCE_LIMIT' if resource_failure else 'PHYSICAL_BACKEND_FAIL',
            error=str(error), traceback=traceback.format_exc(), VCD_complete=simulation_complete,
            partial_VCD_policy='Retain failed-stage artifacts for diagnosis; exclude all partial/unqualified activity from scientific results')
    stages = {p.name.removesuffix('.execution.json'): read(p) for p in folder.glob('*.execution.json')}
    vcd_path = folder / 'activity.vcd'
    launcher_after = resource.getrusage(resource.RUSAGE_SELF)
    launcher_cpu = launcher_after.ru_utime + launcher_after.ru_stime - launcher_before.ru_utime - launcher_before.ru_stime
    instrumentation = dict(stages=stages, analysis=read(folder / 'analysis_instrumentation.json') if (folder / 'analysis_instrumentation.json').exists() else None,
        analysis_failure_localization=read(folder / 'analysis_live.json') if result['status'] == 'FAILED' and (folder / 'analysis_live.json').exists() else None,
        VCD=dict(bytes=vcd_path.stat().st_size if vcd_path.exists() else 0, complete=result['VCD_complete']),
        VCD_generation=dict(wall_seconds=None, shared_stage='simulate',
            reason='VVP performs simulation and $dumpvars emission in the same process; isolated generation time is not observable without changing execution semantics'),
        total_wall_seconds=time.perf_counter() - began,
        launcher_CPU_seconds=launcher_cpu, launcher_peak_RSS_KiB=launcher_after.ru_maxrss,
        total_CPU_seconds=launcher_cpu + sum(r.get('CPU_seconds', 0.) for r in stages.values()),
        peak_RSS_KiB=max([launcher_after.ru_maxrss] + [r.get('peak_RSS_KiB', 0) for r in stages.values()]),
        resources_scope='CPU sum of launcher and sequential child stages; RSS maximum of per-process lifetime high-water marks; not summed simultaneous tree RSS',
        numerical_semantics='Unchanged frozen parser and metric arithmetic; only timers inserted', scientific_method_change=False)
    write(folder / 'instrumentation.json', instrumentation, immutable=True)
    result.update(wall_seconds=instrumentation['total_wall_seconds'], CPU_seconds=instrumentation['total_CPU_seconds'],
        peak_RSS_KiB=instrumentation['peak_RSS_KiB'], instrumentation=external_binding(folder / 'instrumentation.json'), folder=str(folder))
    write(folder / 'result.json', result, immutable=True)
    receipt = OUT / 'physical' / row['design'] / row['role'] / 'activity'
    receipt.mkdir(parents=True, exist_ok=True)
    for name in ('activity_summary.json', 'FF_transition_crosscheck.json', 'spatial_bins.json', 'topology_verification.json',
        'functional_verification.json', 'simulation_manifest.json', 'export.execution.json', 'extract.execution.json',
        'compile.execution.json', 'simulate.execution.json', 'analyze.execution.json', 'analysis_instrumentation.json',
        'analysis_live.json', 'instrumentation.json', 'result.json'):
        if (folder / name).exists():
            if (receipt / name).exists():
                raise ValueError('Preserve previous compact receipt: ' + str(receipt / name))
            shutil.copy2(folder / name, receipt / name)
    print('EXACT_ACTIVITY', row['design'], row['role'], result['status'], flush=True)
    return result


def run_row(row, root=None, timeout_seconds=1800):
    root, folder = prepare_row(row, root)
    return measure_prepared(root, folder, timeout_seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--row', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--analyze-folder', type=Path)
    args = parser.parse_args()
    if args.analyze_folder:
        from pact_cold_start_measure_analyze import analyze_instrumented
        record = analyze_instrumented(args.analyze_folder)
        write(args.analyze_folder / 'analysis_instrumentation.json', record, immutable=True)
    elif args.row:
        run_row(read(args.row), args.root)
    else:
        parser.error('--row or --analyze-folder required')


if __name__ == '__main__':
    main()
