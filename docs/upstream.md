# Upstream fixes and provenance

Frozen local qualification is distinct from an upstream merge or a contemporary tool build.

| Tool / failure | Retained repair scope | Reference |
|---|---|---|
| OpenROAD compile receiver | B3R `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`, exact source/build/patch receipts | [Receiver PR](https://github.com/mwsoli/OpenROAD/pull/1) |
| OpenROAD fixed SO/metadata | B3S endpoint repair `03f7b75bae946796aa854c6a596bed6412e8bd63`, B3T binding `5c3751171685d507939ee7064a67feec786e5219` | [Topology PR](https://github.com/mwsoli/OpenROAD/pull/2) |
| OpenSTA renamed input alias | Direction-sensitive input-to-net assignment, repair `d21c1ae6f97cc2f28d7f2ba5892c24293b8d2259` | [OpenSTA PR 420](https://github.com/The-OpenROAD-Project/OpenSTA/pull/420) |
| OpenROAD alias reader | Exact parent BTerm/module-net ownership through child feedthroughs | [OpenROAD PR 11624](https://github.com/The-OpenROAD-Project/OpenROAD/pull/11624) |
| FAN compound-net construction | Generic connectivity repair and original failed/sanitized/optimized qualification | [Issue 5](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/5) |
| FAN scan fault/state reporting | Complete collapsed-class identities/weights and state export; unchanged generation algorithm/statistics | [Issue 6](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/6) |

OpenSTA PR 420 was open when inspected on 8 October 2026; its integration dependency differs from isolated OpenSTA tests. Other links are recorded provenance; no merge status is asserted.

`patches/upstream/` protects exported local diffs/source records. Qualified FAN receipts remain under `results/pact_gate09_open_source_20261005/dependency_repairs/FAN_ATPG/`; benchmark manifests and end-to-end records retain exact experiment bindings. Build-image exports are maintenance records, not substitute qualification receipts.

Preserve source revisions/submodules, local commits/diffs, non-generated untracked files, reproduction testcases and diagnostic evidence before discarding a tool build. Unreconciled unique work remains retained/quarantined. Cleanup posts no upstream messages.
