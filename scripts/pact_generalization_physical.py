#!/usr/bin/env python3
"""Infrastructure qualification of preregistered unseen designs, before PACT."""
import argparse
import csv
import gzip
import math
import os
from pathlib import Path
import shutil
import subprocess
import traceback

from pact_generalization import ROOT,OUT,binding,now,read,sha,write
from pact_generalization_infrastructure import RUN,FLOW,FAN,REPAIRED,execute,external_binding,DESIGNS
from pact.scan.model import ScanArchitecture,ScanChain
from pact.scan.phase0c import generate_architecture
from pact.scan.phase0b_identity import phase0b_ff_identity_map
from pact.physical.extract_placement import extract_def_scan_cells
from pact.integration.patterns import fan_workload,export_workload,serialize
from pact.integration.permutation import ScanPermutation
from pact.integration.replay import verify,write_recovered_fan
from pact.integration.qualification import simulate,compare_exports
from pact.test.pattern_parser import parse_fan_pat,map_ppi_patterns
from pact.phase0d.external import extract_structured_metrics

IMAGE='sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e'
TEMP=Path('/mnt/d/PACT_EXPERIMENTS/tmp/pact_oss_20261003')
LIB=FLOW/'platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib'
ANNOTATED=TEMP/'NangateOpenCellLibrary_typical_dft.lib'
NAMESPACE=RUN/'namespace'
ATTEMPT=''


def result_path(relative):
    if ATTEMPT:
        return OUT/'repair_attempts'/ATTEMPT/relative
    return OUT/relative


def baseline_folder(design):
    return RUN/('baseline_'+ATTEMPT if ATTEMPT else 'baselines')/design


def select_reference(records):
    """Reject unresolved generator failures; allow disqualified physical runs."""
    if any(r.get('generator_status')!='PASS' for r in records if r['method']!='B0'):
        raise ValueError('Unresolved reference-generation infrastructure failure')
    eligible=[r for r in records if r['status']=='QUALIFIED']
    if not eligible:
        raise ValueError('No permitted reference passed qualification')
    return min(eligible,key=lambda r:(r['routed_scan_wirelength_um'],r['method']))
METHODS=dict(B1=('08f67ee5ecd14db5a42be8c610bbfd1ccf079299',Path('/usr/bin/openroad')),
    B2=('6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf',Path('/mnt/pact-oss-recovery/B2_openroad_10176/build/bin/openroad')),
    B3T=('5c3751171685d507939ee7064a67feec786e5219',TEMP/'topology_recovery_20261004/immutable_binaries/5c3751171685d507939ee7064a67feec786e5219/openroad'))


def prep(design):
    path=OUT/f'physical/{design}/preparation_repaired.json'
    return read(path if path.exists() else OUT/f'physical/{design}/preparation.json')


def docker(command):
    result=['docker','run','--rm','--network=none']
    for path in (ROOT,Path('/root/pact-deps'),Path('/mnt/pact-oss-recovery'),TEMP):
        result+=['--mount',f'type=bind,source={path},target={path},readonly']
    result+=['--mount',f'type=bind,source={RUN},target={RUN}',
        '--env',f'PYTHONPATH={ROOT}/src','--env',f'PACT_ORFS_ROOT={NAMESPACE}/orfs',
        '--entrypoint','/bin/bash',IMAGE,'-c','exec "$@"','pact-command',*map(str,command)]
    return result


def serial_correctness(design,arch,identity,patterns,original,folder,source):
    fan,states=fan_workload(patterns,identity,arch)
    before,after=export_workload(ScanPermutation(arch,arch),states)
    receipt,recovered=verify(arch,arch,before,after,states)
    assert receipt['status']=='PASS'
    write(folder/'serial_replay.json',receipt,immutable=True)
    recovered_path=folder/'patterns_recovered.pat'
    write_recovered_fan(recovered_path,fan,identity,recovered)
    assert parse_fan_pat(recovered_path)==fan
    exported=simulate(REPAIRED,FAN/'techlib/mod_nangate45.mdt',source,recovered_path,folder/'fan')
    correctness=compare_exports(original,exported)
    assert correctness['status']=='PASS'
    write(folder/'test_correctness.json',correctness,immutable=True)
    return dict(serial=external_binding(folder/'serial_replay.json'),faults=external_binding(folder/'test_correctness.json'),
        export=external_binding(folder/'fan/export.json'),statistics=exported['statistics'])


