"""Read-only Gate 10A validation and saved relevant repository test evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/gate10a"
PARENT = "53ebab37fd76970d7c5e676b0caec13c7c16296e"


def bind(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def run_tests(label=""):
    files = sorted(ROOT.glob("tests/test_gate10a*.py"))
    files += sorted(ROOT.glob("tests/test_gate09*.py"))
    files += [ROOT / "tests/unit/test_experiment_receipts.py"]
    command = [sys.executable, "-m", "pytest", "-q", *[p.relative_to(ROOT).as_posix() for p in files]]
    started = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    suffix = "_" + label if label else ""
    path = OUT / ("control/repository_tests" + suffix + ".log")
    with path.open("xb") as stream:
        stream.write(result.stdout)
    write_new(OUT / ("control/repository_tests" + suffix + ".json"), {
        "schema": "pact_gate10a_repository_test_validation_v1", "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).isoformat(), "command": command,
        "exit_code": result.returncode, "wall_seconds": time.monotonic() - before,
        "test_sources": [bind(p) for p in files], "output": bind(path),
        "status": "PASS" if result.returncode == 0 else "FAIL",
    })
    print(result.stdout.decode(errors="replace"))
    return result.returncode


def integrity():
    failures = []
    prereg = json.loads((OUT / "control/preregistration_commit.json").read_text())
    checks = []
    for expected in prereg["files"]:
        # Original binding is Windows absolute; the basename is uniquely frozen.
        path = OUT / Path(expected["path"].replace("\\", "/")).name
        observed = bind(path)
        ok = observed["sha256"] == expected["sha256"] and observed["bytes"] == expected["bytes"]
        checks.append({"expected": expected, "observed": observed, "pass": ok})
        if not ok:
            failures.append("preregistration_bytes:" + path.name)
    changed = subprocess.check_output(["git", "diff", "--name-only", PARENT, "--"], cwd=ROOT, text=True).splitlines()
    allowed = ("reports/gate10a/", "scripts/gate10a_", "scripts/tcl/gate10a_",
               "src/pact/gate10a_", "tests/test_gate10a_", "publication/")
    for name in changed:
        if name not in (".gitattributes", ".gitignore", "README.md", "docs/research_status.md") and not name.startswith(allowed):
            failures.append("unexpected_changed_path:" + name)
    validation = {"schema": "pact_gate10a_preserved_parent_validation_v1",
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "parent": PARENT, "preregistration_commit": prereg["commit"],
                  "preregistration_checks": checks, "changed_paths": changed,
                  "failures": failures, "status": "PASS" if not failures else "FAIL",
                  "Gate09_tracked_file_changes": [p for p in changed if "gate09" in p.lower()]}
    write_new(OUT / "control/final_integrity.json", validation)
    print(json.dumps({"status": validation["status"], "failures": failures}))
    return 0 if not failures else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("tests", "integrity"))
    parser.add_argument("--label", default="", choices=("", "linux", "final"))
    args = parser.parse_args()
    raise SystemExit(run_tests(args.label) if args.action == "tests" else integrity())
