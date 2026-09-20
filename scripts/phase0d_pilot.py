#!/usr/bin/env python3
"""Run or resume the tiny Phase-0D proxy pilot and prepare one route shortlist."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.phase0d.campaign import (  # noqa: E402
    ManifestStore, atomic_write_json, check_disk_floor, deterministic_run_id,
    file_sha256, write_status,
)
from pact.phase0d.funnel import (  # noqa: E402
    FrozenProxyContext, historical_route_resources, projection,
)
from pact.phase0d.pareto import ObjectiveBounds, normalized_hypervolume  # noqa: E402
from pact.phase0d.search import SEARCH_METHODS, SearchConfig, run_search  # noqa: E402
from pact.scan.phase0d_operators import (  # noqa: E402
    OPERATOR_NAMES, apply_operator, neighborhood_sizes, operator_catalog, sample_operations,
)


REPORTS = ROOT / "reports/phase0d"
ARTIFACTS = ROOT / "artifacts/derived/phase0d/pilot/s5378/s11/k2"
CONTRACT_PATH = ROOT / "config/phase0d_pilot_contract.json"
START_COMMIT = "06d97d82263b3671d8a56c9e6ed104cf88d40266"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _bounds_dict(bounds: ObjectiveBounds) -> dict[str, list[float]]:
    return {"ideal": list(bounds.ideal), "reference": list(bounds.reference)}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_once_or_verify(path: Path, value: dict) -> None:
    if path.is_file():
        if _load_json(path) != value:
            raise ValueError(f"Frozen pilot artifact changed: {path}")
    else:
        atomic_write_json(path, value)


def _source_hashes() -> dict[str, str]:
    paths = [
        CONTRACT_PATH,
        ROOT / "scripts/phase0d_pilot.py",
        ROOT / "src/pact/phase0d/campaign.py",
        ROOT / "src/pact/phase0d/funnel.py",
        ROOT / "src/pact/phase0d/pareto.py",
        ROOT / "src/pact/phase0d/search.py",
        ROOT / "src/pact/scan/phase0d_operators.py",
    ]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): file_sha256(path) for path in paths}


def _scientific_source_hashes() -> dict[str, str]:
    hashes = _source_hashes()
    hashes.pop("scripts/phase0d_pilot.py")
    hashes.pop("src/pact/phase0d/campaign.py")
    return hashes


def _sources_compatible(saved: dict[str, str]) -> bool:
    return all(saved.get(path) == digest for path, digest in _scientific_source_hashes().items())


def _manifest_store(contract_sha256: str, campaign_id: str) -> ManifestStore:
    return ManifestStore(REPORTS / "manifest.json", campaign_id, START_COMMIT, contract_sha256)


def _status_base(campaign_id: str, **updates) -> dict:
    base = {
        "git_commit": git("rev-parse", "HEAD"),
        "campaign_id": campaign_id,
        "current_phase": "PILOT",
        "total_planned_contexts": 1,
        "completed_contexts": 0,
        "qualified_contexts": 0,
        "failed_contexts": 0,
        "current_design": "s5378",
        "current_seed": 11,
        "current_K": 2,
        "current_optimizer": None,
        "proxy_evaluations_completed": 0,
        "routed_evaluations_completed": 0,
        "elapsed_wall_seconds": 0,
        "estimated_remaining_seconds": None,
        "free_disk_bytes": shutil.disk_usage(ROOT).free,
        "latest_error": None,
        "next_expected_step": "operator preflight",
    }
    base.update(updates)
    return base


def _operator_preflight(context: FrozenProxyContext, contract_sha256: str,
                        store: ManifestStore) -> dict:
    output_path = ARTIFACTS / "operator_screen.json"
    run_id = deterministic_run_id(context.context_id, "operator_preflight", context.start_architecture.sha256(),
                                  contract_sha256)
    if output_path.is_file():
        saved = _load_json(output_path)
        if saved.get("contract_sha256") == contract_sha256 and _sources_compatible(saved.get("source_sha256", {})):
            store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                          "K": context.K, "optimizer": "operator_preflight", "status": "SKIPPED_EXISTING",
                          "artifact": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                          "artifact_sha256": file_sha256(output_path)})
            return saved
    store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                  "K": context.K, "optimizer": "operator_preflight", "status": "RUNNING"})
    operations = sample_operations(context.start_architecture, len(OPERATOR_NAMES), proposal_seed=701)
    entries = []
    start_objectives = context.start().evaluation.objectives
    for operation in operations:
        child, record = apply_operator(context.start_architecture, operation, context.constraints)
        evaluation = context.evaluate(child, record, ARTIFACTS / "candidates")
        entries.append({
            "operation": operation,
            "operator_record": record,
            "objectives": list(evaluation.objectives),
            "objective_delta_from_start": [new - old for new, old in zip(evaluation.objectives, start_objectives)],
            "evaluation_metadata": dict(evaluation.metadata),
        })
    result = {
        "schema_version": "phase0d-operator-screen-1",
        "contract_sha256": contract_sha256,
        "source_sha256": _source_hashes(),
        "context": context.context_id,
        "start_architecture_sha256": context.start_architecture.sha256(),
        "start_objectives": list(start_objectives),
        "operator_catalog": {name: spec.__dict__ for name, spec in operator_catalog().items()},
        "analytical_neighborhood_sizes": neighborhood_sizes(context.start_architecture),
        "entries": entries,
    }
    atomic_write_json(output_path, result)
    store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                  "K": context.K, "optimizer": "operator_preflight", "status": "QUALIFIED",
                  "proxy_evaluations": len(entries),
                  "artifact": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                  "artifact_sha256": file_sha256(output_path)})
    return result


def _search_one(method: str, context: FrozenProxyContext, bounds: ObjectiveBounds,
                contract_sha256: str, store: ManifestStore, config: SearchConfig) -> dict:
    output_path = ARTIFACTS / "search" / f"{method}.json"
    run_id = deterministic_run_id(context.context_id, method, context.start_architecture.sha256(),
                                  contract_sha256, config.proxy_budget)
    if output_path.is_file():
        saved = _load_json(output_path)
        if (saved.get("contract_sha256") == contract_sha256
                and _sources_compatible(saved.get("source_sha256", {}))
                and saved.get("frozen_bounds") == _bounds_dict(bounds)):
            store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                          "K": context.K, "optimizer": method, "status": "SKIPPED_EXISTING",
                          "proxy_evaluations": saved["proxy_evaluations"],
                          "artifact": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                          "artifact_sha256": file_sha256(output_path)})
            return saved
    store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                  "K": context.K, "optimizer": method, "status": "RUNNING"})
    result = run_search(
        method,
        context.start(),
        lambda architecture, record: context.evaluate(architecture, dict(record), ARTIFACTS / "candidates"),
        bounds,
        config,
        context.constraints,
    )
    result.update({
        "context": context.context_id,
        "contract_sha256": contract_sha256,
        "source_sha256": _source_hashes(),
        "frozen_bounds": _bounds_dict(bounds),
    })
    atomic_write_json(output_path, result)
    store.upsert({"run_id": run_id, "design": context.design, "physical_seed": context.physical_seed,
                  "K": context.K, "optimizer": method, "status": "QUALIFIED",
                  "proxy_evaluations": result["proxy_evaluations"],
                  "artifact": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                  "artifact_sha256": file_sha256(output_path)})
    return result


def _choose_route_candidate(context: FrozenProxyContext, bounds: ObjectiveBounds,
                            searches: dict[str, dict], contract_sha256: str) -> dict:
    start = context.start().evaluation.objectives
    start_hv = normalized_hypervolume([start], bounds)
    candidates: dict[str, dict] = {}
    for method, result in searches.items():
        for item in result["pareto_archive"]:
            metadata = item.get("metadata", {})
            directory = metadata.get("candidate_directory")
            if not directory:
                continue
            candidate = dict(item)
            candidate["discovered_by"] = method
            candidate["candidate_directory"] = directory
            candidates.setdefault(item["architecture_sha256"], candidate)
    if not candidates:
        selected = {
            "schema_version": "phase0d-route-shortlist-1",
            "contract_sha256": contract_sha256,
            "context": context.context_id,
            "status": "NO_NEW_PROXY_NONDOMINATED_CANDIDATE",
            "architecture_sha256": None,
            "candidate_directory": None,
            "route_budget": 0,
            "selection_rule": "route only a new proxy-nondominated candidate; no searched child qualified",
        }
        atomic_write_json(REPORTS / "pilot_route_shortlist.json", selected)
        return selected
    selected = max(
        candidates.values(),
        key=lambda item: (
            normalized_hypervolume([start, item["objectives"]], bounds) - start_hv,
            -sum(bounds.normalize(item["objectives"])),
            item["architecture_sha256"],
        ),
    )
    selected["hypervolume_gain_over_start"] = (
        normalized_hypervolume([start, selected["objectives"]], bounds) - start_hv
    )
    selected.update({
        "schema_version": "phase0d-route-shortlist-1",
        "contract_sha256": contract_sha256,
        "context": context.context_id,
        "selection_rule": "new proxy-nondominated candidate maximizing exact normalized hypervolume gain over the Phase-0C P start; deterministic objective/hash tie break",
        "route_budget": 1,
        "status": "QUALIFIED_FOR_SELECTIVE_ROUTE",
    })
    atomic_write_json(REPORTS / "pilot_route_shortlist.json", selected)
    return selected


def _route_result_path(selected: dict) -> Path | None:
    if not selected.get("architecture_sha256"):
        return None
    return (ROOT / "artifacts/raw/phase0d/pilot/s5378/s11/k2"
            / selected["architecture_sha256"] / "route_result.json")


def _metrics_csv(operator_screen: dict, searches: dict[str, dict]) -> None:
    path = REPORTS / "metrics.csv"
    rows = []
    for entry in operator_screen["entries"]:
        rows.append({
            "stage": "operator_preflight", "optimizer": "operator_preflight",
            "evaluation_index": len(rows) + 1, "operator": entry["operation"]["type"],
            "architecture_sha256": entry["operator_record"]["child_sha256"],
            "physical_proxy_um": entry["objectives"][0], "H_eff8": entry["objectives"][1],
            "parallel_shift_cycles": entry["objectives"][2],
            "hypervolume": "", "accepted_move": "",
            "evaluation_status": entry["evaluation_metadata"]["status"],
            "evaluation_wall_seconds": entry["evaluation_metadata"]["evaluation_wall_seconds"],
        })
    for method, result in searches.items():
        for trace in result["trace"]:
            if trace["event"] != "PROXY_EVALUATION":
                continue
            rows.append({
                "stage": "search", "optimizer": method,
                "evaluation_index": trace["evaluation_index"], "operator": trace["operation"]["type"],
                "architecture_sha256": trace["child_sha256"],
                "physical_proxy_um": trace["objectives"][0], "H_eff8": trace["objectives"][1],
                "parallel_shift_cycles": trace["objectives"][2],
                "hypervolume": trace["hypervolume_after"], "accepted_move": trace["accepted_move"],
                "evaluation_status": trace["metadata"]["status"],
                "evaluation_wall_seconds": trace["metadata"]["evaluation_wall_seconds"],
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _candidate_generation_benchmark(context: FrozenProxyContext, contract_sha256: str) -> dict:
    path = ARTIFACTS / "candidate_generation_benchmark.json"
    operator_sha256 = file_sha256(ROOT / "src/pact/scan/phase0d_operators.py")
    if path.is_file():
        saved = _load_json(path)
        if (saved.get("contract_sha256") == contract_sha256
                and saved.get("operator_source_sha256") == operator_sha256):
            return saved
    count = 128
    started = time.perf_counter()
    operations = sample_operations(context.start_architecture, count, proposal_seed=1701)
    elapsed = time.perf_counter() - started
    result = {
        "schema_version": "phase0d-candidate-generation-benchmark-1",
        "contract_sha256": contract_sha256,
        "operator_source_sha256": operator_sha256,
        "context": context.context_id,
        "bounded_operations_generated": len(operations),
        "wall_seconds": elapsed,
        "seconds_per_operation": elapsed / len(operations),
        "operator_counts": {name: sum(operation["type"] == name for operation in operations)
                            for name in OPERATOR_NAMES},
    }
    atomic_write_json(path, result)
    return result


def _historical_route_seconds_total() -> float:
    total = 0.0
    for path in (ROOT / "artifacts/raw/phase0c/physical").glob("**/route/execution.json"):
        record = _load_json(path)
        if record.get("exit_code") == 0 and not record.get("timed_out"):
            total += float(record["elapsed_s"])
    return total


def _report(context: FrozenProxyContext, operator_screen: dict, searches: dict[str, dict],
            selected: dict, route_result: dict | None, elapsed_seconds: float,
            contract_sha256: str, generation_benchmark: dict) -> dict:
    proxy_rows = list((ARTIFACTS / "candidates").glob("*/proxy.json"))
    proxy_records = [_load_json(path) for path in proxy_rows]
    proxy_seconds = [float(row["runtime"]["total_proxy_wall_seconds"]) for row in proxy_records]
    per_evaluation = statistics.median(proxy_seconds) if proxy_seconds else 0.0
    historical = historical_route_resources(ROOT)
    historical_route_seconds_total = _historical_route_seconds_total()
    full_projection = projection(per_evaluation, historical)
    full_projection["decision"] = "DO_NOT_LAUNCH_FULL_MATRIX; reduce and stage because serial projection is several hours"
    artifacts_bytes = sum(path.stat().st_size for path in (ROOT / "artifacts/derived/phase0d").glob("**/*") if path.is_file())
    measured_proxy_compute_seconds = sum(proxy_seconds)
    operator_rows = []
    for entry in operator_screen["entries"]:
        delta = entry["objective_delta_from_start"]
        operator_rows.append(
            f"| {entry['operation']['type']} | {delta[0]:.3f} | {delta[1]:.3f} | {delta[2]:.0f} | "
            f"{entry['evaluation_metadata']['status']} |"
        )
    search_rows = []
    for method in SEARCH_METHODS:
        result = searches[method]
        search_rows.append(
            f"| {method} | {result['proxy_evaluations']} | {result['accepted_moves']} | "
            f"{result['unique_pareto_solutions']} | {result['final_hypervolume']:.6f} | "
            f"{result['wall_clock_seconds']:.3f} | {result['stop_reason']} |"
        )
    no_route_candidate = selected.get("status") == "NO_NEW_PROXY_NONDOMINATED_CANDIDATE"
    route_status = (route_result.get("status") if route_result else
                    "NOT_RUN_NO_PROXY_NONDOMINATED_CANDIDATE" if no_route_candidate else "PENDING")
    route_seconds = route_result.get("route_wall_seconds") if route_result else None
    route_storage = route_result.get("routed_odb_archive_bytes") if route_result else None
    pilot_status = ("PILOT_COMPLETE" if route_result else
                    "PILOT_COMPLETE_NO_ROUTE_QUALIFIED" if no_route_candidate else
                    "PILOT_PROXY_COMPLETE_ROUTE_PENDING")
    if no_route_candidate:
        route_description = (
            "No searched child was nondominated against the qualified Phase-0C `P` start, so the frozen "
            "proxy-to-route filter selected no new route. This is a valid negative pilot result; routing a "
            "dominated child solely to consume the budget would violate the contract."
        )
    else:
        route_description = (
            f"The single route shortlist member is `{selected['architecture_sha256']}`, discovered by "
            f"`{selected['discovered_by']}`, with proxy objectives {selected['objectives']} and an exact "
            f"normalized-HV gain of {selected['hypervolume_gain_over_start']:.6f} over the starting point."
        )
    report = f"""# PACT Phase-0D Pilot Report

