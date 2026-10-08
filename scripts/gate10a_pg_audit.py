#!/usr/bin/env python3
"""Qualify PG-only in-memory connection normalization without physical results."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from gate10a_run import ROOT, OUT, frozen, verify, binding, sha


def section(text, name):
    found = re.search(r"(?m)^" + name + r"\s.*?\nEND " + name + r"\s*$", text, re.S)
    if not found:
        raise ValueError("Missing DEF invariant section " + name)
    return found[0]


def run():
    commit = "b9869834a3479a57f256c83fa74a4617faab4af2"
    selection, selected = frozen("reports/gate10a/selected_architectures.json", commit)
    output = OUT / "control/pg_connectivity_normalization.json"
    if output.exists():
        raise ValueError("Preserve original PG audit receipt")
    result = {"schema": "pact_gate10a_pg_connectivity_normalization_v1", "status": "STARTED",
              "started_utc": datetime.now(timezone.utc).isoformat(), "preregistered_commit": commit,
              "selection": selected, "implementation_reason": "Late inserted input/output/hold/clock buffers have unconnected PG ITerms in frozen routed ODB. Apply VDD/VSS exact-name global PG connection rules only in memory to satisfy preregistered complete powered-cell coverage.",
              "pre_normalization_smoke_failure": "reports/gate10a/runs/b14_opt/B3T/smoke_nominal_attempt3/receipt.json",
              "physical_comparison_outcomes_observed": False, "original_ODBs_modified_or_written": False,
              "commands": ["add_global_connection -net VDD -inst_pattern {.*} -pin_pattern {^VDD$} -power",
                           "add_global_connection -net VSS -inst_pattern {.*} -pin_pattern {^VSS$} -ground", "global_connect"],
              "source": [binding(Path(__file__)), binding(ROOT / "scripts/tcl/gate10a_pg_connection_audit.tcl")],
              "records": []}
    try:
        for row in selection["architectures"]:
            folder = OUT / "control/pg_audit" / row["design"] / row["architecture"]
            folder.mkdir(parents=True, exist_ok=False)
            odb = verify(row["routed_archive"])
            env = dict(os.environ, GATE10A_ODB=str(odb), GATE10A_OUTPUT=str(folder))
            argv = ["/usr/bin/openroad", "-no_init", "-exit", "scripts/tcl/gate10a_pg_connection_audit.tcl"]
            proc = subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (folder / "audit.log").write_bytes(proc.stdout)
            if proc.returncode or b"GATE10A_PG_AUDIT_COMPLETE" not in proc.stdout:
                raise ValueError("PG inventory process incomplete")
            texts = [(folder / (side + ".def")).read_text() for side in ("before", "after")]
            invariants = {}
            for name in ("COMPONENTS", "NETS", "PINS", "VIAS"):
                present = all(re.search(r"(?m)^" + name + r"\s", text) for text in texts)
                if not present and name == "VIAS":
                    continue
                sections = [section(text, name) for text in texts]
                if sections[0] != sections[1]:
                    raise ValueError("Non-PG DEF content changed: " + name)
                invariants[name] = hashlib.sha256(sections[0].encode()).hexdigest()
            pg_shapes = ["\n".join(sorted((folder / (side + "_pg_shapes.tsv")).read_text().splitlines()))
                         for side in ("before", "after")]
            if pg_shapes[0] != pg_shapes[1]:
                raise ValueError("PG shape/via geometry changed")
            terms = []
            for side in ("before", "after"):
                with (folder / (side + "_pg_terms.tsv")).open() as stream:
                    terms.append({(r["instance"], r["pin"]): r for r in csv.DictReader(stream, delimiter="\t")})
            if terms[0].keys() != terms[1].keys():
                raise ValueError("PG terminal population changed")
            changed = []
            for key, before in terms[0].items():
                after = terms[1][key]
                if before["master"] != after["master"]:
                    raise ValueError("PG cell master changed")
                if before["net"] != after["net"]:
                    if before["net"] or after["net"] != key[1] or key[1] not in ("VDD", "VSS"):
                        raise ValueError("Unexpected PG connection substitution")
                    changed.append({"instance": key[0], "pin": key[1], "old_net": before["net"], "new_net": after["net"]})
            missing_after = [r for r in terms[1].values() if not r["net"]]
            if missing_after:
                raise ValueError("PG terminals remain unconnected")
            record = {"design": row["design"], "architecture": row["architecture"], "status": "PASS",
                      "original_ODB": row["routed_archive"], "changed_PG_terminal_assignments": len(changed),
                      "changed_instance_count": len({r["instance"] for r in changed}),
                      "missing_after": len(missing_after), "invariant_section_sha256": invariants,
                      "pg_shapes_sha256": hashlib.sha256(pg_shapes[0].encode()).hexdigest(),
                      "exact_changes": changed, "command": argv,
                      "outputs": [binding(p) for p in sorted(folder.iterdir())]}
            result["records"].append(record)
            print("PG_QUALIFIED", row["design"], row["architecture"], len(changed), flush=True)
        result["status"] = "PASS"
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "receipt": str(output.relative_to(ROOT)), "error": result.get("error")}))
    return result["status"] == "PASS"


if __name__ == "__main__":
    raise SystemExit(0 if run() else 2)
