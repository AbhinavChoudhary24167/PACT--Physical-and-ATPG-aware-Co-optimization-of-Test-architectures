When an input port and its connected internal net have different names, `VerilogWriter::writeAssigns` emits no input alias. The written Verilog declares the input and an undriven internal wire, so a connected ODB/network graph becomes disconnected in the exported circuit. Output aliases already work.

Include input ports in the existing alias condition and emit `assign internal_net = input_port` for those ports. Output, inout and power/ground handling retain their existing direction and conditions. This changes serialization only; no network connections or timing/optimization behavior change.

Minimal reproducer through OpenROAD's dbNetwork adapter: create one `BUF_X1`, connect its `A` pin to net `internal_input`, attach input BTerm `external_input` to that same net, and similarly connect `Z` to `internal_output` with output BTerm `external_output`. Load the database and call `write_verilog`. Before: only `assign external_output = internal_output` is emitted. After: `assign internal_input = external_input` is also emitted. The existing output alias remains correct. The standalone reproducer source is included below; use the standard Nangate45 test library directory and run it with OpenROAD's embedded Python.

Local before/after validation used OpenSTA `244797f162b465751912b651d55d9854296aa745` and repair `d21c1ae6f97cc2f28d7f2ba5892c24293b8d2259`, linked into an immutable full OpenROAD build. The one-buffer witness reproduces the missing input alias before and passes after. Three scan designs with 179/211/534 FFs independently agree in metadata, saved ODB and generated Verilog after this fix, with no ODB functional connection or placement changes. Three adjacent native DFT golden regressions also pass. This contribution cherry-picks the same one-file repair onto current upstream `d1e43c6f9f4e66cb59c3d7958a4aa7d1626b4614` as `0b73f5daa403a7ae2dc92587b260506f705f426d`; that upstream checkout has not been separately rebuilt locally, and CI is not claimed passing.

```python
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

```
