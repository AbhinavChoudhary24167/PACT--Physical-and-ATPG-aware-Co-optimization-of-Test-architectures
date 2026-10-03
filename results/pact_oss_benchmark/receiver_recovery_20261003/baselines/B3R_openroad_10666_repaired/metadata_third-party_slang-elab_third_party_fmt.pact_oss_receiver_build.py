#!/usr/bin/env python3
"""Create and validate the separately identified, receiver-only B3R derivative."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from pact_oss_benchmark import ROOT, OUT, binding, read, verify, write
import pact_oss_recovery as original
from pact_oss_build_resolution import parse_cache, validate_resolution
from pact_oss_storage import ensure

BASE = '746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656'
NAME = 'B3R_openroad_10666_repaired'
OLD = 'B3_openroad_10666'
RECOVERY = OUT / 'receiver_recovery_20261003'
FOLDER = RECOVERY / 'baselines' / NAME
PREFIX = original.MOUNT / NAME
SOURCE = PREFIX / 'source'
BUILD = PREFIX / 'build'
REPAIR = FOLDER / 'repair'
DATA = original.TEMP / 'receiver_recovery_20261003'
FILE = 'src/dft/src/cells/OneBitScanCell.cpp'
BRANCH = 'fix/dft-dbnetwork-member-receiver'
REMOTE = 'https://github.com/AbhinavChoudhary24167/OpenROAD.git'


def run_git(*args):
    result = subprocess.run(['git', '-C', str(SOURCE), *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('git '+args[0]+' failed: '+result.stderr)
    return result.stdout


def gate():
    ensure()
    original.require_prerequisites()
    verify()
    original_failure = read(original.RECOVERY / 'baselines' / OLD / 'compilation_blocker.json')
    if original_failure['source_commit'] != BASE or original_failure['status'] != 'SOURCE_PATCH_REQUIRED_STOPPED':
        raise ValueError('The verified original B3 receiver defect is not present')
    b2 = read(original.RECOVERY / 'baselines/B2_openroad_10176/qualification.json')
    if b2['status'] != 'PASS' or b2['source_commit'] != '6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf':
        raise ValueError('Exact B2 must remain qualified and unchanged')
    if binding(original.MOUNT / 'B2_openroad_10176/build/bin/openroad')['sha256'] != b2['binary_sha256']:
        raise ValueError('Exact B2 binary changed')


def execute(args, label):
    FOLDER.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, FOLDER / (label + '.pact_oss_receiver_build.py'))
    return original.execute(args, FOLDER, label)


def docker(args):
    # Preserve absolute compiler-cache paths by mounting the independent copies
    # over their old container namespace. Host original source/build stay intact.
    (PREFIX / 'compiler_tmp').mkdir(parents=True, exist_ok=True)
    command = original.docker(args)
    position = command.index('--entrypoint')
    command[position:position] = [
        '--mount', f'type=bind,source={SOURCE},target=/build_storage/{OLD}/source',
        '--mount', f'type=bind,source={BUILD},target=/build_storage/{OLD}/build',
        '--env', f'TMPDIR=/build_storage/{NAME}/compiler_tmp']
    return command


def prepare():
    gate()
    resume = PREFIX.exists()
    if resume and ((REPAIR / 'before_edit.json').exists() or BUILD.exists()):
        raise ValueError('Repair work already advanced; preserve existing evidence')
    SOURCE.mkdir(parents=True, exist_ok=True)
    REPAIR.mkdir(parents=True, exist_ok=True)
    if not resume:
        execute(['git', 'init', str(SOURCE)], 'git_init')
        run_git('remote', 'add', 'origin', REMOTE)
        if execute(['git', '-C', str(SOURCE), 'fetch', '--depth=1', 'origin', BASE], 'git_fetch_base'):
            return 1
        run_git('checkout', '-b', BRANCH, 'FETCH_HEAD')
    else:
        write(REPAIR / 'prepare_attempt1_error.json', dict(status='CHECKOUT_COPY_SYMLINK_COLLISION',
            cause='shutil.copytree dirs_exist_ok does not skip already identical symlinks in a Git checkout',
            source_patch_or_build_attempted=False, remedy='Verify existing link targets and keep identical links while copying regular files with preserved timestamps'))
    if run_git('rev-parse', 'HEAD').strip() != BASE:
        raise ValueError('Repair branch has the wrong exact parent')
    old_source = original.MOUNT / OLD / 'source'
    # Copy the unchanged exact archive files and recursive submodule contents,
    # preserving timestamps so compiled exact-base objects can be reused.
    for path in sorted(old_source.rglob('*')):
        target = SOURCE / path.relative_to(old_source)
        if path.is_symlink():
            if target.is_symlink() and target.readlink() == path.readlink():
                continue
            if target.exists() or target.is_symlink():
                raise ValueError('Exact source symlink differs from checkout: '+str(path))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(path.readlink())
        elif path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            shutil.copy2(path, target)
    if run_git('diff', '--ignore-submodules', '--name-only'):
        raise ValueError('Copied exact source differs from the Git parent')
    source_manifest = read(original.RECOVERY / 'baselines' / OLD / 'source_manifest.json')
    for relative, expected in source_manifest['pinned_source_blobs_checked'].items():
        path = SOURCE / relative
        actual = hashlib.sha256(str(path.readlink()).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        if actual != expected:
            raise ValueError('Unmodified repair checkout differs from exact source: '+relative)
    write(REPAIR / 'before_edit.json', dict(status=run_git('status', '--short'), HEAD=run_git('rev-parse', 'HEAD').strip(),
        remotes=run_git('remote', '-v'), latest_commit=run_git('log', '-1', '--oneline'),
        upstream_base_sha=BASE, branch=BRANCH, exact_recursive_source_binding=binding(original.RECOVERY / 'baselines' / OLD / 'source_manifest.json')))
    identity = {key:subprocess.check_output(['/mnt/d/Git/cmd/git.exe', 'config', '--get', 'user.'+key], text=True, cwd=ROOT).strip()
                for key in ('name', 'email')}
    for key,value in identity.items():
        run_git('config', 'user.'+key, value)
    text = (SOURCE / FILE).read_text()
    for member in ('getLibertyScanIn', 'getLibertyScanOut'):
        before = f'findITerm({member}(test_cell_))'
        if text.count(before) != 1:
            raise ValueError('Expected unique unqualified call not found: '+member)
        text = text.replace(before, f'findITerm(db_network_->{member}(test_cell_))')
    (SOURCE / FILE).write_text(text)
    run_git('diff', '--check')
    if run_git('diff', '--numstat').strip() != '2\t2\t'+FILE:
        raise ValueError('Repair exceeds the two receiver-only lines')
    patch = run_git('diff', '--no-ext-diff', '--binary')
    (REPAIR / 'patch.diff').write_text(patch)
    (REPAIR / 'diagnosis.md').write_text('''# B3 receiver-only compile repair

Exact B2 is unchanged and already built/qualified. The defect is in B3 PR #10666,
base `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. The original failure is preserved.

`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` invoke nonstatic
`sta::dbNetwork` members as unqualified functions. The declarations are already
included in dbNetwork.hh:436–437; adding another package/header cannot supply an
object receiver. Existing methods use `db_network_->` at lines48,58,69,74,79.

The OneBitScanCell constructor stores its supplied STA network. ScanCellFactory
obtains `sta->getDbNetwork()`, derives the TestCell from the same live network,
rejects invalid TestCells and passes that network to the cell. OpenRoad creates
STA before DFT; scan architecture/optimization runs synchronously with that STA.
The network lives until STA teardown. No ownership, lifetime or API change occurs.

The patch adds only `db_network_->` to the two existing calls. It changes no
clustering, scan ordering, cost, parameters, NN/2-Opt/3-Opt, endpoint semantics,
DFT/database behavior or formatting outside those immediate calls. B3R is the
separately labeled derivative; it is never reported as byte-exact B3.
''')
    write(REPAIR / 'patch_proposal.json', dict(upstream_base_sha=BASE, branch=BRANCH, remote=REMOTE,
        repair_commit_sha=None, patch_sha256=binding(REPAIR / 'patch.diff')['sha256'], patch=binding(REPAIR / 'patch.diff'),
        changed_files=[FILE], changed_lines=dict(additions=2,deletions=2), changed_source_sha256={FILE:binding(SOURCE / FILE)['sha256']},
        source_path=str(SOURCE), identity=identity, semantics='Only the two missing db_network_ receivers; exact B2 unchanged'))
    print('COPYING_INDEPENDENT_EXACT_BASE_BUILD_CACHE', flush=True)
    shutil.copytree(original.MOUNT / OLD / 'build', BUILD, symlinks=True)
    cache = {}
    for path in sorted(BUILD.rglob('*')):
        if path.is_file() and not path.is_symlink():
            relative = str(path.relative_to(BUILD))
            old = original.MOUNT / OLD / 'build' / relative
            item = binding(path)
            if item['sha256'] != binding(old)['sha256']:
                raise ValueError('Copied compiler cache differs: '+relative)
            cache[relative] = dict(bytes=item['bytes'],sha256=item['sha256'])
    DATA.mkdir(parents=True, exist_ok=True)
    inventory = DATA / 'B3R_copied_build_inventory.json.gz'
    with gzip.open(inventory, 'wt') as stream:
        json.dump(cache, stream, sort_keys=True)
    write(REPAIR / 'build_cache_reuse.json', dict(status='PASS', files=len(cache), bytes=sum(x['bytes'] for x in cache.values()),
        inventory=binding(inventory), original_failed_build=binding(original.RECOVERY / 'baselines' / OLD / 'build_result.json'),
        original_source_and_build_changed=False, container_source_alias=f'/build_storage/{OLD}/source',
        container_build_alias=f'/build_storage/{OLD}/build', host_source=str(SOURCE), host_build=str(BUILD),
        policy='Independent byte-verified exact-base object copy; repair source is read-only; full target is rebuilt, unchanged base objects can be reused'))
    print('B3R_TWO_CALL_PATCH_AND_INDEPENDENT_CACHE_PREPARED', flush=True)
    return 0


def submodule_metadata():
    """Restore exact Git identities without checking out or rewriting source files."""
    gate()
    records=[]
    for item in read(original.RECOVERY / 'baselines' / OLD / 'build_sources.json')['submodules']:
        path=SOURCE / item['path']
        label='metadata_'+item['path'].replace('/','_')
        if not (path/'.git').exists():
            subprocess.run(['git','init',str(path)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(path),'remote','add','origin','https://github.com/'+item['repository']+'.git'],check=True)
        if not (FOLDER/(label+'.execution.json')).exists():
            if execute(['git','-C',str(path),'fetch','--depth=1','origin',item['commit']],label):
                return 1
        subprocess.run(['git','-C',str(path),'read-tree',item['commit']],check=True)
        subprocess.run(['git','-C',str(path),'update-ref','HEAD',item['commit']],check=True)
        sha=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        diff=subprocess.check_output(['git','-C',str(path),'diff','--ignore-submodules','--name-only'],text=True)
        archive_substitution={}
        if item['path']=='third-party/abc' and diff=='.gitcommit\n' and (path/'.gitcommit').read_text().strip()==sha:
            # GitHub's archive export-subst expands this tracked placeholder.
            # Preserve the exact archived bytes; this is a version stamp only.
            archive_substitution['.gitcommit']=binding(path/'.gitcommit')
            run_git('config','submodule.src/abc.ignore','dirty')
        elif diff:
            raise ValueError('Submodule archive differs from exact Git identity: '+item['path']+' '+diff)
        if sha!=item['commit']:
            raise ValueError('Submodule archive differs from exact Git identity: '+item['path']+' '+diff)
        records.append(dict(path=item['path'],repository=item['repository'],commit=sha,tracked_diff=diff,
            archive_export_subst=archive_substitution,
            metadata_fetch=binding(FOLDER/(label+'.execution.json'))))
    write(REPAIR/'submodule_git_metadata.json',dict(status='PASS',submodules=records,
        policy='Git objects/index/HEAD only; no checkout or source rewrite. Restore independent CMake version detection at exact archived pins.',
        main_tracked_diff=run_git('diff','--numstat')))
    return 0


def configure(final=False):
    gate()
    version = run_git('rev-parse', 'HEAD').strip() if final else BASE+'-B3R-uncommitted'
    if final and version == BASE:
        raise ValueError('Repair must have its own DCO-signed immutable commit')
    args = ['cmake', '-S', f'/build_storage/{OLD}/source', '-B', f'/build_storage/{OLD}/build',
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_GUI=OFF', '-DBUILD_PYTHON=ON', '-DENABLE_TESTS=OFF',
        '-DLINK_TIME_OPTIMIZATION=OFF', '-DCMAKE_C_COMPILER=/usr/bin/gcc', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
        '-DOPENROAD_VERSION='+version, '-DSWIG_EXECUTABLE=/usr/local/bin/swig',
        '-DTCL_HEADER=/usr/include/tcl8.6/tcl.h', '-DTCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libtcl8.6.so',
        '-DCMAKE_PREFIX_PATH=/build_storage/toolchain;/opt/or-tools;/usr/local',
        '-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
    label = 'configure_final' if final else 'configure_repair_validation'
    if (FOLDER/(label+'.execution.json')).exists():
        if final:
            raise ValueError('Final configure receipt already exists')
        label += '_attempt2'
    rc = execute(docker(args), label)
    cache = FOLDER / (label+'.CMakeCache.txt')
    shutil.copy2(BUILD / 'CMakeCache.txt', cache)
    proof = read(original.RECOVERY / 'toolchain/qualification.json')
    validate_resolution(parse_cache(cache), proof, version)
    write(FOLDER / (label+'.dependency_resolution.json'), dict(status='PASS' if not rc else 'FAILED',
        source_version=version, actual_cmake_cache=binding(cache), independent_prerequisite=binding(original.RECOVERY / 'toolchain/qualification.json'),
        actual_resolution=parse_cache(cache), SWIG_version='4.3.0', Tcl_header_version='8.6.12', Tcl_library_runtime_version='8.6.12'))
    if not rc:
        write(FOLDER/'successful_configuration.json',dict(label=label,source_version=version,
            execution=binding(FOLDER/(label+'.execution.json')),resolution=binding(FOLDER/(label+'.dependency_resolution.json')),
            generated_version_header_writable=True,original_source_and_build_changed=False,
            submodule_identities=binding(REPAIR/'submodule_git_metadata.json')))
    return rc


def compile_target(target, label):
    gate()
    DATA.mkdir(parents=True, exist_ok=True)
    resource = DATA / (label+'.resource.txt')
    args = ['/usr/bin/time', '-v', '-o', '/scratch/receiver_recovery_20261003/'+resource.name,
        'cmake', '--build', f'/build_storage/{OLD}/build', '--parallel', '2', '--target', target]
    rc = execute(docker(args), label)
    if resource.exists():
        shutil.copy2(resource, FOLDER / (label+'.container.resource.txt'))
    return rc


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare','metadata','configure','narrow','build','configure_final','build_final'))
    action=parser.parse_args().action
    if action=='prepare': result=prepare()
    elif action=='metadata': result=submodule_metadata()
    elif action.startswith('configure'): result=configure(action.endswith('final'))
    else: result=compile_target('dft_cells_lib' if action=='narrow' else 'openroad',
        {'narrow':'narrow_receiver_target','build':'build_repair_validation','build_final':'build_final'}[action])
    raise SystemExit(result)