def route(design,method,path,preparation,reuse=None):
    arch=ScanArchitecture.from_json(path)
    folder=baseline_folder(design)/method/'physical'
    config=Path(preparation['config']['path'])
    source=Path(preparation['source_placed_database']['path'])
    work=RUN/'orfs'
    variant_name='generalization_'+(ATTEMPT+'_' if ATTEMPT else '')+method
    variant=work/f'results/nangate45/{design}/{variant_name}'
    logs=work/f'logs/nangate45/{design}/{variant_name}'
    variant.mkdir(parents=True,exist_ok=True)
    if reuse:
        variant=Path(reuse['variant'])
        logs=Path(reuse['logs'])
        routed=read(reuse['route_execution'])
        assert routed['exit_code']==0 and not routed['timed_out']
        write(folder/'retained_route.json',dict(classification='IMPLEMENTATION_REPAIR',
            routed_database=external_binding(variant/'5_2_route.odb'),
            route_execution=external_binding(reuse['route_execution']),
            additional_route_executions=0,scientific_method_change=False),immutable=True)
    else:
        execute(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts/phase0c_rewire_odb.py',
            '--source',source,'--architecture',path,'--output',variant/'3_place.odb'],folder/'rewire',timeout=180)
        shutil.copy2(preparation['SDC']['path'],variant/'3_place.sdc')
        routed=execute(['make','-o',str(variant/'3_place.odb'),'-o',str(variant/'3_place.sdc'),
            f'DESIGN_CONFIG={config}',f'FLOW_VARIANT={variant_name}',f'WORK_HOME={work}',
            'GRT_SEED=11','NUM_CORES=2','OPENROAD_EXE=/usr/bin/openroad','YOSYS_EXE=/usr/bin/yosys','route'],
            folder/'route',FLOW,1200)
    metrics=extract_structured_metrics(read(logs/'5_1_grt.json'),read(logs/'5_2_route.json'))
    proof=folder/'routed_verification.json'
    execute(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts/pact_generalization_routed.py',
        '--recognize-sized-scan',
        '--routed',variant/'5_2_route.odb','--architecture',path,'--frozen-def',preparation['placed_def']['path'],
        '--output',proof],folder/'topology',timeout=180)
    topology=read(proof)
    assert topology['status']=='PASS'
    assert metrics['detailed_route_drc_errors']==0
    assert all(math.isfinite(float(metrics[k])) and float(metrics[k])>=0 for k in ('setup_wns_ns','hold_wns_ns'))
    tcl=folder/'extract.tcl'
    tcl.write_text(f'''read_liberty {LIB}
read_db {variant}/5_2_route.odb
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {FLOW}/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {folder}/extracted.spef
exit
''')
    execute(['/usr/bin/openroad','-no_init','-exit',tcl],folder/'extraction',timeout=180)
    assert (folder/'extracted.spef').stat().st_size>0
    archive=folder/'5_2_route.odb.gz'
    with (variant/'5_2_route.odb').open('rb') as a,gzip.open(archive,'wb') as b:
        shutil.copyfileobj(a,b)
    report=dict(status='QUALIFIED',design=design,method=method,architecture_sha256=arch.sha256(),
        routed_scan_wirelength_um=topology['routed_full_scan_path_net_length_upper_bound_um'],
        DRC_errors=0,structured_metrics=metrics,postroute_verification=topology,
        route_wall_seconds=routed['wall_seconds'],extraction=external_binding(folder/'extracted.spef'),
        archive=external_binding(archive))
    write(folder/'route_result.json',report,immutable=True)
    return report


