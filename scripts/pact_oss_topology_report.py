#!/usr/bin/env python3
"""Report completed frozen Stage A and exact repair/upstream provenance."""
import csv
from datetime import datetime, timezone
import json
import urllib.request

from pact_oss_benchmark import OUT, binding, read, write
from pact_oss_compare import implemented_point
import pact_oss_topology as r
import pact_oss_serialization as s
import pact_oss_topology_stage_a as stage
import pact_oss_receiver_upstream as credentials


def upstream_status():
    token = credentials.credential()['password']
    def api(path, data=None):
        request = urllib.request.Request('https://api.github.com'+path,
            data=json.dumps(data).encode() if data is not None else None,
            method='PATCH' if data is not None else 'GET', headers={
            'Authorization': 'Bearer '+token, 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'scan-repair-local-validation'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    result = []
    for path in (r.CAMPAIGN / 'upstream/github_contribution.json', s.SERIAL / 'upstream/github_contribution.json'):
        item = read(path)
        url = item['PR_URL']
        parts = url.split('/')
        repo, number = '/'.join(parts[3:5]), parts[-1]
        pr = api(f'/repos/{repo}/pulls/{number}')
        if repo == 'mwsoli/OpenROAD' and 'Additional representation qualification' not in pr['body']:
            old_body = pr['body']
            body = old_body + '''

### Additional representation qualification

The independent serialization blocker is now isolated in OpenSTA PR https://github.com/The-OpenROAD-Project/OpenSTA/pull/420. With that one-file input-alias writer repair linked alongside this unchanged endpoint patch, three designs (179, 211 and 534 FFs; two chains each) pass fixed SI/internal/fixed SO traversal, exact membership and native metadata/saved ODB/generated Verilog agreement. FF masters, placement/orientation and functional D/CK/Q/QN connections remain unchanged. The one-buffer alias witness fails before and passes after the separate writer patch. This endpoint PR does not contain the OpenSTA submodule update. All three adjacent native DFT golden regressions pass.
'''
            (r.CAMPAIGN / 'upstream/body_before_qualification_update.md').write_text(old_body)
            (r.CAMPAIGN / 'upstream/body_after_qualification_update.md').write_text(body)
            updated = api(f'/repos/{repo}/pulls/{number}', dict(body=body))
            if updated['head']['sha'] != pr['head']['sha']:
                raise ValueError('Contribution branch unexpectedly changed')
            pr = updated
        sha = pr['head']['sha']
        reviews = api(f'/repos/{repo}/pulls/{number}/reviews')
        checks = api(f'/repos/{repo}/commits/{sha}/check-runs')
        statuses = api(f'/repos/{repo}/commits/{sha}/status')
        result.append(dict(PR_URL=url, state=pr['state'], merged=pr['merged'], head_sha=sha,
            reviews=[dict(id=x['id'], state=x['state'], submitted_at=x['submitted_at']) for x in reviews],
            checks=[dict(name=x['name'], status=x['status'], conclusion=x['conclusion']) for x in checks['check_runs']],
            statuses=[dict(context=x['context'], state=x['state']) for x in statuses['statuses']],
            issue_created=False, benchmark_waited_for_review=False))
    write(r.CAMPAIGN / 'upstream/final_status.json', dict(capture_time_utc=datetime.now(timezone.utc).isoformat(), records=result))
    return result


def main():
    r.ensure()
    s.activate()
    rows = list(csv.DictReader((stage.STAGE / 'implemented_metrics.csv').open()))
    selected = [row for row in rows if row['selected'] == 'True']
    if len(selected) != 19 or any(implemented_point(row) is None for row in selected):
        raise ValueError('Stage A selected physical measurements remain incomplete')
    native = read(s.FOLDER / 'qualification.json')
    source = read(s.FOLDER / 'source_manifest.json')
    endpoint = read(s.ENDPOINT_REPAIR / 'repair_manifest.json')
    serializer = read(s.REPAIR / 'repair_manifest.json')
    build = read(s.FOLDER / 'build_result.json')
    prior_binary = read(s.REPAIR / 'parent.json')['parent_binary']
    try:
        upstream = upstream_status()
    except Exception as error:
        upstream = []
        for path in (r.CAMPAIGN / 'upstream/github_contribution.json', s.SERIAL / 'upstream/github_contribution.json'):
            known = read(path)
            upstream.append(dict(PR_URL=known['PR_URL'], state='current status unavailable', merged='unknown',
                reviews=[], checks=[], statuses=[], last_known_state=known['state'],
                last_known_merged=known.get('merged', False), status_error=str(error)))
        write(r.CAMPAIGN / 'upstream/final_status_unavailable.json', dict(records=upstream,
            benchmark_waited_for_review=False, status_error=str(error)))
    methods = [dict(method=m, source=description, repair_class=repair_class, algorithm_changed=False, status=status)
        for m, description, repair_class, status in (
            ('B0','Frozen seed-11 K=2 contiguous supplied-order reference','none','BENCHMARK_QUALIFIED'),
            ('B1','08f67ee5ecd14db5a42be8c610bbfd1ccf079299; native per-chain nearest-neighbor DFT plan','none','BENCHMARK_QUALIFIED'),
            ('B2','6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf','none','BENCHMARK_QUALIFIED'),
            ('B3',r.BASE,'none','BUILD_FAILED'),
            ('B3R',r.PARENT,'R0','TOPOLOGY_FAILED'),
            ('B3S',endpoint['repair_commit_sha'],'R1','ODB_METADATA_PASS_VERILOG_INPUT_ALIAS_FAILED'),
            ('B3T',build['commit'],'R1','BENCHMARK_QUALIFIED'),
            ('P0','9d9103027918b1d4af2b209e6d36133ad82d4a4e','none','BENCHMARK_QUALIFIED'))]
    write(r.CAMPAIGN / 'method_manifest.json', dict(methods=methods, full_B3T_source=binding(s.FOLDER / 'source_manifest.json'),
        qualification=binding(s.FOLDER / 'qualification.json'), selection=binding(stage.STAGE / 'selection_receipt.json'),
        physical_runtime_R0=binding(r.CAMPAIGN / 'stage_a_runtime/runtime.json'),
        B3S_immutable_binary=prior_binary, B3T_immutable_binary=source['immutable_binary']))
    lines = ['# PACT frozen Stage A: physical comparison complete', '',
        'Status: `PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE` / `PACT_EXTERNAL_BENCHMARK_COMPLETE` for the requested B0/B1/exact-B2/B3T/P0 Stage-A comparison.', '',
        f'All 19 preselected method records qualify on Nangate45 with the unchanged common backend, ORFS revision, two-core policy, seed 11 and original FAN workload. {sum(row["status"] == "QUALIFIED" for row in rows)} of 30 indexed architecture records have qualified physical measurements. Seven P0 selected candidates and their original balanced representatives remain frozen. No new search, parameter tuning, ATPG or P1 campaign was run.', '',
        '## Cause and repairs', '',
        '`Dft.cpp::RestitchChain` rewired the new head and internal SI edges, but overwrote the fixed SO endpoint annotation with the tail ITerm without reconnecting the actual endpoint load. KMeans restitching therefore lost the fixed endpoint before local search. Final reordering also left the ODB scan-list metadata stale. In s5378, the optimized 90/89-FF paths ended on n2510gat/n707gat while fixed SOs stayed on interior n2502gat/n2121gat nets.', '',
        'B3S preserves the fixed endpoint variant, reconnects that endpoint to the final tail Q/SO net, and refreshes the existing dbScanList from the same final cell sequence. It rejects implicit reuse of a functional output as a movable scan output and adds a dedicated-output regression preserving every functional Q output. KMeans, NN, directed 2-Opt, direction-preserving 3-Opt, objective and parameters are unchanged. The repaired s5378 internal order exactly matches the failed B3R order.', '',
        'The next independent blocker was `OpenSTA verilog/VerilogWriter.cc::writeAssigns`: renamed input ports lacked `assign internal_net = input_port`, producing disconnected exported Verilog despite connected ODB. The separately approved B3T repair emits that generic input alias; output aliases remain unchanged. A one-buffer witness fails before and passes after. This changes serialization only.', '',
        '| Repair | Class | Exact commit | Patch SHA-256 |',
        '|---|---|---|---|',
        f'| Compile receiver prerequisite | R0 | `{r.PARENT}` | `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960` |',
        f'| DFT endpoint/metadata (`src/dft/src/Dft.cpp`, scan_opt regression) | R1 | `{endpoint["repair_commit_sha"]}` | `{endpoint["patch_sha256"]}` |',
        f'| OpenSTA input alias (`verilog/VerilogWriter.cc`) | R1 | `{serializer["OpenSTA_repair_commit"]}` | `{serializer["OpenSTA_patch_sha256"]}` |',
        f'| OpenROAD B3T submodule binding | R1 | `{build["commit"]}` | `{serializer["patch_sha256"]}` |', '',
        f'B3T binary SHA-256: `{build["binary_sha256"]}`. B3S immutable binary SHA-256: `{prior_binary["sha256"]}`. OpenSTA parent: `{serializer["OpenSTA_parent"]}`. Direct OpenROAD parent: `{serializer["parent_revision"]}`. Source and command receipts bind the unchanged KMeans 100-iteration limit, 50 candidate neighbors, original capacity constraints and endpoint-excluding objective. The three adjacent native DFT regressions pass. Failed build/fixture attempts and earlier immutable binaries remain preserved. B3T reused the owned B3S build prefix; earlier original-path build receipts are retained alongside the immutable executable snapshots, rather than claiming that prefix still holds B3S.', '',
        'The physical launch also required an R0 runtime repair: use the existing PACT virtual environment (recorded NumPy 2.5.3 and SciPy 1.18.1) and provide the optional import-time Numba 0.67.0 / llvmlite 0.49.0 dependency in an isolated D-backed directory. The old virtual environment and every frozen flow source remain unchanged; no optimizer kernel is invoked. Failure traces, wheel hashes and the successful full route-adapter import are recorded under `stage_a_runtime`.', '',
        '## Native qualification', '',
        '| Design | FFs | Chains | Chain lengths | SI | Internal | Fixed SO | Metadata / ODB / Verilog |',
        '|---|---:|---:|---|---|---|---|---|']
    for design, item in native['designs'].items():
        proof = read(item['proof']['path'])
        lines.append(f'| {design} | {proof["FF_count"]} | 2 | '+ '/'.join(map(str,proof['chain_lengths']))+' | PASS | PASS | PASS | PASS |')
    lines += ['', 'Exact FF membership once, capacity, complete SI-to-SO traversal, no cycles/forks/orphans, and unchanged FF master/location/orientation/D/CK/functional Q/QN fanout and unrelated nets pass. The canonical order comes directly from the qualified native output.', '',
        '## Physical results', '',
        'Wire is the routed full scan-path connected-net length upper bound in µm. E is all-data capacitance-weighted transitions in millions of fF·transitions; H4/H8 are peak fF·transitions per spatial bin/cycle. P0 denotes the original balanced representative, with every other preselected P0 point retained in the CSV.', '',
        '| Design | Method | Scan wire upper bound (µm) | E (million) | H4 | H8 | DRC |',
        '|---|---|---:|---:|---:|---:|---:|']
    for design in r.DESIGNS:
        for method in ('B0','B1','B2','B3T','P0'):
            row = next(row for row in rows if row['design'] == design and row['method'] == method and row['representative'] == 'True')
            lines.append(f'| {design} | {method} | {float(row["routed_scan_path_cost_um"]):.2f} | {float(row["measured_E"])/1e6:.3f} | {float(row["measured_H4"]):.2f} | {float(row["measured_H8"]):.2f} | {row["DRC"]} |')
    lines += ['', 'Detailed-route total wire, global-route setup/hold timing, extracted ground-plus-pin capacitance, load/unload shift activity, hotspot bin/cycle, and secondary scan-data activity are in `stage_a/implemented_metrics.csv`; all exact pairwise deltas and nondominance are retained. Timing is the frozen global-route analysis, not detailed-route signoff. Exact scan-only routed attribution is unknown where Q nets share functional fanout. Congestion/overflow remain unknown when absent from the frozen metrics. Coupling is recorded separately and excluded from the primary activity proxies.', '',
        '## Upstream', '']
    for item in upstream:
        ci = ('Current CI/review status unavailable' if item.get('status_error') else
              '; '.join(x['name']+': '+str(x['conclusion'] or x['status']) for x in item['checks']) or 'No check runs reported')
        status = '; '.join(x['context']+': '+x['state'] for x in item['statuses'])
        if status:
            ci += '; '+status
        reviews = 'Unknown' if item.get('status_error') else (', '.join(x['state'] for x in item['reviews']) or 'No reviews reported')
        lines.append(f'- [{item["PR_URL"]}]({item["PR_URL"]}): {item["state"]}; merged={item["merged"]}; {reviews}; {ci}.')
    lines += ['', 'No separate issue was opened. Benchmark execution did not wait for reviews, CI or merge. The OpenSTA contribution cherry-picks the experimental one-file repair onto the recorded current upstream base; that separate upstream checkout was not rebuilt locally, as disclosed in the PR.', '',
        'No remaining implementation blocker prevents the requested Stage-A comparison. Scientific interpretation is limited to these three designs, the frozen workload and measured activity proxies.', '',
        'Receipts: `ROOT_CAUSE.md`, `verilog_input_alias/ROOT_CAUSE.md`, `method_manifest.json`, both repair manifests, `stage_a/selection_receipt.json`, `stage_a/implemented_metrics.csv`, `stage_a/pairwise_comparison.csv`, `stage_a/scientific_questions.json`, and `upstream/final_status.json`. Large ODB/VCD/DEF/SPEF data and exact command logs remain hash-bound at the recorded D: paths.']
    (r.CAMPAIGN / 'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')
    write(r.CAMPAIGN / 'completion.json', dict(status='PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE',
        scientific_status='PACT_EXTERNAL_BENCHMARK_COMPLETE', scope='Frozen requested Stage A; no P1 claim',
        selected_qualified=19, selected_P0=7, qualified_architecture_records=sum(row['status']=='QUALIFIED' for row in rows),
        report=binding(r.CAMPAIGN / 'FINAL_REPORT.md'), metrics=binding(stage.STAGE / 'implemented_metrics.csv'),
        comparison=binding(stage.STAGE / 'pairwise_comparison.csv'), native_qualification=binding(s.FOLDER / 'qualification.json'),
        timestamp_utc=datetime.now(timezone.utc).isoformat(), remaining_implementation_blocker=None))
    print('PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
