#!/usr/bin/env python3
"""Verify both historical and versioned evidence seals without rerunning work."""
from pathlib import Path
import hashlib
import os

from pact_oss_benchmark import OUT, binding, read, write
from pact_oss_stage_a import STAGE, gate
from pact_oss_recovery import RECOVERY, MOUNT


def audit():
    state=read(STAGE/'status.json')
    if state['stage_a']=='PACT_STAGE_A_INCOMPLETE' and state.get('B3')=='COMPILATION_FAILED_SOURCE_PATCH_REQUIRED':
        from pact_oss_seal_recovery_blocked import check_build_evidence
        check_build_evidence()
    else:
        gate()
    from pact_oss_verify import audit as original_audit
    original_audit()
    manifest=read(STAGE/'evidence_manifest.json')
    checked=0
    for group in ('artifacts','benchmark_sources','external_artifacts'):
        for name,item in manifest[group].items():
            if binding(item['path'])['sha256']!=item['sha256']:
                raise ValueError('Versioned sealed evidence changed: '+group+'/'+name)
            checked+=1
            if checked%100==0:
                print('SEALED_BINDINGS_VERIFIED',checked,flush=True)
    for name in ('B2_openroad_10176','B3_openroad_10666'):
        source=read(RECOVERY/'baselines'/name/'source_manifest.json')
        for relative,expected in source['pinned_source_blobs_checked'].items():
            path=MOUNT/name/'source'/relative
            actual=hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
            if actual!=expected:
                raise ValueError('Pinned algorithm source changed: '+name+'/'+relative)
    if state['Stage_B'] not in ('NOT_STARTED_USER_SCOPE_STAGE_A_ONLY','NOT_STARTED_STAGE_A_STOP_CONDITION') or state['P0_model_changed'] or state['P0_selection_changed']:
        raise ValueError('Stage-A scope or frozen P0 boundary changed')
    target=STAGE/'final_integrity_audit.json'
    if not target.exists():
        write(target,dict(status='PASS',new_sealed_bindings_checked=checked,
            original_frozen_bindings=454,original_sealed_bindings=122,original_canonical_architectures=24,
            evidence_manifest=binding(STAGE/'evidence_manifest.json'),Stage_B=state['Stage_B'],classification=state['stage_a']))
    print('VERSIONED_STAGE_A_FINAL_INTEGRITY_PASS',checked,flush=True)


if __name__=='__main__':
    audit()
