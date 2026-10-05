#!/usr/bin/env python3
"""Design-name/path adapter to the frozen native reference generators."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import pact_oss_native as native
import pact_oss_generator as generator
import pact_oss_topology_generator as topology


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--namespace',type=Path,required=True)
    p.add_argument('--design',required=True)
    p.add_argument('--method',choices=('B1','B2','B3T'),required=True)
    p.add_argument('--commit',required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--liberty',type=Path,required=True)
    args=p.parse_args()
    # Only lookup paths vary. Commands, topology recovery, native algorithms,
    # source identities, placement and fixed endpoint checks are unchanged.
    native.ROOT=args.namespace
    if args.method=='B1':
        native.run(args.design,args.source,args.output,args.liberty,optimize=False)
    elif args.method=='B2':
        generator.main(args)
    else:
        topology.main(args)


if __name__=='__main__':
    main()
