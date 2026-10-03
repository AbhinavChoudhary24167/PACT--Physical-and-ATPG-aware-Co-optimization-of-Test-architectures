"""Independently compare emitted Verilog topology with the saved-ODB observation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[7]
FOLDER=Path(__file__).resolve().parent
RAW=Path('D:/PACT_EXPERIMENTS/tmp/pact_oss_20261003/receiver_recovery_20261003/B3R_openroad_10666_repaired/s5378')
LINUX_ROOT='/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/'


def read(path):
    return json.loads(path.read_text())


def binding(path):
    try:
        location=LINUX_ROOT+path.relative_to(ROOT).as_posix()
    except ValueError:
        location='/mnt/d/'+path.relative_to(Path('D:/')).as_posix()
    return dict(path=location,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


observation=read(RAW/'connectivity.json')
assert observation['status']=='OBSERVATION_ONLY' and not observation['optimizer_executed'] and not observation['connectivity_modified']
after=observation['after']
before=observation['before']
assert after['sha256']==binding(RAW/'generated.odb')['sha256']
assert before['sha256']==binding(RAW/'generator_input.odb')['sha256']
text=(RAW/'generated.v').read_text()
ff={name:dict(re.findall(r'\.(\w+)\s*\(([^)]*)\)',body))
    for name,body in re.findall(r'\bSDFF_X1\s+(\S+)\s*\((.*?)\);',text,re.S)}
assert set(ff)==set(after['cells'])
for name,pins in ff.items():
    assert all(pins[pin]==after['cells'][name]['pins'][pin] for pin in ('SI','Q','D','CK'))
by_si={}
for name,pins in ff.items():
    by_si.setdefault(pins['SI'],[]).append(name)
outputs=dict(re.findall(r'assign\s+(test_so_[01])\s*=\s*([^;]+);',text))
assert outputs=={name:after['ports'][name]['name'] for name in ('test_so_0','test_so_1')}
paths=[]
metadata=[]
for ci in range(2):
    net=after['ports'][f'test_si_{ci}']['name']
    order=[]
    seen=set()
    while net not in seen:
        seen.add(net)
        matches=by_si.get(net,[])
        if not matches:
            break
        assert len(matches)==1
        name=matches[0]
        order.append(name)
        net=ff[name]['Q']
    odb_path=after['traces'][ci]
    assert order==odb_path['ff_order'] and net==odb_path['terminal_net']['name']
    assert odb_path['error']=='CANNOT_TRACE_FIXED_SI_SO'
    positions={name:[i+1 for i,cell in enumerate(order) if ff[cell]['Q']==output_net]
        for name,output_net in outputs.items()}
    paths.append(dict(chain=ci,FF_count=len(order),first=order[0],last=order[-1],terminal_net=net,
        FF_order=order,fixed_output_positions=positions,terminal_has_fixed_SO=False,
        generated_verilog_matches_saved_ODB_order=True))
    listing=after['scan_metadata'][ci]['list_iteration']
    mismatch=[i+1 for i,(left,right) in enumerate(zip(listing,order)) if left!=right]
    metadata.append(dict(chain=ci,same_membership=set(listing)==set(order),
        metadata_FF_count=len(listing),physical_FF_count=len(order),different_positions=len(mismatch),
        first_mismatch_slot=mismatch[0] if mismatch else None,metadata_prefix=listing[:3],physical_prefix=order[:3],
        scope='Observed metadata iteration disagrees with physical SI-to-Q order; it cannot substitute for endpoint-qualified connectivity'))
assert [item['FF_count'] for item in paths]==[90,89]
assert not set(paths[0]['FF_order'])&set(paths[1]['FF_order'])
assert set(paths[0]['FF_order'])|set(paths[1]['FF_order'])==set(ff)
unchanged=observation['FF_inventory_placement_functional_unchanged']
assert unchanged
for name in ff:
    left,right=before['cells'][name],after['cells'][name]
    assert all(left[key]==right[key] for key in ('location','master','orientation'))
    assert all(left['pins'][key]==right['pins'][key] for key in ('D','CK'))
build=read(FOLDER.parents[1]/'build_result.json')
repair=read(FOLDER.parents[1]/'repair/repair_manifest.json')
source=read(FOLDER/'inherited_restitch_source.json')
assert source['byte_identical_to_upstream_base']
assert source['upstream_base_sha']==repair['upstream_base_sha']
assert source['repair_commit_sha']==repair['repair_commit_sha']==build['commit']
execution=read(FOLDER/'connectivity_read_attempt2.execution.json')
assert execution['returncode']==0
result=dict(status='SOURCE_TOPOLOGY_BLOCKER_STOPPED',method='B3R',
    method_display='B3R — PR #10666 + minimal compile repair',design='s5378',
    timestamp=datetime.now(timezone.utc).isoformat(),upstream_base_sha=repair['upstream_base_sha'],
    repair_commit_sha=repair['repair_commit_sha'],patch_sha256=repair['patch_sha256'],binary_sha256=build['binary_sha256'],
    topology_qualification='FAIL',actual_chain_lengths=[90,89],actual_terminal_nets=[item['terminal_net'] for item in paths],
    fixed_SO_terminates_generated_chains=False,FF_functional_placement_unchanged=unchanged,
    generated_ODB=binding(RAW/'generated.odb'),generated_verilog=binding(RAW/'generated.v'),
    saved_ODB_observation=binding(RAW/'connectivity.json'),read_execution=binding(FOLDER/'connectivity_read_attempt2.execution.json'),
    source_evidence=dict(inherited_restitch_provenance=binding(FOLDER/'inherited_restitch_source.json'),
        source_provenance_script=binding(FOLDER/'independent_source_provenance.py'),
        independent_netlist_script=binding(Path(__file__).resolve()),
        frozen_native_adapter=binding(ROOT/'scripts/pact_oss_native.py'),
        repair_manifest=binding(FOLDER.parents[1]/'repair/repair_manifest.json'),
        build_result=binding(FOLDER.parents[1]/'build_result.json')),
    inherited_source=source['inherited_source'],inherited_source_byte_identical_to_upstream_base=True,
    failure_class='INHERITED_B3_RESTITCH_PHYSICAL_SO_ENDPOINT_SEMANTICS',
    adapter_assumption_failure=False,
    primary_failure='RestitchChain changes SI/interior nets and only updates scan_out metadata. The fixed SO BTerms remain on intermediate FF Q nets and neither optimized tail reaches its fixed physical SO.',
    paths=paths,metadata_iteration=metadata,
    additional_source_patch_applied=False,additional_generator_runs=0,downstream_physical_runs=0,
    remaining_designs={'s9234':'NOT_ATTEMPTED','s15850':'NOT_ATTEMPTED'},
    qualification_recommendation='Preserve source topology blocker, keep Stage-A routes and measurements gated, and seal the incomplete result without fabricating or restitching a canonical architecture',
    fixed_backend_read_attempt=dict(returncode=1,reason='Generated ODB schema0.132 exceeds fixed reader schema0.129; no database read or modification occurred'))
target=FOLDER/'independent_diagnosis.json'
if target.exists():
    raise ValueError('Independent diagnosis receipt already exists')
target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({key:result[key] for key in ('status','actual_chain_lengths','actual_terminal_nets','fixed_SO_terminates_generated_chains','FF_functional_placement_unchanged')},indent=2))
