"""Strict FAN BASIC_SCAN adapter and identity-based serial remapper."""
from dataclasses import asdict
from pact.scan.validate import validate_ff_identity_map
from pact.test.pattern_parser import parse_fan_pat


def fan_workload(path, identity, architecture):
    fan = parse_fan_pat(path)
    validate_ff_identity_map(identity, [c.name for c in architecture.cells])
    lookup = {r['atpg_signal']: r['physical_instance'] for r in identity}
    if set(lookup) != set(fan.pseudo_primary_inputs):
        raise ValueError('FAN header and canonical FF identity map differ')
    clocks = {c.name: c.clock_domain for c in architecture.cells}
    if any(clocks[r['physical_instance']] != r['clock_domain'] for r in identity):
        raise ValueError('Identity-map clock domain differs')
    rows = []
    for i, p in enumerate(fan.patterns):
        if p.pi2 or p.po2 or p.scan_in:
            raise ValueError(f'Pattern {i+1}: nonempty PI2/PO2/SI requires unsupported sequential timing')
        rows.append(dict(pattern=i+1, source_fields=asdict(p),
                         load_state={lookup[n]: b for n, b in zip(fan.pseudo_primary_inputs, p.ppi)},
                         response_state={lookup[n]: b for n, b in zip(fan.pseudo_primary_inputs, p.ppo)}))
    if not rows:
        raise ValueError('Empty ATPG workload')
    return fan, rows


def serialize(architecture, state, *, response=False):
    names = {c.name for c in architecture.cells}
    if set(state) != names or any(v not in ('0', '1', 'X') for v in state.values()):
        raise ValueError('Expected complete FF state with 0/1/X; partial maps are unsupported')
    cycles = max(len(c.cells) for c in architecture.chains)
    result = {}
    for c in architecture.chains:
        bits = ''.join(state[n] for n in reversed(c.cells))
        result[c.chain_id] = bits + 'X' * (cycles-len(bits)) if response else '0' * (cycles-len(bits)) + bits
    return result


def remap_serial(before, after, vectors, *, response=False):
    """Decode using old chain orientation, then serialize via canonical identity."""
    if set(vectors) != {c.chain_id for c in before.chains}:
        raise ValueError('Serial chain set differs')
    cycles = max(len(c.cells) for c in before.chains)
    state = {}
    for c in before.chains:
        bits = vectors[c.chain_id]
        if len(bits) != cycles or set(bits) - set('01X'):
            raise ValueError('Malformed serial vector')
        useful = bits[:len(c.cells)] if response else bits[-len(c.cells):]
        for n, bit in zip(reversed(c.cells), useful):
            state[n] = bit
    return serialize(after, state, response=response)


def export_workload(permutation, rows):
    before, after = permutation.before, permutation.after
    original, remapped = [], []
    for row in rows:
        load = serialize(before, row['load_state'])
        response = serialize(before, row['response_state'], response=True)
        common = dict(pattern=row['pattern'], source_fields=row['source_fields'])
        original.append(dict(common, load=load, unload=response))
        remapped.append(dict(common, load=remap_serial(before, after, load),
                             unload=remap_serial(before, after, response, response=True)))
    def package(arch, patterns):
        return dict(schema='pact_serial_basic_scan_v1', architecture_sha256=arch.sha256(),
                    cycles=max(len(c.cells) for c in arch.chains),
                    protocol='load with SE=1; apply PI1 and one functional capture with SE=0; unload with SE=1',
                    unload_sampling='SO before shift edge; valid first chain_length cycles',
                    shorter_chain_load='leading zero padding; common clock for every chain',
                    X_policy='symbolic load unknown; masked expected response; never filled',
                    patterns=patterns)
    return package(before, original), package(after, remapped)
