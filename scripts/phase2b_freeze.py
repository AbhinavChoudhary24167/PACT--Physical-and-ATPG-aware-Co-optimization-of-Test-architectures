#!/usr/bin/env python3
"""One-time preregistration; no Phase-2B measurements collected here."""
from phase2b_common import *
from datetime import datetime, timezone
import platform
import subprocess
from pact.experiment_storage import configure_experiment_storage, guard_disk_space

def main():
    if (REPORT / 'freeze.json').exists():
        raise RuntimeError('Refusing to replace Phase-2B freeze')
    paths = configure_experiment_storage()
    guard_disk_space(paths, estimated_bytes=2*1024**3)
    REPORT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    inputs = read(OLD / 'provenance.json')
    for name, sha in read(OLD / 'freeze.json')['files'].items():
        assert file_sha256(OLD / name) == sha
    inputs.update(read(OLD / 'measurement_provenance.json')['files'])
    for name, sha in inputs.items():
        assert file_sha256(Path(name)) == sha, name
    # Preserve existing compact evidence and code, including dirty/untracked work.
    for folder in ('reports', 'src', 'scripts', 'config', 'tests', 'docs'):
        for p in sorted((ROOT / folder).rglob('*')):
            if p.is_file() and REPORT not in p.parents and '__pycache__' not in p.parts and 'phase2b' not in str(p):
                inputs[str(p)] = file_sha256(p)
    extra = [LIB, RULES, PLATFORM/'setRC.tcl', PLATFORM/'lef/NangateOpenCellLibrary.tech.lef',
             PLATFORM/'lef/NangateOpenCellLibrary.macro.mod.lef',
             PLATFORM.parent.parent/'scripts/final_outputs.tcl',
             Path('/root/pact-deps/OpenROAD/src/rcx/README.md'),
             Path('/root/pact-deps/FAN_ATPG/pkg/core/src/pattern_rw.cpp')]
    for d,q in read(OLD/'test_quality.json').items():
        extra += [Path(q['placed_def']).with_suffix('.v'),
                  ROOT/f'artifacts/raw/tool_qualification/fan_atpg/benchmarks/{d}.v']
    for p in extra:
        inputs[str(p)] = file_sha256(p)
    write(REPORT/'architecture_set.json', read(OLD/'architecture_set.json'))
    features = {
        'pattern_bits': ['POST-SYNTHESIS', 'frozen FAN PPI, architecture-defined shift order'],
        'H_eff8': ['POST-PLACEMENT', 'exact frozen Phase-2A value, no retuning'],
        'fanout': ['POST-SYNTHESIS', 'placed DEF connectivity projected to selected scan order; no routed graph'],
        'pin_cap_ff': ['POST-SYNTHESIS', 'typical Liberty input pin capacitance, fF'],
        'ff_xy_sink_xy_ports': ['POST-PLACEMENT', 'frozen pre-route placed DEF, cell origins; fixed Phase-0C port policy'],
        'hpwl_star_scan_length': ['POST-PLACEMENT', 'computed solely from pre-route graph and coordinates'],
        'layer3_cap_per_um': ['PRE-SYNTHESIS', 'technology setRC.tcl metal3 0.103981 fF/um; fixed, not fitted'],
        'routed_wirelength': ['POST-ROUTE', 'LABEL ONLY; never accepted by predictor API'],
        'SPEF_capacitance': ['POST-ROUTE', 'LABEL ONLY; never accepted by predictor API'],
        'spatial_windows': ['POST-PLACEMENT', 'Phase-2A fixed 10x10 bins, all wholly contained 2x2 windows']}
    write(REPORT/'feature_availability.json', {k:dict(stage=v[0],definition=v[1],role='label_only' if v[0]=='POST-ROUTE' else 'predictor') for k,v in features.items()})
    contract = '''# Phase-2B physical activity model qualification contract

Freeze before collection. Retain all 21 Phase-2A architectures: 9 s5378,
6 s9234, 6 s15850. Fixed seed 11, K=2. No optimizer/search/ATPG/placement/
routing runs; no changes to any earlier evidence. Exact ODB archive and
decompressed hashes checked before extraction, copied to D: experiment area.

Primary waveform remains the exact Phase-2A zero-initial, carry-loaded,
no-capture/no-final-unload stable-state shift sequence, enabling direct comparison.
Audit all seven FAN fields and upstream BASIC_SCAN writer. If complete capture
states can be independently validated, record a separate load/capture/next-load/
final-zero-unload FF sequence; never mix its measurements into primary labels.
Zero final-unload SI is an explicit protocol choice, not recovered tester history.
Missing/unknown capture bits or unverifiable correspondence =>
FULL_TEST_WAVEFORM_UNQUALIFIED. No inferred glitches or cell internal switching.

Extraction: installed ORFS Nangate45 rules, model index 0, corner X, OpenRCX
on exact 5_2_route ODB copies. Preserve originals and do not invoke ORFS finish
(which deletes obstructions). Explicit coupling_threshold=0.1 fF; cc_model=10,
context_depth=5, version=1.0; inspect installed API. SPEF ground-only and
ground+one-times-coupling endpoint-load sensitivities. Main capacitance label
uses ground+one-times incident coupling, plus actual routed sink pin loads.
This is a load-weighted transition count, fF-transitions, NOT energy or power;
coupling does not model aggressor correlation or Miller switching. Sum owned
Q/QN nets through existing BUF/CLKBUF/INV paths, uniquely per FF; excludes other
logic, clock/PI/SE driven nets and cell internals. Investigate all-net metric
scope but do not invent missing combinational waveforms. Capacitance targets
exist only if every selected architecture passes nonzero RC, all owned nets
covered, finite values, SPEF accounting and exact route checks. Otherwise
electrical validation BLOCKED; continue geometric labels unchanged.

Fixed predictors: M0 raw toggles; M1 frozen H_eff8; M2 internal scan-link
Manhattan and port-aware FF-source output link distances (SI is not FF-driven);
M4 connected input count and Liberty pin capacitance; M5 sum of owned-net HPWL
and driver-to-sink Manhattan star length; M3 pin fF + 0.103981 fF/um * HPWL.
Metal3 coefficient comes from installed technology setRC.tcl, never fitted.
Functional-only M4/M5 variants omit added SI/SO loads. Start from pre-route
placed DEF graph, remove original SI/test_so connections, append selected
scan links and fixed output ports, traverse only pre-existing transparent
cells. Geometry uses cell origins and placed output-port locations; no route
length, routed placement, inserted route buffers or target enters predictors.
M6: local peak for every nonnegative per-FF weight using fixed Phase-2A bins.
No fitted coefficients, ML, per-design tuning or leave-one-out fitting needed.

Targets: raw total; frozen routed wire-weighted total and local peak;
qualified capacitance total/local peak only when available. Report every
predictor vs every target: Spearman, tau-b, Pearson, exact ascending rankings,
all pair directions with ties, equal-design mean-normalized and fractional-rank
pooling using Phase-2A implementation. No statistical significance claim.
Plots: two geometric scatter grids with ranks, optional two capacitance grids,
one compact design-by-metric heatmap. No retrospective binning or selection.

Decision: qualification requires a total/local metric family with rho>=0.7
and >=75% correct direction among non-tied pairs for BOTH geometric endpoints
on EVERY design, with no target leakage. If capacitance qualifies, require
the same electrical endpoint gate for joint qualification, report separately.
Partial if a family raises rho by >=0.2 over H_eff8 on BOTH geometric endpoints
on at least two designs but fails qualification; otherwise fail. These are
descriptive finite-set thresholds, not population validation. Preserve all
negative results. No automatic Phase-2C integration.

Measure graph/weight construction and scoring wall time, peak RSS, dimensions.
Use sparse/per-FF arrays; no dense FF-by-FF matrices. Focused analytic tests,
then full PACT regression. Hash prior evidence after execution, all inputs,
scripts and outputs. Large inventories/SPEF/traces/logs under
D:/PACT_EXPERIMENTS/results/phase2b_activity_model. No raw experiment data in git.
'''
    (REPORT/'EXPERIMENT_CONTRACT.md').write_text(contract)
    cmd = lambda args: subprocess.check_output(args, text=True, cwd=ROOT).strip()
    write(REPORT/'provenance.json', dict(inputs=inputs, git_commit=cmd(['git','rev-parse','HEAD']),
        initial_git_status=(REPORT/'initial_git_status.txt').read_text(encoding='utf-8-sig'), python=platform.python_version(),
        environment=platform.platform(), openroad=cmd(['openroad','-version']),
        orfs_commit=cmd(['git','-C',str(PLATFORM.parent.parent.parent),'rev-parse','HEAD'])))
    names = ['EXPERIMENT_CONTRACT.md','architecture_set.json','feature_availability.json','provenance.json']
    write(REPORT/'freeze.json', dict(frozen_utc=datetime.now(timezone.utc).isoformat(),
        files={n:file_sha256(REPORT/n) for n in names}, architectures=21, new_routes=0, new_optimizer_runs=0))
    integrity()
    print('FROZEN', len(inputs), 'inputs; 21 architectures')

if __name__ == '__main__': main()
