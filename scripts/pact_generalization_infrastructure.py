#!/usr/bin/env python3
"""Preregister and qualify new inputs using the frozen FAN/ORFS semantics."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

from pact_generalization import ROOT, OUT, binding, now, read, sha, write
from pact.scan.identity import scan_ff_instances, supplied_scan_order
from pact.test.pattern_parser import parse_fan_pat
from pact.integration.faults import parse_statistics

DEPS = Path('/root/pact-deps')
FAN = DEPS/'FAN_ATPG'
RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_generalization_20261004')
FLOW = DEPS/'OpenROAD-flow-scripts/flow'
DESIGNS = ('s208','s510','s953','s1196','s1238','s35932','s38417','s38584')
REPAIRED = ROOT/'scratch/FAN_ATPG-report-repair/bin/opt/fan'


def external_binding(path):
    path = Path(path)
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def execute(command, folder, cwd=ROOT, timeout=900, env=None):
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder/'execution.json'
    if receipt.exists():
        raise ValueError('Preserve prior execution: ' + str(receipt))
    began = time.perf_counter()
    with (folder/'stdout.txt').open('w') as output, (folder/'stderr.txt').open('w') as error:
        process = subprocess.Popen(list(map(str,command)), cwd=cwd, stdout=output, stderr=error,
                                   env=env, start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    result = dict(command=list(map(str,command)), cwd=str(cwd), exit_code=code,
        timed_out=timed_out, wall_seconds=time.perf_counter()-began, timestamp_utc=now(),
        stdout=external_binding(folder/'stdout.txt'), stderr=external_binding(folder/'stderr.txt'))
    write(receipt, result, immutable=True)
    print(folder.name, code, round(result['wall_seconds'], 2), 'seconds', flush=True)
    if code or timed_out:
        raise RuntimeError('Command failed: ' + str(receipt))
    return result


def register():
    rows = []
    for design in DESIGNS:
        path = FAN/f'mod_netlist/{design}.v'
        ff = scan_ff_instances(path)
        text = path.read_text()
        rows.append(dict(design=design, source='FAN_ATPG pinned ISCAS89 mapped full-scan netlist',
            source_url=f'https://github.com/NTU-LaDS-II/FAN_ATPG/blob/26b2b36c0e9db11a4b6d9e759df6e44357121f39/mod_netlist/{design}.v',
            source_commit='26b2b36c0e9db11a4b6d9e759df6e44357121f39', source_file=external_binding(path),
            FF_count=len(ff), mapped_cell_count=len(re.findall(r'\b\w+_X\d+\s+\w+\s*\(',text)),
            size_stratum='small' if len(ff)<100 else ('medium' if len(ff)<600 else 'large'),
            ATPG_target_fault_count=None, ATPG_pattern_count=None,
            compatibility='UNQUALIFIED; source is already mapped full scan; no PACT evaluation',
            expected_resources=dict(physical_cores=2, solver_threads=1,
                scratch_estimate_GiB=1 if len(ff)<600 else 4, physical_stage_timeout_seconds=1200),
            prior_use_audit='No matches in repository docs/results/reports/experiments/config/benchmarks; s27 excluded because previously used for tool qualification',
            license_provenance='FAN_ATPG repository MIT; original ISCAS89 redistribution rights not independently established; sources remain in existing dependency checkout'))
    protocol = dict(schema='pact_generalization_preregistration_v1', created_utc=now(),
        classification='BENCHMARK_SELECTION_FROZEN_BEFORE_OUTCOMES', designs=rows,
        selection_rule='All eight unused mapped ISCAS89 circuits available at the pinned FAN revision; no outcome-dependent source selection or substitutions',
        frozen_core=binding(OUT/'manifests/pact_v1_frozen_manifest.json'),
        fixed_method=dict(K=2, seed=11, epsilons=[.02,.05,.10], max_evaluations=20000,
            stagnation_attempts=2000,lane_attempts=150,neighbors=16,segment=8,archive_size=16,weights=[1.,1.,1.],
            stateful_logic_depth=3, route_limit=3,
            runtime_policy='300 seconds per mutation loop for FF<=600; 300*ceil(FF/600) for FF>600; no per-design tuning',
            primary_role='balanced', alternative_roles=['best_E','best_H4','best_H8'],
            reference_rule='minimum qualified routed scan cost among permitted B0/B1/B2/B3T before PACT search'),
        outcomes=dict(improvement_threshold='Strict coordinate reduction beyond relative 1e-10 numerical equality; no empirical effect-size threshold',
            categories=['PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES','PACT_ACTIVITY_MIXED','PACT_NO_MEANINGFUL_ADVANTAGE','PACT_PHYSICAL_QUALIFICATION_FAIL','PACT_EXECUTION_BLOCKED']),
        safety_limits=dict(physical_stage_seconds=1200, ATPG_seconds=900, measurement_seconds=1800,
            solver_worker_seconds='max(1800,4*declared_loop_seconds)', minimum_free_scratch_GiB=20),
        stop_policy='Stop and report scientific failure, unpreserved ATPG correctness, prohibitive scaling, contradictory hotspot assumptions, or backend unable to support required sizes; never retune',
        failure_policy='Retain every selected design and every preselected candidate; infrastructure failures are not evidence against PACT')
    write(OUT/'manifests/campaign_preregistration.json', protocol, immutable=True)
    return protocol


def prepare(design):
    protocol = read(OUT/'manifests/campaign_preregistration.json')
    row = next(r for r in protocol['designs'] if r['design']==design)
    source = Path(row['source_file']['path'])
    assert sha(source)==row['source_file']['sha256']
    folder = RUN/'inputs'/design
    folder.mkdir(parents=True,exist_ok=True)
    record = dict(design=design, source=row['source_file'], gates={}, status='INFRASTRUCTURE_PENDING')
    stage = 'BENCHMARK_SOURCE_FAIL'
    try:
        order = supplied_scan_order(source)
        write(folder/'source_scan_order.json',list(order),immutable=True)
        record['gates']['source_topology']='PASS'
        stage = 'ATPG_FAIL'
        scripts = [f'read_lib {FAN}/techlib/mod_nangate45.mdt',f'read_netlist {source}',
            'report_netlist','build_circuit --frame 1','report_circuit','set_fault_type saf','add_fault --all',
            'set_static_compression on','set_dynamic_compression on','set_X-Fill on','run_atpg',
            'report_statistics',f'write_pattern {folder}/patterns.pat','exit']
        (folder/'atpg.script').write_text('\n'.join(scripts)+'\n')
        record['ATPG_execution']=execute([REPAIRED,'-f',folder/'atpg.script'],folder/'atpg_generate',FAN,900)
        output=(folder/'atpg_generate/stdout.txt').read_text()
        if '**ERROR' in output:
            raise ValueError('FAN reported an error')
        parsed = parse_fan_pat(folder/'patterns.pat')
        stats = parse_statistics(output)
        assert len(parsed.patterns)==stats['patterns'] and len(parsed.pseudo_primary_inputs)==row['FF_count']
        record.update(ATPG_statistics=stats, patterns=external_binding(folder/'patterns.pat'))
        record['gates']['ATPG']='PASS'
        stage = 'SCAN_TOPOLOGY_FAIL'
        # The existing balanced K=2 preparation requires >=8 FF per chain.
        # Do not bypass that guard or switch K in this campaign.
        if row['FF_count']//2<8:
            raise ValueError('Existing K=2 architecture generator rejects n//K < 8; frozen K policy retained')
        stage = 'SYNTHESIS_FAIL'
        original = source.read_text()
        compatible = re.sub(r'\bBUF_X3\b','BUF_X4',original)
        netlist = folder/'compatible.v'
        netlist.write_text(compatible)
        write(folder/'preparation.json',dict(source=row['source_file'],compatible=external_binding(netlist),
            translations=[dict(from_cell='BUF_X3',to_cell='BUF_X4',instances=len(re.findall(r'\bBUF_X3\b',original)),
                reason='Same qualified Boolean buffer compatibility translation; master absent from Nangate45')]),immutable=True)
        (folder/'constraint.sdc').write_text('create_clock -name clk -period 10.0 [get_ports CK]\nset_input_delay 0.0 -clock clk [all_inputs]\nset_output_delay 0.0 -clock clk [all_outputs]\n')
        config=folder/'config.mk'
        config.write_text(f'export DESIGN_NAME = {design}\nexport PLATFORM = nangate45\nexport SYNTH_NETLIST_FILES = {netlist}\nexport VERILOG_FILES = $(SYNTH_NETLIST_FILES)\nexport SDC_FILE = {folder}/constraint.sdc\nexport CORE_UTILIZATION = 35\nexport PLACE_DENSITY_LB_ADDON = 0.20\nexport TNS_END_PERCENT = 100\n')
        work=RUN/'orfs'
        variant=work/f'results/nangate45/{design}/generalization_source'
        record['placement_execution']=execute(['make',f'DESIGN_CONFIG={config}',f'WORK_HOME={work}',
            'FLOW_VARIANT=generalization_source','NUM_CORES=2','OPENROAD_EXE=/usr/bin/openroad','YOSYS_EXE=/usr/bin/yosys','place'],
            folder/'synthesis_placement',FLOW,1200)
        assert (variant/'3_place.odb').is_file() and (variant/'3_place.sdc').is_file()
        record['gates'].update(synthesis='PASS',scan_representation='PASS',placement='PASS')
        stage='PHYSICAL_BACKEND_FAIL'
        base=work/f'results/nangate45/{design}/phase0b_s11_B0'
        base.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ,PACT_PHASE0B_SOURCE_ODB=str(variant/'3_place.odb'),
            PACT_PHASE0B_PLACED_ODB=str(base/'3_place.odb'),PACT_PHASE0B_PLACEMENT_OUT=str(folder),PACT_PHASE0B_PHYSICAL_SEED='11')
        record['seed_execution']=execute(['/usr/bin/openroad','-no_init','-exit',ROOT/'scripts/tcl/phase0b_seed_placement.tcl'],
            folder/'seed_placement',env=env)
        shutil.copy2(variant/'3_place.sdc',base/'3_place.sdc')
        record.update(status='PLACEMENT_READY_PENDING_REFERENCES',config=external_binding(config),
            source_placed_database=external_binding(base/'3_place.odb'),SDC=external_binding(base/'3_place.sdc'),
            placed_def=external_binding(folder/'placed.def'),placed_netlist=external_binding(folder/'placed.v'))
    except Exception as error:
        record.update(status='PACT_EXECUTION_BLOCKED',failure_class=stage,error=str(error),traceback=traceback.format_exc())
        write(OUT/f'failures/{design}_preparation.json',record,immutable=True)
    write(OUT/f'physical/{design}/preparation.json',record,immutable=True)
    print(design,record['status'],record.get('error',''),flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('register','prepare','manifest'))
    p.add_argument('--design',choices=DESIGNS)
    args=p.parse_args()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',
        PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',PACT_DEPENDENCY_ROOT=str(DEPS),
        PATH='/usr/bin:'+os.environ['PATH'])
    if args.action=='register':
        register()
    elif args.action=='prepare':
        for design in ([args.design] if args.design else DESIGNS):
            if not (OUT/f'physical/{design}/preparation.json').exists():
                prepare(design)
    else:
        protocol=read(OUT/'manifests/campaign_preregistration.json')
        for row in protocol['designs']:
            preparation=read(OUT/f"physical/{row['design']}/preparation.json")
            stats=preparation.get('ATPG_statistics',{})
            row.update(ATPG_target_fault_count=stats.get('total'),ATPG_pattern_count=stats.get('patterns'),
                compatibility=preparation['status'], qualification_receipt=binding(OUT/f"physical/{row['design']}/preparation.json"))
        write(OUT/'manifests/generalization_benchmark_manifest.json',dict(schema='pact_generalization_benchmarks_v1',
            frozen_utc=now(),selection_preregistration=binding(OUT/'manifests/campaign_preregistration.json'),
            designs=protocol['designs'],no_PACT_search_executed=True),immutable=True)


if __name__=='__main__':
    main()
