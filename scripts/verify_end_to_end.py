#!/usr/bin/env python3
"""Verify sealed end-to-end evidence without search, EDA or FAN execution."""
import argparse
import csv
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.integration.permutation import file_hash,read,write
from pact.integration.qualification import parse_export,compare_exports
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan
from pact.test.pattern_parser import parse_fan_pat


def verify(output):
    dataset=read(output/'canonical_results.json')
    frozen=read(output/'frozen_baselines.json')
    selected=read(output/'selected_candidates.json')
    for name,expected in dataset['executed_qualification_sources'].items():
        if file_hash(output/'executed_sources'/name)!=expected:
            raise ValueError('Executed qualification source changed')
    repair=read(output/'upstream_repair/qualification.json')
    if (file_hash(output/'upstream_repair/qualification.json')!=dataset['upstream_implementation_repair']['qualification_sha256'] or
        repair['repair_commit']!=dataset['upstream_implementation_repair']['commit']):
        raise ValueError('Repair qualification binding differs')
    for design,label in dataset['primary_candidates'].items():
        if 'balanced' not in next(r for r in selected[design] if r['candidate']==label)['route_roles']:
            raise ValueError('Primary candidate differs from existing balanced selection')
    metrics=ROOT/'results/pact_oss_benchmark/topology_recovery_20261004/stage_a/implemented_metrics.csv'
    if file_hash(metrics)!=frozen['frozen_metrics']['sha256']:
        raise ValueError('Frozen Stage-A measurements changed')
    references={}
    records=dataset['records']
    if len(records)!=12 or len({(r['design'],r['candidate']) for r in records})!=12:
        raise ValueError('Missing or duplicate final record')
    historical={r['candidate']:r for r in csv.DictReader((ROOT/'results/pact_stage_b/routed_results.csv').open())}
    for row in records:
        design,label=row['design'],row['candidate']
        folder=output/'correctness'/design/label
        if row['qualification_status']!='QUALIFIED' or set(row['gates'].values())!={'PASS'}:
            raise ValueError('Failed final qualification: '+label)
        for key,bound in row['provenance'].items():
            path=folder/'fan/export.json' if key=='complete_fault_export' else (
                output/'architectures'/f'{design}_{label}.json' if key=='architecture' else
                folder/ {'physical':'physical_proof.json','serial':'serial_replay.json',
                         'faults':'test_correctness.json','recovered_patterns':'patterns_recovered.pat'}[key])
            if file_hash(path)!=bound['sha256']:
                raise ValueError('Corrupted final artifact: '+str(path))
        architecture=ScanArchitecture.from_json(output/'architectures'/f'{design}_{label}.json')
        validate_scan(architecture)
        if architecture.sha256()!=row['architecture_hash'] or (len(architecture.cells),len(architecture.chains))!=(row['FF_count'],row['chain_count']):
            raise ValueError('Final architecture identity/dimensions differ')
        exported=parse_export((folder/'fan/stdout.txt').read_text())
        if exported!=read(folder/'fan/export.json'):
            raise ValueError('Native FAN output differs from canonical export')
        if design not in references:
            if row['architecture_hash']!=frozen['baselines'][design]['architecture_hash']:
                raise ValueError('First comparison row must be frozen reference')
            original=parse_export((output/'correctness'/design/'original_workload/stdout.txt').read_text())
            if compare_exports(original,exported)['status']!='PASS':
                raise ValueError('Reference does not preserve original fault universe/detection')
            references[design]=(row,exported)
        reference,reference_export=references[design]
        if compare_exports(reference_export,exported)['status']!='PASS':
            raise ValueError('Detected identities differ: '+label)
        if parse_fan_pat(folder/'patterns_recovered.pat')!=parse_fan_pat(ROOT/f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat'):
            raise ValueError('Recovered functional workload differs: '+label)
        proof=read(folder/'physical_proof.json')
        if row['gates']['EXTRACTION']!='PASS' or proof['route']['report']['DRC_errors']!=row['DRC_count']:
            raise ValueError('Physical results differ from proof')
        if row['method']=='PACT':
            item=next(r for r in selected[design] if r['candidate']==label)
            if row['architecture_hash']!=item['architecture_sha256']:
                raise ValueError('PACT row differs from pre-route selection')
            for key,source in (('routed_scan_wirelength_um','scan_wire_um'),('E','E'),('H4','H4'),('H8','H8'),('WNS','setup_WNS_ns')):
                if row[key]!=float(historical[label][source]):
                    raise ValueError('Measured value changed: '+label+' '+key)
            for key,delta in row['deltas_percent'].items():
                if abs(delta-100*(row[key]/reference[key]-1))>1e-10:
                    raise ValueError('Delta uses another reference: '+label)
            if row['routed_scan_wirelength_um']>reference['routed_scan_wirelength_um']*(1+row['epsilon']):
                raise ValueError('Routed budget violated')
    if dataset['status']!='PACT_END_TO_END_SOLUTION_QUALIFIED' or dataset['remaining_blockers']:
        raise ValueError('Final milestone not qualified')
    completion=read(output/'completion.json')
    if completion['canonical_results_sha256']!=file_hash(output/'canonical_results.json'):
        raise ValueError('Completion dataset binding differs')
    result=dict(status='PASS',records_checked=12,detected_identity_comparisons=12,
        datasets=binding(output/'canonical_results.json'),
        frozen_baselines=binding(output/'frozen_baselines.json'),
        physical_results_unchanged=True,no_search_or_EDA_execution=True)
    write(output/'final_verification.json',result)
    return result


def binding(path):
    return dict(path=str(path),sha256=file_hash(path))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'results/pact_end_to_end_20261004')
    args=parser.parse_args()
    print(verify(args.results))
