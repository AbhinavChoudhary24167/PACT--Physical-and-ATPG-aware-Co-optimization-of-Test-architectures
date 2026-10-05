#!/usr/bin/env python3
"""Recover byte-identical receipts additively, without editing frozen paths."""
import hashlib
from pathlib import Path
import subprocess
from pact_generalization import ROOT,OUT,binding,now,read,sha,write


def relative(uri):
    if uri.startswith('repo://'):
        return uri[7:]
    marker='/PACT/PACT/'
    if marker in uri:
        return uri.split(marker,1)[1]
    return None


def variants(data):
    lf=data.replace(b'\r\n',b'\n')
    return [('bytes',data),('LF',lf),('CRLF',lf.replace(b'\n',b'\r\n'))]


def main():
    diagnosis=read(OUT/'manifests/stale_binding_diagnosis.json')
    original=read(OUT/'manifests/pact_v1_frozen_external_manifest.json')
    recovered={}
    missing=[]
    for failure in diagnosis['failures']:
        b=failure['original_binding']
        expected=b['sha256']
        if expected in recovered:
            continue
        candidates=diagnosis['exact_recovery_candidates'][expected]
        data=None
        source=None
        for item in candidates:
            if 'git_commit' in item:
                data=subprocess.check_output(['git','show',item['git_commit']+':'+item['path']],cwd=ROOT)
            else:
                raw=Path(item['path']).read_bytes()
                data=dict(variants(raw))[item['transform']]
            if hashlib.sha256(data).hexdigest()==expected:
                source=item
                break
        if source is None:
            path=relative(b['path'])
            commits=subprocess.check_output(['git','log','--all','--format=%H','--',path],cwd=ROOT,text=True).splitlines() if path else []
            for commit in commits:
                result=subprocess.run(['git','show',commit+':'+path],cwd=ROOT,capture_output=True)
                if result.returncode:
                    continue
                for transform,raw in variants(result.stdout):
                    if hashlib.sha256(raw).hexdigest()==expected:
                        data=raw
                        source=dict(git_commit=commit,path=path,transform=transform)
                        break
                if source:
                    break
        if source is None:
            missing.append(b)
            continue
        path=OUT/'manifests/retained_bindings'/f"{expected}_{Path(b['path']).name}"
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            assert sha(path)==expected
        else:
            path.write_bytes(data)
        recovered[expected]=dict(binding=binding(path),exact_recovery_source=source)
    rows=[]
    for row in original['files']:
        b=row['original_binding']
        recovery=recovered.get(b['sha256']) if row['status']!='PASS' else None
        rows.append(dict(row,final_status='PASS' if row['status']=='PASS' or recovery else row['status'],
                         recovery=recovery))
    result=dict(schema='pact_v1_frozen_relocated_manifest_v1',created_utc=now(),
        status='PACT_V1_CORE_FREEZE_VERIFIED' if not missing else 'FROZEN_PROVENANCE_RECOVERY_BLOCKED',
        original_manifest=binding(OUT/'manifests/pact_v1_frozen_manifest.json'),
        initial_external_inventory=binding(OUT/'manifests/pact_v1_frozen_external_manifest.json'),
        classification='IMPLEMENTATION_REPAIR',repair='Exact byte preservation and path relocation only',
        historical_writes=0,historical_tool_executions=0,bindings_checked=len(rows),
        unique_receipts_recovered=len(recovered),unresolved=missing,files=rows)
    write(OUT/'manifests/pact_v1_frozen_relocated_manifest.json',result,immutable=True)
    print(result['status'],len(recovered),'exact receipts recovered',len(missing),'unresolved')
    for b in missing:
        print('UNRESOLVED',b['path'])


if __name__=='__main__':
    main()
