#!/usr/bin/env python3
"""Create the authorized targeted PR through existing account authentication."""
from datetime import datetime, timezone
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import pact_oss_receiver_upstream as contribution
from pact_oss_benchmark import binding, read, write


def main(sha):
    contribution.validated(sha)
    plan = read(contribution.UPSTREAM / 'submission_plan.json')
    pushed = read(contribution.UPSTREAM / 'push_result.json')
    if plan['repair_commit_sha'] != sha or pushed['status'] != 'PASS' or pushed['verified_remote_sha'] != sha:
        raise ValueError('The exact validated repair was not pushed')
    values = contribution.credential()

    def api(path, data=None):
        payload = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request('https://api.github.com' + path, data=payload, headers={
            'Authorization': 'Bearer ' + values['password'], 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'PACT-B3R-upstream-contribution'})
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.load(response)

    _, user = api('/user')
    if user['login'] != contribution.ACCOUNT:
        raise ValueError('Authenticated account differs from the authorized repair fork owner')
    _, target = api('/repos/' + contribution.TARGET + '/git/ref/heads/' + contribution.TARGET_BRANCH)
    _, head = api('/repos/' + contribution.REPOSITORY + '/git/ref/heads/' + contribution.build.BRANCH)
    if target['object']['sha'] != contribution.build.BASE or head['object']['sha'] != sha:
        raise ValueError('Target or head branch moved; creating a larger or different repair PR is forbidden')
    query = urllib.parse.urlencode(dict(state='all', head=contribution.ACCOUNT + ':' + contribution.build.BRANCH,
                                      base=contribution.TARGET_BRANCH))
    _, existing = api('/repos/' + contribution.TARGET + '/pulls?' + query)
    request = dict(base=contribution.TARGET_BRANCH,
        head=contribution.ACCOUNT + ':' + contribution.build.BRANCH,
        title=plan['title'], body=(contribution.UPSTREAM / 'pull_request_body.md').read_text(),
        draft=False, maintainer_can_modify=True)
    try:
        if existing:
            status, result = 200, existing[0]
            created = False
        else:
            status, result = api('/repos/' + contribution.TARGET + '/pulls', request)
            created = True
    except urllib.error.HTTPError as error:
        write(contribution.UPSTREAM / 'rest_pull_request_creation.json', dict(status='failed',
            capture_time_utc=datetime.now(timezone.utc).isoformat(), http_status=error.code,
            error=error.read().decode(), target_repository=contribution.TARGET,
            target_branch=contribution.TARGET_BRANCH, repair_commit_sha=sha,
            secrets_stored=False, secrets_printed=False, helper=binding(__file__)))
        print('UPSTREAM_PULL_REQUEST_API_FAILED', error.code, flush=True)
        return 1
    if result['head']['sha'] != sha or result['base']['sha'] != contribution.build.BASE:
        raise ValueError('Created PR refs differ from the exact verified receiver repair')
    write(contribution.UPSTREAM / 'rest_pull_request_creation.json', dict(status='created' if created else 'reused',
        capture_time_utc=datetime.now(timezone.utc).isoformat(), http_status=status,
        authenticated_login=user['login'], target_repository=contribution.TARGET,
        target_branch=contribution.TARGET_BRANCH, target_base_sha=target['object']['sha'],
        repair_commit_sha=sha, created=created, pr_url=result['html_url'], pr_number=result['number'],
        body=binding(contribution.UPSTREAM / 'pull_request_body.md'),
        secrets_stored=False, secrets_printed=False, helper=binding(__file__), raw_response=result))
    print('UPSTREAM_PULL_REQUEST_READY', result['html_url'], result['number'], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
