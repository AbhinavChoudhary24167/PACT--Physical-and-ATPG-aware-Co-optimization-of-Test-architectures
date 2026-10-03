#!/usr/bin/env python3
"""Qualify the actual B3R executable on the unchanged frozen K=2 inputs.

This adds evidence in the receiver recovery namespace. Exact B2 and the
original failed B3 remain untouched. No optimizer is implemented in Python.
"""
import argparse
from pathlib import Path
import re
import shutil

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, write
from pact_oss_recovery import TEMP, MOUNT, IMAGE, docker, execute, require_prerequisites
from pact_oss_receiver_stage_a import (
    BASELINES, PREVIOUS, DATA, REPAIRED_FILE, checked, exclusive,
    validate_baseline, validate_repair,
)
from pact_oss_canonicalize import csv_write, validate_architecture
from pact.scan.model import ScanArchitecture

METHOD = 'B3R'
NAME = BASELINES[METHOD]['name']
FOLDER = BASELINES[METHOD]['folder']
SOURCE = MOUNT / NAME / 'source'
BINARY = MOUNT / NAME / 'build/bin/openroad'
SCRATCH = DATA / NAME
DISPLAY = 'B3R — PR #10666 + minimal compile repair'


def validate_build_identity(build, repair, sources):
    """An uncommitted or provisional validation build cannot generate evidence."""
    commit = repair.get('repair_commit_sha')
    if not isinstance(commit, str) or re.fullmatch('[0-9a-f]{40}', commit) is None:
        raise ValueError('Generation requires the immutable repair commit SHA')
    base = BASELINES[METHOD]['upstream_base_sha']
    if commit == base:
        raise ValueError('Repaired B3R cannot be labeled as exact B3')
    if build.get('status') != 'BUILT' or not build.get('binary') or not build.get('binary_sha256'):
        raise ValueError('Generation requires the immutable final B3R build result')
    if build.get('commit') != commit or sources.get('repair_commit_sha') != commit:
        raise ValueError('Build/source evidence differs from the repair commit')
    if {build.get('upstream_base_sha'), repair.get('upstream_base_sha'), sources.get('upstream_base_sha')} != {base}:
        raise ValueError('Build/source/repair evidence differs from pinned B3 base')
    patch = repair.get('patch_sha256')
    if not isinstance(patch, str) or re.fullmatch('[0-9a-f]{64}', patch) is None or sources.get('patch_sha256') != patch:
        raise ValueError('Build source is not bound to the exact receiver patch')
    if set(repair['changed_files']) != {REPAIRED_FILE}:
        raise ValueError('Repair includes an unauthorized file')
    return commit


def validate_runtime_identity(record, build, repair):
    """Bind the executing binary, commit and patch to both kinds of proof."""
    expected = dict(status='PASS', method=METHOD, source_commit=build['commit'],
        binary_sha256=build['binary_sha256'], upstream_base_sha=repair['upstream_base_sha'],
        repair_patch_sha256=repair['patch_sha256'], method_display=DISPLAY)
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError('Actual B3R runtime identity differs: ' + key)


def prerequisites():
    from pact_oss_storage import ensure
    from pact_oss_verify import audit as original_audit
    ensure()
    require_prerequisites()
    original_audit()
    validate_baseline('B2', BASELINES['B2'])
    build = read(FOLDER / 'build_result.json')
    repair = read(FOLDER / 'repair/repair_manifest.json')
    sources = read(FOLDER / 'source_manifest.json')
    validate_build_identity(build, repair, sources)
    if Path(build['binary']['path']).resolve() != BINARY.resolve():
        raise ValueError('Final B3R binary is not in its independent build prefix')
    if checked(build['binary'])['sha256'] != build['binary_sha256']:
        raise ValueError('Final B3R executable changed')
    for key in ('build', 'configuration', 'source_manifest'):
        if isinstance(build.get(key), dict) and 'path' in build[key]:
            checked(build[key])
    original = PREVIOUS / 'baselines/B3_openroad_10666'
    hashes = read(original / 'source_manifest.json')['pinned_source_blobs_checked']
    validate_repair(SOURCE, repair, hashes, original / 'diagnostics' / REPAIRED_FILE)
    annotation = read(OUT / 'protocol/dft_metadata_adapter.json')
    for key in ('original_liberty', 'regenerated_liberty'):
        checked(annotation[key])
    old_sources = read(PREVIOUS / 'stage_a/evidence_manifest.json')['benchmark_sources']
    for relative in ('scripts/pact_oss_native.py', 'scripts/pact_oss_generator.py', 'scripts/pact_oss_command_probe.py'):
        checked(old_sources[relative])
    frozen_native = read(OUT / 'stage_a/evidence_manifest.json')['benchmark_sources']['scripts/pact_oss_native.py']
    checked(frozen_native)
    for design in DESIGNS:
        common = read(OUT / 'baselines/B1_openroad_native' / design / 'common_input.json')
        if binding(TEMP / 'placed_common' / design / '3_place.odb')['sha256'] != common['source']['sha256']:
            raise ValueError('Qualified common placed generator input changed: ' + design)
    return build, repair


