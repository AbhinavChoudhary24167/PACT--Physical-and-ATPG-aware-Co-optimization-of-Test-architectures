"""Timers around the frozen exact analysis; numerical operations stay intact.

The VCD tokenizer and transition counter are one streaming routine. The nested
flush routine is timed separately, so parsing time excludes transition-window
accounting. VVP's VCD emission is integrated with simulation and is reported as
such by the launcher; no isolated emission time is invented.
"""
import ast
import copy
from contextlib import contextmanager
import functools
import hashlib
import time
from pathlib import Path
try:
    import resource
except ImportError:  # Windows can run focused semantics tests; WSL measures RSS.
    resource = None

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / 'src/pact/physical_effect.py'


class AnalysisTimers:
    def __init__(self):
        self.stages = {}
        self.progress_path = None
        self.active = []

    def checkpoint(self):
        if self.progress_path is not None:
            import json
            self.progress_path.write_text(json.dumps(dict(active_stages=self.active, completed=self.receipt()),
                indent=2, sort_keys=True) + '\n')

    @contextmanager
    def span(self, name):
        begin = time.perf_counter()
        before_cpu = time.process_time()
        self.active.append(name)
        self.checkpoint()
        try:
            yield
        finally:
            record = self.stages.setdefault(name, dict(wall_seconds=0., cpu_seconds=0., calls=0))
            record['wall_seconds'] += time.perf_counter() - begin
            record['cpu_seconds'] += time.process_time() - before_cpu
            record['calls'] += 1
            record['process_peak_RSS_KiB'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
            self.active.remove(name)
            self.checkpoint()

    def flush_decorator(self, function):
        # Avoid getrusage per VCD timestamp: the inclusive parser span records
        # CPU/RSS, and these two clock reads separate flush wall time exactly.
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            began = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                record = self.stages.setdefault('transition_extraction', dict(wall_seconds=0., calls=0))
                record['wall_seconds'] += time.perf_counter() - began
                record['calls'] += 1
        return wrapped

    def receipt(self):
        result = dict(self.stages)
        parent = result.get('vcd_parse_and_transition', {})
        child = result.get('transition_extraction', {})
        if 'wall_seconds' in parent and 'wall_seconds' in child:
            result['vcd_parse'] = dict(wall_seconds=max(0., parent['wall_seconds'] - child['wall_seconds']),
                includes='streaming text IO, header/event parsing, allocations and timestamp dispatch',
                cpu_seconds=None, peak_RSS_KiB=None,
                resource_attribution='CPU/RSS shared with vcd_parse_and_transition; do not sum inclusive and exclusive spans')
        return result


def _span(name, body):
    expression = ast.parse(name, mode='eval').body if isinstance(name, str) and name.startswith('f\'') else ast.Constant(name)
    return ast.fix_missing_locations(ast.With(items=[ast.withitem(context_expr=ast.Call(func=ast.Name(id='__measurement_span', ctx=ast.Load()),
        args=[expression], keywords=[]))], body=body))


def instrumented_namespace(timers):
    """Load hash-checked frozen functions with only timer statements added."""
    import json
    frozen_manifest = json.loads((ROOT / 'results/pact_generalization_20261004/manifests/pact_v1_frozen_manifest.json').read_text())
    expected = next(b['sha256'] for b in frozen_manifest['files'] if b['path'] == 'repo://src/pact/physical_effect.py')
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest() != expected:
        raise ValueError('Frozen physical-effect implementation changed')
    tree = ast.parse(FROZEN.read_text())
    original_operations = ast.dump(tree, include_attributes=False)
    parser = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'vcd_transitions')
    flush = next(n for n in parser.body if isinstance(n, ast.FunctionDef) and n.name == 'flush')
    flush.decorator_list.append(ast.Name(id='__measurement_flush', ctx=ast.Load()))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'analyze')
    body = function.body
    def index(fragment):
        matches = [i for i, node in enumerate(body) if fragment in ast.unparse(node).splitlines()[0]]
        if len(matches) != 1:
            raise ValueError('Frozen instrumentation anchor ambiguous: ' + fragment)
        return matches[0]
    # Group from the end so earlier list positions remain valid. No original
    # statements are deleted, replaced, reordered or arithmetically changed.
    first = index('metrics =')
    scope_loop = next(n for n in body[first:] if isinstance(n, ast.For) and ast.unparse(n.target) == 'scope')
    resolution_loop = next(n for n in scope_loop.body if isinstance(n, ast.For) and ast.unparse(n.target) == 'resolution')
    resolution_loop.body = [_span("f'H{resolution}_computation_{scope}'", resolution_loop.body)]
    rindex = scope_loop.body.index(resolution_loop)
    scope_loop.body[:rindex] = [_span("f'E_computation_{scope}'", scope_loop.body[:rindex])]
    caps_start = index('caps = []')
    caps_stop = index('metrics =')
    body[caps_start:caps_stop] = [_span('capacitance_attribution', body[caps_start:caps_stop])]
    spef_i = index('spef = parse_spef')
    body[spef_i:spef_i+1] = [_span('spef_parse', body[spef_i:spef_i+1])]
    ff_start = index('qcols =')
    ff_stop = spef_i
    body[ff_start:ff_stop] = [_span('ff_transition_crosscheck', body[ff_start:ff_stop])]
    counts_i = index('counts, vcd = vcd_transitions')
    body[counts_i:counts_i+1] = [_span('vcd_parse_and_transition', body[counts_i:counts_i+1])]
    class RemoveOnlyTimers(ast.NodeTransformer):
        def visit_With(self, node):
            node = self.generic_visit(node)
            if len(node.items) == 1 and isinstance(node.items[0].context_expr, ast.Call):
                call = node.items[0].context_expr
                if isinstance(call.func, ast.Name) and call.func.id == '__measurement_span':
                    return node.body
            return node

        def visit_FunctionDef(self, node):
            node = self.generic_visit(node)
            node.decorator_list = [n for n in node.decorator_list if not (isinstance(n, ast.Name) and n.id == '__measurement_flush')]
            return node
    if ast.dump(RemoveOnlyTimers().visit(copy.deepcopy(tree)), include_attributes=False) != original_operations:
        raise AssertionError('Instrumentation changed an original executable operation')
    namespace = dict(__measurement_span=timers.span, __measurement_flush=timers.flush_decorator,
        __name__='pact_cold_start_frozen_instrumented_analysis', __file__=str(FROZEN))
    exec(compile(ast.fix_missing_locations(tree), str(FROZEN), 'exec'), namespace)
    return namespace


def analyze_instrumented(folder):
    timers = AnalysisTimers()
    timers.progress_path = Path(folder) / 'analysis_live.json'
    namespace = instrumented_namespace(timers)
    with timers.span('analysis_total'):
        namespace['analyze'](folder)
    return dict(stages=timers.receipt(), frozen_source_sha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
        instrumentation='AST timer context/decorator insertion only; all original numeric/parser operations retained in original order',
        scientific_method_change=False)
