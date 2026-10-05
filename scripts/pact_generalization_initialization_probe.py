#!/usr/bin/env python3
"""Read-only probe of the frozen new-design input-loading contract."""
from dataclasses import asdict
import math
import subprocess
import traceback
from pact_generalization import ROOT,OUT,binding,now,read,write
from pact.optimizer.stage_b import Config
from pact_stage_b import load


def main():
    benchmark=read(OUT/'manifests/generalization_benchmark_manifest.json')
    rows=[]
    for design in benchmark['designs']:
        n=design['FF_count']
        rows.append(dict(design=design['design'],FF_count=n,chain_count=2,
            configs=[asdict(Config(epsilon=e,seconds=300*max(1,math.ceil(n/600)))) for e in (.02,.05,.10)],
            seeds=[11],primary_role='balanced',route_limit=3,
            expected_start_labels=['B2','B3T','P0'],
            P0_state='NOT_YET_CREATED_FOR_UNSEEN_DESIGN',source_configuration='Frozen qualified core plus preregistered runtime scaling rule'))
    write(OUT/'searches/exact_configuration.json',dict(schema='pact_generalization_search_config_v1',
        created_utc=now(),presearch=True,records=rows,
        optimizer_sources=[binding(ROOT/p) for p in ('src/pact/optimizer/stage_b.py','src/pact/optimizer/candidate_stateful.py',
            'src/pact/optimizer/candidate_sensitive.py','src/pact/optimizer/stateful_geometry.py','src/pact/optimizer/search.py')]),immutable=True)
    try:
        load('s1196')
        raise AssertionError('Frozen loader unexpectedly accepted an unseen design')
    except KeyError as error:
        result=dict(schema='pact_generalization_initialization_blocker_v1',created_utc=now(),
            classification='ENGINEERING_SCALABILITY_BLOCKER',subtype='UNSEEN_INPUT_INITIALIZATION',
            design='s1196',failure_class='TOOL_BUG',error=repr(error),traceback=traceback.format_exc(),
            frozen_loader=binding(ROOT/'scripts/pact_stage_b.py'),
            dependency_loader=binding(ROOT/'scripts/pact_v2.py'),
            evidence='pact_stage_b.load -> pact_candidate_sensitive.load -> pact_v2.load -> DESIGNS[design]; table has only the historical three designs',
            required_initialization='Current Stage-B loader consumes qualified B2/B3T orders and a pre-existing balanced P0 endpoint produced through the prior working/v2/candidate-sensitive/stateful experiment chain',
            outstanding_decision='Define how the full frozen precursor pipeline supplies P0 on unseen designs; no substitute seed or omitted P0 has been authorized',
            scientific_method_changes=0,PACT_searches_executed=0,
            runtime_scalability_measured=False,
            question='Reproduce the full frozen P0 pipeline, or stop if P0 initialization cannot be reproduced?')
        write(OUT/'failures/frozen_initialization_contract.json',result,immutable=True)
        print(result['classification'],result['subtype'],result['error'])


if __name__=='__main__':
    main()
