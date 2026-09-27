"""pact-integrate: frozen solver recommendation to implementation and test replay."""
import argparse
import json
from pathlib import Path
from .flow import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    for name in ('placement', 'scan-topology', 'patterns', 'identity-map', 'optimizer-run',
                 'solver-input', 'liberty', 'source-odb', 'fan-root'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--time-limit', '--time-budget', type=float, default=60)
    parser.add_argument('--wire-allowance', type=float, default=.10)
    parser.add_argument('--adapter', choices=('qualified', 'direct'), default='qualified')
    parser.add_argument('--openroad', default='openroad')
    parser.add_argument('--tool-timeout', type=float, default=180)
    args = parser.parse_args()
    if args.time_limit <= 0 or args.tool_timeout <= 0:
        parser.error('Time limits must be positive')
    print(json.dumps(run(args, Path(__file__).resolve().parents[3]), indent=2))


if __name__ == '__main__':
    main()
