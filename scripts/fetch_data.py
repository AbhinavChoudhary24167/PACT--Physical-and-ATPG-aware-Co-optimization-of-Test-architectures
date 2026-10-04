#!/usr/bin/env python3
"""Fetch recorded dependency revisions; never replace an existing checkout."""
import argparse
from pathlib import Path
import subprocess

PINS = {
    'OpenROAD-flow-scripts': ('https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git',
                            '5e8b1450d19263f797a27c4f371b9dd19f32a3aa'),
    'FAN_ATPG': ('https://github.com/NTU-LaDS-II/FAN_ATPG.git',
                 '26b2b36c0e9db11a4b6d9e759df6e44357121f39'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('external'))
    args = parser.parse_args()
    for name, (url, commit) in PINS.items():
        target = args.output / name
        if target.exists():
            actual = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != commit:
                raise ValueError(f'{target} has a different revision; choose a new destination')
            print(name, 'existing pinned checkout', commit)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--no-checkout', url, str(target)], check=True)
        subprocess.run(['git', '-C', str(target), 'checkout', '--detach', commit], check=True)
        subprocess.run(['git', '-C', str(target), 'submodule', 'update', '--init', '--recursive'], check=True)
        print(name, commit)


if __name__ == '__main__':
    main()
