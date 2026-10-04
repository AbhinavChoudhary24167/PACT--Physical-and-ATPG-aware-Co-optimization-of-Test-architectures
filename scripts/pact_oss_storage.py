#!/usr/bin/env python3
"""Verify D-backed mount on every invocation; recover an owned fallback build."""
from pact.experiment_storage import experiment_root
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from pact_oss_benchmark import OUT, binding, write
from pact_oss_acquire import TEMP

DATA = TEMP / 'recovery_20261003'
DISK = DATA / 'build-storage.ext4'
MOUNT = Path(str(experiment_root() / "build"))
PROOF = OUT / 'recovery_20261003'


def mount_info(path):
    result = subprocess.run(['findmnt', '-J', str(path)], text=True, capture_output=True)
    return json.loads(result.stdout)['filesystems'][0] if result.returncode == 0 else None


def ensure():
    if not DISK.is_file() or DISK.stat().st_size != 16 * 1024**3:
        raise RuntimeError('Expected dedicated D: ext4 image is missing')
    MOUNT.mkdir(parents=True, exist_ok=True)
    info = mount_info(MOUNT)
    if info is None:
        if list(MOUNT.iterdir()):
            raise RuntimeError('Refusing to hide an unmounted fallback build; relocate it first')
        subprocess.run(['mount', '-o', 'loop', str(DISK), str(MOUNT)], check=True)
        info = mount_info(MOUNT)
    if not info or info['fstype'] != 'ext4' or not info['source'].startswith('/dev/loop'):
        raise RuntimeError('Build prefix is not mounted on the dedicated D: image')
    backing = subprocess.check_output(['losetup', '-n', '-O', 'BACK-FILE', info['source']], text=True).strip()
    if Path(backing).resolve() != DISK.resolve():
        raise RuntimeError('Loop device backing file differs from authorized D: image')
    print('D_BACKED_BUILD_MOUNT_VERIFIED', info['source'], backing, flush=True)
    return info


def inventory(root):
    rows = {}
    for path in sorted(root.rglob('*')):
        if path.parts[len(root.parts)] == 'lost+found':
            continue
        relative = str(path.relative_to(root))
        if path.is_symlink():
            rows[relative] = dict(symlink=str(path.readlink()))
        elif path.is_file():
            rows[relative] = dict(bytes=path.stat().st_size, sha256=binding(path)['sha256'])
    return rows


def relocate():
    started = datetime.now(timezone.utc).isoformat()
    if mount_info(MOUNT) is not None:
        raise RuntimeError('Relocation applies only to the observed unmounted fallback')
    expected_roots = {'B2_openroad_10176', 'toolchain', 'toolchain_build', 'toolchain_sources'}
    if {p.name for p in MOUNT.iterdir()} != expected_roots:
        raise RuntimeError('Fallback directory contains unexpected files; no deletion is permitted')
    backup = Path(str(experiment_root() / 'build-backup'))
    temporary = Path(str(experiment_root() / 'build-transfer'))
    if backup.exists():
        raise RuntimeError('Relocation backup already exists')
    temporary.mkdir(parents=True, exist_ok=True)
    if list(temporary.iterdir()):
        raise RuntimeError('Temporary mount path is not empty')
    subprocess.run(['mount', '-o', 'loop', str(DISK), str(temporary)], check=True)
    if {p.name for p in temporary.iterdir()} - {'lost+found'}:
        raise RuntimeError('Destination disk contains data; refusing to overwrite it')
    before = inventory(MOUNT)
    print('COPYING_VERIFIED_PARTIAL_BUILD', len(before), 'files', flush=True)
    for source in MOUNT.iterdir():
        shutil.copytree(source, temporary / source.name, symlinks=True)
    after = inventory(temporary)
    if before != after:
        raise RuntimeError('Relocation hash comparison failed; original retained')
    subprocess.run(['sync'], check=True)
    subprocess.run(['umount', str(temporary)], check=True)
    MOUNT.rename(backup)
    MOUNT.mkdir()
    info = ensure()
    if before != inventory(MOUNT):
        raise RuntimeError('Remounted D: copy differs; original retained')
    inventory_path = DATA / 'relocated_build_inventory.json.gz'
    with gzip.open(inventory_path, 'wt') as stream:
        json.dump(before, stream, sort_keys=True)
    # Delete only the exact newly-created generated backup after byte-for-byte
    # verification of its recoverable D: copy. No qualified/user path is touched.
    if backup.resolve() != Path(str(experiment_root() / 'build-backup')):
        raise RuntimeError('Unexpected resolved cleanup target')
    shutil.rmtree(backup)
    write(PROOF / 'storage_relocation.json', dict(status='PASS', timestamp_start=started,
          timestamp_end=datetime.now(timezone.utc).isoformat(), files_verified=len(before),
          data_bytes_verified=sum(r.get('bytes', 0) for r in before.values()),
          exact_partial_source_and_build_copy=True, inventory=binding(inventory_path), disk_path=str(DISK),
          mount=info, source_root=str(MOUNT), source_semantics_or_build_flags_changed=False,
          original_fallback_removed_only_after_complete_hash_equivalence=True,
          cause='WSL dropped the short-lived initial loop mount between invocations; build prefix temporarily used WSL root filesystem',
          prevention='Every later build/generation invocation independently verifies and restores the same D:-backed mount',
          relocation_script=binding(__file__)))
    print('PARTIAL_BUILD_RELOCATION_PASS', len(before), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('ensure', 'relocate'))
    globals()[parser.parse_args().action]()
