#!/usr/bin/env python3
"""Publish the tested B3R commit without recreating it or persisting credentials."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

import pact_oss_receiver_build as build
from pact_oss_benchmark import binding, read, write

ACCOUNT = 'AbhinavChoudhary24167'
REPOSITORY = ACCOUNT + '/OpenROAD'
TARGET = 'mwsoli/OpenROAD'
TARGET_BRANCH = 'dft/scan-chain-optimizer'
UPSTREAM = build.RECOVERY / 'upstream'
WINDOWS_GIT = 'git'


def environment():
    env = os.environ.copy()
    for key in ('GIT_ASKPASS', 'SSH_ASKPASS', 'GIT_TRACE', 'GIT_TRACE_PACKET',
                'GIT_TRACE_CURL', 'GIT_CURL_VERBOSE', 'GCM_TRACE'):
        env.pop(key, None)
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    return env


def credential():
    # Credential Manager receives and returns credentials through process pipes.
    # The password is never serialized, printed, or saved in a helper/config file.
    result = subprocess.run([WINDOWS_GIT, 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n', text=True,
        capture_output=True, cwd=build.ROOT, env=environment(), timeout=90)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password') or values.get('username', '').lower() != ACCOUNT.lower():
        raise RuntimeError('Existing Git Credential Manager authentication is unavailable or belongs to another account')
    return values


def credential_helper(operation):
    request = dict(line.split('=', 1) for line in sys.stdin.read().splitlines() if '=' in line)
    if operation != 'get':
        return
    if request.get('protocol') != 'https' or request.get('host') != 'github.com':
        raise ValueError('Credential helper accepts only the intended HTTPS GitHub host')
    values = credential()
    sys.stdout.write('username=' + values['username'] + '\npassword=' + values['password'] + '\n\n')


def auth():
    values = credential()
    request = urllib.request.Request('https://api.github.com/user', headers={
        'Authorization': 'Bearer ' + values['password'], 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'PACT-B3R-upstream-validation'})
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
        status = response.status
    if result['login'] != ACCOUNT:
        raise ValueError('Authenticated GitHub API user differs from the authorized fork owner')
    write(UPSTREAM / 'authentication_preflight.json', dict(status='PASS',
        capture_time_utc=datetime.now(timezone.utc).isoformat(), authenticated_login=result['login'],
        authenticated_id=result['id'], api_status=status, windows_git_path=WINDOWS_GIT,
        windows_git_version=subprocess.check_output([WINDOWS_GIT, '--version'], text=True).strip(),
        credential_source='Existing Windows Git Credential Manager through process pipes',
        secrets_stored=False, secrets_printed=False, helper=binding(__file__)))
    print('UPSTREAM_AUTHENTICATION_PASS', result['login'], status, flush=True)


def validated(sha):
    build.gate()
    repair = read(build.REPAIR / 'repair_manifest.json')
    tests = read(build.REPAIR / 'tests.json')
    binary = read(build.FOLDER / 'build_result.json')
    if repair['repair_commit_sha'] != sha or repair['upstream_base_sha'] != build.BASE:
        raise ValueError('Push must use exactly the locally tested immutable B3R commit')
    if not repair['DCO_verified'] or repair['changed_files'] != [build.FILE] or repair['algorithm_semantics_changed']:
        raise ValueError('The authorized receiver-only DCO validation is missing')
    if repair['changed_lines'] != dict(additions=4, deletions=2) or tests['status'] != 'PASS':
        raise ValueError('The minimal patch or focused local tests did not pass')
    formatting = read(build.REPAIR / 'formatting.json')
    if formatting['status'] != 'PASS' or 'clang-format version 18.' not in formatting['version']:
        raise ValueError('The independent clang-format-18 validation is missing')
    if set(tests['tests_after']) != {'scan_opt_sky130', 'place_sort_sky130', 'one_cell_sky130'}:
        raise ValueError('The three required focused integration tests are missing')
    if binary['status'] != 'BUILT' or binary['commit'] != sha:
        raise ValueError('The final immutable B3R executable has not been built')
    if binding(build.BUILD / 'bin/openroad')['sha256'] != binary['binary_sha256']:
        raise ValueError('The validated B3R executable changed')
    if build.run_git('rev-parse', 'HEAD').strip() != sha or build.run_git('status', '--short'):
        raise ValueError('The isolated repair checkout is no longer the clean tested commit')
    if build.run_git('rev-parse', sha + '^').strip() != build.BASE:
        raise ValueError('The repair commit has a different original B3 parent')
    patch = build.run_git('diff', sha + '^', sha, '--no-ext-diff', '--binary').encode()
    if hashlib.sha256(patch).hexdigest() != repair['patch_sha256']:
        raise ValueError('The published commit patch differs from the tested patch')
    expected = build.run_git('show', build.BASE + ':' + build.FILE)
    for member in ('getLibertyScanIn', 'getLibertyScanOut'):
        call = f'findITerm({member}(test_cell_))'
        if expected.count(call) != 1:
            raise ValueError('The exact parent does not contain the two expected calls')
        expected = expected.replace(call, f'findITerm(db_network_->{member}(test_cell_))')
    actual = build.run_git('show', sha + ':' + build.FILE)
    if ''.join(expected.split()) != ''.join(actual.split()):
        raise ValueError('The formatted repair contains a change beyond the two receiver additions')
    return repair, tests, binary


def prepare(sha):
    repair, tests, binary = validated(sha)
    formatting = read(build.REPAIR / 'formatting.json')
    body = f'''`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` currently call the non-static `sta::dbNetwork` methods `getLibertyScanIn()` and `getLibertyScanOut()` without an object receiver. At PR #10666 revision `{build.BASE}`, both calls fail to compile.

Qualify these two existing calls with the cell's existing `db_network_` member. `ScanCellFactory` obtains this network from the active STA instance and passes it with the corresponding `TestCell` to `OneBitScanCell`. `clang-format-18` wraps only these two repaired return statements onto two lines each, producing four added lines and two removed lines in one file. The functional changes are only the two missing receivers; scan ordering, cost functions, clustering, NN/2-Opt/3-Opt logic, parameters, and scan-pin endpoint semantics are unchanged.

This contribution targets `mwsoli/OpenROAD:{TARGET_BRANCH}`, the head branch of [The-OpenROAD-Project/OpenROAD#10666](https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666). The receiver defect is absent from exact PR #10176 and current upstream `master`.

Local validation at the pinned PR revision plus this repair:

- Independent WSL formatter `{formatting['version']}` validates the immediate call sites with `clang-format-18 -i --lines=106:111`; `git diff --check` passes. The committed source matches the exact parent plus the two receiver additions and immediate formatting.
- `dft_cells_lib` and the full `openroad` target build successfully with GCC 11.4.0, SWIG 4.3.0, and Tcl development headers/library 8.6.12 in the isolated toolchain.
- Existing DFT integration tests `scan_opt_sky130`, `place_sort_sky130`, and `one_cell_sky130` pass, including their checked golden outputs.
- DCO sign-off is present in commit `{sha}`.

Base: `{build.BASE}`. Repair commit: `{sha}`. Patch SHA256: `{repair['patch_sha256']}`. The controlled PACT benchmark uses this same immutable commit under the explicit label **B3R — PR #10666 + minimal compile repair**; exact B2 remains unchanged.
'''
    (UPSTREAM / 'pull_request_body.md').write_text(body)
    write(UPSTREAM / 'submission_plan.json', dict(status='VALIDATED_PUSH_PENDING',
        target_repository=TARGET, target_branch=TARGET_BRANCH, target_base_sha=build.BASE,
        head_repository=REPOSITORY, head_branch=build.BRANCH, repair_commit_sha=sha,
        patch_sha256=repair['patch_sha256'], title='dft: qualify dbNetwork calls in scan-pin location accessors',
        body=binding(UPSTREAM / 'pull_request_body.md'), local_repair=binding(build.REPAIR / 'repair_manifest.json'),
        local_tests=binding(build.REPAIR / 'tests.json'), local_build=binding(build.FOLDER / 'build_result.json'),
        local_binary_sha256=binary['binary_sha256'], local_formatting=binding(build.REPAIR / 'formatting.json'),
        helper=binding(__file__)))
    print('UPSTREAM_SUBMISSION_PREPARED', sha, flush=True)


def push(sha):
    validated(sha)
    plan = read(UPSTREAM / 'submission_plan.json')
    if plan['repair_commit_sha'] != sha or plan['target_base_sha'] != build.BASE:
        raise ValueError('Prepared contribution does not match the requested commit')
    remote = subprocess.check_output(['git', 'ls-remote', build.REMOTE, 'refs/heads/' + build.BRANCH],
        text=True, env=environment()).strip()
    if remote and remote.split()[0] != sha:
        raise ValueError('The intended remote repair branch already has a different commit; force push is forbidden')
    helper = '!' + sys.executable + ' ' + str(Path(__file__).resolve()) + ' credential'
    command = ['git', '-C', str(build.SOURCE), '-c', 'credential.helper=', '-c', 'credential.helper=' + helper,
        'push', '--porcelain', build.REMOTE, sha + ':refs/heads/' + build.BRANCH]
    result = subprocess.run(command, text=True, capture_output=True, env=environment(), timeout=180)
    verified = subprocess.run(['git', 'ls-remote', build.REMOTE, 'refs/heads/' + build.BRANCH],
        text=True, capture_output=True, env=environment(), timeout=60)
    remote_sha = verified.stdout.split()[0] if verified.returncode == 0 and verified.stdout.strip() else None
    record = dict(status='PASS' if result.returncode == 0 and remote_sha == sha else 'PUSH_FAILED',
        capture_time_utc=datetime.now(timezone.utc).isoformat(), command=command, returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr, repository=REPOSITORY, branch=build.BRANCH,
        local_repair_sha=sha, verified_remote_sha=remote_sha, verification_returncode=verified.returncode,
        verification_stdout=verified.stdout, verification_stderr=verified.stderr,
        recreated_commit=False, force_push=False, secrets_stored=False, secrets_printed=False,
        helper=binding(__file__))
    write(UPSTREAM / 'push_result.json', record)
    print('UPSTREAM_REPAIR_PUSH', record['status'], remote_sha, flush=True)
    return 0 if record['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('auth', 'prepare', 'push', 'credential'))
    parser.add_argument('value', nargs='?')
    args = parser.parse_args()
    if args.action == 'credential':
        credential_helper(args.value)
    elif args.action == 'auth':
        auth()
    elif args.action == 'prepare':
        prepare(args.value)
    else:
        raise SystemExit(push(args.value))
