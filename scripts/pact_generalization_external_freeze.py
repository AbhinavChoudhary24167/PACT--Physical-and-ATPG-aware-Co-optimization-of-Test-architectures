#!/usr/bin/env python3
"""Bind retained external route, measurement and technology evidence read-only."""
from pathlib import Path
import sys
from pact_generalization import ROOT,OUT,CORE,binding,now,read,sha,write


def collect(value, bindings):
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and 'sha256' in value:
            key=(value['path'],value['sha256'])
            bindings[key]=value
        for child in value.values():
            collect(child,bindings)
    elif isinstance(value,list):
        for child in value:
            collect(child,bindings)


def resolve(uri):
    for prefix,base in (('repo://',ROOT),('run://',Path('/mnt/d/PACT_EXPERIMENTS')),
                        ('dep://',Path('/root/pact-deps'))):
        if uri.startswith(prefix):
            return base/uri[len(prefix):]
    return Path(uri)


def main():
    bindings={}
    for row in read(CORE/'canonical_results.json')['records']:
        folder=CORE/'correctness'/row['design']/row['candidate']
        collect(read(folder/'physical_proof.json'),bindings)
    # Measurement manifests and simulation receipts bind the actual libraries,
    # extraction rules and runtime inputs used to produce the frozen metrics.
    for b in list(bindings.values()):
        path=resolve(b['path'])
        if path.name in ('manifest.json','simulation_manifest.json') and path.is_file():
            collect(read(path),bindings)
    rows=[]
    for (uri,expected),b in sorted(bindings.items()):
        path=resolve(uri)
        observed=sha(path) if path.is_file() else None
        rows.append(dict(original_binding=b,resolved_path=str(path),observed_sha256=observed,
            status='PASS' if observed==expected else ('MISSING' if observed is None else 'HASH_MISMATCH')))
    result=dict(schema='pact_v1_external_frozen_manifest_v1',created_utc=now(),
        parent_manifest=binding(OUT/'manifests/pact_v1_frozen_manifest.json'),
        status='PASS' if all(r['status']=='PASS' for r in rows) else 'RETAINED_ARTIFACT_INTEGRITY_FAILURE',
        historical_tool_executions=0,historical_writes=0,files=rows)
    write(OUT/'manifests/pact_v1_frozen_external_manifest.json',result,immutable=True)
    print(result['status'],len(rows),'external bindings',flush=True)
    for row in rows:
        if row['status']!='PASS':
            print(row['status'],row['original_binding']['path'],flush=True)


if __name__=='__main__':
    main()
