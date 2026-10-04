#!/usr/bin/env python3
"""Reporter regression: full universe, selected state and weighted statistics.

Usage: python3 tests/report_fault_scan.py FAN LIB NETLIST PATTERNS
Uses existing patterns and single-frame stuck-at simulation, never run_atpg.
"""
import collections
from pathlib import Path
import re
import subprocess
import sys
import tempfile

fan,lib,netlist,patterns=map(lambda p:Path(p).resolve(),sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='fan-report-regression-') as temporary:
    outputs=[]
    for command in ('report_fault','report_fault -s DT'):
        script=Path(temporary)/'replay.script'
        script.write_text('\n'.join((f'read_lib {lib}',f'read_netlist {netlist}',
            'build_circuit --frame 1',f'read_pattern {patterns}',
            'set_fault_type saf','add_fault -a','run_fault_sim','report_statistics',command,'exit'))+'\n')
        run=subprocess.run([str(fan),'-f',str(script)],capture_output=True,text=True,check=True)
        assert '**ERROR' not in run.stdout+run.stderr
        records=re.findall(r'^#\s+(SA[01])\s+(UD|DT|PT|AU|TI|RE|AB)\s+(.+?)\s+\[equivalent=(\d+)\]\s*$',run.stdout,re.M)
        identities=[(kind,site) for kind,_,site,_ in records]
        assert len(set(identities))==len(identities), 'duplicate identity'
        assert all(not site.startswith('(') for _,site in identities), 'unresolved scan site'
        sums=collections.Counter()
        for _,state,_,weight in records:
            assert int(weight)>0
            sums[state]+=int(weight)
        dt=int(re.search(r'DT \(detected\)\s+(\d+)',run.stdout)[1])
        assert sums['DT']==dt
        if command=='report_fault':
            assert len(records)==int(re.search(r'FU \(collapsed\)\s+(\d+)',run.stdout)[1])
            assert sum(sums.values())==int(re.search(r'FU \(full\)\s+(\d+)',run.stdout)[1])
        else:
            assert set(sums)=={'DT'}
        outputs.append({(kind,site,int(weight)) for kind,state,site,weight in records if state=='DT'})
    assert outputs[0]==outputs[1], 'state-filtered detected identities differ'
print('PASS complete and filtered fault identities with unchanged weighted counts')
