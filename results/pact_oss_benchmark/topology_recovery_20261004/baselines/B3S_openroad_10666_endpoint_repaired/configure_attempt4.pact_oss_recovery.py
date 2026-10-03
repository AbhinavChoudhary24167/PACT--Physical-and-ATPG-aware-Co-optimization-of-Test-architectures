#!/usr/bin/env python3
"""Reproduce pinned external generators without modifying the qualified backend.

All new receipts are additive under recovery_20261003. The historical seal stays
unchanged. Commands run in an immutable Docker image and are recorded verbatim.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

from pact_oss_benchmark import ROOT, OUT, binding, read, write
from pact_oss_acquire import TEMP

IMAGE = 'sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e'
RECOVERY = OUT / 'recovery_20261003'
DATA = TEMP / 'recovery_20261003'
MOUNT = Path('/mnt/pact-oss-recovery')
METHOD = 'B2_openroad_10176'


def execute(args, folder, label):
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / (label + '.execution.json')
    if receipt.exists():
        raise ValueError('Refusing to overwrite execution: ' + str(receipt))
    snapshot = folder / (label + '.' + Path(__file__).name)
    shutil.copy2(__file__, snapshot)
    start = time.perf_counter()
    print('EXECUTING', json.dumps(args), flush=True)
    with (folder / (label + '.log')).open('w') as log:
        result = subprocess.run(['/usr/bin/time', '-v', '-o', str(folder / (label + '.resource.txt')), *args],
                                stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    record = dict(command=args, returncode=result.returncode, elapsed_seconds=time.perf_counter()-start,
                  timestamp=datetime.now(timezone.utc).isoformat(), log=binding(folder / (label + '.log')),
                  resources=binding(folder / (label + '.resource.txt')), executed_driver=binding(snapshot))
    write(receipt, record)
    print('FINISHED', label, result.returncode, record['elapsed_seconds'], flush=True)
    return result.returncode


def docker(args):
    return ['docker', 'run', '--rm', '--network=none',
            '--mount', f'type=bind,source={ROOT},target=/workspace,readonly',
            '--mount', f'type=bind,source={TEMP},target=/scratch',
            '--mount', f'type=bind,source={MOUNT},target=/build_storage',
            '--entrypoint', '/bin/bash', IMAGE, '-c', 'exec "$@"', 'pact-command', *args]


def storage():
    DATA.mkdir(parents=True, exist_ok=True)
    disk = DATA / 'build-storage.ext4'
    MOUNT.mkdir(parents=True, exist_ok=True)
    if not disk.exists():
        with disk.open('xb') as stream:
            stream.truncate(16 * 1024**3)
        subprocess.run(['mkfs.ext4', '-F', '-m', '0', str(disk)], check=True)
    if subprocess.run(['mountpoint', '-q', str(MOUNT)]).returncode:
        subprocess.run(['mount', '-o', 'loop', str(disk), str(MOUNT)], check=True)
    actual = subprocess.check_output(['findmnt', '-J', str(MOUNT)], text=True)
    write(RECOVERY / 'storage.json', dict(disk_path=str(disk), mount_path=str(MOUNT),
          size_bytes=disk.stat().st_size, allocation_bytes=disk.stat().st_blocks * 512,
          findmnt=json.loads(actual), policy='Dedicated ext4 image on authorized D: storage; no existing filesystem changed'))


def provision():
    storage()
    inspect = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE], text=True))[0]
    if inspect['Id'] != IMAGE:
        raise RuntimeError('Wrong immutable Docker image')
    write(RECOVERY / 'toolchain_image.json', inspect)
    rc = execute(docker(['python3', '/workspace/scripts/pact_oss_toolchain_probe.py']), RECOVERY / 'toolchain', 'prerequisite_probe')
    if rc:
        return rc
    qualification = DATA / 'toolchain_probe/qualification.json'
    shutil.copy2(qualification, RECOVERY / 'toolchain/qualification.json')
    shutil.copy2(DATA / 'toolchain_probe/build/CMakeCache.txt', RECOVERY / 'toolchain/CMakeCache.txt')
    return 0


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as stream:
        for member in stream:
            parts = Path(member.name).parts
            if len(parts) > 1:
                member.name = str(Path(*parts[1:]))
                stream.extract(member, destination, filter='data')


def sources():
    folder = RECOVERY / 'baselines' / METHOD
    receipt = folder / 'source_manifest.json'
    if receipt.exists():
        return read(receipt)
    historical = read(OUT / 'baselines' / METHOD / 'build_sources.json')
    pin = read(OUT / 'baselines' / METHOD / 'source_pin.json')
    source = MOUNT / METHOD / 'source'
    for entry in [dict(path='', archive=historical['main_archive'])] + historical['submodules']:
        item = entry['archive']
        if binding(item['path'])['sha256'] != item['sha256']:
            raise RuntimeError('Saved archive integrity failure: ' + item['path'])
        print('EXTRACTING_PINNED_SOURCE', entry['path'], flush=True)
        extract(item['path'], source / entry['path'])
    checked = {}
    for relative, expected in pin['source_files'].items():
        path = source / relative
        actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        if actual != expected['sha256']:
            raise RuntimeError('Pinned source Git blob mismatch: ' + relative)
        checked[relative] = actual
    record = dict(commit=pin['commit'], repository=pin['repository'], saved_build_sources=binding(OUT / 'baselines' / METHOD / 'build_sources.json'),
                  source_pin=binding(OUT / 'baselines' / METHOD / 'source_pin.json'), source_directory=str(source),
                  saved_archive_and_submodule_hashes_verified=True, pinned_source_blobs_checked=checked,
                  source_modifications=[], extraction='Fresh exact archives into dedicated D:-backed ext4; generated build headers excluded from source semantics')
    write(receipt, record)
    return record


def require_prerequisites():
    qualification = RECOVERY / 'toolchain/qualification.json'
    proof = read(qualification)
    if proof['status'] != 'PASS' or not proof['B2_configuration_retry_authorized_by_prerequisites']:
        raise RuntimeError('Independent SWIG/Tcl gate has not passed')
    if binding(DATA / 'toolchain_probe/qualification.json')['sha256'] != binding(qualification)['sha256']:
        raise RuntimeError('Independent prerequisite evidence changed')
    image = read(RECOVERY / 'toolchain_image.json')
    if image['Id'] != IMAGE:
        raise RuntimeError('Toolchain image changed')


def dependencies():
    require_prerequisites()
    folder = RECOVERY / 'toolchain'
    tag = json.loads(subprocess.check_output(['curl', '--fail', '--silent', '--show-error', '--max-time', '60',
                                             'https://api.github.com/repos/fmtlib/fmt/commits/12.1.0'], text=True))
    commit = tag['sha']
    write(folder / 'fmt_tag_resolution.json', tag)
    archive = DATA / ('fmt_' + commit + '.tar.gz')
    if not archive.exists():
        subprocess.run(['curl', '--fail', '-L', '--silent', '--show-error', '--max-time', '120',
                        'https://codeload.github.com/fmtlib/fmt/tar.gz/' + commit, '-o', str(archive)], check=True)
    source = MOUNT / 'toolchain_sources/fmt'
    extract(archive, source)
    commands = [
        ['cmake', '-S', '/build_storage/toolchain_sources/fmt', '-B', '/build_storage/toolchain_build/fmt',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=/build_storage/toolchain',
         '-DFMT_TEST=OFF', '-DFMT_DOC=OFF', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON'],
        ['cmake', '--build', '/build_storage/toolchain_build/fmt', '--parallel', '2', '--target', 'install']]
    for label, args in zip(('fmt_configure', 'fmt_build_install'), commands):
        rc = execute(docker(args), folder, label)
        if rc:
            return rc
    write(folder / 'fmt_source.json', dict(repository='https://github.com/fmtlib/fmt', version='12.1.0',
          commit=commit, archive=binding(archive), source_manifest_policy='Exact commit-addressed archive; no source edits',
          install_prefix='/build_storage/toolchain', source_requirement='Pinned slang external/CMakeLists.txt:8'))
    rc = execute(docker(['python3', '/workspace/scripts/pact_oss_dependency_probe.py']), folder, 'dependency_probe')
    if not rc:
        shutil.copy2(DATA / 'dependency_probe/qualification.json', folder / 'dependency_qualification.json')
        shutil.copy2(DATA / 'dependency_probe/build/CMakeCache.txt', folder / 'dependency_CMakeCache.txt')
    return rc


def audit_dependencies():
    require_prerequisites()
    folder = RECOVERY / 'toolchain'
    rc = execute(docker(['python3', '/workspace/scripts/pact_oss_dependency_probe.py', '--attempt', '2']), folder, 'dependency_probe_attempt2')
    if not rc:
        shutil.copy2(DATA / 'dependency_probe2/qualification.json', folder / 'dependency_qualification.json')
        shutil.copy2(DATA / 'dependency_probe2/build/CMakeCache.txt', folder / 'dependency_CMakeCache.txt')
    return rc


def configure():
    require_prerequisites()
    if read(RECOVERY / 'toolchain/dependency_qualification.json')['status'] != 'PASS':
        raise RuntimeError('Complete dependency audit has not passed')
    source = sources()
    folder = RECOVERY / 'baselines' / METHOD
    build = MOUNT / METHOD / 'build'
    if build.exists():
        raise RuntimeError('B2 recovery requires a clean out-of-source build')
    command = ['cmake', '-S', f'/build_storage/{METHOD}/source', '-B', f'/build_storage/{METHOD}/build',
               '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_GUI=OFF', '-DBUILD_PYTHON=ON',
               '-DENABLE_TESTS=OFF', '-DENABLE_GPU=OFF', '-DLINK_TIME_OPTIMIZATION=OFF',
               '-DCMAKE_C_COMPILER=/usr/bin/gcc', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
               '-DOPENROAD_VERSION=' + source['commit'], f'-DCMAKE_INSTALL_PREFIX=/build_storage/{METHOD}/install',
               '-DSWIG_EXECUTABLE=/usr/local/bin/swig', '-DTCL_HEADER=/usr/include/tcl8.6/tcl.h',
               '-DTCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libtcl8.6.so', '-DCMAKE_PREFIX_PATH=/build_storage/toolchain;/opt/or-tools;/usr/local',
               '-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0',
               '-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
    rc = execute(docker(command), folder, 'configure')
    if (build / 'CMakeCache.txt').exists():
        shutil.copy2(build / 'CMakeCache.txt', folder / 'CMakeCache.txt')
    write(folder / 'build_manifest.json', dict(status='CONFIGURED' if not rc else 'CONFIGURATION_FAILED',
          commit=source['commit'], image=IMAGE, prerequisites=binding(RECOVERY / 'toolchain/qualification.json'),
          source_manifest=binding(folder / 'source_manifest.json'), configuration=binding(folder / 'configure.execution.json'),
          binary_sha256=None, fixed_backend_unchanged=binding('/usr/bin/openroad')))
    return rc


def build():
    from pact_oss_storage import ensure
    ensure()
    require_prerequisites()
    folder = RECOVERY / 'baselines' / METHOD
    manifest = read(folder / 'build_manifest.json')
    if manifest['status'] != 'CONFIGURED':
        raise RuntimeError('B2 configuration has not succeeded')
    rc = execute(docker(['/usr/bin/time', '-v', '-o', '/scratch/recovery_20261003/build_resume1_container.resource.txt',
                        'cmake', '--build', f'/build_storage/{METHOD}/build', '--parallel', '2', '--target', 'openroad']), folder, 'build_resume1')
    if (DATA / 'build_resume1_container.resource.txt').exists():
        shutil.copy2(DATA / 'build_resume1_container.resource.txt', folder / 'build_resume1.container.resource.txt')
    binary = MOUNT / METHOD / 'build/bin/openroad'
    manifest.update(status='BUILT' if not rc else 'COMPILATION_FAILED', build=binding(folder / 'build_resume1.execution.json'),
                    configuration_manifest=binding(folder / 'build_manifest.json'),
                    first_build_interruption=binding(folder / 'build.execution.json'),
                    binary=binding(binary) if binary.exists() else None,
                    binary_sha256=binding(binary)['sha256'] if binary.exists() else None)
    write(folder / 'build_result.json', manifest)
    return rc


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('provision', 'dependencies', 'audit_dependencies', 'configure', 'build'))
    args = parser.parse_args()
    raise SystemExit(globals()[args.action]())
