# Git-history cleanup recommendation

**STRONGLY_RECOMMENDED**, after required physical inputs have been exported to a durable hash-verified research archive. No public/main history rewrite, garbage collection, remote push or force-push was performed.

## Evidence

Before cleanup .git occupied 1,399,485,073 logical bytes. Unique historical blobs total 2,006,773,618 uncompressed bytes; results/artifacts/reports account for over 99%. These are dominated by generated physical output and repeated experimental data/source copies. The largest blob is results/phase2c_repair_multiseed/initial_worktree.patch, 52,976,858 uncompressed bytes. Large repeated final/fill ODBs and metric/CSV collections follow. [Top historical objects](historical_blobs.tsv) and [category totals](history_metrics.json) identify exact paths and contribution. Packed deltas, compression and duplicate loose/pack storage prevent treating per-blob disk bytes as additive pack savings.

Before cleanup commits, all local refs contain 28,534,631 text additions and 627,420 deletions under git log --all --no-renames --numstat. results contributes 21,023,137 additions, artifacts 5,628,393 and reports 1,833,843. This local churn is distinct from both current source LOC and GitHub code-frequency; the supplied roughly 22-million-line remote statistic was not independently queried. Ordinary cleanup commits add deletions but retain old additions/blobs, so no remote-statistic correction is claimed.

## Proposed operation, separately approved

1. Freeze collaborators' pushes. Save all remote refs and a full mirror/bundle outside the working checkout; verify the backup by restoring into a separate repository. Record tags, branches, Git LFS pointers if present, releases and any extra fork-only refs.
2. Export exact required physical ODB/SDC/count inputs, with SHA256 and provenance, including inputs only available externally. Exact reproduction currently depends partly on pre-cleanup revision f2569d498cd5f26a88c4954ec163498eb3cf7d91. Do not remove the only recoverable copy of required data. A dependency clone is insufficient.
3. Build and review an explicit path list from file_classification.tsv entries marked E under artifacts/results/reports and the historical-object inventory. Include old generated renamed paths from every remote ref. Exclude every retained core/input/metric/patch path and scientific source history. Do not filter whole results/ or artifacts/ prefixes: they contain retained evidence. Retired source and historical docs can remain in source history without affecting the dominant storage problem.
4. Run the following on the backed-up disposable mirror, first with --dry-run, then without it only after reviewing its ref/commit maps:

```sh
git filter-repo --paths-from-file disposable-history-paths.txt --invert-paths --dry-run
# Review the dry run and backups before the separately approved rewrite.
git filter-repo --paths-from-file disposable-history-paths.txt --invert-paths
```

The path list is an explicit reviewed input, not a generated wildcard recipe to run blindly. Each entry removes that filename through all history; check whether any retained historical input occupied the same filename. A size-based purge is unsafe for original scientific inputs. Re-audit object size, retained hashes, refs, clean-checkout build/tests and portable replay before any publication.

5. Publish the rewritten refs only with explicit owner/collaborator authorization. It requires coordinated force updates to affected branches/tags and may require temporarily changing branch protections. Never force-push automatically. GitHub may retain PR/fork/cached objects and statistics until server-side processing; filter-repo does not guarantee immediate remote storage/code-frequency correction.

Commit hashes, tags pointing to changed history, links and signatures change. Existing clones/forks must re-clone or carefully migrate topic work; merging an old branch can reintroduce removed objects. Keep the full backup and an old-to-new revision map. Current working-tree cleanup is already useful independently of this operation.
