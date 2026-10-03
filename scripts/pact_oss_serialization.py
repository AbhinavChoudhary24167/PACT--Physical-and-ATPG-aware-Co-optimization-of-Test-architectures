#!/usr/bin/env python3
"""Separate approved OpenSTA serialization repair and combined B3T identity."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import pact_oss_topology as r
from pact_oss_benchmark import binding, read, write

SERIAL = r.CAMPAIGN / 'verilog_input_alias'
ENDPOINT_FOLDER = r.FOLDER
ENDPOINT_REPAIR = r.REPAIR
NAME = 'B3T_openroad_10666_serialization_repaired'
FOLDER = r.CAMPAIGN / 'baselines' / NAME
REPAIR = FOLDER / 'repair'
STA_PARENT = '244797f162b465751912b651d55d9854296aa745'
STA_FILE = 'verilog/VerilogWriter.cc'
BRANCH = 'repair/verilog-input-alias'


def activate():
    r.NAME, r.METHOD, r.FOLDER, r.REPAIR = NAME, 'B3T', FOLDER, REPAIR
    # Storage stays in the owned source/build prefix; immutable commits and
    # executable snapshots preserve the earlier B3S attempt separately.


def prepare():
    r.ensure()
    endpoint = read(ENDPOINT_REPAIR / 'repair_manifest.json')
    parent = endpoint['repair_commit_sha']
    if r.git('rev-parse', 'HEAD').strip() != parent or r.git('diff', '--ignore-submodules', '--name-only').strip():
        raise ValueError('Serializer repair must start from the exact endpoint derivative')
    if read(ENDPOINT_FOLDER / 'native_tests_attempt2/tests.json')['status'] != 'PASS':
        raise ValueError('Finish native endpoint qualification first')
    sta = r.SOURCE / 'src/sta'
    def sta_git(*args):
        return subprocess.check_output(['git','-C',str(sta),*args],text=True)
    if sta_git('rev-parse','HEAD').strip() != STA_PARENT or sta_git('status','--short').strip():
        raise ValueError('Exact unmodified OpenSTA parent required')
    REPAIR.mkdir(parents=True, exist_ok=True)
    saved = r.DATA / 'immutable_binaries' / parent / 'openroad'
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(r.BUILD / 'bin/openroad', saved)
    write(REPAIR / 'parent.json', dict(parent_revision=parent, parent_method='B3S',
        parent_build=binding(ENDPOINT_FOLDER / 'build_result.json'), parent_binary=binding(saved),
        endpoint_repair=binding(ENDPOINT_REPAIR / 'repair_manifest.json'),
        OpenSTA_parent=STA_PARENT, approval='User explicitly approved the separate R1 OpenSTA input-alias repair',
        root_cause=binding(SERIAL / 'ROOT_CAUSE.md'), proposed_patch=binding(SERIAL / 'proposed.patch')))
    r.git('switch','-c',BRANCH,parent)
    sta_git('switch','-c',BRANCH,STA_PARENT)
    for key in ('name','email'):
        sta_git('config','user.'+key,r.git('config','user.'+key).strip())
    path = sta / STA_FILE
    original = path.read_text()
    (REPAIR / 'VerilogWriter.parent.cc').write_text(original)
    text = original.replace('// multiple output ports.', '// a port with a different name.')
    text = text.replace('&& (network_->direction(port)->isAnyOutput()\n',
                        '&& (network_->direction(port)->isAnyOutput()\n              || network_->direction(port)->isInput()\n')
    before = '''        sta::print(stream_, " assign {} = {};\\n",
                   port_vname,
                   net_vname);'''
    after = '''        if (network_->direction(port)->isInput()) {
          sta::print(stream_, " assign {} = {};\\n",
                     net_vname,
                     port_vname);
        }
        else {
          sta::print(stream_, " assign {} = {};\\n",
                     port_vname,
                     net_vname);
        }'''
    if text.count(before) != 1:
        raise ValueError('Unique writer alias defect missing')
    path.write_text(text.replace(before,after))
    sta_git('diff','--check')
    if sta_git('diff','--name-only').strip() != STA_FILE:
        raise ValueError('Serializer patch exceeds approved one-file scope')
    (REPAIR / 'OpenSTA.patch.diff').write_text(sta_git('diff','--binary','--no-ext-diff'))
    sta_git('add',STA_FILE)
    sta_git('commit','-s','-m','verilog: preserve input ports with distinct connected net names')
    sta_commit = sta_git('rev-parse','HEAD').strip()
    r.git('add','src/sta')
    r.git('commit','-s','-m','sta: preserve renamed input port connectivity in generated Verilog')
    commit = r.git('rev-parse','HEAD').strip()
    (REPAIR / 'patch.diff').write_text(r.git('diff',parent,commit,'--binary','--no-ext-diff'))
    write(REPAIR / 'repair_manifest.json',dict(method='B3T',repair_class='R1',repair_commit_sha=commit,
        parent_revision=parent,upstream_base_sha=r.BASE,changed_files=['src/sta'],
        OpenSTA_parent=STA_PARENT,OpenSTA_repair_commit=sta_commit,
        OpenSTA_changed_files=[STA_FILE],OpenSTA_patch=binding(REPAIR / 'OpenSTA.patch.diff'),
        OpenSTA_patch_sha256=binding(REPAIR / 'OpenSTA.patch.diff')['sha256'],
        patch=binding(REPAIR / 'patch.diff'),patch_sha256=binding(REPAIR / 'patch.diff')['sha256'],
        endpoint_repair=binding(ENDPOINT_REPAIR / 'repair_manifest.json'),
        changed_source_sha256={'src/sta/'+STA_FILE:binding(path)['sha256']},
        algorithm_changed=False,objective_changed=False,search_space_changed=False,parameters_changed=False,
        endpoint_semantics_changed=False,ODB_connectivity_changed=False,
        behavior='Emit equivalent Verilog input alias when port and net names differ',
        signed_commit=r.git('log','-1','--format=full'),OpenSTA_signed_commit=sta_git('log','-1','--format=full')))
    activate()
    print('BENCHMARK_BLOCKER_VERILOG_INPUT_ALIAS_REPAIRED',commit,sta_commit,flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','build','qualify','tests'))
    parser.add_argument('--design',choices=r.DESIGNS)
    args=parser.parse_args()
    if args.action=='prepare':
        prepare()
    else:
        activate()
        if args.action=='build':
            raise SystemExit(r.build())
        elif args.action=='qualify':
            raise SystemExit(r.qualify(args.design))
        else:
            import pact_oss_topology_tests
            raise SystemExit(pact_oss_topology_tests.main('B3T_native_tests'))