def references(design):
    preparation=prep(design)
    if preparation['status']!='PLACEMENT_READY_PENDING_REFERENCES':
        return
    folder=baseline_folder(design)
    folder.mkdir(parents=True,exist_ok=True)
    patterns=Path(preparation['patterns']['path'])
    source=Path(preparation['source']['path'])
    try:
        identity,aliases=phase0b_ff_identity_map(source,Path(preparation['placed_netlist']['path']),parse_fan_pat(patterns))
    except ValueError:
        from pact_generalization_identity import identity_map
        identity,proof=identity_map(patterns.parent/'compatible.v',Path(preparation['placed_netlist']['path']),
            parse_fan_pat(patterns),LIB)
        aliases=dict(classification='IMPLEMENTATION_REPAIR',
            repair='Prove every functional source/parity and FF inventory before accepting Q-net renames',
            proof=proof,scientific_method_change=False)
    write(folder/'ff_identity_map.json',dict(records=identity,transparent_aliases=aliases),immutable=True)
    cells=extract_def_scan_cells(Path(preparation['placed_def']['path']),[r['physical_instance'] for r in identity],'CK')
    input_folder=patterns.parent
    order=read(input_folder/'source_scan_order.json')
    one=ScanArchitecture(cells,(ScanChain('chain_0',tuple(order),'test_si','test_so'),))
    arch=generate_architecture(one,2,'B0',map_ppi_patterns(parse_fan_pat(patterns),identity),architecture_seed=101)
    archpath=folder/'B0/architecture.json'
    arch.to_json(archpath)
    refpath=NAMESPACE/f'artifacts/derived/phase0c/{design}/s11/k2/B0.architecture.json'
    arch.to_json(refpath)
    common=folder/'common/3_place.odb'
    execute(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts/phase0c_rewire_odb.py',
        '--source',preparation['source_placed_database']['path'],'--architecture',archpath,'--output',common],folder/'common/rewire')
    shim=NAMESPACE/f'orfs/flow/results/nangate45/{design}/phase0b_s11_B0'
    shim.mkdir(parents=True,exist_ok=True)
    shutil.copy2(preparation['SDC']['path'],shim/'3_place.sdc')
    original=simulate(REPAIRED,FAN/'techlib/mod_nangate45.mdt',source,patterns,folder/'original_workload')
    results=[]
    for method in ('B0','B1','B2','B3T'):
        item=dict(design=design,method=method,status='FAILED',source_revision=METHODS.get(method,('supplied_source',))[0])
        item['generator_status']='PASS' if method=='B0' else 'PENDING'
        stage='PHYSICAL_BACKEND_FAIL'
        try:
            if method!='B0':
                commit,exe=METHODS[method]
                output=folder/method/'generator'
                command=[exe,'-python','-no_init','-exit',ROOT/'scripts/pact_generalization_openroad.py',
                    '--namespace',NAMESPACE,'--design',design,'--method',method,'--commit',commit,
                    '--source',common,'--output',output,'--liberty',ANNOTATED]
                env=dict(os.environ,PACT_ORFS_ROOT=str(NAMESPACE/'orfs'))
                execute(command if method=='B1' else docker(command),folder/method/'generation',env=env)
                item['generator_status']='PASS'
                archpath=output/('architecture.json' if method=='B1' else 'canonical.json')
            candidate=ScanArchitecture.from_json(archpath)
            report=route(design,method,archpath,preparation)
            stage='ATPG_FAIL'
            correctness=serial_correctness(design,candidate,identity,patterns,original,folder/method/'correctness',source)
            item.update(status='QUALIFIED',architecture=external_binding(archpath),architecture_hash=candidate.sha256(),
                exact_scan_order=[list(c.cells) for c in candidate.chains],chain_count=len(candidate.chains),
                routed_scan_wirelength_um=report['routed_scan_wirelength_um'],timing=report['structured_metrics'],
                DRC=report['DRC_errors'],correctness=correctness,
                provenance=external_binding(folder/method/'physical/route_result.json'))
        except Exception as error:
            if item['generator_status']=='PENDING':
                item['generator_status']='FAIL'
            item.update(failure_class=stage,error=str(error),traceback=traceback.format_exc())
            write(result_path(f'failures/{design}_{method}_reference.json'),item,immutable=True)
        results.append(item)
        write(result_path(f'baselines/{design}_references.json'),dict(design=design,records=results))
        print('REFERENCE',design,method,item['status'],item.get('error',''),flush=True)
    try:
        selected=select_reference(results)
    except ValueError as error:
        write(result_path(f'physical/{design}/presearch_qualification.json'),dict(design=design,status='PACT_EXECUTION_BLOCKED',
            failure_class='PHYSICAL_BACKEND_FAIL',error=str(error)),immutable=True)
        return
    write(result_path(f'baselines/{design}_selected.json'),dict(selected,frozen_utc=now(),
        selection_rule='minimum qualified routed scan cost among B0/B1/B2/B3T before PACT search'),immutable=True)
    write(result_path(f'physical/{design}/presearch_qualification.json'),dict(design=design,status='INFRASTRUCTURE_QUALIFIED',
        selected_reference=selected['method'],gates=dict(synthesis='PASS',scan='PASS',ATPG='PASS',topology='PASS',
        placement='PASS',reference_method='PASS',routing='PASS',extraction='PASS',timing='PASS',DRC='PASS')),immutable=True)


def main():
    global ATTEMPT
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--design',choices=DESIGNS)
    p.add_argument('--attempt',choices=('runtime_paths_repaired','functional_identity_repaired','buffer_traversal_repaired'))
    args=p.parse_args()
    ATTEMPT=args.attempt or ''
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PATH='/usr/bin:'+os.environ['PATH'])
    assert sha('/usr/bin/openroad')==read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json')['implementation_binary_sha256']
    assert sha(REPAIRED)==read(ROOT/'results/pact_end_to_end_20261004/upstream_repair/qualification.json')['repaired_executable_sha256']
    # WSL may tear down a mount between executor calls. Restore the existing
    # image read-only within the lifetime of this worker, never rebuild it.
    if subprocess.run(['mountpoint','-q','/mnt/pact-oss-recovery']).returncode:
        subprocess.run(['mount','-o','loop,ro',str(TEMP/'recovery_20261003/build-storage.ext4'),
            '/mnt/pact-oss-recovery'],check=True)
    for path in (ANNOTATED,*(entry[1] for entry in METHODS.values())):
        if not path.is_file():
            raise FileNotFoundError('Qualified runtime input unavailable: '+str(path))
    for design in ([args.design] if args.design else DESIGNS):
        if result_path(f'physical/{design}/presearch_qualification.json').exists():
            continue
        try:
            references(design)
        except Exception as error:
            write(result_path(f'failures/{design}_reference_preparation.json'),dict(design=design,status='PACT_EXECUTION_BLOCKED',
                failure_class='SCAN_TOPOLOGY_FAIL',error=str(error),traceback=traceback.format_exc()),immutable=True)
            print('REFERENCE_PREPARATION_FAILED',design,str(error),flush=True)


if __name__=='__main__':
    main()
