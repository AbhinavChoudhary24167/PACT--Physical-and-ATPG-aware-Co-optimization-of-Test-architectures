"""Exercise the exact nested traversal before and after its guard repair."""
import ast
import inspect
from types import SimpleNamespace
import pytest
from pact.physical.phase0d_routed import verify_routed
from pact_generalization_routed import OLD,NEW,repaired_source


def path_function(graph,repaired):
    source=inspect.getsource(verify_routed)
    tree=ast.parse(repaired_source(source) if repaired else source)
    nested=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='path')
    namespace={'buffers':graph}
    exec(compile(ast.Module(body=[nested],type_ignores=[]),'frozen_path','exec'),namespace)
    return lambda a,b:namespace['path'](SimpleNamespace(getName=lambda:a),SimpleNamespace(getName=lambda:b))


def line(n):
    return {str(i):[(str(i+1),'b'+str(i))] for i in range(n)}


def test_source_change_is_only_the_guard():
    original=inspect.getsource(verify_routed)
    assert repaired_source(original).replace(NEW,OLD)==original


def test_existing_short_paths_identical():
    for n in (0,1,8):
        graph=line(n)
        assert path_function(graph,False)('0',str(n))==path_function(graph,True)('0',str(n))


def test_ten_buffer_path_previously_false_rejected():
    graph=line(10)
    with pytest.raises(ValueError,match='found 0'):
        path_function(graph,False)('0','10')
    assert path_function(graph,True)('0','10')==['b'+str(i) for i in range(10)]


def test_cycle_and_missing_target_still_rejected():
    graph={'a':[('b','b0')],'b':[('a','b1')]}
    with pytest.raises(ValueError,match='found 0'):
        path_function(graph,True)('a','missing')


def test_unrelated_branch_preserves_original_criterion():
    graph={'a':[('dead','d'),('target','b')]}
    assert path_function(graph,False)('a','target')==path_function(graph,True)('a','target')==['b']
