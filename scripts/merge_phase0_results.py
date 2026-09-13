#!/usr/bin/env python3
"""Combine already validated per-design records without changing measurements."""
from __future__ import annotations

from pathlib import Path

from pact.analysis.aggregate import load_results


def main() -> None:
    """Validate both evidence-linked inputs and write their unchanged JSONL lines."""
    root = Path(__file__).resolve().parents[1]
    schema = root / "config/schemas/result.schema.json"
    paths = [root / f"artifacts/derived/phase0/{name}/results.jsonl" for name in ("s5378", "s9234")]
    for path in paths:
        load_results(path, schema)
    output = root / "artifacts/derived/phase0/results.jsonl"
    output.write_text("".join(path.read_text(encoding="utf-8") for path in paths), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