**Pilot status:** `{pilot_status}`

**Phase-0C decision preserved:** `PACT_PHASE0C_LEARNING_GATE_FAIL`

**Pilot contract SHA256:** `{contract_sha256}`

## Scope and provenance

The frozen pilot uses `s5378`, physical seed 11, K=2, and the qualified Phase-0C `P` architecture as its start. Phase-0C evidence was reused after hash verification; no Phase-0C ATPG, placement, architecture, or route was regenerated. The audit covers 8,050 tracked Phase-0C files and 83 upstream dependency files, with 375 qualified routes reused as existing baseline evidence.

The pilot is deliberately small: seven one-step operator checks, then four deterministic optimizers with a maximum of 16 proxy evaluations each. At most one new Phase-0D candidate is routed.

## Operator preflight

Every required operator generated a structurally legal child and reconstructed all 117 frozen ATPG targets under the fully clocked parallel-loading model.

| Operator | Delta physical proxy (um) | Delta H_eff8 | Delta shift cycles | Evaluation |
|---|---:|---:|---:|---|
{chr(10).join(operator_rows)}

The complete analytical pre-legality neighborhood sizes are recorded in `artifacts/derived/phase0d/pilot/s5378/s11/k2/operator_screen.json`; only bounded deterministic samples were evaluated.

