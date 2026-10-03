#!/usr/bin/env python3
"""Read upstream status descriptions; no CI trigger or review wait."""
from datetime import datetime, timezone
import json
import urllib.request

from pact_oss_benchmark import write
import pact_oss_topology as r
import pact_oss_receiver_upstream as credentials


def main():
    token = credentials.credential()['password']
    def api(path):
        request = urllib.request.Request('https://api.github.com'+path, headers={
            'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
            'User-Agent':'scan-repair-status-details'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    base = '/repos/The-OpenROAD-Project/OpenSTA'
    pr = api(base+'/pulls/420')
    statuses = api(base+'/commits/'+pr['head']['sha']+'/status')['statuses']
    comments = api(base+'/issues/420/comments')
    reviews = api(base+'/pulls/420/reviews')
    write(r.CAMPAIGN / 'upstream/OpenSTA_status_details.json', dict(
        capture_time_utc=datetime.now(timezone.utc).isoformat(),
        statuses=[{name:item.get(name) for name in ('context','state','description','target_url')} for item in statuses],
        comments=[dict(user=item['user']['login'],body=item['body'],url=item['html_url']) for item in comments],
        reviews=[dict(user=item['user']['login'],state=item['state'],body=item['body'],url=item['html_url']) for item in reviews]))
    for item in statuses:
        print(item['context'], item['state'], item['description'], item['target_url'])
    for item in comments+reviews:
        print(item['user']['login'], item['body'][:1500])


if __name__ == '__main__':
    main()
