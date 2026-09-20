"""Deterministic IDs, resumable manifests, guards, and concise status files."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Iterable


ALLOWED_STATUSES = frozenset({
    "PLANNED", "RUNNING", "QUALIFIED", "INVALID", "TIMEOUT", "FAILED",
    "SKIPPED_EXISTING", "REUSED_VERIFIED",
})
COMPLETED_STATUSES = frozenset({
    "QUALIFIED", "INVALID", "TIMEOUT", "FAILED", "SKIPPED_EXISTING", "REUSED_VERIFIED",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_run_id(*parts: Any) -> str:
    return canonical_sha256(["PACT_PHASE0D", *parts])[:20]


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def check_disk_floor(path: Path, minimum_free_bytes: int) -> int:
    free = shutil.disk_usage(path).free
    if free < minimum_free_bytes:
        raise RuntimeError(f"DISK_FLOOR_REACHED: free={free}, required={minimum_free_bytes}")
    return free


def valid_cached_artifact(path: Path, expected_sha256: str) -> bool:
    return path.is_file() and file_sha256(path) == expected_sha256


@dataclass
class ManifestStore:
    path: Path
    campaign_id: str
    phase0d_starting_commit: str
    contract_sha256: str

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": "phase0d-manifest-1",
                "campaign_id": self.campaign_id,
                "phase0d_starting_commit": self.phase0d_starting_commit,
                "contract_sha256": self.contract_sha256,
                "created_utc": utc_now(),
                "updated_utc": utc_now(),
                "rows": [],
            }
        manifest = json.loads(self.path.read_text(encoding="utf-8"))
        expected = (self.campaign_id, self.phase0d_starting_commit, self.contract_sha256)
        actual = (manifest.get("campaign_id"), manifest.get("phase0d_starting_commit"), manifest.get("contract_sha256"))
        if actual != expected:
            raise ValueError(f"Manifest provenance mismatch: {actual!r} != {expected!r}")
        self._validate_rows(manifest.get("rows", []))
        return manifest

    @staticmethod
    def _validate_rows(rows: Iterable[dict[str, Any]]) -> None:
        run_ids: set[str] = set()
        for row in rows:
            if row.get("status") not in ALLOWED_STATUSES:
                raise ValueError(f"Invalid manifest status: {row.get('status')!r}")
            run_id = row.get("run_id")
            if not isinstance(run_id, str) or len(run_id) != 20 or run_id in run_ids:
                raise ValueError(f"Invalid or duplicate run_id: {run_id!r}")
            run_ids.add(run_id)

    def save(self, manifest: dict[str, Any]) -> None:
        self._validate_rows(manifest.get("rows", []))
        manifest["updated_utc"] = utc_now()
        atomic_write_json(self.path, manifest)

    def upsert(self, row: dict[str, Any]) -> dict[str, Any]:
        if row.get("status") not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid manifest status: {row.get('status')!r}")
        manifest = self.load()
        existing = next((item for item in manifest["rows"] if item["run_id"] == row["run_id"]), None)
        if existing is None:
            manifest["rows"].append(dict(row))
        else:
            existing.update(row)
        self.save(manifest)
        return manifest

    def first_unfinished(self) -> dict[str, Any] | None:
        manifest = self.load()
        return next((row for row in manifest["rows"] if row["status"] not in COMPLETED_STATUSES), None)


def write_status(json_path: Path, markdown_path: Path, status: dict[str, Any]) -> None:
    payload = dict(status)
    payload.setdefault("timestamp_utc", utc_now())
    fields = [
        ("Timestamp", "timestamp_utc"), ("Git commit", "git_commit"),
        ("Campaign ID", "campaign_id"), ("Current phase", "current_phase"),
        ("Total planned contexts", "total_planned_contexts"),
        ("Completed contexts", "completed_contexts"),
        ("Qualified contexts", "qualified_contexts"), ("Failed contexts", "failed_contexts"),
        ("Current design", "current_design"), ("Current seed", "current_seed"),
        ("Current K", "current_K"), ("Current optimizer", "current_optimizer"),
        ("Proxy evaluations completed", "proxy_evaluations_completed"),
        ("Routed evaluations completed", "routed_evaluations_completed"),
        ("Elapsed wall time (s)", "elapsed_wall_seconds"),
        ("Estimated remaining time (s)", "estimated_remaining_seconds"),
        ("Free disk bytes", "free_disk_bytes"), ("Latest error", "latest_error"),
        ("Next expected step", "next_expected_step"),
    ]
    lines = ["# PACT Phase-0D Status", ""]
    for label, key in fields:
        value = payload.get(key)
        lines.append(f"- {label}: `{value}`")
    lines.append("")
    atomic_write_json(json_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, markdown_path)
