#!/usr/bin/env python3
"""Apply the authorized commit-scoped PR description without changing Git refs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

import pact_oss_receiver_upstream as contribution
from pact_oss_benchmark import binding, write

SHA = '0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8'
PATH = '/repos/mwsoli/OpenROAD/pulls/1'
BODY = (
    '`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` call the '
    'non-static `sta::dbNetwork` methods `getLibertyScanIn()` and '
    '`getLibertyScanOut()` without an object receiver, causing compilation to fail.\n\n'
    'Qualify both calls with the existing `db_network_` member. The diff contains '
    'only the two receiver qualifications and formatting of the affected return statements.\n'
)


def main():
    output = contribution.UPSTREAM
    names = ('pull_request_body_commit_scope.md', 'github_pr_before_commit_scope_edit.json',
             'github_pr_after_commit_scope_edit.json', 'pull_request_commit_scope_edit.json')
    if any((output / name).exists() for name in names):
        raise ValueError('Preserve the existing commit-scoped description evidence')
    values = contribution.credential()

    def api(path, data=None):
        request = urllib.request.Request('https://api.github.com' + path,
            data=json.dumps(data).encode() if data is not None else None,
            method='PATCH' if data is not None else 'GET', headers={
                'Authorization': 'Bearer ' + values['password'],
                'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'OpenROAD-receiver-repair'})
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, json.load(response)

    _, user = api('/user')
    if user['login'] != contribution.ACCOUNT:
        raise ValueError('Authenticated account differs from the authorized PR author')
    _, before = api(PATH)
    if before['head']['sha'] != SHA or before['base']['sha'] != contribution.build.BASE:
        raise ValueError('PR refs differ from the preserved receiver repair')
    body_path = output / names[0]
    body_path.write_text(BODY)
    write(output / names[1], before)
    http_status, _ = api(PATH, dict(body=BODY))
    _, after = api(PATH)
    write(output / names[2], after)
    if after['body'] != BODY or after['head']['sha'] != SHA or after['base']['sha'] != contribution.build.BASE:
        raise ValueError('Commit-scoped wording or unchanged PR refs did not verify')
    write(output / names[3], dict(status='UPDATED_AND_VERIFIED',
        capture_time_utc=datetime.now(timezone.utc).isoformat(), pr_url=after['html_url'],
        updated_fields=['body'], http_status=http_status, head_sha_before=before['head']['sha'],
        head_sha_after=after['head']['sha'], base_sha_before=before['base']['sha'],
        base_sha_after=after['base']['sha'], commit_amended=False, source_patch_changed=False,
        revised_body=binding(body_path), metadata_before=binding(output / names[1]),
        metadata_after=binding(output / names[2]), helper=binding(Path(__file__)),
        previous_edit_receipt=binding(output / 'pull_request_description_edit.json'),
        user_request='Only the issue and changes in this commit; remove PACT and unrelated references',
        secrets_stored=False, secrets_printed=False))
    print('COMMIT_SCOPED_PR_DESCRIPTION_VERIFIED', after['html_url'], after['head']['sha'], flush=True)


if __name__ == '__main__':
    main()
