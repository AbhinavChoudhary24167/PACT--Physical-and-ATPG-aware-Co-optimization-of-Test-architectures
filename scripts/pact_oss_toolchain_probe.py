#!/usr/bin/env python3
"""Independently qualify SWIG/Tcl in the immutable build image before OpenROAD.

Run inside the pinned Docker image, with /scratch and /workspace mounted.
No OpenROAD configuration is performed by this probe.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def sha(path):
    path = Path(path)
    return dict(path=str(path), resolved_path=str(path.resolve()),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def command(args, cwd=None, input=None):
    result = subprocess.run(args, cwd=cwd, input=input, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print('COMMAND', json.dumps(args), '\n' + result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError(f'Prerequisite probe failed ({result.returncode}): {args}')
    return result.stdout.strip()


def main():
    root = Path('/scratch/recovery_20261003/toolchain_probe')
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'qualification.json').exists():
        raise ValueError('Immutable toolchain qualification already exists')
    swig = shutil.which('swig')
    version = command([swig, '-version'])
    match = re.search(r'SWIG Version (\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (4, 3, 0):
        raise RuntimeError('SWIG >=4.3 is mandatory before B2 configuration')
    (root / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.25)
project(PACTPrerequisiteProbe LANGUAGES C CXX)
list(PREPEND CMAKE_MODULE_PATH "/scratch/B2_openroad_10176/build_source/cmake")
find_package(SWIG 4.3 REQUIRED)
find_package(TCL)
if(NOT EXISTS "${TCL_HEADER}" OR NOT EXISTS "${TCL_LIBRARY}")
  message(FATAL_ERROR "Real Tcl development header and library are mandatory")
endif()
file(WRITE "${CMAKE_BINARY_DIR}/resolved.txt"
 "SWIG_EXECUTABLE=${SWIG_EXECUTABLE}\nSWIG_VERSION=${SWIG_VERSION}\nSWIG_DIR=${SWIG_DIR}\nTCL_HEADER=${TCL_HEADER}\nTCL_INCLUDE_PATH=${TCL_INCLUDE_PATH}\nTCL_LIBRARY=${TCL_LIBRARY}\n")
add_executable(tcl_probe tcl_probe.c)
target_include_directories(tcl_probe PRIVATE ${TCL_INCLUDE_PATH})
target_link_libraries(tcl_probe PRIVATE ${TCL_LIBRARY})
''')
    (root / 'tcl_probe.c').write_text('''#include <stdio.h>
#include <string.h>
#include <tcl.h>
int main(int argc, char **argv) {
  Tcl_FindExecutable(argv[0]);
  Tcl_Interp *interp = Tcl_CreateInterp();
  if (Tcl_Init(interp) != TCL_OK) { puts(Tcl_GetStringResult(interp)); return 1; }
  int major, minor, patch, type;
  Tcl_GetVersion(&major, &minor, &patch, &type);
  printf("header=%s\\nruntime=%d.%d.%d\\n", TCL_PATCH_LEVEL, major, minor, patch);
  if (major != TCL_MAJOR_VERSION || minor != TCL_MINOR_VERSION || patch != TCL_RELEASE_SERIAL) return 2;
  if (Tcl_Eval(interp, "expr {6 * 7}") != TCL_OK || strcmp(Tcl_GetStringResult(interp), "42")) return 3;
  Tcl_DeleteInterp(interp); Tcl_Finalize(); return 0;
}
''')
    command(['cmake', '-S', str(root), '-B', str(root / 'build'),
             '-DCMAKE_C_COMPILER=/usr/bin/gcc', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
             '-DSWIG_EXECUTABLE=' + swig,
             '-DTCL_HEADER=/usr/include/tcl8.6/tcl.h',
             '-DTCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libtcl8.6.so'])
    command(['cmake', '--build', str(root / 'build'), '--parallel', '1'])
    tcl_probe = command([str(root / 'build/tcl_probe')])
    resolved = dict(line.split('=', 1) for line in (root / 'build/resolved.txt').read_text().splitlines())
    if resolved['SWIG_EXECUTABLE'] != swig:
        raise RuntimeError('CMake selected a different SWIG')
    (root / 'pactprobe.i').write_text('%module pactprobe\n%inline %{ int probe_answer(void) { return 42; } %}\n')
    command([swig, '-tcl', '-o', str(root / 'pactprobe_wrap.c'), str(root / 'pactprobe.i')])
    command(['/usr/bin/gcc', '-shared', '-fPIC', '-I' + resolved['TCL_INCLUDE_PATH'],
             str(root / 'pactprobe_wrap.c'), resolved['TCL_LIBRARY'], '-o', str(root / 'pactprobe.so')])
    tclsh = shutil.which('tclsh')
    tcl_result = command([tclsh], input=f'load {root}/pactprobe.so\nputs [probe_answer]\nputs [info patchlevel]\n')
    if tcl_result.splitlines() != ['42', '8.6.12']:
        raise RuntimeError('SWIG-generated Tcl module did not execute correctly')
    result = dict(status='PASS', B2_configuration_retry_authorized_by_prerequisites=True,
                  swig_version=match[0], swig_version_output=version, tcl_probe_output=tcl_probe,
                  swig_tcl_module_output=tcl_result, cmake_resolved=resolved,
                  executables={name: sha(shutil.which(name)) for name in ('swig', 'cmake', 'tclsh', 'gcc', 'g++', 'bison', 'flex', 'python3')},
                  tcl_header=sha(resolved['TCL_HEADER']), tcl_library=sha(resolved['TCL_LIBRARY']),
                  os_release=Path('/etc/os-release').read_text(),
                  compiler_output=command(['/usr/bin/g++', '--version']),
                  cmake_output=command(['cmake', '--version']),
                  packages=command(['dpkg-query', '-W', 'tcl8.6-dev', 'python3-dev', 'bison', 'flex', 'zlib1g-dev', 'libyaml-cpp-dev']),
                  source_requirement='B2 src/CMakeLists.txt:124; cmake/FindTCL.cmake',
                  probe_source=sha(__file__))
    (root / 'qualification.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('INDEPENDENT_SWIG_TCL_QUALIFICATION_PASS', flush=True)


if __name__ == '__main__':
    main()
