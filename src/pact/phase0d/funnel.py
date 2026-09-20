"""Frozen-input structural and proxy stages of the Phase-0D evaluation funnel."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Any

from pact.analysis.phase0c_activity import direct_sink_weights, parallel_activity_metrics
from pact.phase0d.campaign import atomic_write_json, file_sha256
from pact.phase0d.pareto import ObjectiveBounds, ObjectiveVector, freeze_bounds
from pact.phase0d.search import Evaluation, EvaluatedArchitecture
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.scan.phase0c import chain_statistics
from pact.scan.phase0d_operators import OperatorConstraints, structural_proof
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


def proxy_objectives(row: dict[str, Any]) -> ObjectiveVector:
    return (
        float(row["scan_geometry"]["total_scan_hpwl_um"]),
        float(row["activity"]["grids"]["8"]["H_eff"]),
        float(row["chain_statistics"]["parallel_shift_cycles"]),
    )


def _relative(root: Path, path: Path) -> str:
    try:
        value = path.relative_to(root)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


@dataclass
class FrozenProxyContext:
    root: Path
    design: str
    physical_seed: int
    K: int
    start_method: str
    start_architecture: ScanArchitecture
    start_proxy: dict[str, Any]
    frozen_def: Path
    patterns: list[dict[str, int]]
    weights: dict[str, int]
    portfolio_rows: list[dict[str, Any]]
    input_sha256: dict[str, str]
    constraints: OperatorConstraints

    @classmethod
    def load(cls, root: Path, design: str, physical_seed: int, K: int,
             start_method: str = "P", constraints: OperatorConstraints = OperatorConstraints()) -> "FrozenProxyContext":
        campaign = json.loads((root / "config/phase0c_campaign.json").read_text(encoding="utf-8"))
        if design not in campaign["designs"] or physical_seed not in campaign["physical_seeds"] or K not in campaign["K_values"]:
            raise ValueError("Context is outside the frozen Phase-0C population")
        context_dir = root / f"artifacts/derived/phase0c/{design}/s{physical_seed}/k{K}"
        start_arch_path = context_dir / f"{start_method}.architecture.json"
        start_proxy_path = context_dir / f"{start_method}.proxy.json"
        start_arch = ScanArchitecture.from_json(start_arch_path)
        start_proxy = json.loads(start_proxy_path.read_text(encoding="utf-8"))
        if start_proxy.get("architecture_sha256") != start_arch.sha256():
            raise ValueError("Frozen start architecture and proxy disagree")
        for relative, expected in start_proxy.get("input_sha256", {}).items():
            path = root / relative
            if not path.is_file() or file_sha256(path) != expected:
                raise ValueError(f"Frozen Phase-0C input hash mismatch: {relative}")

        placement = root / f"artifacts/raw/phase0b/placements/{design}/s{physical_seed}"
        placed_v, placed_def = placement / "placed.v", placement / "placed.def"
        fan = root / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat"
        identity = root / f"artifacts/derived/{design}/ff_identity_map.json"
        identity_records = json.loads(identity.read_text(encoding="utf-8"))["records"]
        patterns = map_ppi_patterns(parse_fan_pat(fan), identity_records)
        ff = {item.name: item for item in scan_ff_instances(placed_v)}
        if set(ff) != {cell.name for cell in start_arch.cells}:
            raise ValueError("Placed FF identity differs from the frozen architecture")
        weights = direct_sink_weights(placed_v, {name: item.q_net for name, item in ff.items()})
        portfolio_rows = []
        for proxy_path in sorted(context_dir.glob("*.proxy.json")):
            row = json.loads(proxy_path.read_text(encoding="utf-8"))
            if row.get("status") not in {"LOGICAL_AND_PROXY_QUALIFIED_PHYSICAL_PENDING", "QUALIFIED"}:
                raise ValueError(f"Unqualified frozen proxy row: {proxy_path}")
            portfolio_rows.append(row)
        if not portfolio_rows:
            raise ValueError("Frozen Phase-0C portfolio is empty")
        phase0d_inputs = [
            root / "config/phase0d_pilot_contract.json",
            root / "src/pact/phase0d/funnel.py",
            root / "src/pact/phase0d/search.py",
            root / "src/pact/phase0d/pareto.py",
            root / "src/pact/scan/phase0d_operators.py",
            placed_v, placed_def, fan, identity,
        ]
        input_hashes = dict(start_proxy.get("input_sha256", {}))
        input_hashes.update({_relative(root, path): file_sha256(path) for path in phase0d_inputs})
        return cls(root, design, physical_seed, K, start_method, start_arch, start_proxy,
                   placed_def, patterns, weights, portfolio_rows, input_hashes, constraints)

    @property
    def context_id(self) -> str:
        return f"{self.design}/s{self.physical_seed}/k{self.K}"

    def frozen_bounds(self) -> ObjectiveBounds:
        return freeze_bounds(proxy_objectives(row) for row in self.portfolio_rows)

    def start(self) -> EvaluatedArchitecture:
        return EvaluatedArchitecture(
            self.start_architecture,
            Evaluation(proxy_objectives(self.start_proxy), {
                "status": "REUSED_VERIFIED",
                "source": self.start_proxy["architecture_path"],
                "method": self.start_method,
            }),
        )

    def evaluate(self, architecture: ScanArchitecture, operator_record: dict[str, Any],
                 output_root: Path) -> Evaluation:
        candidate_dir = output_root / architecture.sha256()
        architecture_path = candidate_dir / "architecture.json"
        proof_path = candidate_dir / "structural_proof.json"
        proxy_path = candidate_dir / "proxy.json"
        if proxy_path.is_file() and architecture_path.is_file() and proof_path.is_file():
            saved = json.loads(proxy_path.read_text(encoding="utf-8"))
            if (saved.get("architecture_sha256") == architecture.sha256()
                    and saved.get("input_sha256") == self.input_sha256
                    and saved.get("status") == "QUALIFIED"):
                return Evaluation(proxy_objectives(saved), {
                    "status": "REUSED_VERIFIED",
                    "candidate_directory": _relative(self.root, candidate_dir),
                    "proxy_sha256": file_sha256(proxy_path),
                    "evaluation_wall_seconds": 0.0,
                    "operator": operator_record["type"],
                    "H_eff16": saved["activity"]["grids"]["16"]["H_eff"],
                    "H_eff32": saved["activity"]["grids"]["32"]["H_eff"],
                    "total_shift_toggles": saved["activity"]["total_shift_toggles"],
                    "peak_simultaneous_toggles": saved["activity"]["peak_simultaneous_toggles"],
                })

        started = time.perf_counter()
        proof_started = time.perf_counter()
        proof = structural_proof(self.start_architecture, architecture, self.patterns, self.constraints)
        proof_seconds = time.perf_counter() - proof_started
        activity_started = time.perf_counter()
        activity = parallel_activity_metrics(architecture, self.patterns, self.weights)
        activity_seconds = time.perf_counter() - activity_started
        geometry = phase0c_scan_geometry(architecture, self.frozen_def)
        stats = chain_statistics(architecture, len(self.patterns))
        wall_seconds = time.perf_counter() - started
        row = {
            "schema_version": "phase0d-proxy-qualification-1",
            "status": "QUALIFIED",
            "design": self.design,
            "physical_seed": self.physical_seed,
            "K": self.K,
            "architecture_sha256": architecture.sha256(),
            "architecture_path": _relative(self.root, architecture_path),
            "operator_record": operator_record,
            "structural_proof": proof,
            "chain_statistics": stats,
            "scan_geometry": geometry,
            "activity": activity,
            "input_sha256": self.input_sha256,
            "runtime": {
                "structural_proof_seconds": proof_seconds,
                "parallel_activity_seconds": activity_seconds,
                "total_proxy_wall_seconds": wall_seconds,
            },
            "physical": {
                "routed_evaluation_status": "NOT_SELECTED",
                "detailed_route_DRC_errors": None,
                "full_netlist_routed_wirelength_um": None,
                "via_count": None,
                "setup_wns_ns": None,
                "hold_wns_ns": None,
                "initial_global_route_utilization": None,
                "global_route_overflow": None,
            },
        }
        candidate_dir.mkdir(parents=True, exist_ok=True)
        architecture.to_json(architecture_path)
        atomic_write_json(proof_path, proof)
        atomic_write_json(proxy_path, row)
        return Evaluation(proxy_objectives(row), {
            "status": "EXECUTED_NEW",
            "candidate_directory": _relative(self.root, candidate_dir),
            "proxy_sha256": file_sha256(proxy_path),
            "evaluation_wall_seconds": wall_seconds,
            "operator": operator_record["type"],
            "H_eff16": activity["grids"]["16"]["H_eff"],
            "H_eff32": activity["grids"]["32"]["H_eff"],
            "total_shift_toggles": activity["total_shift_toggles"],
            "peak_simultaneous_toggles": activity["peak_simultaneous_toggles"],
        })


def historical_route_resources(root: Path) -> dict[str, float | int | None]:
    route_times = []
    for execution_path in sorted((root / "artifacts/raw/phase0c/physical").glob("**/route/execution.json")):
        record = json.loads(execution_path.read_text(encoding="utf-8"))
        if record.get("exit_code") == 0 and not record.get("timed_out"):
            route_times.append(float(record["elapsed_s"]))
    archives = list((root / "artifacts/raw/phase0c/physical").glob("**/5_2_route.odb.gz"))
    sizes = [path.stat().st_size for path in archives]
    return {
        "existing_qualified_routes_reused": 375,
        "historical_successful_route_samples": len(route_times),
        "historical_route_seconds_median": statistics.median(route_times) if route_times else None,
        "historical_route_seconds_min": min(route_times) if route_times else None,
        "historical_route_seconds_max": max(route_times) if route_times else None,
        "historical_odb_archives": len(sizes),
        "historical_odb_archive_bytes_median": statistics.median(sizes) if sizes else None,
    }


def projection(proxy_seconds_per_evaluation: float, historical: dict[str, float | int | None],
               contexts: int = 60, optimizers: int = 4, proxy_budget: int = 128,
               route_budget: int = 8) -> dict[str, float | int | str | None]:
    proxy_evaluations = contexts * optimizers * proxy_budget
    new_routes = contexts * optimizers * route_budget
    route_median = historical["historical_route_seconds_median"]
    storage_median = historical["historical_odb_archive_bytes_median"]
    route_seconds = float(route_median) * new_routes if route_median is not None else None
    total_seconds = proxy_seconds_per_evaluation * proxy_evaluations + (route_seconds or 0.0)
    policy = "INTERACTIVE" if total_seconds <= 600 else "MEDIUM" if total_seconds <= 2700 else "LONG"
    if total_seconds > 4 * 3600:
        policy = "VERY_LONG_REDUCE_AND_STAGE"
    return {
        "contexts": contexts,
        "optimizers": optimizers,
        "proxy_budget_each": proxy_budget,
        "route_budget_each": route_budget,
        "projected_proxy_evaluations": proxy_evaluations,
        "projected_new_routes": new_routes,
        "projected_proxy_seconds": proxy_seconds_per_evaluation * proxy_evaluations,
        "projected_route_seconds_from_historical_median": route_seconds,
        "projected_total_seconds_serial": total_seconds,
        "projected_new_odb_archive_bytes": float(storage_median) * new_routes if storage_median is not None else None,
        "runtime_policy": policy,
    }