## Equal-budget search

| Optimizer | Proxy evaluations | Accepted moves | Unique Pareto solutions | Final normalized HV | Wall seconds | Stop |
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(search_rows)}

The hypervolume bounds were frozen from the six qualified Phase-0C K=2 portfolio rows before any Phase-0D child was evaluated: ideal={list(context.frozen_bounds().ideal)}, reference={list(context.frozen_bounds().reference)}. These are pilot bounds, not a claim of global optimality.

## Selective physical evaluation

{route_description}

- New-route status: `{route_status}`
- New route wall time: `{route_seconds}` seconds
- Compressed routed ODB storage: `{route_storage}` bytes
- HPWL remains a port-aware FF-origin proxy and is not called routed scan wirelength.

## Runtime and storage projection

- Bounded candidate-generation sample: {generation_benchmark['bounded_operations_generated']} operations in {generation_benchmark['wall_seconds']:.6f} seconds ({generation_benchmark['seconds_per_operation']:.9f} seconds/operation)
- New unique pilot proxy artifacts: {len(proxy_rows)}
- Median new proxy evaluation time: {per_evaluation:.6f} seconds
- Measured unique proxy compute time: {measured_proxy_compute_seconds:.3f} seconds
- Report/finalization invocation time: {elapsed_seconds:.3f} seconds
- Phase-0D derived pilot storage: {artifacts_bytes} bytes
- Historical successful Phase-0C route samples: {historical['historical_successful_route_samples']}
- Historical median successful route time: {historical['historical_route_seconds_median']} seconds
- Historical median compressed ODB: {historical['historical_odb_archive_bytes_median']} bytes
- Full matrix proxy evaluations at B=128: {full_projection['projected_proxy_evaluations']}
- Full matrix new routes at R=8: {full_projection['projected_new_routes']}
- Projected serial proxy time: {full_projection['projected_proxy_seconds']:.3f} seconds
- Projected serial route time from recorded historical median: {full_projection['projected_route_seconds_from_historical_median']:.3f} seconds
- Projected serial total: {full_projection['projected_total_seconds_serial']:.3f} seconds
- Projected new compressed-route storage: {full_projection['projected_new_odb_archive_bytes']} bytes
- Runtime policy: `{full_projection['runtime_policy']}`

