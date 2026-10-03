"""Reject unqualified development files and floating revisions in build receipts."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from pact_oss_build_resolution import parse_cache, validate_resolution


PIN = '6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf'


def qualified():
    resolved = dict(SWIG_EXECUTABLE='/isolated/bin/swig', SWIG_DIR='/isolated/share/swig/4.3.0',
                    SWIG_VERSION='4.3.0', TCL_HEADER='/isolated/include/tcl.h',
                    TCL_LIBRARY='/isolated/lib/libtcl8.6.so')
    proof = dict(status='PASS', cmake_resolved=resolved)
    cache = {name: dict(type='FILEPATH', value=value) for name, value in resolved.items()}
    cache['OPENROAD_VERSION'] = dict(type='STRING', value=PIN)
    return cache, proof


def test_cache_preserves_paths_lists_and_embedded_equals(tmp_path):
    path = tmp_path / 'CMakeCache.txt'
    path.write_text('// comment\n# comment\nTCL_HEADER:FILEPATH=/path with spaces/tcl.h\n'
                    'CMAKE_PREFIX_PATH:STRING=/isolated;/usr/local\nVALUE:STRING=a=b\n')
    cache = parse_cache(path)
    assert cache['TCL_HEADER']['value'] == '/path with spaces/tcl.h'
    assert cache['CMAKE_PREFIX_PATH']['value'] == '/isolated;/usr/local'
    assert cache['VALUE']['value'] == 'a=b'


def test_accepts_exact_independently_qualified_resolution():
    cache, proof = qualified()
    validate_resolution(cache, proof, PIN)


@pytest.mark.parametrize('failure', ('swig_path', 'tcl_header_missing', 'tcl_header_notfound',
                                   'tcl_library_mismatch', 'old_swig', 'floating_revision', 'unpassed_probe'))
def test_rejects_unqualified_configuration(failure):
    cache, proof = qualified()
    proof = copy.deepcopy(proof)
    if failure == 'swig_path':
        cache['SWIG_EXECUTABLE']['value'] = '/usr/bin/swig'
    elif failure == 'tcl_header_missing':
        del cache['TCL_HEADER']
        cache['TCL_TCLSH'] = dict(type='FILEPATH', value='/isolated/bin/tclsh')
    elif failure == 'tcl_header_notfound':
        cache['TCL_HEADER']['value'] = 'TCL_HEADER-NOTFOUND'
    elif failure == 'tcl_library_mismatch':
        cache['TCL_LIBRARY']['value'] = '/other/lib/libtcl8.6.so'
    elif failure == 'old_swig':
        cache['SWIG_VERSION']['value'] = proof['cmake_resolved']['SWIG_VERSION'] = '4.2.1'
    elif failure == 'floating_revision':
        cache['OPENROAD_VERSION']['value'] = 'main'
    else:
        proof['status'] = 'FAILED'
    with pytest.raises(ValueError):
        validate_resolution(cache, proof, PIN)
