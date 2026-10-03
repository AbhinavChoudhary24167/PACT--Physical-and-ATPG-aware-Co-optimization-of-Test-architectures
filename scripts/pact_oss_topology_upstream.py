#!/usr/bin/env python3
"""Submit the exact qualified derivative to the optimizer maintainer's branch."""
from datetime import datetime, timezone
import json
import subprocess
import sys
import urllib.parse
import urllib.request

import pact_oss_topology as r
import pact_oss_receiver_upstream as credentials
from pact_oss_benchmark import binding, read, write

ACCOUNT = 'AbhinavChoudhary24167'
FORK = ACCOUNT + '/OpenROAD'
TARGET = 'mwsoli/OpenROAD'
TARGET_BRANCH = 'dft/scan-chain-optimizer'
REMOTE_BRANCH = 'fix/dft-scan-output-topology'
UPSTREAM = r.CAMPAIGN / 'upstream'


def main():
    r.ensure()
    build = read(r.FOLDER / 'build_result.json')
    repair = read(r.REPAIR / 'repair_manifest.json')
    tests = read(r.FOLDER / 'native_tests_attempt2/tests.json')
    sha = build['commit']
    witness = read(r.FOLDER / 's5378/qualification.json')
    if tests['status'] != 'PASS' or witness['status'] != 'PASS' or repair['repair_commit_sha'] != sha:
        raise ValueError('Contribution requires the exact narrowly qualified repair')
    r.git('merge-base','--is-ancestor',sha,'HEAD')
    parent_snapshot = r.CAMPAIGN / 'baselines/B3T_openroad_10666_serialization_repaired/repair/parent.json'
    binary = read(parent_snapshot)['parent_binary'] if parent_snapshot.exists() else build['binary']
    if binding(binary['path'])['sha256'] != build['binary_sha256']:
        raise ValueError('Qualified binary changed')
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    values = credentials.credential()
    def api(path, data=None):
        payload = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request('https://api.github.com'+path, data=payload, headers={
            'Authorization': 'Bearer '+values['password'], 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'OpenROAD-DFT-endpoint-repair'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    user = api('/user')
    if user['login'] != ACCOUNT:
        raise ValueError('Existing account differs from authorized fork owner')
    target = api('/repos/'+TARGET+'/git/ref/heads/'+TARGET_BRANCH)['object']['sha']
    if target not in (r.BASE, r.PARENT):
        write(UPSTREAM / 'target_moved.json', dict(status='TARGET_MOVED', actual=target, pinned=r.BASE,
            local_repair=sha, policy='Preserve experiment history; avoid submitting unrelated branch differences'))
        raise ValueError('Maintainer target moved; inspect before publication')
    body = f'''Scan-chain optimization can leave a configured fixed scan-output port connected to the pre-optimization tail, while metadata points to the new tail ITerm. The resulting internal scan path does not reach the fixed SO. Per-chain optimization also leaves `dbScanList` order at its pre-optimization order.

`RestitchChain` now connects the existing fixed output load to the final tail's Q/SO net, preserving functional Q fanout and endpoint identity, and repopulates the scan list from the same final ordered vector using OpenDB's prepend convention. An implicitly reused ordinary functional output is rejected before optimization unless an explicit configured scan output is supplied; moving that functional output would change the circuit. No substitute endpoint is created by the optimizer.

Minimal reproducer: the updated existing `src/dft/test/scan_opt_sky130.tcl` places ten scan cells, supplies a dedicated `scan_out_0`, executes `execute_dft_plan; scan_opt`, traces all ten cells from fixed SI to fixed SO, checks that SO is the tail, verifies every original functional output remains on its Q net, and compares normalized metadata order with the physical path. The test remains registered in both CMake and Bazel.

Observed at pinned optimizer revision `{r.BASE}` plus the receiver correction: two chains of 90/89 scan cells can end on new Q nets while both fixed SO ports remain on interior Q nets. The intended scan-in/scan-out preservation is stated in the parent optimizer PR. The fix touches native reconstruction and its regression only; KMeans (100 iterations), NN, directed 2-Opt, direction-preserving 3-Opt, 50 candidates, capacity, objective and endpoint cost remain unchanged.

Local validation: immutable full OpenROAD build with GCC 11.4.0, SWIG 4.3.0 and Tcl 8.6.12; updated `scan_opt_sky130` plus `place_sort_sky130` and `one_cell_sky130` all pass. A 179-cell placed-netlist witness now traces complete 90/89-cell paths from fixed SI through every FF to fixed SO, with scan-list order matching ODB and unchanged FF masters, placement and functional connections. The optimized cell order is unchanged from the failing parent's internal order. Exact local endpoint derivative: `{sha}`.

An independent serializer defect remains separate: when an input BTerm and its net have different names, the current OpenSTA Verilog writer omits the input alias. That defect is being repaired separately; this PR does not claim full serialized-netlist benchmark qualification until that independent repair is qualified.

This targets the branch behind The-OpenROAD-Project/OpenROAD#10666. It includes the separately submitted compile-only receiver prerequisite from https://github.com/mwsoli/OpenROAD/pull/1 when that prerequisite is not yet in the target branch. Endpoint repair commits preserve their individual history and DCO sign-offs.
'''
    (UPSTREAM / 'pull_request_body.md').write_text(body)
    remote = 'https://github.com/'+FORK+'.git'
    existing = subprocess.check_output(['git','ls-remote',remote,'refs/heads/'+REMOTE_BRANCH], text=True,
        env=credentials.environment(), timeout=60).strip()
    if existing and existing.split()[0] != sha:
        raise ValueError('Never overwrite another remote branch revision')
    helper = '!'+sys.executable+' '+str(credentials.Path(credentials.__file__).resolve())+' credential'
    command = ['git','-C',str(r.SOURCE),'-c','credential.helper=','-c','credential.helper='+helper,
        'push','--porcelain',remote,sha+':refs/heads/'+REMOTE_BRANCH]
    result = subprocess.run(command, text=True, capture_output=True, env=credentials.environment(), timeout=180)
    write(UPSTREAM / 'push_result.json', dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
        sha=sha, remote_branch=REMOTE_BRANCH, force_push=False, secrets_stored=False, secrets_printed=False))
    if result.returncode:
        raise RuntimeError('Authenticated repair push failed; see safe receipt')
    if api('/repos/'+FORK+'/git/ref/heads/'+REMOTE_BRANCH)['object']['sha'] != sha:
        raise ValueError('Published head differs from tested source')
    query = urllib.parse.urlencode(dict(state='all',head=ACCOUNT+':'+REMOTE_BRANCH,base=TARGET_BRANCH))
    existing_prs = api('/repos/'+TARGET+'/pulls?'+query)
    if existing_prs:
        pr = existing_prs[0]
    else:
        pr = api('/repos/'+TARGET+'/pulls', dict(base=TARGET_BRANCH, head=ACCOUNT+':'+REMOTE_BRANCH,
            title='dft: preserve fixed scan outputs and optimized chain metadata', body=body,
            draft=False, maintainer_can_modify=True))
    checks = api('/repos/'+TARGET+'/commits/'+sha+'/check-runs')
    reviews = api('/repos/'+TARGET+'/pulls/'+str(pr['number'])+'/reviews')
    write(UPSTREAM / 'github_contribution.json', dict(status='PR_CREATED', PR_URL=pr['html_url'],
        source_commit=sha, target_repository=TARGET,target_branch=TARGET_BRANCH,target_base_sha=target,
        capture_time_utc=datetime.now(timezone.utc).isoformat(), state=pr['state'], draft=pr['draft'],
        merged=pr.get('merged',False), reviews=[dict(state=x['state'],user=x['user']['login']) for x in reviews],
        checks=[dict(name=x['name'],status=x['status'],conclusion=x['conclusion']) for x in checks['check_runs']],
        body=binding(UPSTREAM / 'pull_request_body.md'), patch_sha256=repair['patch_sha256'],
        benchmark_waited_for_review=False, secrets_stored=False, secrets_printed=False))
    print('UPSTREAM_PR_CREATED',pr['html_url'],flush=True)


if __name__ == '__main__':
    main()
