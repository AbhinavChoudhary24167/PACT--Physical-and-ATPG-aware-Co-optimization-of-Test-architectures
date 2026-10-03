#!/usr/bin/env python3
"""Additive B3S endpoint-correctness recovery; frozen methods stay untouched."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, write
from pact_oss_recovery import TEMP, MOUNT, IMAGE, docker, execute
from pact_oss_storage import ensure

PARENT = '0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8'
BASE = '746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656'
OLD = 'B3_openroad_10666'
RECEIVER = 'B3R_openroad_10666_repaired'
NAME = 'B3S_openroad_10666_endpoint_repaired'
CAMPAIGN = OUT / 'topology_recovery_20261004'
FOLDER = CAMPAIGN / 'baselines' / NAME
REPAIR = FOLDER / 'repair'
PREFIX = MOUNT / NAME
SOURCE = PREFIX / 'source'
BUILD = PREFIX / 'build'
DATA = TEMP / 'topology_recovery_20261004'
BRANCH = 'repair/B3-scan-output-topology'
FILE = 'src/dft/src/Dft.cpp'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True)


def container(args, repaired=True, flow=False):
    command = docker(args)
    extra = []
    if repaired:
        for name in (OLD, RECEIVER):
            extra += ['--mount', f'type=bind,source={SOURCE},target=/build_storage/{name}/source',
                      '--mount', f'type=bind,source={BUILD},target=/build_storage/{name}/build']
        extra += ['--env', f'TMPDIR=/build_storage/{NAME}/compiler_tmp']
    if flow:
        extra += ['--mount', 'type=bind,source=/root/pact-deps/OpenROAD-flow-scripts/flow/results,target=/root/pact-deps/OpenROAD-flow-scripts/flow/results,readonly']
    command[command.index('--entrypoint'):command.index('--entrypoint')] = extra
    return command


def run(args, folder, label):
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, folder / (label + '.pact_oss_topology.py'))
    return execute(args, folder, label)


def reproduce():
    ensure()
    folder = CAMPAIGN / 'B3R_witness'
    old = OUT / 'receiver_recovery_20261003/baselines' / RECEIVER
    build = read(old / 'build_result.json')
    if build['commit'] != PARENT or binding(build['binary']['path'])['sha256'] != build['binary_sha256']:
        raise ValueError('Immutable B3R identity changed')
    if subprocess.check_output(['git', '-C', str(MOUNT / RECEIVER / 'source'), 'rev-parse', 'HEAD'], text=True).strip() != PARENT:
        raise ValueError('B3R source parent changed')
    scratch = DATA / 'B3R_witness/s5378'
    scratch.mkdir(parents=True, exist_ok=True)
    args = [f'/build_storage/{RECEIVER}/build/bin/openroad', '-python', '-no_init', '-exit',
            '/workspace/scripts/pact_oss_receiver_generator.py', '--method', 'B3R', '--commit', PARENT,
            '--upstream-base', BASE, '--patch-sha256', read(old / 'repair/repair_manifest.json')['patch_sha256'],
            '--design', 's5378', '--source', '/scratch/placed_common/s5378/3_place.odb',
            '--output', '/scratch/topology_recovery_20261004/B3R_witness/s5378',
            '--liberty', '/scratch/NangateOpenCellLibrary_typical_dft.lib']
    rc = run(container(args, repaired=False, flow=True), folder, 'reproduce')
    if rc == 0 or 'Cannot faithfully trace native SI/SO connectivity' not in (folder / 'reproduce.log').read_text():
        raise ValueError('Expected immutable topology failure was not reproduced')
    shutil.copy2(scratch / 'generated.v', folder / 'generated.v')
    write(folder / 'witness.json', dict(status='BENCHMARK_BLOCKER_SCAN_OUTPUT_TOPOLOGY_REPRODUCED',
        parent=PARENT, binary=build['binary'], original_build=binding(old / 'build_result.json'),
        execution=binding(folder / 'reproduce.execution.json'),
        ODB=binding(scratch / 'generated.odb'), Verilog=binding(folder / 'generated.v'),
        input=binding(scratch / 'generator_input.odb')))
    observe = [f'/build_storage/{RECEIVER}/build/bin/openroad', '-python', '-no_init', '-exit',
        '/workspace/scripts/pact_oss_receiver_connectivity.py',
        '--input', '/scratch/topology_recovery_20261004/B3R_witness/s5378/generator_input.odb',
        '--generated', '/scratch/topology_recovery_20261004/B3R_witness/s5378/generated.odb',
        '--output', '/scratch/topology_recovery_20261004/B3R_witness/observation.json']
    if run(container(observe, repaired=False), folder, 'observe'):
        raise RuntimeError('Witness observation failed')
    shutil.copy2(DATA / 'B3R_witness/observation.json', folder / 'observation.json')
    print('BENCHMARK_BLOCKER_SCAN_OUTPUT_TOPOLOGY_REPRODUCED', flush=True)


def prepare():
    ensure()
    if not (CAMPAIGN / 'ROOT_CAUSE.md').is_file():
        raise ValueError('Write source-level root cause before source mutation')
    if PREFIX.exists():
        raise ValueError('Preserve existing repair worktree')
    PREFIX.mkdir()
    for directory in ('source', 'build'):
        subprocess.run(['cp', '-a', str(MOUNT / RECEIVER / directory), str(PREFIX / directory)], check=True)
    (PREFIX / 'compiler_tmp').mkdir()
    if git('rev-parse', 'HEAD').strip() != PARENT or git('diff', '--ignore-submodules', '--name-only').strip():
        raise ValueError('Isolated source does not match immutable parent')
    git('switch', '-c', BRANCH, PARENT)
    REPAIR.mkdir(parents=True, exist_ok=True)
    for relative in (FILE, 'src/dft/src/optimizer/Opt.cpp', 'src/dft/src/optimizer/KMeans.hh',
                     'src/dft/src/optimizer/OdbScanCellAdapter.cpp', 'src/dft/src/cells/OneBitScanCell.cpp'):
        target = REPAIR / 'parent_source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / relative, target)
    write(REPAIR / 'parent.json', dict(parent=PARENT, upstream_base=BASE, branch=BRANCH,
        source=str(SOURCE), parent_binary=binding(MOUNT / RECEIVER / 'build/bin/openroad'),
        source_snapshots={str(p.relative_to(REPAIR / 'parent_source')): binding(p)
            for p in (REPAIR / 'parent_source').rglob('*') if p.is_file()},
        build_cache='Independent cp -a of immutable B3R build; container aliases preserve absolute paths',
        root_cause=binding(CAMPAIGN / 'ROOT_CAUSE.md')))


def implement():
    ensure()
    if git('rev-parse', 'HEAD').strip() != PARENT:
        raise ValueError('Unexpected source revision')
    path = SOURCE / FILE
    text = path.read_text()
    text = text.replace('//   cells[n-1].SO → chain.scan_out  (metadata only — see note below)',
                        '//   cells[n-1].SO → chain.scan_out')
    text = text.replace('// Note on scan_out: the chain-level scan_out BTerm/ITerm is typically a\n'
        '// functional Q output that must remain on its original net.  We only update\n'
        '// the chain metadata pointer (setScanOut) rather than physically moving nets.',
        '// Preserve the fixed scan_out endpoint and the functional fanout of each\n'
        '// cell output.  Only the endpoint load moves when the tail changes.')
    before = '''  // Update chain scan_out metadata to the last cell's SO ITerm.
  odb::dbITerm* last_so = cells.back()->getScanOutITerm();
  if (last_so != nullptr) {
    chain->setScanOut(last_so);
  }
'''
    after = '''  // Connect the fixed scan output load to the final tail's existing net.
  odb::dbITerm* last_so = cells.back()->getScanOutITerm();
  if (last_so != nullptr) {
    odb::dbNet* net = last_so->getNet();
    if (net == nullptr) {
      net = odb::dbNet::create(block, last_so->getName().c_str());
      if (net == nullptr) {
        logger->error(
            utl::DFT, 15, "Failed to create net for scan_opt restitching.");
      }
      net->setSigType(odb::dbSigType::SCAN);
      last_so->connect(net);
    }
    std::visit(
        [&](auto&& pin) {
          if (pin != nullptr) {
            pin->connect(net);
          }
        },
        chain->getScanOut());
  }

  // Keep ODB scan-list order consistent with the restitched physical order.
  // insertAtFront stores the reverse of the logical scan order.
  odb::dbScanList* list = getScanList(chain);
  if (list != nullptr) {
    std::map<std::string, odb::dbScanInst*> scan_insts;
    for (odb::dbScanInst* scan_inst : list->getScanInsts()) {
      scan_insts.emplace(scan_inst->getInst()->getName(), scan_inst);
    }
    list->clear();
    for (const auto* cell : cells) {
      scan_insts.at(std::string(cell->getName()))->insertAtFront(list);
    }
  }
'''
    if text.count(before) != 1:
        raise ValueError('Expected unique defect is absent')
    path.write_text(text.replace(before, after))
    subprocess.run(['clang-format-18', '-i', '--lines=68:158', str(path)], check=True)
    git('diff', '--check')
    if git('diff', '--name-only').strip() != FILE:
        raise ValueError('Repair exceeds native reconstruction source')
    for relative, item in read(REPAIR / 'parent.json')['source_snapshots'].items():
        if relative != FILE and binding(SOURCE / relative)['sha256'] != item['sha256']:
            raise ValueError('Algorithm source changed: ' + relative)
    (REPAIR / 'patch.diff').write_text(git('diff', '--binary', '--no-ext-diff'))
    git('add', FILE)
    git('commit', '-s', '-m', 'dft: preserve scan endpoints and synchronize optimized chain order')
    commit = git('rev-parse', 'HEAD').strip()
    write(REPAIR / 'repair_manifest.json', dict(repair_class='R1', method='B3S', repair_commit_sha=commit,
        parent_revision=PARENT, upstream_base_sha=BASE, changed_files=[FILE],
        patch=binding(REPAIR / 'patch.diff'), patch_sha256=binding(REPAIR / 'patch.diff')['sha256'],
        changed_source_sha256={FILE: binding(path)['sha256']}, algorithm_changed=False,
        objective_changed=False, search_space_changed=False, parameters_changed=False,
        endpoint_semantics='Restore fixed endpoint load connection; retain endpoint identity and functional nets',
        metadata='Same final cell order drives SI/internal/SO rewiring and reverse-stored dbScanList',
        signed_commit=git('log', '-1', '--format=full')))
    print('B3_NATIVE_ENDPOINT_REPAIR_IMPLEMENTED', commit, flush=True)


def build():
    ensure()
    repair = read(REPAIR / 'repair_manifest.json')
    commit = repair['repair_commit_sha']
    if git('rev-parse', 'HEAD').strip() != commit or git('diff', '--ignore-submodules', '--name-only').strip():
        raise ValueError('Never build benchmark from moving worktree')
    old = OUT / 'receiver_recovery_20261003/baselines' / RECEIVER
    args = read(old / 'configure_final.execution.json')['command']
    args = args[args.index('cmake'):]
    args = ['-DOPENROAD_VERSION=' + commit if s.startswith('-DOPENROAD_VERSION=') else s for s in args]
    attempt = 1
    while (FOLDER / ('configure' + ('' if attempt == 1 else '_attempt'+str(attempt)) + '.execution.json')).exists():
        attempt += 1
    suffix = '' if attempt == 1 else '_attempt'+str(attempt)
    if run(container(args), FOLDER, 'configure'+suffix):
        return 1
    shutil.copy2(BUILD / 'CMakeCache.txt', FOLDER / 'CMakeCache.txt')
    if run(container(['cmake', '--build', f'/build_storage/{OLD}/build', '--parallel', '2', '--target', 'openroad']), FOLDER, 'build'+suffix):
        return 1
    if run(container([f'/build_storage/{NAME}/build/bin/openroad', '-version']), FOLDER, 'version'+suffix):
        return 1
    if commit not in (FOLDER / ('version'+suffix+'.log')).read_text():
        raise ValueError('Binary must identify immutable repair commit')
    binary = binding(BUILD / 'bin/openroad')
    write(FOLDER / 'build_result.json', dict(status='BUILT', method='B3S', commit=commit,
        upstream_base_sha=BASE, parent_revision=PARENT, binary=binary, binary_sha256=binary['sha256'],
        source_manifest=binding(REPAIR / 'repair_manifest.json'),
        build=binding(FOLDER / ('build'+suffix+'.execution.json')), configuration=binding(FOLDER / ('configure'+suffix+'.execution.json')), image=IMAGE))
    return 0


def refine():
    ensure()
    first = read(REPAIR / 'repair_manifest.json')
    if git('rev-parse', 'HEAD').strip() != first['repair_commit_sha']:
        raise ValueError('Preserve immutable first attempt')
    shutil.copy2(REPAIR / 'repair_manifest.json', REPAIR / 'attempt1_repair_manifest.json')
    shutil.copy2(REPAIR / 'patch.diff', REPAIR / 'attempt1_patch.diff')
    path = SOURCE / FILE
    text = path.read_text()
    old = 'utl::DFT, 15, "Failed to create net for scan_opt restitching."'
    if text.count(old) != 2:
        raise ValueError('Expected duplicate diagnostic witness')
    offset = text.rindex(old)
    text = text[:offset] + text[offset:].replace(old, 'utl::DFT, 20, "Failed to create net for scan_opt output."', 1)
    marker = '''  odb::dbDft* db_dft = block->getDft();

  // ---------------------------------------------------------------------------
  // Spatial pre-clustering'''
    replacement = '''  odb::dbDft* db_dft = block->getDft();

  // A functional output implicitly reused by stitching must not be moved.
  // Require an explicitly configured scan output before changing chain tails.
  size_t ordinal = 0;
  for (odb::dbScanChain* chain : db_dft->getScanChains()) {
    const auto output_name = fmt::format(
        FMT_RUNTIME(dft_config_->getScanStitchConfig().getOutNamePattern()),
        ordinal++);
    if (auto* term = std::get_if<odb::dbBTerm*>(&chain->getScanOut());
        term != nullptr && *term != nullptr && (*term)->getName() != output_name) {
      logger_->error(utl::DFT,
                     22,
                     "scan_opt requires a configured scan output {}; {} is an "
                     "implicitly reused functional output.",
                     output_name,
                     (*term)->getName());
    }
  }

  // ---------------------------------------------------------------------------
  // Spatial pre-clustering'''
    if text.count(marker) != 1:
        raise ValueError('Expected scanOpt entry missing')
    path.write_text(text.replace(marker, replacement))
    subprocess.run(['clang-format-18', '-i', '--lines=120:159', '--lines=425:449', str(path)], check=True)
    test = SOURCE / 'src/dft/test/scan_opt_sky130.tcl'
    t = test.read_text()
    t = t.replace('execute_dft_plan\n', '''# Dedicated scan output: functional output ports must retain their Q nets.
set block [ord::get_db_block]
set so_net [odb::dbNet_create $block scan_out_0]
set so_port [odb::dbBTerm_create $so_net scan_out_0]
$so_port setIoType OUTPUT
$so_port setSigType SCAN
set functional_outputs {}
for {set i 1} {$i <= 10} {incr i} {
  dict set functional_outputs output$i [[$block findBTerm output$i] getNet]
}

execute_dft_plan
''')
    t = t.replace('scan_opt\n', '''scan_opt

# Independently trace the optimized physical order to the original fixed SO.
set net [[$block findBTerm scan_in_0] getNet]
set so_net [$so_port getNet]
set order {}
set visited {}
while {$net != $so_net} {
  if {[lsearch -exact $visited $net] >= 0} { error "scan cycle" }
  lappend visited $net
  set successors {}
  foreach pin [$net getITerms] {
    if {[[$pin getMTerm] getName] == "SCD"} {
      lappend successors [$pin getInst]
    }
  }
  if {[llength $successors] != 1} { error "scan fork or missing fixed SO" }
  set inst [lindex $successors 0]
  lappend order [$inst getName]
  set net [[$inst findITerm Q] getNet]
}
if {[llength $order] != 10 || [llength [lsort -unique $order]] != 10} {
  error "scan membership changed or SO is interior"
}
foreach pin [$so_net getITerms] {
  if {[[$pin getMTerm] getName] == "SCD"} { error "SO is not the tail" }
}
dict for {name net} $functional_outputs {
  if {[[$block findBTerm $name] getNet] != $net} {
    error "functional output moved"
  }
}
set metadata {}
foreach chain [[$block getDft] getScanChains] {
  foreach partition [$chain getScanPartitions] {
    foreach scan_list [$partition getScanLists] {
      foreach scan_inst [$scan_list getScanInsts] {
        lappend metadata [[$scan_inst getInst] getName]
      }
    }
  }
}
if {[lreverse $metadata] != $order} { error "stale optimized scan metadata" }
''')
    test.write_text(t)
    # The golden gains the dedicated endpoint but retains every functional Q.
    golden = SOURCE / 'src/dft/test/scan_opt_sky130.vok'
    g = golden.read_text().replace('    scan_in_0);', '    scan_in_0,\n    scan_out_0);')
    g = g.replace(' input scan_in_0;', ' input scan_in_0;\n output scan_out_0;')
    g = g.replace('endmodule', ' assign scan_out_0 = output8;\nendmodule')
    golden.write_text(g)
    git('diff', '--check')
    git('add', FILE, 'src/dft/test/scan_opt_sky130.tcl', 'src/dft/test/scan_opt_sky130.vok')
    git('commit', '-s', '-m', 'dft: guard functional output reuse and exercise fixed scan endpoints')
    commit = git('rev-parse', 'HEAD').strip()
    (REPAIR / 'patch.diff').write_text(git('diff', PARENT, commit, '--binary', '--no-ext-diff'))
    first.update(repair_commit_sha=commit, prior_attempt_commit=first['repair_commit_sha'],
        changed_files=git('diff', PARENT, '--name-only').splitlines(),
        patch=binding(REPAIR / 'patch.diff'), patch_sha256=binding(REPAIR / 'patch.diff')['sha256'],
        changed_source_sha256={FILE: binding(path)['sha256']},
        regression='Existing scan_opt_sky130 test: fixed dedicated SO, unchanged functional outputs, complete membership and metadata order',
        functional_output_reuse='Reject implicit functional SO reuse before optimization; configured scan loads retain fixed identity',
        signed_commit=git('log', '-1', '--format=full'))
    (REPAIR / 'repair_manifest.json').write_text(json.dumps(first, indent=2, sort_keys=True)+'\n')
    print('B3_NATIVE_ENDPOINT_REPAIR_REFINED', commit, flush=True)


def qualify(design):
    ensure()
    build = read(FOLDER / 'build_result.json')
    repair = read(REPAIR / 'repair_manifest.json')
    if binding(build['binary']['path'])['sha256'] != build['binary_sha256']:
        raise ValueError('Immutable binary changed')
    scratch = DATA / NAME / design
    scratch.mkdir(parents=True, exist_ok=True)
    args = [f'/build_storage/{NAME}/build/bin/openroad', '-python', '-no_init', '-exit',
        '/workspace/scripts/pact_oss_topology_generator.py', '--method', 'B3S', '--commit', build['commit'],
        '--design', design, '--source', f'/scratch/placed_common/{design}/3_place.odb',
        '--output', f'/scratch/topology_recovery_20261004/{NAME}/{design}',
        '--liberty', '/scratch/NangateOpenCellLibrary_typical_dft.lib']
    rc = run(container(args, flow=True), FOLDER / design, 'generate')
    for filename in ('qualification.json', 'canonical.json', 'architecture.json', 'generated.v', 'semantic_qualification.json'):
        if (scratch / filename).exists():
            shutil.copy2(scratch / filename, FOLDER / design / filename)
    if rc:
        return rc
    proof = read(FOLDER / design / 'semantic_qualification.json')
    if proof['status'] != 'PASS':
        raise ValueError('Native representation/functional qualification failed')
    print('B3_TOPOLOGY_QUALIFIED', design, proof['chain_lengths'], flush=True)
    if all((FOLDER / d / 'semantic_qualification.json').exists() for d in DESIGNS):
        write(FOLDER / 'qualification.json', dict(status='PASS', method='B3S', source_commit=build['commit'],
            binary_sha256=build['binary_sha256'], repair=binding(REPAIR / 'repair_manifest.json'),
            designs={d: dict(proof=binding(FOLDER / d / 'semantic_qualification.json'),
                            canonical=binding(FOLDER / d / 'canonical.json'),
                            chain_lengths=read(FOLDER / d / 'qualification.json')['chain_lengths'],
                            architecture_hash=read(FOLDER / d / 'qualification.json')['canonical_architecture_hash']) for d in DESIGNS}))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('reproduce', 'prepare', 'implement', 'refine', 'build', 'qualify'))
    parser.add_argument('--design', choices=DESIGNS)
    args = parser.parse_args()
    result = qualify(args.design) if args.action == 'qualify' else globals()[args.action]()
    raise SystemExit(result or 0)
