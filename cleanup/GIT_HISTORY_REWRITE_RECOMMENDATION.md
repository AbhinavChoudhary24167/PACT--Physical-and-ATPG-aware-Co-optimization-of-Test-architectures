# Git history rewrite recommendation

No public history rewrite or force push was performed. Canonical `.git` measured
1,094,276,470 bytes before cleanup and 1,094,521,254
bytes in the post-removal snapshot. Reachable unique historical blobs sum to
2,153,399,570 uncompressed bytes; this is not an
estimate of compressed pack savings.

The current tracked tree contains 4,041 files / 259,287,902
Git blob bytes. Its largest retained inputs are bound to scientific receipts.
The previous publication cleanup had already removed bulk current raw output;
this campaign preserves remaining qualified evidence instead of breaking hashes.

A separate deliberate rewrite could remove historical accidental raw ORFS,
measurement/build dumps and exported whole-worktree patches. The largest single
blob is 52,976,858 bytes (`results/phase2c_repair_multiseed/initial_worktree.patch`). Savings cannot be promised
from summed blob lengths because pack deltas and shared scientific paths matter.

Proposed procedure: make a fresh disposable `git clone --mirror`, preserve a
verified bundle plus all branch/tag refs, use `git filter-repo --analyze`, and
review an exact `--paths-from-file` removal list. Only then run
`git filter-repo --invert-paths --paths-from-file approved-historical-paths.txt`
on the disposable mirror. Compare fresh packed clone sizes and revalidate all
receipt links before seeking separate authorization to publish rewritten refs.
Do not use a size threshold: it could erase essential frozen inputs.

Risks include changed commit IDs, broken issue/receipt links, invalid signatures,
open PR conflicts and clone migration. GitHub caches/forks can retain old objects.
The unchanged public-history approach remains the campaign decision.

| Blob bytes | Path | Object ID |
|---:|---|---|
| 52,976,858 | `results/phase2c_repair_multiseed/initial_worktree.patch` | `2f94e58270052d7dda2521072b4547139879da99` |
| 10,182,820 | `results/pact_v2/comparison.csv` | `5a4d57ce3c8b60ee45b87b2d57abf694202cb08f` |
| 8,456,994 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_3_fillcell.odb` | `354b596fc3b69194f2d0ec0d0d4065ac86a0654e` |
| 8,448,583 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_3_fillcell.odb` | `51702a7ad744b2416cd190aaa8863ed424f60ba2` |
| 8,294,847 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_3_fillcell.odb` | `fae3caecb7385026f0cdd3407cd8c34a5dd495fd` |
| 8,291,839 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_3_fillcell.odb` | `26cdd9ed7304f9a18774ae2ae5c218e2aabc2f6f` |
| 8,291,740 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_3_fillcell.odb` | `f5a4fe95d52c088529368be051359c89cd9bfd69` |
| 8,289,923 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_3_fillcell.odb` | `bb25ce3802bcaafdf1b00c694f7ea1c6f2e5d015` |
| 8,262,908 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_3_fillcell.odb` | `adad0ea2deef4946d5e2d58619a877e60eb416b2` |
| 8,256,112 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_3_fillcell.odb` | `4be3109d0d46bed849d5418ffc420f68b4606bf2` |
| 8,253,879 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_3_fillcell.odb` | `73e27d16da18ad924786fb5f29e125fc8565d961` |
| 8,252,016 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_3_fillcell.odb` | `ba026e3c418c980914a9e1995efa90d8cdc06b0c` |
| 7,714,997 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_8b6295eabcab/5_3_fillcell.odb` | `5e7924286b71689bbe613c17daa3ff7046018def` |
| 7,710,633 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_3_fillcell.odb` | `9090d72b11647728890d35812377685e23ebc1f0` |
| 7,614,586 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_34c4efab4658/5_3_fillcell.odb` | `8b3d2c161f90ddb652bdc03210eefe466d413d6e` |
| 7,611,575 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_f5334df8b242/5_3_fillcell.odb` | `8d333b954f8f10cd5f864b974d455377c43dcee8` |
| 7,600,861 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_0fd3dde8ed21/5_3_fillcell.odb` | `7999ed993806ff33e7e7ac5ba5fdf670410d59dc` |
| 7,600,509 | `results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_6dc9a5e67277/5_3_fillcell.odb` | `a91b55be6214b256c44744376c60b60877fd2aca` |
| 6,917,635 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_ca5d4a289098/5_2_route.odb` | `a8f1953030724a2e98ca1e1d6a5eb886f74965e2` |
| 6,914,681 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_2_route.odb` | `d50d24ccf0eb92e46d484c4aec519630bdeb549c` |
| 6,914,001 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_942cc66b689d/5_2_route.odb` | `bc153f7ff670ce223224cbb9fdbb0f619764f5c5` |
| 6,900,602 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_2_route.odb` | `878baebc4f6c794823d151855c7d9d6bc0cb9aea` |
| 6,748,883 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_2_route.odb` | `cac20146a49579637b27980a4edaf330a1551a3b` |
| 6,747,066 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_2_route.odb` | `f6fe7d8824c870cea9c49acd911dc7c1dfaf2047` |
| 6,746,685 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_2_route.odb` | `7b2acb06cb45302d55903d41d5f38d28771a980d` |
| 6,743,677 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_2_route.odb` | `4959b2b7fb927b0c0822fb9b18a8bc2c9af51224` |
| 6,714,386 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_2_route.odb` | `9d0301eb113b8219695b69a81f36e09f30228aa8` |
| 6,713,436 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_2_route.odb` | `afae5e0af52810ec1bf3813b1fe0f1a5405a70df` |
| 6,711,023 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_2_route.odb` | `fcb82c547f3b9d4fcbb31aa5a7f757af9e962d80` |
| 6,703,854 | `results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_2_route.odb` | `c2b4fc6f091ddbac0af1d8a83aaa2110bef0a3c0` |
