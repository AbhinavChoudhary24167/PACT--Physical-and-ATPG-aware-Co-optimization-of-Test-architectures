#!/usr/bin/env python3
"""Resolve required external packages without configuring OpenROAD itself."""
import json
import argparse
from pathlib import Path
import subprocess


def main(attempt):
    root = Path('/scratch/recovery_20261003') / ('dependency_probe' + attempt)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.25)
project(PACTDependencyProbe LANGUAGES C CXX)
find_package(Boost 1.87 CONFIG REQUIRED COMPONENTS iostreams serialization thread)
find_package(Eigen3 3.4 CONFIG REQUIRED)
find_package(absl CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(fmt 12.1 CONFIG REQUIRED)
find_package(LEMON NAMES LEMON lemon REQUIRED)
find_package(ortools CONFIG REQUIRED)
find_package(yaml-cpp CONFIG REQUIRED)
find_package(BISON 3.2 REQUIRED)
find_package(FLEX REQUIRED)
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(OpenMP REQUIRED)
find_package(ZLIB REQUIRED)
find_library(CUDD_LIB cudd REQUIRED)
find_path(CUDD_INCLUDE cudd.h REQUIRED)
set(output "")
foreach(name Boost_VERSION Boost_DIR Boost_INCLUDE_DIRS Eigen3_VERSION Eigen3_DIR absl_VERSION absl_DIR
 spdlog_VERSION spdlog_DIR fmt_VERSION fmt_DIR LEMON_INCLUDE_DIRS LEMON_LIBRARY LEMON_LIBRARIES LEMON_DIR
 ortools_VERSION ortools_DIR yaml-cpp_VERSION yaml-cpp_DIR BISON_VERSION BISON_EXECUTABLE FLEX_VERSION FLEX_EXECUTABLE
 Python3_VERSION Python3_EXECUTABLE Python3_INCLUDE_DIRS Python3_LIBRARIES OpenMP_CXX_VERSION ZLIB_VERSION ZLIB_INCLUDE_DIRS ZLIB_LIBRARIES CUDD_LIB CUDD_INCLUDE)
 string(APPEND output "${name}=${${name}}\\n")
endforeach()
file(WRITE "${CMAKE_BINARY_DIR}/resolved.txt" "${output}")
''')
    args = ['cmake', '-S', str(root), '-B', str(root / 'build'),
            '-DCMAKE_C_COMPILER=/usr/bin/gcc', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
            '-DCMAKE_PREFIX_PATH=/build_storage/toolchain;/opt/or-tools;/usr/local',
            '-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0']
    print('COMMAND', json.dumps(args), flush=True)
    subprocess.run(args, check=True)
    result = dict(line.split('=', 1) for line in (root / 'build/resolved.txt').read_text().splitlines())
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    (root / 'qualification.json').write_text(json.dumps(dict(status='PASS', cmake_resolved=result), indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', default='')
    main(parser.parse_args().attempt)
