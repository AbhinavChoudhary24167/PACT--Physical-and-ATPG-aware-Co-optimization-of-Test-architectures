#!/usr/bin/env python3
"""Invoke the existing compiled command probe with the distinct B3T identity."""
import argparse
from pathlib import Path
from pact_oss_command_probe import main

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.method = 'B3T'
    main(args)
