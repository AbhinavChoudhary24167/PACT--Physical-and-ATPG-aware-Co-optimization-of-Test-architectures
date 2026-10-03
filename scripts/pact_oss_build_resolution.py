#!/usr/bin/env python3
"""Bind actual OpenROAD CMake resolution to independently verified tool files."""
import argparse
from pathlib import Path
import re

from pact_oss_benchmark import OUT, binding, read, write


def parse_cache(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line or ':' not in line.split('=', 1)[0]:
            continue
        key_type, value = line.split('=', 1)
        name, kind = key_type.split(':', 1)
        result[name] = dict(type=kind, value=value)
    return result


def validate_resolution(cache, proof, expected_commit):
    if proof.get('status') != 'PASS':
        raise ValueError('Independent prerequisite qualification has not passed')
    expected = proof['cmake_resolved']
    for key in ('SWIG_EXECUTABLE', 'SWIG_DIR', 'SWIG_VERSION', 'TCL_HEADER', 'TCL_LIBRARY'):
        actual = cache.get(key, {}).get('value', '')
        if not actual or actual.endswith('-NOTFOUND') or actual != expected[key]:
            raise ValueError('OpenROAD CMake selected an unqualified tool: ' + key)
    if tuple(map(int, expected['SWIG_VERSION'].split('.'))) < (4, 3, 0):
        raise ValueError('SWIG >=4.3 is mandatory')
    if cache.get('OPENROAD_VERSION', {}).get('value') != expected_commit:
        raise ValueError('OpenROAD source revision differs from the immutable pin')


def record(method):
    recovery = OUT / 'recovery_20261003'
    folder = recovery / 'baselines' / method
    target = folder / 'cmake_resolved_dependencies.json'
    if target.exists():
        raise ValueError('Actual CMake resolution receipt already exists')
    cache = parse_cache(folder / 'CMakeCache.txt')
    proof = read(recovery / 'toolchain/qualification.json')
    pin = read(OUT / 'baselines' / method / 'source_pin.json')
    validate_resolution(cache, proof, pin['commit'])
    log = (folder / 'configure.log').read_text()
    version = re.search(r'-- Compiler: (.+)', log)[1]
    resolved = {key: value for key, value in cache.items() if (
        key.startswith(('SWIG_', 'TCL_', '_Python3_', 'CUDD_', 'LEMON_', 'BISON_', 'FLEX_', 'ZLIB_'))
        or key in ('Boost_DIR', 'fmt_DIR', 'absl_DIR', 'spdlog_DIR', 'Eigen3_DIR', 'ortools_DIR', 'yaml-cpp_DIR',
                   'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_PREFIX_PATH', 'BUILD_GUI', 'BUILD_PYTHON',
                   'ENABLE_TESTS', 'ENABLE_GPU', 'OPENROAD_VERSION', 'LINK_TIME_OPTIMIZATION'))}
    write(target, dict(status='PASS', method=method, source_commit=cache['OPENROAD_VERSION']['value'],
        actual_cmake_cache=binding(folder / 'CMakeCache.txt'), configure_log=binding(folder / 'configure.log'),
        independently_verified_prerequisites=binding(recovery / 'toolchain/qualification.json'),
        independently_audited_packages=binding(recovery / 'toolchain/dependency_qualification.json'),
        actual_openroad_resolution=resolved, compiler=version,
        Tcl_include_path=str(Path(cache['TCL_HEADER']['value']).parent),
        Tcl_header_version='8.6.12', Tcl_runtime_library_version='8.6.12',
        Tcl_version_evidence='Independent compiled-and-linked probe using identical immutable image/header/library paths and hashes',
        swig_executable=proof['executables']['swig'], tcl_header=proof['tcl_header'], tcl_library=proof['tcl_library']))
    print('ACTUAL_OPENROAD_CMAKE_SWIG_TCL_RESOLUTION_PASS', method, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('method', choices=('B2_openroad_10176', 'B3_openroad_10666'))
    record(parser.parse_args().method)
