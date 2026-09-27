"""Independent cycle-level replay. Does not import the remapping implementation."""


def shift(architecture, streams, initial=None):
    names = {c.name for c in architecture.cells}
    state = dict(initial) if initial is not None else dict.fromkeys(names, 'X')
    if set(state) != names or set(state.values()) - set('01X'):
        raise ValueError('Malformed initial replay state')
    cycles = max(len(c.cells) for c in architecture.chains)
    if set(streams) != {c.chain_id for c in architecture.chains}:
        raise ValueError('Replay stream chain mismatch')
    if any(len(s) != cycles or set(s)-set('01X') for s in streams.values()):
        raise ValueError('Replay stream width/symbol mismatch')
    observed = {c.chain_id: '' for c in architecture.chains}
    for t in range(cycles):
        previous = state.copy()
        for chain in architecture.chains:
            observed[chain.chain_id] += previous[chain.cells[-1]]
            for position, ff in enumerate(chain.cells):
                state[ff] = streams[chain.chain_id][t] if position == 0 else previous[chain.cells[position-1]]
    return state, observed


def verify(before, after, original, remapped, source_rows):
    for arch, workload in ((before, original), (after, remapped)):
        if workload['architecture_sha256'] != arch.sha256():
            raise ValueError('Replay topology hash mismatch')
    if not len(original['patterns']) == len(remapped['patterns']) == len(source_rows):
        raise ValueError('Replay pattern count mismatch')
    errors = []
    load_known = response_known = load_x = response_x = 0
    recovered = []
    for old, new, source in zip(original['patterns'], remapped['patterns'], source_rows):
        if old['pattern'] != source['pattern'] or new['pattern'] != source['pattern']:
            raise ValueError('Pattern ordering changed')
        if old['source_fields'] != source['source_fields'] or new['source_fields'] != source['source_fields']:
            raise ValueError('Functional stimulus/response metadata changed')
        states = [shift(a, p['load'])[0] for a, p in ((before, old), (after, new))]
        for ff, expected in source['load_state'].items():
            load_known += expected != 'X'
            load_x += expected == 'X'
            if states[0][ff] != expected or states[1][ff] != expected:
                errors.append(dict(pattern=source['pattern'], stage='load', ff=ff))
        # Functional capture is not synthesized here: use the supplied expected
        # capture state and independently shift it out through the actual chain.
        decoded = []
        for arch, pattern in ((before, old), (after, new)):
            zeros = {c.chain_id: '0' * max(len(k.cells) for k in arch.chains) for c in arch.chains}
            _, samples = shift(arch, zeros, source['response_state'])
            recovered_response = {}
            for chain in arch.chains:
                expected = pattern['unload'][chain.chain_id]
                if len(expected) != len(zeros[chain.chain_id]) or set(expected)-set('01X'):
                    raise ValueError('Malformed unload stream')
                # Track the identity leaving SO each cycle, independently of
                # the remapper's vector-to-position formula.
                occupants = list(chain.cells)
                for cycle in range(len(chain.cells)):
                    ff = occupants.pop()
                    bit = expected[cycle]
                    recovered_response[ff] = bit
                    if samples[chain.chain_id][cycle] != bit:
                        errors.append(dict(pattern=source['pattern'], stage='unload', ff=ff))
                if set(expected[len(chain.cells):]) - {'X'}:
                    raise ValueError('Unload padding must be masked')
            decoded.append(recovered_response)
        for ff, expected in source['response_state'].items():
            response_known += expected != 'X'
            response_x += expected == 'X'
            if decoded[0][ff] != decoded[1][ff] or decoded[1][ff] != expected:
                errors.append(dict(pattern=source['pattern'], stage='response_identity', ff=ff))
        recovered.append(dict(load_state=states[1], response_state=decoded[1]))
    load_fail = any(e['stage'] == 'load' for e in errors)
    unload_fail = any(e['stage'] != 'load' for e in errors)
    return dict(status='FAIL' if errors else 'PASS', patterns_checked=len(source_rows),
                FF_states_checked=load_known+load_x, known_load_bits_checked=load_known,
                known_response_bits_checked=response_known, load_X_bits=load_x,
                response_X_bits=response_x, mismatches=len(errors), errors=errors[:100],
                load_replay='FAIL' if load_fail else 'PASS',
                unload_replay='FAIL' if unload_fail else 'PASS',
                capture_scope='expected PPO state supplied; functional capture not simulated by shift replay',
                X_handling='exact symbolic transport; X response is masked; no fill'), recovered


def write_recovered_fan(path, fan, identity, recovered):
    """FAN input reconstructed from independently replayed serial state/response."""
    lookup = {r['atpg_signal']: r['physical_instance'] for r in identity}
    lines = [' '.join(fan.primary_inputs)+' |', ' '.join(fan.pseudo_primary_inputs)+' |',
             ' '.join(fan.primary_outputs), 'BASIC_SCAN', f'_num_of_pattern_{len(recovered)}']
    for i, (p, recovered_row) in enumerate(zip(fan.patterns, recovered), 1):
        ppi = ''.join(recovered_row['load_state'][lookup[n]] for n in fan.pseudo_primary_inputs)
        ppo = ''.join(recovered_row['response_state'][lookup[n]] for n in fan.pseudo_primary_inputs)
        lines.append(f'_pattern_{i} ' + ' | '.join((p.pi1, p.pi2, ppi, p.scan_in, p.po1, p.po2, ppo)))
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
