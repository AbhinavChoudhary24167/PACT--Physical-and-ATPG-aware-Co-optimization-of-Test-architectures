#!/usr/bin/env python3
"""Run the frozen real-generator adapter, explicitly identifying B3R."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pact_oss_generator import main as generate

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--method', required=True, choices=('B3R',))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--upstream-base', required=True)
    parser.add_argument('--patch-sha256', required=True)
    parser.add_argument('--design', required=True, choices=('s5378','s9234','s15850'))
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--liberty', required=True, type=Path)
    args=parser.parse_args()
    generate(args)
    path=args.output/'qualification.json'
    proof=json.loads(path.read_text())
    proof.update(upstream_base_sha=args.upstream_base, repair_patch_sha256=args.patch_sha256,
        method_display='B3R — PR #10666 + minimal compile repair',
        receiver_wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path.write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
