# Historical archive index

Bulk evidence lives outside Git. [MANIFEST.csv](MANIFEST.csv) records source location, original/compressed bytes, SHA256, count, dates and retention/reproduction value. [Verification receipts](verification.json) describe full-stream decompression and member checks; complete per-file manifests accompany the archives.

Accept an archive only after every file's SHA256/length, symlink target and member count agree and the decompressor completes integrity verification. Failed/interrupted compression leaves originals intact. Quarantine/removal has a separate ledger.

Restore a complete campaign with its original relative layout into the chosen experiment root and verify compressed/extracted hashes. Immutable raw-path receipts stay provenance. No public release URL is invented.

Keep active source/configuration, compact evidence, frozen inputs and unique repairs directly. Archive closed campaigns including negative/failed outcomes. Revisions/build procedures replace regenerable dependency builds only after all local modifications/testcases are protected. Unknown material stays retained.
