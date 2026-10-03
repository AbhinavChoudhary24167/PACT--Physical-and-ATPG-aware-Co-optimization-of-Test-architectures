#!/usr/bin/env python3
"""Verify both historical and versioned evidence seals without rerunning work."""
from pact_oss_benchmark import OUT, binding, read, write
from pact_oss_receiver_stage_a import STAGE, PREVIOUS, gate, checked as check_binding


def audit():
    state=read(STAGE/'status.json')
    if (state.get('stop_condition')=='B3R_GENERATED_SCAN_OUTPUT_TOPOLOGY_FAILED'
            and state.get('stage_a')=='PACT_STAGE_A_INCOMPLETE'
            and state.get('B3R')=='BUILD_PASS_COMMAND_PASS_ARCHITECTURE_QUALIFICATION_FAILED'):
        from pact_oss_receiver_seal_blocked import check_blocked_evidence
        check_blocked_evidence()
    else:
        gate()
    check_binding(state['previous_recovery_seal'])
    previous=read(PREVIOUS/'stage_a/evidence_manifest.json')
    previous_checked=0
    for group in ('artifacts','benchmark_sources','external_artifacts'):
        for item in previous[group].values():
            check_binding(item)
            previous_checked+=1
    manifest=read(STAGE/'evidence_manifest.json')
    checked=0
    for group in ('artifacts','benchmark_sources','external_artifacts'):
        for name,item in manifest[group].items():
            if binding(item['path'])['sha256']!=item['sha256']:
                raise ValueError('Versioned sealed evidence changed: '+group+'/'+name)
            checked+=1
            if checked%100==0:
                print('SEALED_BINDINGS_VERIFIED',checked,flush=True)
    if state['Stage_B'] not in ('NOT_STARTED_USER_SCOPE_STAGE_A_ONLY','NOT_STARTED_STAGE_A_STOP_CONDITION') or state['P0_model_changed'] or state['P0_selection_changed']:
        raise ValueError('Stage-A scope or frozen P0 boundary changed')
    target=STAGE/'final_integrity_audit.json'
    if not target.exists():
        write(target,dict(status='PASS',new_sealed_bindings_checked=checked,previous_recovery_bindings_checked=previous_checked,
            original_frozen_bindings=454,original_sealed_bindings=122,original_canonical_architectures=24,
            evidence_manifest=binding(STAGE/'evidence_manifest.json'),Stage_B=state['Stage_B'],classification=state['stage_a']))
    print('VERSIONED_STAGE_A_FINAL_INTEGRITY_PASS',checked,flush=True)


if __name__=='__main__':
    audit()
