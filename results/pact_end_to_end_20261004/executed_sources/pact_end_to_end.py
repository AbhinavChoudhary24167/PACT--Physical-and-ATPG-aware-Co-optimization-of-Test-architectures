#!/usr/bin/env python3
"""Seal existing qualified physical results and run architecture-bound FAN replay.

No optimizer, objective, workload, placement or backend is changed by this gate.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.integration.permutation import file_hash, read, write
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan
from pact.integration.patterns import fan_workload, export_workload
from pact.integration.permutation import ScanPermutation
from pact.integration.replay import verify, write_recovered_fan
from pact.integration.qualification import simulate, compare_exports

DESIGNS = ('s5378', 's9234', 's15850')
STAGE = ROOT/'results/pact_oss_benchmark/topology_recovery_20261004/stage_a'
COMMITS = dict(B2='6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf',
               B3T='5c3751171685d507939ee7064a67feec786e5219')


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def resolve(path, experiments, dependencies):
    replacements = {'repo://': ROOT, 'run://': experiments, 'dep://': dependencies,
                    '/mnt/d/PACT_EXPERIMENTS/': experiments,
                    '/root/pact-deps/': dependencies}
    for prefix, base in replacements.items():
        if str(path).startswith(prefix):
            return base/str(path)[len(prefix):]
    return Path(path)


def binding(path):
    path = Path(path)
    return dict(path=str(path), sha256=file_hash(path), bytes=path.stat().st_size)


def architecture_path(row, args):
    path = resolve(row['architecture_path'], args.experiments, args.dependencies)
    if path.is_file():
        return path
    # Cleanup removed redundant canonical copies. The executed search retained
    # the same canonical architecture; its semantic hash must match below.
    matches = sorted((args.campaign/row['design']).glob(f'budget_*/architectures/{row["architecture_hash"]}.json'))
    if not matches:
        raise FileNotFoundError(f'No retained architecture {row["architecture_hash"]}')
    return matches[0]


def check(record, args):
    path = resolve(record['path'], args.experiments, args.dependencies)
    if file_hash(path) != record['sha256']:
        raise ValueError('Provenance hash differs: '+str(path))
    return path


def physical(arch, route, measurement, args, output):
    sha = arch.sha256()
    if route['report']['architecture_sha256'] != sha or route['report']['status'] != 'QUALIFIED':
        raise ValueError('Route not qualified for exact architecture')
    report = route['report']
    check(route['report_binding'], args)
    check(route['archive'], args)
    topology = report['postroute_verification']
    expected = {(i,a,b) for i,c in enumerate(arch.chains) for a,b in zip(c.cells,c.cells[1:])}
    observed = {(e['chain'],e['source_ff'],e['dest_ff']) for e in topology['edges']}
    if expected != observed or len(topology['edges']) != len(expected):
        raise ValueError('Routed topology does not equal selected order')
    if (topology['status'] != 'PASS' or not topology['all_chain_inputs_outputs_verified'] or
        not topology['fixed_port_positions_verified'] or topology['scan_ff_count'] != len(arch.cells) or
        topology['K'] != len(arch.chains)):
        raise ValueError('Physical topology qualification failed')
    timing = report['structured_metrics']
    if report['DRC_errors'] != 0:
        raise ValueError('Nonzero detailed-route DRC')
    if any(not math.isfinite(float(timing[k])) or float(timing[k]) < 0 for k in ('setup_wns_ns','hold_wns_ns')):
        raise ValueError('Global-route timing qualification failed')
    if measurement['status'] != 'QUALIFIED':
        raise ValueError('Activity/extraction not qualified')
    for key in ('summary','topology','functional','crosscheck','manifest','simulation_manifest'):
        check(measurement[key], args)
    for key in ('topology','functional','crosscheck'):
        if read(resolve(measurement[key]['path'],args.experiments,args.dependencies))['status'] != 'PASS':
            raise ValueError('Measured correctness failed: '+key)
    manifest = read(resolve(measurement['manifest']['path'],args.experiments,args.dependencies))
    if manifest['fixed_backend']['sha256'] != args.frozen_backend:
        raise ValueError('Different physical backend')
    for key in ('fixed_backend','library','simulation_cells','extraction_rules'):
        check(manifest[key],args)
    row = next(r for r in manifest['rows'] if r['architecture_sha256'] == sha)
    for key in ('source_placed_database','SDC','source_netlist','routed_archive','qualification','workload'):
        check(row[key],args)
    for record in row['inputs'].values():
        check(record,args)
    if row['physical_seed'] != 11 or row['K'] != 2 or row['chain_lengths'] != [len(c.cells) for c in arch.chains]:
        raise ValueError('Physical configuration differs')
    if row['routed_archive']['sha256'] != route['archive']['sha256']:
        raise ValueError('Measurement belongs to another routed database')
    simulation = read(resolve(measurement['simulation_manifest']['path'],args.experiments,args.dependencies))
    if simulation['architecture_sha256'] != sha:
        raise ValueError('Simulation belongs to another architecture')
    # These retained source artifacts connect extraction and simulation to the
    # qualified routed ODB; no new physical campaign is launched.
    for key in ('extracted.spef','routed.odb','routed.v','workload.json','cycles.json','net_mapping.json'):
        check(simulation['inputs'][key],args)
    folder = resolve(measurement['summary']['path'],args.experiments,args.dependencies).parent
    for filename in ('export.execution.json','extract.execution.json','compile.execution.json','simulate.execution.json'):
        execution = read(folder/filename)
        if execution['returncode'] != 0:
            raise ValueError('Failed physical execution: '+filename)
    summary = read(folder/'activity_summary.json')
    check(dict(path=str(folder/'activity.vcd'),sha256=summary['VCD']['sha256']),args)
    scope=summary['scopes']['all_data']
    write(output/'physical_proof.json',dict(route=route,measurement=measurement,
        verified_hashes=True,exact_internal_edges=len(expected),
        condition_identity=dict(backend=manifest['fixed_backend']['sha256'],
            library=manifest['library']['sha256'],extraction_rules=manifest['extraction_rules']['sha256'],
            cells=manifest['simulation_cells']['sha256'],placement=row['source_placed_database']['sha256'],
            SDC=row['SDC']['sha256'],inputs={k:v['sha256'] for k,v in row['inputs'].items()},
            seed=row['physical_seed'],K=row['K'],schedule=(row['capture'],row['load_unload'],row['clock_period_ns']))))
    return dict(SCAN_TOPOLOGY='PASS',ROUTE='PASS',DRC='PASS',TIMING='PASS',EXTRACTION='PASS'), dict(
        routed_scan_wirelength_um=report['routed_full_scan_path_net_length_upper_bound_um'],
        total_routed_wirelength_um=timing.get('total_detailed_route_wirelength_um'),
        E=scope['cap_weighted_ff_transitions']['total'],
        H4=scope['grids']['4']['cap_peak_per_cycle']['maximum'],
        H8=scope['grids']['8']['cap_peak_per_cycle']['maximum'],
        WNS=timing['setup_wns_ns'],TNS=timing['setup_tns_ns'],
        hold_WNS=timing['hold_wns_ns'],hold_TNS=timing['hold_tns_ns'],
        timing_stage='global_route',DRC_count=report['DRC_errors'],extraction_status='PASS',
        physical_runtime_seconds=report['route_wall_seconds'],pattern_count=row['patterns'],
        metric_scope='all_data; ground+pin C*N; H4/H8 source-localized bins/cycle; scan WL is connected scan-net upper bound'), row


def csv_write(path, rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def qualify(args, frozen):
    if args.fan_root is None:
        raise ValueError('--fan-root must name the qualified reporter repair')
    check(frozen['frozen_metrics'],args)
    repair=read(args.output/'upstream_repair/qualification.json')
    if repair['status'] != 'PASS' or file_hash(args.fan_root/'bin/opt/fan') != repair['repaired_executable_sha256']:
        raise ValueError('FAN reporting repair not qualified')
    args.frozen_backend=frozen['backend']['implementation_binary_sha256']
    if file_hash('/usr/bin/openroad') != args.frozen_backend:
        raise ValueError('Frozen OpenROAD backend changed')
    selections=read(args.output/'selected_candidates.json')
    previous=args.output/'canonical_results.json'
    if previous.exists():
        attempts=args.output/'qualification_attempts'
        index=len(list(attempts.glob('*.json')))+1 if attempts.exists() else 1
        write(attempts/f'attempt_{index}.json',read(previous))
    records=[]
    searches=[]
    for design in DESIGNS:
        baseline=frozen['baselines'][design]
        routes=read(STAGE/'routes'/f'{design}.json')['records']
        measurements=read(STAGE/'measurements'/f'{design}.json')['records']
        candidate_routes=read(args.campaign/'routes'/f'{design}.json')['records']
        candidate_measurements=read(args.campaign/'measurements'/f'{design}.json')['records']
        common_patterns=ROOT/f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat'
        identity=read(ROOT/f'artifacts/derived/{design}/ff_identity_map.json')['records']
        netlist=ROOT/f'artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v'
        lib=args.dependencies/'FAN_ATPG/techlib/mod_nangate45.mdt'
        items=[dict(candidate=baseline['method'],method=baseline['method'],architecture=baseline['architecture_file']['path'],
                    architecture_sha256=baseline['architecture_hash'],baseline=True)]+[dict(s,method='PACT',baseline=False) for s in selections[design]]
        original=simulate(args.fan_root/'bin/opt/fan',lib,netlist,common_patterns,
            args.output/'correctness'/design/'original_workload')
        expected=read(args.output/'upstream_repair'/design/'qualified_original/export.json')['statistics']
        if original['statistics'] != expected:
            raise ValueError('Frozen FAN statistics changed')
        conditions=None
        reference_export=None
        for item in items:
            label=item['candidate']; sha=item['architecture_sha256']
            folder=args.output/'correctness'/design/label
            folder.mkdir(parents=True,exist_ok=True)
            record=dict(design=design,method=item['method'],candidate=label,architecture_hash=sha,
                source_commit=baseline['source_commit'] if item['baseline'] else None,
                search_seed=None if item['baseline'] else 11,physical_seed=11,
                qualification_status='FAIL',gates={},provenance={})
            try:
                arch=ScanArchitecture.from_json(Path(item['architecture']))
                validate_scan(arch)
                if arch.sha256()!=sha:
                    raise ValueError('Selected architecture hash differs')
                arch.to_json(args.output/'architectures'/f'{design}_{label}.json')
                record.update(chain_count=len(arch.chains),FF_count=len(arch.cells),chain_lengths=[len(c.cells) for c in arch.chains])
                route=(routes if item['baseline'] else candidate_routes)[sha]
                measure=(measurements if item['baseline'] else candidate_measurements)[sha]
                gates,values,row=physical(arch,route,measure,args,folder)
                record['gates'].update(gates); record.update(values)
                actual=read(folder/'physical_proof.json')['condition_identity']
                if conditions is None:
                    conditions=actual
                elif conditions!=actual:
                    raise ValueError('Comparison physical/workload conditions differ')
                # Parent capacities/endpoints are the already executed solver's
                # start. B3T may permute the capacity multiset, as frozen Stage B allows.
                parent=arch
                search=None
                if not item['baseline']:
                    check(item['architecture_file'],args); check(item['search_origin'],args); check(item['input_receipt'],args)
                    inputs=read(item['input_receipt']['path']); search=read(item['search_origin']['path'])
                    if inputs['physical_reference']['architecture_hash']!=baseline['architecture_hash'] or search['reference_label']!=baseline['method']:
                        raise ValueError('Solver used a different external reference')
                    if file_hash(ROOT/'src/pact/optimizer/stage_b.py')!=inputs['source_files']['src/pact/optimizer/stage_b.py']['sha256']:
                        raise ValueError('Executed optimizer source changed')
                    parents=sorted((args.campaign/design).glob(f'budget_*/architectures/{item["parent_architecture_sha256"]}.json'))
                    if not parents:
                        raise ValueError('Solver parent architecture missing')
                    parent=ScanArchitecture.from_json(parents[0])
                    if parent.sha256()!=item['parent_architecture_sha256']:
                        raise ValueError('Solver parent hash differs')
                    record.update(source_commit=inputs['source_commit'],solver_config=inputs['config'],
                        search_runtime_seconds=search['runtime_seconds'],candidates_evaluated=search['evaluations'],
                        parent_architecture_hash=parent.sha256(),reference_architecture_hash=baseline['architecture_hash'],
                        solver_origin=item['label'],selection_reason=item['route_roles'],predicted_metrics=item['metrics'],
                        scan_HPWL_um=item['metrics']['wire_um'],epsilon=item['epsilon'])
                fan,states=fan_workload(common_patterns,identity,parent)
                permutation=ScanPermutation(parent,arch)
                before,after=export_workload(permutation,states)
                proof,recovered=verify(parent,arch,before,after,states)
                if proof['status']!='PASS':
                    raise ValueError('Independent serial replay failed')
                permutation.to_json(folder/'permutation.json')
                write(folder/'serial_replay.json',proof)
                write_recovered_fan(folder/'patterns_recovered.pat',fan,identity,recovered)
                candidate=simulate(args.fan_root/'bin/opt/fan',lib,netlist,folder/'patterns_recovered.pat',folder/'fan')
                against=original if reference_export is None else reference_export
                fault=compare_exports(against,candidate)
                write(folder/'test_correctness.json',fault)
                if fault['status']!='PASS':
                    raise ValueError('Fault correctness gate failed')
                if item['baseline']:
                    reference_export=candidate
                    baseline_search=read(args.campaign/design/'budget_0.02/search.json')
                    baseline_prediction=next(r for r in baseline_search['baselines'] if r['label']==baseline['method'])
                    record['scan_HPWL_um']=baseline_prediction['metrics']['wire_um']
                stats=candidate['statistics']
                record['gates'].update(ATPG='PASS',FAULT_COVERAGE='PASS',FAULT_IDENTITY='PASS',SERIAL_REPLAY='PASS')
                record.update(target_faults=stats['total'],detected_faults=stats['detected'],
                    undetected_faults=stats['total']-stats['detected'],fault_coverage=100*stats['detected']/stats['total'],
                    FAN_reported_coverage=stats['coverage'],ATPG_pattern_count=stats['patterns'],
                    detected_collapsed_classes=fault['detected_collapsed_classes'],
                    fault_identity_scope=fault['identity_scope'],uncollapsed_member_identity_equivalence='NOT_ENUMERATED')
                if stats['patterns']!=record['pattern_count']:
                    raise ValueError('Physical and FAN workload pattern counts differ')
                if not item['baseline']:
                    ref=next(r for r in records if r['design']==design and r['method']!='PACT')
                    if record['routed_scan_wirelength_um']>ref['routed_scan_wirelength_um']*(1+item['epsilon']):
                        raise ValueError('Candidate violates recorded routed wire budget')
                    record['deltas_percent']={k:100*(record[k]/ref[k]-1) for k in ('routed_scan_wirelength_um','E','H4','H8')}
                else:
                    record['deltas_percent']={k:0. for k in ('routed_scan_wirelength_um','E','H4','H8')}
                record['qualification_status']='QUALIFIED'
                record['runtime']=dict(physical_seconds=record['physical_runtime_seconds'],
                    search_seconds=record.get('search_runtime_seconds'),
                    fan_seconds=read(folder/'fan/execution.json')['runtime_seconds'],physical_and_search_reused=True)
                record['provenance']=dict(physical=binding(folder/'physical_proof.json'),
                    serial=binding(folder/'serial_replay.json'),faults=binding(folder/'test_correctness.json'),
                    complete_fault_export=binding(folder/'fan/export.json'),
                    recovered_patterns=binding(folder/'patterns_recovered.pat'),
                    architecture=binding(args.output/'architectures'/f'{design}_{label}.json'))
            except (ValueError,KeyError,FileNotFoundError,StopIteration) as error:
                record.update(failure_reason=str(error),failure_class='implementation_or_provenance_failure')
                (folder/'gate_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            records.append(record)
            print('END_TO_END',design,label,record['qualification_status'],record.get('failure_reason',''),flush=True)
        for path in sorted((args.campaign/design).glob('budget_*/search.json')):
            run=read(path); inputs=read(path.parent/'inputs.json')
            searches.append(dict(design=design,config=run['config'],reference=run['reference_label'],
                evaluations=run['evaluations'],search_seconds=run['search_seconds'],runtime_seconds=run['runtime_seconds'],
                termination=run['termination'],source_commit=inputs['source_commit'],receipt=binding(path)))
    complete=all(r['qualification_status']=='QUALIFIED' for r in records) and len(records)==12
    status='PACT_END_TO_END_SOLUTION_QUALIFIED' if complete else 'PACT_IMPLEMENTATION_BLOCKED'
    write(args.output/'canonical_results.json',dict(schema='pact_end_to_end_results_v1',status=status,
        starting_sha=frozen['starting_sha'],qualification_source_sha=git('rev-parse','HEAD'),
        physical_results_reused=True,optimizer_unchanged=True,searches=searches,records=records,
        remaining_blockers=[] if complete else [dict(design=r['design'],candidate=r['candidate'],reason=r.get('failure_reason')) for r in records if r['qualification_status']!='QUALIFIED'],
        identity_limit='Complete identity equality is established for frozen FAN collapsed target classes and their weights; individual uncollapsed equivalence-class members are not enumerated'))
    report(args,records,status,searches)


def report(args,records,status,searches):
    keys=('design','candidate','routed_scan_wirelength_um','E','H4','H8','WNS','DRC_count','fault_coverage','qualification_status')
    flat=[{k:r.get(k) for k in keys} | {f'delta_{k}_percent':r.get('deltas_percent',{}).get(k) for k in ('routed_scan_wirelength_um','E','H4','H8')} for r in records]
    csv_write(args.output/'comparison.csv',flat)
    lines=[status,'',
        'References are frozen by minimum qualified routed scan cost among B0/B1/B2/B3T before this gate. All nine prior Stage-B selections are retained; the optimizer, objective, seeds, workload and common backend are unchanged. Saved search/physical runs are reused with verified input/output hashes, exact routed edges, extraction and simulation proofs.', '',
        '| Design | Method | Routed scan WL (µm) | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS (ns) | DRC | Fault coverage % | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in records:
        if r['qualification_status']!='QUALIFIED':
            lines.append(f'| {r["design"]} | {r["candidate"]} | — | — | — | — | — | — | — | — | — | — | — | FAIL: {r.get("failure_reason")} |')
            continue
        d=r['deltas_percent']
        lines.append(f'| {r["design"]} | {r["candidate"]} | {r["routed_scan_wirelength_um"]:.3f} | {d["routed_scan_wirelength_um"]:.4f} | {r["E"]:.3f} | {d["E"]:.4f} | {r["H4"]:.5f} | {d["H4"]:.4f} | {r["H8"]:.5f} | {d["H8"]:.4f} | {r["WNS"]:.5f} | {r["DRC_count"]} | {r["fault_coverage"]:.6f} | QUALIFIED |')
    lines += ['',
        'E is extracted ground-plus-pin C×transitions in fF·transitions. H4/H8 are the frozen maximum source-bin/cycle metrics. Routed scan WL includes shared functional branches and is an upper bound, not exact scan-only attribution. WNS is the existing global-route setup value; hold WNS/TNS are in the canonical dataset. Detailed-route DRC is zero. No signoff timing, watts or IR-drop claim is made.', '',
        'FAN correctness uses the original functional circuit/library after independent serial recovery for each exact selected architecture. Complete collapsed target universes, equivalence weights and detected class identities match the frozen reference; all simulated pattern counts and weighted full/detected counts agree. The original extraction premarks some CK/SE/SI faults detected, and that semantics is preserved. Individual uncollapsed class-member identities are not enumerated and are not claimed equivalent.', '',
        'The reporting-only FAN repair is isolated on fix/report-fault-scan-identities, based on 26b2b36c0e9db11a4b6d9e759df6e44357121f39. It preserves extraction and simulation statistics on all three frozen workloads. See upstream_repair/qualification.json and reporter.patch.', '',
        'Searches: seed 11, K=2, epsilons 0.02/0.05/0.10, 300 seconds per mutation loop, 20,000 evaluations, 2,000 stagnation attempts, 16 neighbors, segment 8, archive 16, 150-attempt lane restarts and existing balanced weights (1,1,1). There are '+str(sum(s['evaluations'] for s in searches))+' exact candidate evaluations across the nine saved runs. Complete configuration, source, parent/reference hashes, selection roles and runtimes are in selected_candidates.json and canonical_results.json. No search or route was repeated for this sealing task.', '',
        'The balanced C1 selections improve E/H4/H8 for s5378 and s9234 with routed wire costs. s15850 C1 regresses H4; its retained best_E C2 improves all three activity coordinates. All s9234 selections remain dominated on the original wire/E/H8 Stage-A front, while the frozen four-coordinate analysis retains H4 tradeoffs. All nine outcomes are reported; no baseline or objective was changed to make them positive.']
    (args.output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def freeze(args):
    rows = csv_rows(STAGE/'implemented_metrics.csv')
    baselines = {}
    for design in DESIGNS:
        valid = [r for r in rows if r['design'] == design and r['status'] == 'QUALIFIED'
                 and r['method'] in ('B0', 'B1', 'B2', 'B3T')]
        selected = min(valid, key=lambda r: float(r['routed_scan_path_cost_um']))
        if selected['method'] not in ('B2', 'B3T'):
            raise ValueError('External minimum differs from frozen Stage-B reference')
        path = architecture_path(selected, args)
        arch = ScanArchitecture.from_json(path)
        if arch.sha256() != selected['architecture_hash']:
            raise ValueError('External reference architecture hash differs')
        baselines[design] = dict(selected, source_commit=COMMITS[selected['method']],
            qualified=True, architecture_file=binding(path),
            selection_reason='Minimum qualified measured routed scan-path net-length upper bound among B0/B1/B2/B3T; existing Stage-B reference rule',
            external_alternatives=[{k:r[k] for k in ('method','architecture_hash','status','routed_scan_path_cost_um')} for r in valid])
    data = dict(schema='pact_frozen_external_references_v1',
        starting_sha=git('rev-parse','HEAD'), starting_branch=git('branch','--show-current'),
        frozen_metrics=binding(STAGE/'implemented_metrics.csv'), baselines=baselines,
        backend=read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json'))
    target = args.output/'frozen_baselines.json'
    if target.exists():
        prior = read(target)
        if prior['baselines'] != baselines or prior['frozen_metrics'] != data['frozen_metrics']:
            raise ValueError('Frozen baseline manifest would change')
        return prior
    write(target, data)
    selections = {}
    for design in DESIGNS:
        entries = read(args.campaign/'selection'/f'{design}.json')
        selections[design] = [dict(row, candidate=f'{design}_C{i+1}',
            architecture_file=binding(row['architecture']), search_seed=11,
            search_origin=binding(args.campaign/design/f'budget_{row["epsilon"]:.2f}'/'search.json'),
            input_receipt=binding(args.campaign/design/f'budget_{row["epsilon"]:.2f}'/'inputs.json'))
            for i,row in enumerate(entries)]
        if len(entries) > 3:
            raise ValueError('Existing representative set exceeds three orders')
    write(args.output/'selected_candidates.json', selections)
    audit = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
        starting_sha=data['starting_sha'], branch=data['starting_branch'],
        starting_worktree=git('status','--porcelain=v1'),
        existing_milestones=['PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE','PACT_EXTERNAL_BENCHMARK_COMPLETE','PACT_STAGE_B_MULTI_DESIGN_CONVERGENCE'],
        implementation_map=dict(
            optimizer=['src/pact/optimizer/stage_b.py','src/pact/optimizer/search.py'],
            evaluator=['src/pact/optimizer/candidate_stateful.py','src/pact/optimizer/candidate_sensitive.py','src/pact/optimizer/candidate_physical.py','src/pact/optimizer/stateful_geometry.py'],
            rewiring=['scripts/phase0c_rewire_odb.py','scripts/tcl/rewire_scan.tcl'],
            topology=['scripts/pact_oss_receiver_connectivity.py','scripts/pact_oss_topology_tests.py'],
            fan=['src/pact/integration/faults.py','src/pact/integration/patterns.py','src/pact/integration/replay.py'],
            physical=['scripts/pact_v2.py','scripts/pact_oss_receiver_measure.py','scripts/physical_effect_export.py','src/pact/physical_effect.py'],
            regressions=['tests/unit/test_end_to_end.py','tests/unit/test_stage_b.py','tests/unit/test_oss_results.py','tests/unit/test_oss_scientific.py']),
        reuse='All nine saved Stage-B searches/selections and qualified routes/extractions/activity; no historical validation matrix rerun',
        gap='Architecture-bound serial/FAN replay and complete detected collapsed-fault-class export; known FAN reporter crash',
        methodology_change='None; any objective/predictor/operator change is OUT_OF_SCOPE_METHOD_CHANGE')
    write(args.output/'audit.json', audit)
    print('FROZEN', {d:b['method'] for d,b in baselines.items()}, flush=True)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'qualify'])
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--experiments', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'results/pact_end_to_end_20261004')
    parser.add_argument('--fan-root', type=Path)
    args = parser.parse_args()
    manifest = freeze(args)
    if args.action == 'qualify':
        qualify(args, manifest)


if __name__ == '__main__':
    main()
