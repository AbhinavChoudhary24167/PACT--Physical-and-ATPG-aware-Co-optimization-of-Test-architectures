#!/usr/bin/env python3
"""Publish the approved generic writer repair independently of DFT changes."""
from datetime import datetime, timezone
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import pact_oss_topology as r
import pact_oss_serialization as s
import pact_oss_receiver_upstream as credentials
from pact_oss_benchmark import binding, read, write

TARGET='The-OpenROAD-Project/OpenSTA'
FORK='AbhinavChoudhary24167/OpenSTA'
BRANCH='fix/verilog-input-alias'
OUT=s.SERIAL/'upstream'


def main():
    r.ensure()
    s.activate()
    repair=read(s.REPAIR/'repair_manifest.json')
    if read(s.FOLDER/'qualification.json')['status']!='PASS' or read(s.SERIAL/'after.proof.json')['status']!='PASS':
        raise ValueError('Publish only after all-design and minimal serialization qualification')
    OUT.mkdir(parents=True,exist_ok=True)
    values=credentials.credential()
    def api(path,data=None):
        req=urllib.request.Request('https://api.github.com'+path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+values['password'],'Accept':'application/vnd.github+json',
                'Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'OpenSTA-input-alias-repair'})
        with urllib.request.urlopen(req,timeout=60) as response:
            return json.load(response)
    if api('/user')['login']!='AbhinavChoudhary24167':
        raise ValueError('Unexpected authenticated fork owner')
    target=api('/repos/'+TARGET)
    base_branch=target['default_branch']
    base_sha=api('/repos/'+TARGET+'/git/ref/heads/'+base_branch)['object']['sha']
    sta=r.SOURCE/'src/sta'
    subprocess.run(['git','-C',str(sta),'fetch','https://github.com/'+TARGET+'.git',base_sha],check=True)
    work=r.MOUNT/'upstream_OpenSTA_input_alias'
    if work.exists():
        raise ValueError('Preserve existing upstream worktree')
    subprocess.run(['git','-C',str(sta),'worktree','add','-b','upstream/verilog-input-alias',str(work),base_sha],check=True)
    result=subprocess.run(['git','-C',str(work),'cherry-pick','-s',repair['OpenSTA_repair_commit']],text=True,capture_output=True)
    write(OUT/'cherry_pick.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
        exact_experimental_commit=repair['OpenSTA_repair_commit'],upstream_base=base_sha,worktree=str(work)))
    if result.returncode:
        raise RuntimeError('Upstream cherry-pick needs adaptation; experiment continues independently')
    sha=subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()
    files=subprocess.check_output(['git','-C',str(work),'diff',base_sha,sha,'--name-only'],text=True).splitlines()
    if files!=['verilog/VerilogWriter.cc']:
        raise ValueError('Upstream contribution must be the isolated one-file writer patch')
    (OUT/'patch.diff').write_bytes(subprocess.check_output(['git','-C',str(work),'diff',base_sha,sha,'--binary']))
    try:
        fork=api('/repos/'+FORK)
    except urllib.error.HTTPError as error:
        if error.code!=404:
            raise
        fork=api('/repos/'+TARGET+'/forks',dict(default_branch_only=True))
    if fork['full_name']!=FORK:
        raise ValueError('Unexpected serializer repair fork')
    remote='https://github.com/'+FORK+'.git'
    existing=subprocess.check_output(['git','ls-remote',remote,'refs/heads/'+BRANCH],text=True,
        env=credentials.environment(),timeout=60).strip()
    if existing and existing.split()[0]!=sha:
        raise ValueError('Never force-push an existing repair revision')
    helper='!'+sys.executable+' '+str(credentials.Path(credentials.__file__).resolve())+' credential'
    command=['git','-C',str(work),'-c','credential.helper=','-c','credential.helper='+helper,
        'push','--porcelain',remote,sha+':refs/heads/'+BRANCH]
    result=subprocess.run(command,text=True,capture_output=True,env=credentials.environment(),timeout=180)
    write(OUT/'push.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
        sha=sha,force_push=False,secrets_stored=False,secrets_printed=False))
    if result.returncode:
        raise RuntimeError('Serializer repair push failed; see safe receipt')
    body=f'''When an input port and its connected internal net have different names, `VerilogWriter::writeAssigns` emits no input alias. The written Verilog declares the input and an undriven internal wire, so a connected ODB/network graph becomes disconnected in the exported circuit. Output aliases already work.

Include input ports in the existing alias condition and emit `assign internal_net = input_port` for those ports. Output, inout and power/ground handling retain their existing direction and conditions. This changes serialization only; no network connections or timing/optimization behavior change.

Minimal reproducer through OpenROAD's dbNetwork adapter: create one `BUF_X1`, connect its `A` pin to net `internal_input`, attach input BTerm `external_input` to that same net, and similarly connect `Z` to `internal_output` with output BTerm `external_output`. Load the database and call `write_verilog`. Before: only `assign external_output = internal_output` is emitted. After: `assign internal_input = external_input` is also emitted. The existing output alias remains correct. The standalone reproducer source is included below; use the standard Nangate45 test library directory and run it with OpenROAD's embedded Python.

Local before/after validation used OpenSTA `{s.STA_PARENT}` and repair `{repair['OpenSTA_repair_commit']}`, linked into an immutable full OpenROAD build. The one-buffer witness reproduces the missing input alias before and passes after. Three scan designs with 179/211/534 FFs independently agree in metadata, saved ODB and generated Verilog after this fix, with no ODB functional connection or placement changes. Three adjacent native DFT golden regressions also pass. This contribution cherry-picks the same one-file repair onto current upstream `{base_sha}` as `{sha}`; that upstream checkout has not been separately rebuilt locally, and CI is not claimed passing.

```python
{(r.ROOT/'scripts/pact_verilog_alias_witness.py').read_text()}
```
'''
    (OUT/'pull_request_body.md').write_text(body)
    query=urllib.parse.urlencode(dict(state='all',head='AbhinavChoudhary24167:'+BRANCH,base=base_branch))
    existing_prs=api('/repos/'+TARGET+'/pulls?'+query)
    pr=existing_prs[0] if existing_prs else api('/repos/'+TARGET+'/pulls',dict(base=base_branch,
        head='AbhinavChoudhary24167:'+BRANCH,title='verilog: preserve input aliases when port and net names differ',
        body=body,draft=False,maintainer_can_modify=True))
    write(OUT/'github_contribution.json',dict(PR_URL=pr['html_url'],state=pr['state'],merged=pr.get('merged',False),
        experimental_commit=repair['OpenSTA_repair_commit'],upstream_commit=sha,upstream_base=base_sha,
        target=TARGET,target_branch=base_branch,patch=binding(OUT/'patch.diff'),body=binding(OUT/'pull_request_body.md'),
        capture_time_utc=datetime.now(timezone.utc).isoformat(),CI_status='NOT_YET_CHECKED',review_status='NOT_YET_CHECKED',
        benchmark_waited_for_review=False,secrets_stored=False,secrets_printed=False))
    print('OPENSTA_PR_CREATED',pr['html_url'],flush=True)


if __name__=='__main__':
    main()
