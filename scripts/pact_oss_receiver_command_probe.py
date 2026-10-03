#!/usr/bin/env python3
"""Probe actual linked PR10666 behavior, retaining the repaired identity."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pact_oss_command_probe import main as probe

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--method',required=True,choices=('B3R',))
    parser.add_argument('--commit',required=True)
    parser.add_argument('--upstream-base',required=True)
    parser.add_argument('--patch-sha256',required=True)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    probe(args)
    proof=json.loads(args.output.read_text())
    proof.update(upstream_base_sha=args.upstream_base,repair_patch_sha256=args.patch_sha256,
        method_display='B3R — PR #10666 + minimal compile repair',
        receiver_probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    args.output.write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
