"""SPEF reference-only parser; forbidden as an input to load predictors."""
import re
import math


def parse_spef(text):
    unit = re.search(r'\*C_UNIT\s+([\d.eE+-]+)\s+(\w+)', text)
    if unit is None or unit[2].upper() not in ('FF','PF'):
        raise ValueError('Unsupported SPEF C_UNIT')
    scale = float(unit[1]) * (1000 if unit[2].upper() == 'PF' else 1)
    names, nets = {}, {}
    mode, current = None, None
    for line in text.splitlines():
        fields = line.split()
        if not fields: continue
        if fields[0] == '*NAME_MAP': mode='names'; continue
        if fields[0] == '*D_NET':
            name = names.get(fields[1], fields[1])
            if name in nets: raise ValueError('Duplicate SPEF net')
            current = dict(declared_ff=float(fields[2])*scale, ground_ff=0., coupling_ff=0.,
                           resistors=0, capacitors=0)
            nets[name] = current; mode=None; continue
        if fields[0] in ('*CAP','*RES','*CONN','*END'):
            mode=fields[0]; continue
        if mode == 'names' and re.fullmatch(r'\*\d+', fields[0]): names[fields[0]]=fields[1]
        elif mode == '*CAP' and fields[0].isdigit():
            if len(fields) not in (3,4): raise ValueError('Unsupported SPEF capacitor')
            value = float(fields[-1])*scale
            if not math.isfinite(value) or value < 0: raise ValueError('Invalid SPEF cap')
            current['ground_ff' if len(fields)==3 else 'coupling_ff'] += value
            current['capacitors'] += 1
        elif mode == '*RES' and fields[0].isdigit():
            if len(fields) != 4 or not math.isfinite(float(fields[-1])) or float(fields[-1]) < 0:
                raise ValueError('Invalid SPEF resistor')
            current['resistors'] += 1
    if not nets: raise ValueError('Empty SPEF')
    for name, net in nets.items():
        expected = net['ground_ff'] + net['coupling_ff']
        if abs(net['declared_ff']-expected) > max(0.002, expected*2e-4):
            raise ValueError(f'SPEF total mismatch: {name}: {net}')
    return nets