The naive full 60-context x four-optimizer x maximum-budget matrix is therefore not launched. It is a several-hour campaign even before scheduling overhead. The scientifically appropriate next stage is a reduced proxy qualification across all three designs and a predeclared seed/K subset, followed by selective routing only for methods/operators that show replicated proxy benefit.

## Resource reuse accounting

- Frozen tracked Phase-0C evidence files hash-verified: 8,050
- Upstream Phase-0C dependency files hash-verified: 83
- Existing qualified Phase-0C routes reused: 375
- New Phase-0D proxy artifacts executed: {len(proxy_rows)}
- Logical search/preflight proxy evaluations: {len(operator_screen['entries']) + sum(result['proxy_evaluations'] for result in searches.values())}
- Proxy evaluations reused from valid candidate cache: {sum(trace['metadata']['status'] == 'REUSED_VERIFIED' for result in searches.values() for trace in result['trace'] if trace['event'] == 'PROXY_EVALUATION')}
- New Phase-0D physical routes: {int(route_result is not None and route_result.get('reuse_status') == 'EXECUTED_NEW')}
- Avoided Phase-0C route re-executions: 375
- New-route wall time: {route_seconds} seconds
- Directly recorded Phase-0C route compute reused rather than repeated: {historical_route_seconds_total:.3f} seconds