def container(args, flow_inputs=False):
    command = docker(args)
    mounts = ['--mount', f'type=bind,source={SOURCE},target=/build_storage/{NAME}/source,readonly']
    if flow_inputs:
        mounts += ['--mount', 'type=bind,source=/root/pact-deps/OpenROAD-flow-scripts/flow/results,target=/root/pact-deps/OpenROAD-flow-scripts/flow/results,readonly']
    position = command.index('--entrypoint')
    command[position:position] = mounts
    return command


def run(command, folder, label):
    snapshot = folder / (label + '.pact_oss_receiver_generate.py')
    if snapshot.exists():
        raise ValueError('Preserve the existing generation attempt: ' + str(snapshot))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, snapshot)
    return execute(command, folder, label)


def copy_new(source, destination):
    if destination.exists():
        raise ValueError('Refusing to replace generator evidence: ' + str(destination))
    shutil.copy2(source, destination)


def generate():
    with exclusive(FOLDER, 'generation'):
        build, repair = prerequisites()
        if (FOLDER / 'generation_inputs.json').exists() or (FOLDER / 'qualification.json').exists():
            raise ValueError('Generation evidence exists; preserve its outcome and namespace')
        inputs = {}
        for design in DESIGNS:
            common = OUT / 'baselines/B1_openroad_native' / design / 'common_input.json'
            inputs[design] = dict(common_input=binding(common), placed_database=binding(TEMP / 'placed_common' / design / '3_place.odb'))
        snapshots = {}
        for relative in ('scripts/pact_oss_receiver_generate.py', 'scripts/pact_oss_receiver_generator.py',
                         'scripts/pact_oss_receiver_command_probe.py', 'scripts/pact_oss_generator.py',
                         'scripts/pact_oss_command_probe.py', 'scripts/pact_oss_native.py'):
            destination = FOLDER / 'generation_source_snapshots' / Path(relative).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_new(ROOT / relative, destination)
            snapshots[relative] = binding(destination)
        write(FOLDER / 'generation_inputs.json', dict(method=METHOD, method_display=DISPLAY,
            source_commit=build['commit'], upstream_base_sha=repair['upstream_base_sha'], patch_sha256=repair['patch_sha256'],
            final_build=binding(FOLDER / 'build_result.json'), repair_manifest=binding(FOLDER / 'repair/repair_manifest.json'),
            source_manifest=binding(FOLDER / 'source_manifest.json'), exact_B2_reused=binding(BASELINES['B2']['folder'] / 'qualification.json'),
            immutable_image=IMAGE, common_inputs=inputs, source_snapshots=snapshots,
            selection=binding(OUT / 'stage_a/P0_SELECTION.json'), new_search_runs=0,
            commands='execute_dft_plan then actual compiled scan_opt; frozen adapter; no substitute optimizer'))
        executable = f'/build_storage/{NAME}/build/bin/openroad'
        if run(container([executable, '-version']), FOLDER, 'binary_version'):
            return 1
        if build['commit'] not in (FOLDER / 'binary_version.log').read_text():
            raise ValueError('B3R executable does not report the immutable repair commit')
        SCRATCH.mkdir(parents=True, exist_ok=True)
        identity = ['--method', METHOD, '--commit', build['commit'], '--upstream-base', repair['upstream_base_sha'],
                    '--patch-sha256', repair['patch_sha256']]
        probe = container([executable, '-python', '-no_init', '-exit',
            '/workspace/scripts/pact_oss_receiver_command_probe.py', *identity,
            '--source', f'/build_storage/{NAME}/source',
            '--output', f'/scratch/receiver_recovery_20261003/{NAME}/compiled_behavior.json'])
        if run(probe, FOLDER, 'compiled_command_probe'):
            return 1
        copy_new(SCRATCH / 'compiled_behavior.json', FOLDER / 'compiled_behavior.json')
        copy_new(SCRATCH / 'compiled_behavior.commands.txt', FOLDER / 'compiled_behavior.commands.txt')
        validate_runtime_identity(read(FOLDER / 'compiled_behavior.json'), build, repair)
        rows, qualifications = [], {}
        frozen = read(OUT / 'stage_a/P0_FREEZE.json')
        for design in DESIGNS:
            scratch = SCRATCH / design
            scratch.mkdir(parents=True, exist_ok=True)
            args = ['/usr/bin/time', '-v', '-o', f'/scratch/receiver_recovery_20261003/{NAME}/{design}/generator.resource.txt',
                executable, '-python', '-no_init', '-exit', '/workspace/scripts/pact_oss_receiver_generator.py',
                *identity, '--design', design, '--source', f'/scratch/placed_common/{design}/3_place.odb',
                '--output', f'/scratch/receiver_recovery_20261003/{NAME}/{design}',
                '--liberty', '/scratch/NangateOpenCellLibrary_typical_dft.lib']
            target = FOLDER / design
            if run(container(args, flow_inputs=True), target, 'generate'):
                write(FOLDER / 'qualification.json', dict(status='FAILED', method=METHOD, method_display=DISPLAY,
                    failed_design=design, completed_designs=qualifications, source_commit=build['commit'],
                    upstream_base_sha=repair['upstream_base_sha'], patch_sha256=repair['patch_sha256'],
                    binary_sha256=build['binary_sha256'], compiled_behavior=binding(FOLDER / 'compiled_behavior.json')))
                return 2
            for filename in ('qualification.json', 'architecture.json', 'canonical.json', 'generated.v', 'generator.resource.txt'):
                copy_new(scratch / filename, target / filename)
            proof = read(target / 'qualification.json')
            validate_runtime_identity(proof, build, repair)
            if not proof['endpoint_geometry_unchanged'] or not proof['canonical_translation_preserves_inventory_assignment_order']:
                raise ValueError('B3R canonical endpoint/order qualification failed')
            canonical = ScanArchitecture.from_json(target / 'canonical.json')
            reference = ScanArchitecture.from_json(Path(frozen['frozen_inputs'][design]['B0_reference']['path']))
            validate_architecture(canonical, reference)
            if canonical.sha256() != proof['canonical_architecture_hash'] or proof['FF_count'] != len(reference.cells) or proof['K'] != 2:
                raise ValueError('B3R canonical inventory/identity differs from its runtime proof')
            if proof['chain_lengths'] != [len(chain.cells) for chain in canonical.chains]:
                raise ValueError('B3R chain lengths differ from canonical proof')
            qualifications[design] = dict(proof=binding(target / 'qualification.json'), canonical=binding(target / 'canonical.json'),
                chain_lengths=proof['chain_lengths'], architecture_hash=canonical.sha256())
            for chain in canonical.chains:
                for index, ff in enumerate(chain.cells):
                    rows.append(dict(design=design, method=METHOD, method_display=DISPLAY, chain_id=chain.chain_id,
                        chain_index=index, ordered_ff_identity=ff, scan_in=chain.scan_in, scan_out=chain.scan_out,
                        chain_length=len(chain.cells), architecture_hash=canonical.sha256(), architecture_path=str(target / 'canonical.json')))
            print('QUALIFIED', METHOD, design, proof['chain_lengths'], canonical.sha256(), flush=True)
        # Recheck all immutable inputs, exact B2 and repair scope after execution.
        prerequisites()
        if len(rows) != 924:
            raise ValueError('Three-design B3R FF manifest is incomplete')
        csv_write(FOLDER / 'architecture_manifest.csv', list(rows[0]), rows)
        write(FOLDER / 'qualification.json', dict(status='PASS', method=METHOD, method_display=DISPLAY,
            source_commit=build['commit'], upstream_base_sha=repair['upstream_base_sha'], repair_commit_sha=repair['repair_commit_sha'],
            patch_sha256=repair['patch_sha256'], repair_patch_sha256=repair['patch_sha256'],
            binary_sha256=build['binary_sha256'], image=IMAGE, designs=qualifications,
            algorithm_source_blobs_unchanged_except_minimal_receiver_qualification=True,
            architecture_manifest=binding(FOLDER / 'architecture_manifest.csv'),
            parameter_evidence=binding(OUT / 'protocol/algorithm_audit.json'),
            generator_liberty_metadata=binding(OUT / 'protocol/dft_metadata_adapter.json'),
            compiled_behavior=binding(FOLDER / 'compiled_behavior.json'), generation_inputs=binding(FOLDER / 'generation_inputs.json'),
            commands='execute_dft_plan then actual compiled scan_opt; no substitute optimizer',
            exact_B2_regenerated=False, new_physical_implementations=0))
        validate_baseline(METHOD, BASELINES[METHOD])
        return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('method', nargs='?', default=METHOD, choices=(METHOD,))
    parser.parse_args()
    raise SystemExit(generate())
