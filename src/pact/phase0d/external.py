"""Bounded external-command execution and strict ORFS metric extraction."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any

from pact.phase0d.campaign import atomic_write_json


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def run_bounded(command: list[str], output_dir: Path, cwd: Path, timeout_seconds: int,
                required_outputs: list[Path], resume: bool = True) -> dict[str, Any]:
    """Run once with a hard timeout; retain every failed/superseded attempt."""
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "execution.json"
    if record_path.exists():
        previous = json.loads(record_path.read_text(encoding="utf-8"))
        valid = (
            previous.get("exit_code") == 0
            and not previous.get("timed_out")
            and previous.get("command") == command
            and previous.get("cwd") == str(cwd)
            and all(path.is_file() and digest(path) == previous.get("outputs", {}).get(str(path))
                    for path in required_outputs)
        )
        if resume and valid:
            return {**previous, "resumed_valid_result": True}
        archive = output_dir / f"attempt_{len(list(output_dir.glob('attempt_*'))) + 1:03d}"
        archive.mkdir()
        for name in ("execution.json", "stdout.log", "stderr.log"):
            source = output_dir / name
            if source.exists():
                source.rename(archive / name)
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    start = datetime.now(timezone.utc)
    tick = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    with (output_dir / "stdout.log").open("wb") as stdout, (output_dir / "stderr.log").open("wb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError) as error:
            timed_out = isinstance(error, subprocess.TimeoutExpired)
            stderr.write(f"\nLAUNCH_ERROR {error}\n".encode())
    record = {
        "command": command,
        "cwd": str(cwd),
        "start_utc": start.isoformat(),
        "end_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": time.monotonic() - tick,
        "timeout_s": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "outputs": {str(path): digest(path) for path in required_outputs if path.is_file()},
        "required_outputs_present": all(path.is_file() for path in required_outputs),
        "stdout_sha256": digest(output_dir / "stdout.log"),
        "stderr_sha256": digest(output_dir / "stderr.log"),
    }
    atomic_write_json(record_path, record)
    return record


def extract_structured_metrics(grt: dict[str, Any], drt: dict[str, Any]) -> dict[str, Any]:
    required_grt = {
        "setup_wns_ns": "globalroute__timing__setup__ws",
        "setup_tns_ns": "globalroute__timing__setup__tns",
        "hold_wns_ns": "globalroute__timing__hold__ws",
        "hold_tns_ns": "globalroute__timing__hold__tns",
        "setup_violated_endpoints": "globalroute__timing__drv__setup_violation_count",
        "hold_violated_endpoints": "globalroute__timing__drv__hold_violation_count",
        "max_slew_violations": "globalroute__timing__drv__max_slew",
        "max_cap_violations": "globalroute__timing__drv__max_cap",
        "max_fanout_violations": "globalroute__timing__drv__max_fanout",
        "global_route_wirelength_um": "globalroute__global_route__wirelength",
    }
    required_drt = {
        "total_detailed_route_wirelength_um": "detailedroute__route__wirelength",
        "detailed_route_drc_errors": "detailedroute__route__drc_errors",
        "detailed_route_vias": "detailedroute__route__vias",
    }
    missing = [key for key in required_grt.values() if key not in grt]
    missing.extend(key for key in required_drt.values() if key not in drt)
    if missing:
        raise ValueError(f"Required structured ORFS metrics absent: {missing}")
    result = {label: grt[key] for label, key in required_grt.items()}
    result.update({label: drt[key] for label, key in required_drt.items()})
    result.update({
        "timing_stage": "global_route",
        "global_route_overflow": next((grt[key] for key in (
            "globalroute__global_route__overflow", "globalroute__route__overflow") if key in grt), None),
        "congestion": next((grt[key] for key in (
            "globalroute__global_route__congestion", "globalroute__route__congestion") if key in grt), None),
        "layer_utilization": {key: value for key, value in grt.items() if "layer_utilization" in key},
        "pdnsim_classification": "NOT_RUN_NO_QUALIFIED_TEST_CURRENT_MODEL",
    })
    return result