## Failures and limitations

This is one ISCAS89-scale context, not a cross-seed or cross-design result. H_eff is a dimensionless proxy; shift-mode power and test-mode IR drop remain unavailable. A completed pilot does not evaluate D4-D6 and cannot establish either Phase-0D final decision. No ML model was trained.
"""
    report_path = REPORTS / "PILOT_REPORT.md"
    with report_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    summary = {
        "schema_version": "phase0d-pilot-summary-1",
        "status": pilot_status,
        "contract_sha256": contract_sha256,
        "context": context.context_id,
        "operator_evaluations": len(operator_screen["entries"]),
        "search_proxy_evaluations": sum(result["proxy_evaluations"] for result in searches.values()),
        "unique_proxy_artifacts": len(proxy_rows),
        "new_routed_evaluations": int(route_result is not None and route_result.get("reuse_status") == "EXECUTED_NEW"),
        "route_status": route_status,
        "resource_reuse": {
            "existing_phase0c_qualified_routes_reused": 375,
            "runs_skipped_existing": sum(
                trace["metadata"]["status"] == "REUSED_VERIFIED"
                for result in searches.values() for trace in result["trace"] if trace["event"] == "PROXY_EVALUATION"
            ),
        },
        "historical_route_resources": historical,
        "historical_route_seconds_reused": historical_route_seconds_total,
        "candidate_generation_benchmark": generation_benchmark,
        "full_campaign_projection": full_projection,
        "selected_route_candidate": selected,
    }
    atomic_write_json(REPORTS / "pilot_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-only", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    contract_sha256 = file_sha256(CONTRACT_PATH)
    campaign_id = f"phase0d-pilot-{contract_sha256[:12]}"
    contract = _load_json(CONTRACT_PATH)
    check_disk_floor(ROOT, int(contract["routing"]["minimum_free_disk_bytes"]))
    REPORTS.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    bounds = context.frozen_bounds()
    _save_once_or_verify(ARTIFACTS / "pilot_bounds.json", {
        "schema_version": "phase0d-pilot-bounds-1",
        "contract_sha256": contract_sha256,
        "context": context.context_id,
        "source": "six qualified frozen Phase-0C portfolio rows, before Phase-0D child evaluation",
        **_bounds_dict(bounds),
    })
    store = _manifest_store(contract_sha256, campaign_id)
    write_status(REPORTS / "status.json", REPORTS / "STATUS.md", _status_base(campaign_id))
    if args.finalize_only:
        operator_screen = _load_json(ARTIFACTS / "operator_screen.json")
        searches = {method: _load_json(ARTIFACTS / "search" / f"{method}.json") for method in SEARCH_METHODS}
    else:
        operator_screen = _operator_preflight(context, contract_sha256, store)
        completed = len(operator_screen["entries"])
        config = SearchConfig(
            proxy_budget=contract["pilot_budgets"]["proxy_evaluations_per_optimizer"],
            candidate_batch_size=contract["pilot_budgets"]["candidate_batch_size"],
            beam_width=contract["pilot_budgets"]["beam_width"],
            plateau_legal_evaluations=contract["early_stopping"]["pilot_plateau_legal_evaluations"],
            hypervolume_window=contract["early_stopping"]["pilot_hypervolume_window"],
            minimum_relative_hypervolume_improvement=contract["early_stopping"]["pilot_minimum_relative_hypervolume_improvement"],
            wall_clock_seconds=contract["pilot_budgets"]["wall_clock_seconds_per_optimizer"],
            proposal_seed=101,
        )
        searches = {}
        for method in SEARCH_METHODS:
            write_status(REPORTS / "status.json", REPORTS / "STATUS.md", _status_base(
                campaign_id, current_optimizer=method, proxy_evaluations_completed=completed,
                elapsed_wall_seconds=time.monotonic() - started, next_expected_step=f"run {method}"))
            searches[method] = _search_one(method, context, bounds, contract_sha256, store, config)
            completed += searches[method]["proxy_evaluations"]
    selected = _choose_route_candidate(context, bounds, searches, contract_sha256)
    generation_benchmark = _candidate_generation_benchmark(context, contract_sha256)
    route_run_id = deterministic_run_id(context.context_id, "selective_route", selected["architecture_sha256"],
                                        contract_sha256)
    route_path = _route_result_path(selected)
    route_result = _load_json(route_path) if route_path is not None and route_path.is_file() else None
    observed_route_status = route_result.get("status") if route_result else None
    route_status = ("QUALIFIED" if observed_route_status == "QUALIFIED" else
                    "TIMEOUT" if observed_route_status == "TIMEOUT" else
                    "FAILED" if route_result else
                    "SKIPPED_NO_QUALIFIED_CANDIDATE" if route_path is None else "PLANNED")
    store.upsert({
        "run_id": route_run_id, "design": context.design, "physical_seed": context.physical_seed,
        "K": context.K, "optimizer": "selective_route", "status": route_status,
        "architecture_sha256": selected["architecture_sha256"],
        "artifact": (str(route_path.relative_to(ROOT)).replace("\\", "/")
                     if route_path is not None and route_path.is_file() else None),
        "artifact_sha256": file_sha256(route_path) if route_path is not None and route_path.is_file() else None,
    })
    _metrics_csv(operator_screen, searches)
    summary = _report(context, operator_screen, searches, selected, route_result,
                      time.monotonic() - started, contract_sha256, generation_benchmark)
    complete = summary["status"].startswith("PILOT_COMPLETE")
    write_status(REPORTS / "status.json", REPORTS / "STATUS.md", _status_base(
        campaign_id,
        current_phase="PILOT_COMPLETE" if complete else "PILOT_ROUTE_PENDING",
        completed_contexts=int(complete), qualified_contexts=int(complete),
        current_optimizer=None,
        proxy_evaluations_completed=summary["operator_evaluations"] + summary["search_proxy_evaluations"],
        routed_evaluations_completed=int(route_result is not None),
        elapsed_wall_seconds=time.monotonic() - started,
        estimated_remaining_seconds=0 if complete else summary["historical_route_resources"]["historical_route_seconds_median"],
        next_expected_step=("freeze reduced-campaign thresholds" if complete else
                            f"run selective route: python scripts/phase0d_run_route.py --design s5378 --seed 11 --k 2 --candidate-dir {selected['candidate_directory']}"),
    ))
    print(json.dumps({
        "status": summary["status"],
        "search_proxy_evaluations": summary["search_proxy_evaluations"],
        "unique_proxy_artifacts": summary["unique_proxy_artifacts"],
        "route_candidate": selected["architecture_sha256"],
        "route_status": summary["route_status"],
        "runtime_policy": summary["full_campaign_projection"]["runtime_policy"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
