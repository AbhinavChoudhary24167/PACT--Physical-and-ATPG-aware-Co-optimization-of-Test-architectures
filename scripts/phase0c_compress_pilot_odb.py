#!/usr/bin/env python3
"""Losslessly archive pilot routed ODBs as deterministic gzip on the small workspace drive."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def sha_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    converted = 0
    for metrics_path in sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json")):
        record = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not record.get("variant", "").startswith("phase0c_s"):
            continue
        raw = metrics_path.parent / "5_2_route.odb"
        if not raw.exists():
            continue
        compressed = metrics_path.parent / "5_2_route.odb.gz"
        temporary = compressed.with_suffix(".gz.tmp")
        with raw.open("rb") as incoming, temporary.open("wb") as outgoing:
            with gzip.GzipFile(filename="", mode="wb", fileobj=outgoing, mtime=0) as zipped:
                shutil.copyfileobj(incoming, zipped)
        with raw.open("rb") as incoming:
            original_sha = sha_stream(incoming)
        with gzip.open(temporary, "rb") as restored:
            restored_sha = sha_stream(restored)
        if original_sha != restored_sha or original_sha != record["routed_odb_sha256"]:
            temporary.unlink()
            raise ValueError(f"Lossless ODB verification failed: {raw}")
        if compressed.exists():
            with gzip.open(compressed, "rb") as prior:
                if sha_stream(prior) != original_sha:
                    raise ValueError(f"Existing compressed ODB differs: {compressed}")
            temporary.unlink()
        else:
            temporary.replace(compressed)
        backup = metrics_path.parent / "route_metrics_pre_compression.json"
        if not backup.exists():
            shutil.copy2(metrics_path, backup)
        record["routed_odb_archive"] = str(compressed.relative_to(ROOT)).replace("\\", "/")
        record["routed_odb_gzip_sha256"] = hashlib.sha256(compressed.read_bytes()).hexdigest()
        metrics_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raw.unlink()
        converted += 1
    print(json.dumps({"losslessly_compressed_pilot_odb_count": converted}))


if __name__ == "__main__":
    main()
