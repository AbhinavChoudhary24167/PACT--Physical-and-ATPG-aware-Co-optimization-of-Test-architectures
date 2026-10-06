#!/usr/bin/env python3
"""Preserve inactive failed-build fixture cache on F; retain D path aliases."""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_experiment_receipts import atomic_write

CACHE = Path('/mnt/d/PACT_EXPERIMENTS/tmp/pact_oss_20261003/B2_openroad_10176/build_source')
DEST = Path('/mnt/f/PACT_HOST_CACHE/20261006/gate09-source-fixtures')
RECEIPT = ROOT / 'results/pact_gate09_open_source_20261005/storage_fixture_relocation.json'


def main():
    if RECEIPT.exists() or DEST.exists() or CACHE.is_symlink() or CACHE.resolve() != CACHE:
        raise ValueError('Preserve prior relocation; exact inactive cache root required')
    candidates = [p for p in CACHE.rglob('*') if p.is_file() and not p.is_symlink()
                  and p.resolve().is_relative_to(CACHE) and
                  any(part in ('test','examples','doc') for part in p.relative_to(CACHE).parts)]
    selected, size = [], 0
    for path in sorted(candidates,key=lambda p:(-p.stat().st_size,str(p))):
        selected.append(path)
        size += path.stat().st_size
        if size >= 1024**3:
            break
    if size < 1024**3 or shutil.disk_usage(DEST.parent.parent).free < size+5*1024**3:
        raise ValueError('Insufficient recoverable fixture cache or destination margin')
    rows = [dict(source=admission.binding(p), destination=str(DEST / p.relative_to(CACHE))) for p in selected]
    record = dict(schema='pact_gate09_inactive_fixture_cache_relocation_v1', status='COPYING',
        source_root=str(CACHE), destination_root=str(DEST), selected_bytes=size, records=rows,
        policy='Inactive failed NTFS build source-test fixture cache; all bytes retained on F and D names retained as aliases',
        scientific_results_deleted=0, source_semantics_changes=0, qualified_binary_changes=0,
        D_free_bytes_before=shutil.disk_usage('/mnt/d').free)
    atomic_write(RECEIPT, record, immutable=True)
    for row in rows:
        source, destination = Path(row['source']['path']), Path(row['destination'])
        if source.resolve() != source or not source.is_relative_to(CACHE) or not destination.is_relative_to(DEST):
            raise ValueError('Resolved relocation path escaped explicit cache roots')
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
        if admission.digest(destination) != row['source']['sha256'] or destination.stat().st_size != row['source']['bytes']:
            raise ValueError('Destination differs; all original files retained')
        row['destination_binding'] = admission.binding(destination)
    record['status'] = 'ALL_COPIES_REHASHED_ORIGINALS_RETAINED'
    atomic_write(RECEIPT, record)
    for row in rows:
        source, destination = Path(row['source']['path']), Path(row['destination'])
        # No recursive deletion: remove only this verified duplicate regular file.
        if source.resolve() != source or not source.is_relative_to(CACHE) or admission.verify(row['source'])['status'] != 'PASS':
            raise ValueError('Original changed; duplicate removal not permitted')
        source.unlink()
        try:
            source.symlink_to(destination)
        except Exception:
            shutil.copyfile(destination,source)
            raise
        if admission.verify(row['source'])['status'] != 'PASS':
            raise ValueError('Preserved D path no longer reads identical bytes')
        row['D_alias_verified'] = True
        row['verified_duplicate_removed_bytes'] = row['source']['bytes']
        atomic_write(RECEIPT,record)
    record.update(status='PASS', D_free_bytes_after=shutil.disk_usage('/mnt/d').free,
                  F_free_bytes_after=shutil.disk_usage('/mnt/f').free,
                  source=admission.binding(Path(__file__)))
    atomic_write(RECEIPT, record)
    print('GATE09_FIXTURE_CACHE_RELOCATION_PASS',size,len(rows),flush=True)


if __name__=='__main__':
    main()
