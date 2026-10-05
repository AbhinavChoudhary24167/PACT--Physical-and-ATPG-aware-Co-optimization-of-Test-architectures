#!/usr/bin/env python3
"""Record final Git provenance without trying to embed a commit's own SHA."""
import subprocess
from pact_generalization import ROOT, OUT, binding, now, read, write


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def main():
    freeze=read(OUT/'manifests/pact_v1_frozen_manifest.json')
    branch=git('branch','--show-current')
    assert branch=='experiment/generalization-scalability-20261004'
    paths=set(git('diff','--name-only',freeze['repository_sha']).splitlines())
    paths.update(git('ls-files','--others','--exclude-standard').splitlines())
    paths.update(str((OUT/name).relative_to(ROOT)).replace('\\','/') for name in (
        'repository_final_checkpoint.json','repository_final_changes.txt'))
    assert not paths.intersection(b['path'].removeprefix('repo://') for b in freeze['files'])
    change_path=OUT/'repository_final_changes.txt'
    change_path.write_text('\n'.join(sorted(paths))+'\n',encoding='utf-8')
    write(OUT/'repository_final_checkpoint.json',dict(
        created_utc=now(),starting_SHA=freeze['repository_sha'],branch=branch,
        final_scientific_evidence_commit=git('rev-parse','HEAD'),
        ending_commit_tag='pact-v1-generalization-blocked-20261004',
        ending_SHA_resolution='git rev-parse pact-v1-generalization-blocked-20261004',
        note='The containing metadata commit cannot embed its own hash. The tag and final response identify it exactly.',
        commits=git('log','--reverse','--format=%H %s',freeze['repository_sha']+'..HEAD').splitlines(),
        changed_files=sorted(paths),frozen_inventory_files_changed=0,
        file_inventory=binding(change_path),
        qualification_audit=binding(OUT/'logs/final_artifact_audit.json')),immutable=True)
    print('FINAL_REPOSITORY_PROVENANCE_PASS',len(paths),'changed/new files; frozen inventory unchanged')


if __name__=='__main__':
    main()
