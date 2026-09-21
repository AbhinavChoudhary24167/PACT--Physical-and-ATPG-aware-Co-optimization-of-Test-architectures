#!/usr/bin/env python3
"""Bound and archive every external Phase-0B command, including failures."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(command: list[str], out: Path, cwd: Path, timeout_s: int,
        required: list[Path], resume: bool = True) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / "execution.json"
    if record_path.exists():
        previous = json.loads(record_path.read_text(encoding="utf-8"))
        valid = (previous.get("exit_code") == 0 and not previous.get("timed_out")
                 and previous.get("command") == command
                 and previous.get("cwd") == str(cwd)
                 and all(path.is_file() and digest(path) == previous.get("outputs", {}).get(str(path))
                         for path in required))
        if resume and valid:
            return {**previous, "resumed_valid_result": True}
        if not valid:
            # Keep every failed or invalid attempt rather than overwriting it.
            archive = out / f"attempt_{len(list(out.glob('attempt_*'))) + 1:03d}"
            archive.mkdir()
            for name in ("execution.json", "stdout.log", "stderr.log"):
                source = out / name
                if source.exists():
                    source.rename(archive / name)
    start = datetime.now(timezone.utc)
    tick = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                exit_code = process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            timed_out = True
        except OSError as exc:
            stderr.write(f"\nLAUNCH_ERROR {exc}\n".encode())
    record = {
        "command": command, "cwd": str(cwd), "start_utc": start.isoformat(),
        "end_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": time.monotonic() - tick, "timeout_s": timeout_s,
        "timed_out": timed_out, "exit_code": exit_code,
        "outputs": {str(path): digest(path) for path in required if path.is_file()},
        "required_outputs_present": all(path.is_file() for path in required),
        "stdout_sha256": digest(out / "stdout.log"),
        "stderr_sha256": digest(out / "stderr.log"),
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--required", type=Path, action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.timeout < 1:
        parser.error("a command and positive timeout are required")
    result = run(command, args.out.resolve(), args.cwd.resolve(), args.timeout,
                 [path.resolve() for path in args.required])
    print(json.dumps({key: result[key] for key in ("exit_code", "timed_out", "required_outputs_present")}, sort_keys=True))
    if result["exit_code"] != 0 or result["timed_out"] or not result["required_outputs_present"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
