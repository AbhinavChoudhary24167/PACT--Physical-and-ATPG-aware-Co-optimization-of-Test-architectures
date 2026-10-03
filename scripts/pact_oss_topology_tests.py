#!/usr/bin/env python3
"""Run only the fixed endpoint witness and two adjacent native regressions."""
from pathlib import Path
import shutil

import pact_oss_topology as r
from pact_oss_benchmark import binding, read, write


def main(attempt='native_tests'):
    r.ensure()
    build = read(r.FOLDER / 'build_result.json')
    records = {}
    for name in ('scan_opt_sky130', 'place_sort_sky130', 'one_cell_sky130'):
        raw = r.DATA / attempt / name
        raw.mkdir(parents=True, exist_ok=True)
        args = ['/usr/bin/env', f'OPENROAD_EXE=/build_storage/{r.NAME}/build/bin/openroad',
            'TEST_NAME='+name, 'TEST_EXT=tcl', 'TEST_TYPE=tcl', 'TEST_CHECK_LOG=True',
            'TEST_CHECK_PASSFAIL=False', f'RESULTS_DIR=/scratch/topology_recovery_20261004/{attempt}/{name}',
            '/bin/bash', f'/build_storage/{r.NAME}/source/test/regression_test.sh']
        command = r.container(args)
        index = command.index('--entrypoint')
        command[index:index] = ['--workdir', f'/build_storage/{r.NAME}/source/src/dft/test']
        code = r.run(command, r.FOLDER / attempt, name)
        records[name] = dict(status='PASS' if code == 0 else 'FAIL',
            execution=binding(r.FOLDER / attempt / (name+'.execution.json')),
            outputs={p.name: binding(p) for p in raw.iterdir() if p.is_file()})
        target = r.FOLDER / attempt / name
        target.mkdir(exist_ok=True)
        for p in raw.iterdir():
            if p.is_file():
                shutil.copy2(p, target / p.name)
    write(r.FOLDER / attempt / 'tests.json', dict(status='PASS' if all(t['status']=='PASS' for t in records.values()) else 'FAIL',
        commit=build['commit'], binary_sha256=build['binary_sha256'], tests=records,
        test_registration='Existing scan_opt_sky130 remains registered in both CMake and Bazel',
        broadened_unrelated_testing=False))
    return 0 if all(t['status']=='PASS' for t in records.values()) else 1


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else 'native_tests'))
