#!/usr/bin/env python3
"""Configure an immutable OSS revision in isolated D: storage.

No qualified system package, binary, source checkout, or physical flow is changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

from pact_oss_benchmark import OUT, binding, read, write
from pact_oss_acquire import TEMP, json_get
from pact_oss_preflight import execute


def archive(repo, commit, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        subprocess.run(['curl', '-L', '--fail', '--max-time', '180', '--silent', '--show-error',
                        f'https://codeload.github.com/{repo}/tar.gz/{commit}', '-o', str(destination)], check=True)
    return binding(destination)


def extract(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path) as stream:
        # Keep exact source and fixtures, and strip only the archive root.
        for member in stream:
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            member.name = str(Path(*parts[1:]))
            stream.extract(member, destination, filter='data')


def submodules(repo, commit, destination, cache, prefix=''):
    tree = json_get(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Truncated immutable submodule inventory')
    links = [r for r in tree['tree'] if r['type'] == 'commit']
    if not links:
        return []
    import configparser
    config = configparser.ConfigParser()
    config.read(destination / '.gitmodules')
    urls = {config[s]['path']: config[s]['url'] for s in config.sections()}
    result = []
    for row in links:
        url = urls[row['path']]
        if url.startswith('../../'):
            child_repo = url[6:].removesuffix('.git')
        elif url.startswith('https://github.com/'):
            child_repo = url.removeprefix('https://github.com/').removesuffix('.git')
        else:
            raise ValueError('Unsupported pinned public submodule URL: ' + url)
        child = destination / row['path']
        name = prefix + row['path']
        tar = cache / (name.replace('/', '_') + '_' + row['sha'] + '.tar.gz')
        artifact = archive(child_repo, row['sha'], tar)
        print('SUBMODULE', name, row['sha'], flush=True)
        extract(tar, child)
        result.append(dict(path=name, repository=child_repo, commit=row['sha'], archive=artifact))
        result.extend(submodules(child_repo, row['sha'], child, cache, name + '/'))
    return result


def main(method):
    folder = OUT / 'baselines' / method
    pin = read(folder / 'source_pin.json')
    scratch = TEMP / method
    source = scratch / 'build_source'
    tar = scratch / 'source.tar.gz'
    repo = pin['repository'].removeprefix('https://github.com/')
    root_archive = archive('The-OpenROAD-Project/OpenROAD', pin['commit'], tar)
    if not (source / 'third-party/CMakeLists.txt').exists():
        extract(tar, source)
    # Bind the build's exact DFT code to the acquired commit-addressed Git blobs.
    for relative, expected in pin['source_files'].items():
        path = source / relative
        sha = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        if sha != expected['sha256']:
            raise ValueError('Build source differs from pinned Git blob: ' + relative)
    children = submodules(repo, pin['commit'], source, scratch / 'submodule_archives')
    write(folder / 'build_sources.json', dict(repository=pin['repository'], commit=pin['commit'],
                                             main_archive=root_archive, submodules=children,
                                             DFT_source_hash_equivalence='PASS', source_directory=str(source)))
    commands = ['cmake', '-S', str(source), '-B', str(scratch / 'build'),
                '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_GUI=OFF', '-DBUILD_PYTHON=ON',
                '-DENABLE_TESTS=OFF', '-DENABLE_GPU=OFF', '-DLINK_TIME_OPTIMIZATION=OFF',
                '-DOPENROAD_VERSION=' + pin['commit'], '-DCMAKE_INSTALL_PREFIX=' + str(scratch / 'install')]
    result = execute(commands, folder, 'configure')
    write(folder / 'build_status.json', dict(status='CONFIGURED' if result['returncode'] == 0 else 'CONFIGURATION_FAILED',
                                            commit=pin['commit'], configuration=result,
                                            binary_built=False, baseline_reproduced=False,
                                            environment_policy='Qualified /usr/bin/openroad, ORFS and system dependencies untouched; all generated build data isolated on D:'))
    if result['returncode']:
        print('STOP_BASELINE_BUILD', method, 'CONFIGURATION_FAILED', flush=True)
        return 2
    print('CONFIGURED', method, flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('method', choices=('B2_openroad_10176', 'B3_openroad_10666'))
    args = parser.parse_args()
    raise SystemExit(main(args.method))
