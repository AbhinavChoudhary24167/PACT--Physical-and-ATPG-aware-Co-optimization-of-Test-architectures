#!/usr/bin/env python3
"""Apply the user-authorized technical PR wording without changing its commit."""
from datetime import datetime, timezone
import json
import urllib.request

import pact_oss_receiver_upstream as contribution
from pact_oss_benchmark import binding, write

SHA = '0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8'
PR_NUMBER = 1
PATH = '/repos/mwsoli/OpenROAD/pulls/1'


def main():
    output = contribution.UPSTREAM
    body_file = output / 'pull_request_body_technical.md'
    body = body_file.read_text()
    receipt = output / 'pull_request_description_edit.json'
    if receipt.exists() or (output / 'github_pr_before_technical_edit.json').exists():
        raise ValueError('Preserve the existing description edit receipt; do not overwrite it')
    values = contribution.credential()

    def api(path, data=None):
        request = urllib.request.Request('https://api.github.com' + path,
            data=json.dumps(data).encode() if data is not None else None,
            method='PATCH' if data is not None else 'GET', headers={
                'Authorization': 'Bearer ' + values['password'],
                'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'PACT-B3R-technical-description'})
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.load(response)

    _, user = api('/user')
    if user['login'] != contribution.ACCOUNT:
        raise ValueError('Authenticated account is not the authorized PR author')
    _, before = api(PATH)
    if before['head']['sha'] != SHA or before['base']['sha'] != contribution.build.BASE:
        raise ValueError('The repair head or target base differs from the preserved contribution')
    write(output / 'github_pr_before_technical_edit.json', before)
    status, updated = api(PATH, dict(body=body))
    _, after = api(PATH)
    write(output / 'github_pr_after_technical_edit.json', after)
    if after['body'] != body or after['head']['sha'] != SHA or after['base']['sha'] != contribution.build.BASE:
        raise ValueError('The updated description or preserved PR refs did not verify')
    write(receipt, dict(status='updated', capture_time_utc=datetime.now(timezone.utc).isoformat(),
        pr_url=after['html_url'], pr_number=PR_NUMBER, target_repository='mwsoli/OpenROAD',
        target_branch=contribution.TARGET_BRANCH, head_sha_before=before['head']['sha'],
        head_sha_after=after['head']['sha'], base_sha_before=before['base']['sha'],
        base_sha_after=after['base']['sha'], updated_fields=['body'], http_status=status,
        commit_amended=False, commit_recreated=False, source_patch_changed=False, force_push=False,
        original_body_preserved=binding(output / 'pull_request_body.md'),
        revised_body=binding(body_file), metadata_before=binding(output / 'github_pr_before_technical_edit.json'),
        metadata_after=binding(output / 'github_pr_after_technical_edit.json'),
        helper=binding(__file__), secrets_stored=False, secrets_printed=False,
        ci_review_or_merge_wait_performed=False,
        reason='User explicitly requested a technical PR description and preservation of the repair commit SHA'))
    print('TECHNICAL_PR_DESCRIPTION_UPDATED', after['html_url'], after['head']['sha'], flush=True)


if __name__ == '__main__':
    main()
