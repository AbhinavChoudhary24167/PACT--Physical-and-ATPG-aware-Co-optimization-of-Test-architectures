#!/usr/bin/env python3
"""One-buffer reproducer for preserving distinct input/output port names."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import odb
from openroad import Design, Tech


def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    db = odb.dbDatabase.create()
    odb.read_lef(db, str(args.library / 'Nangate45.lef'))
    chip = odb.dbChip.create(db, next(iter(db.getTechs())))
    block = odb.dbBlock.create(chip, 'input_alias')
    inst = odb.dbInst.create(block, db.findMaster('BUF_X1'), 'buffer')
    for internal, external, direction, pin in (
            ('internal_input', 'external_input', 'INPUT', 'A'),
            ('internal_output', 'external_output', 'OUTPUT', 'Z')):
        net = odb.dbNet.create(block, internal)
        term = odb.dbBTerm.create(net, external)
        term.setIoType(direction)
        inst.findITerm(pin).connect(net)
    source = args.output / 'input.odb'
    odb.write_db(db, str(source))
    tech = Tech()
    tech.readLiberty(str(args.library / 'Nangate45_typ.lib'))
    design = Design(tech)
    design.readDb(str(source))
    verilog = args.output / 'output.v'
    design.evalTclString(f'write_verilog {verilog}')
    text = verilog.read_text()
    aliases = dict(re.findall(r'\bassign\s+(\S+)\s*=\s*(\S+)\s*;', text))
    passed = aliases.get('internal_input') == 'external_input' and aliases.get('external_output') == 'internal_output'
    binary = Path('/proc/self/exe').resolve()
    (args.output / 'proof.json').write_text(json.dumps(dict(status='PASS' if passed else 'MISSING_INPUT_ALIAS',
        aliases=aliases, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        input_ODB_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        output_Verilog_sha256=hashlib.sha256(verilog.read_bytes()).hexdigest(),
        input_direction_correct=aliases.get('internal_input') == 'external_input',
        output_direction_preserved=aliases.get('external_output') == 'internal_output',
        FF_count=0, unrelated_optimizer_required=False), indent=2, sort_keys=True)+'\n')
    print('INPUT_OUTPUT_ALIAS_WITNESS', 'PASS' if passed else 'MISSING_INPUT_ALIAS', flush=True)
    return 0 if passed else 2


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    raise SystemExit(main(parser.parse_args()))
