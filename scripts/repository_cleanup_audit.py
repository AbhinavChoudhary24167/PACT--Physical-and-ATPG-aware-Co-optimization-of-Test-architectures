#!/usr/bin/env python3
"""Measure checkout and Git storage without following links or modifying history."""
import argparse
from collections import defaultdict
import csv
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/repository_cleanup'
SOURCE_SUFFIXES = {'.py', '.sh', '.tcl', '.mk', '.sdc', '.toml'}
BINARY_SUFFIXES = {'.gz', '.zip', '.png', '.pdf', '.npz', '.npy', '.odb', '.gds', '.so', '.a', '.exe', '.dll'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8', errors='replace')


def files(folder):
    for directory, dirs, names in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory)/d).is_symlink()
                   and not getattr(Path(directory)/d, 'is_junction', lambda: False)()]
        for name in names:
            path = Path(directory)/name
            try:
                if not path.is_symlink() and path.is_file():
                    yield path
            except OSError:
                continue


def line_count(path):
    if path.suffix.lower() in BINARY_SUFFIXES:
        return 0
    count = 0
    last = b''
    with path.open('rb') as stream:
        chunk = stream.read(1024*1024)
        if b'\0' in chunk:
            return 0
        while chunk:
            count += chunk.count(b'\n')
            last = chunk[-1:]
            chunk = stream.read(1024*1024)
    return count + int(bool(last) and last != b'\n')


def table(rows, header):
    return '| ' + ' | '.join(header) + ' |\n|' + '|'.join('---' for _ in header) + '|\n' + ''.join('| ' + ' | '.join(map(str, r)) + ' |\n' for r in rows)


def measure(label, history=False):
    REPORT.mkdir(parents=True, exist_ok=True)
    tracked = set(filter(None, git('ls-files', '-z').split('\0')))
    rows, totals = [], defaultdict(lambda: [0, 0])
    checkout = git_size = 0
    largest = []
    for path in files(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        size = path.stat().st_size
        if rel.startswith('.git/'):
            git_size += size
            continue
        checkout += size
        totals[rel.split('/')[0]][0] += 1
        totals[rel.split('/')[0]][1] += size
        largest.append((size, rel))
        if rel in tracked:
            rows.append((rel, size, line_count(path)))
    rows.sort()
    with (REPORT/f'{label}_tracked_inventory.tsv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['path', 'bytes', 'text_lines'])
        writer.writerows(rows)
    source_lines = sum(lines for p, _, lines in rows if p.startswith(('src/', 'scripts/', 'tests/')) and Path(p).suffix in SOURCE_SUFFIXES)
    snapshot = dict(branch=git('branch', '--show-current').strip(), head=git('rev-parse', 'HEAD').strip(),
                    tracked_files=len(rows), tracked_bytes=sum(r[1] for r in rows), tracked_text_lines=sum(r[2] for r in rows),
                    source_test_lines=source_lines, checkout_bytes=checkout, git_bytes=git_size,
                    total_bytes=checkout+git_size, directories=dict(totals), largest_tracked=sorted(rows, key=lambda r:-r[1])[:100])
    (REPORT/f'{label}_metrics.json').write_text(json.dumps(snapshot, indent=2)+'\n', encoding='utf-8')
    status = git('status', '--short', '-uall')
    sub = subprocess.run(['git', 'submodule', 'status'], cwd=ROOT, capture_output=True, text=True)
    gitlinks = [r for r in git('ls-files', '--stage').splitlines() if r.startswith('160000')]
    (REPORT/f'{label}_git_state.txt').write_text(f'Branch: {snapshot["branch"]}\nHEAD: {snapshot["head"]}\n\n{status}\n{git("count-objects", "-vH")}\nSubmodule command exit: {sub.returncode}\n{sub.stdout}{sub.stderr}\nTracked gitlinks: {gitlinks}\n', encoding='utf-8')
    doc = f'# {label.replace("_", " ").title()} inventory\n\nLogical file bytes; links are excluded. Text LOC counts LF-separated records (including a final unterminated line), excluding binary files. It includes generated text and is distinct from source/test LOC. The Git index supplies tracked paths.\n\n' + table([(k, snapshot[k]) for k in ('tracked_files','tracked_bytes','tracked_text_lines','source_test_lines','checkout_bytes','git_bytes','total_bytes')], ['Measurement','Value'])
    doc += '\n## Directory storage\n\n' + table([(p,n,b) for p,(n,b) in sorted(totals.items(), key=lambda r:-r[1][1])], ['Directory','Files','Bytes'])
    doc += '\n## Largest tracked files\n\n' + table(sorted(rows, key=lambda r:-r[1])[:100], ['Path','Bytes','Text lines'])
    doc += '\n## Largest checkout files (including ignored dependencies)\n\n' + table([(p,b) for b,p in sorted(largest, reverse=True)[:100]], ['Path','Bytes'])
    if history:
        names = {}
        for line in git('rev-list', '--objects', '--all').splitlines():
            sha, _, name = line.partition(' ')
            names[sha] = name
        blobs = []
        for line in git('cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize) %(objectsize:disk)').splitlines():
            sha, kind, size, disk = line.split()
            if kind == 'blob':
                blobs.append((sha, int(size), int(disk), names.get(sha, '(unreachable or unnamed)')))
        blobs.sort(key=lambda r:-r[1])
        with (REPORT/'historical_blobs.tsv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(['oid','bytes','disk_bytes','historical_path'])
            writer.writerows(blobs[:200])
        categories = defaultdict(lambda:[0,0])
        for sha,size,disk,name in blobs:
            key = name.split('/')[0] if '/' in name else '(root or unreachable)'
            categories[key][0] += size
            categories[key][1] += disk
        (REPORT/'history_metrics.json').write_text(json.dumps(dict(blob_count=len(blobs), unique_blob_bytes=sum(r[1] for r in blobs), categories=dict(categories)),indent=2)+'\n',encoding='utf-8')
        doc += '\n## Historical storage\n\n' + table([(p,*v) for p,v in sorted(categories.items(),key=lambda r:-r[1][0])], ['Category','Uncompressed unique blob bytes','Object disk bytes'])
        doc += '\nObject disk bytes depend on packing/deltas and may count duplicate loose/packed storage differently from pack totals. No garbage collection or history rewrite was performed. Largest blobs are in `historical_blobs.tsv`.\n'
    (REPORT/f'{label}_inventory.md').write_text(doc, encoding='utf-8')
    print(json.dumps({k:v for k,v in snapshot.items() if k not in ('directories','largest_tracked')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', choices=['pre_cleanup','post_cleanup'], required=True)
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    measure(args.label, args.history)
