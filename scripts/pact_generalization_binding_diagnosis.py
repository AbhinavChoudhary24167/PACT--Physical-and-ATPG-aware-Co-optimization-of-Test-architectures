#!/usr/bin/env python3
"""Read-only diagnosis of stale frozen receipt bindings; no EDA execution."""
import hashlib
from pathlib import Path
import subprocess
from pact_generalization import ROOT,OUT,read,sha,write,now


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest=read(OUT/'manifests/pact_v1_frozen_external_manifest.json')
    failures=[r for r in manifest['files'] if r['status']!='PASS']
    expected={r['original_binding']['sha256'] for r in failures}
    matches={h:[] for h in expected}
    candidates=[]
    for folder in (ROOT/'results/pact_end_to_end_20261004',ROOT/'results/pact_oss_benchmark',ROOT/'results/pact_stage_b',ROOT/'scripts'):
        candidates.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py','.json'))
    for row in failures:
        path=Path(row['resolved_path'])
        if path.is_file():
            candidates.append(path)
    for path in sorted(set(candidates)):
        data=path.read_bytes()
        variants={'bytes':data,'LF':data.replace(b'\r\n',b'\n')}
        variants['CRLF']=variants['LF'].replace(b'\n',b'\r\n')
        for form,content in variants.items():
            h=digest(content)
            if h in matches:
                matches[h].append(dict(path=str(path),transform=form))
    for source in ('scripts/physical_effect.py','scripts/physical_effect_export.py','scripts/pact_oss_receiver_measure.py'):
        commits=subprocess.check_output(['git','log','--all','--format=%H','--',source],cwd=ROOT,text=True).splitlines()
        for commit in commits:
            result=subprocess.run(['git','show',commit+':'+source],cwd=ROOT,capture_output=True)
            if result.returncode:
                continue
            h=digest(result.stdout)
            if h in matches:
                matches[h].append(dict(git_commit=commit,path=source,transform='git blob'))
    result=dict(timestamp_utc=now(),failures=failures,exact_recovery_candidates=matches,
        no_historical_tool_executions=True,no_historical_writes=True)
    write(OUT/'manifests/stale_binding_diagnosis.json',result,immutable=True)
    for row in failures:
        b=row['original_binding']
        print(b['path'],len(matches[b['sha256']]),'exact matches',flush=True)


if __name__=='__main__':
    main()
