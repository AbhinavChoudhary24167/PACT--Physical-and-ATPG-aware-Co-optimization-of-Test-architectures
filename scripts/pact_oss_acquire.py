#!/usr/bin/env python3
"""Pin public OpenROAD source snapshots without touching qualified installations."""
from pact.environment import dependency_path
from pact.experiment_storage import experiment_root
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/pact_oss_benchmark'
TEMP = Path(('' + str(experiment_root()) + '/tmp/pact_oss_20261003'))
UPSTREAM = 'https://api.github.com/repos/The-OpenROAD-Project/OpenROAD'


def get(url):
    return subprocess.check_output(['curl', '-L', '--fail', '--max-time', '30', '--silent', '--show-error',
                                    '-A', 'PACT-controlled-OSS-benchmark', url], timeout=40)


def json_get(url):
    return json.loads(get(url))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('Acquisition evidence already exists: ' + str(path))
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    methods = [('B1_openroad_native', None, '08f67ee5ec'),
               ('B2_openroad_10176', 10176, None), ('B3_openroad_10666', 10666, None)]
    versions = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                    implementation_openroad_version=subprocess.check_output(['openroad', '-version'], text=True).strip(),
                    implementation_binary_sha256=hashlib.sha256(Path('/usr/bin/openroad').read_bytes()).hexdigest(),
                    ORFS_commit=subprocess.check_output(['git', '-C', ('' + str(dependency_path("OpenROAD-flow-scripts")) + ''), 'rev-parse', 'HEAD'], text=True).strip(),
                    installed_source_checkout_commit=subprocess.check_output(['git', '-C', ('' + str(dependency_path("OpenROAD")) + ''), 'rev-parse', 'HEAD'], text=True).strip(),
                    note='Installed source checkout and native binary revisions differ; source is acquired at the binary version revision for native semantics.',
                    temporary_storage=str(TEMP), baselines={})
    for method, pr, revision in methods:
        folder = OUT / 'baselines' / method
        if (folder / 'source_pin.json').exists():
            record = json.loads((folder / 'source_pin.json').read_text())
            versions['baselines'][method] = dict(repository=record['repository'], commit=record['commit'],
                                                 base_revision=record['OpenROAD_base_revision'])
            print(method, 'already pinned', record['commit'], flush=True)
            continue
        if pr:
            if (folder / 'upstream_pr.json').exists():
                saved = json.loads((folder / 'upstream_pr.json').read_text())
                head, base, repo, merge_base = saved['head_sha'], saved['base_tip_sha'], saved['head_repository'], saved['merge_base_sha']
            else:
                metadata = json_get(UPSTREAM + f'/pulls/{pr}')
                head = metadata['head']['sha']
                base = metadata['base']['sha']
                repo = metadata['head']['repo']['full_name']
                comparison = json_get(UPSTREAM + f'/compare/{base}...{head}')
                merge_base = comparison['merge_base_commit']['sha']
                write(folder / 'upstream_pr.json', dict(number=pr, url=metadata['html_url'], state=metadata['state'],
                                                   head_sha=head, head_repository=repo, head_ref=metadata['head']['ref'],
                                                   base_tip_sha=base, merge_base_sha=merge_base,
                                                   fetched_at=datetime.now(timezone.utc).isoformat()))
        else:
            head = json_get(UPSTREAM + '/commits/' + revision)['sha']
            repo, base, merge_base = 'The-OpenROAD-Project/OpenROAD', head, head
        tree = json_get(f'https://api.github.com/repos/{repo}/git/trees/{head}?recursive=1')
        if tree.get('truncated'):
            raise ValueError('Truncated upstream source inventory')
        items = [row for row in tree['tree'] if row['type'] == 'blob' and (
            row['path'].startswith('src/dft/') or row['path'] in ('AGENTS.md', 'CMakeLists.txt', '.gitmodules', 'etc/Build.sh', 'docs/agents/build.md'))]
        source = TEMP / method / 'source_audit'
        def download(row):
            target = source / row['path']
            raw = target.read_bytes() if target.exists() else get(f'https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD/{head}/{row["path"]}')
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if blob != row['sha']:
                raise ValueError('Source Git blob mismatch: ' + row['path'])
            return row, raw
        files = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            retrieved = list(pool.map(download, items))
        # Serialize DrvFS writes; only network retrieval is parallel.
        for row, raw in retrieved:
            target = source / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(raw)
            files[row['path']] = dict(git_blob=row['sha'], sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), path=str(target))
        record = dict(repository='https://github.com/' + repo, commit=head, OpenROAD_base_revision=merge_base,
                      upstream_base_tip=base, source_files=files, source_tree_git_sha=tree['sha'],
                      source_acquisition='Immutable commit-addressed raw GitHub files; full pinned build checkout pending',
                      binary='installed /usr/bin/openroad' if not pr else None,
                      build_status='installed native binary' if not pr else 'not yet attempted',
                      algorithm_status='source inspected separately; no prompt-summary substitution')
        write(folder / 'source_pin.json', record)
        versions['baselines'][method] = dict(repository=record['repository'], commit=head, base_revision=merge_base)
        print(method, head, 'base', merge_base, 'source files', len(files), flush=True)
    write(OUT / 'protocol/tool_versions.json', versions)


if __name__ == '__main__':
    main()
