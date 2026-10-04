# Pre Cleanup inventory

Logical file bytes; symbolic links are excluded. The original walker followed one Windows junction, as explained in junction_policy.md. Text LOC counts LF-separated records (including a final unterminated line), excluding binary files. It includes generated text and is distinct from source/test LOC. The Git index supplies tracked paths.

| Measurement | Value |
|---|---|
| tracked_files | 15509 |
| tracked_bytes | 2297638437 |
| tracked_text_lines | 27885967 |
| source_test_lines | 44950 |
| checkout_bytes | 13249306671 |
| git_bytes | 1399485073 |
| total_bytes | 14648791744 |

## Directory storage

| Directory | Files | Bytes |
|---|---|---|
| results | 6186 | 6236744078 |
| external | 11328 | 2898956067 |
| reports | 1449 | 2637733558 |
| artifacts | 12646 | 1060811164 |
| .optimizer-deps | 1642 | 211299881 |
| .venv | 6251 | 194493827 |
| scripts | 390 | 3738285 |
| src | 211 | 2708306 |
| tests | 205 | 2099404 |
| .optimizer-cache | 30 | 457845 |
| docs | 17 | 89729 |
| .pytest_cache | 5 | 41171 |
| config | 14 | 25056 |
| PACT_PHASE2A_SHIFT_ACTIVITY_VALIDATION.md | 1 | 22424 |
| PACT_OPTIMIZER_V2_SCALABLE_SEARCH_REPORT.md | 1 | 16380 |
| solution_status.md | 1 | 11307 |
| PACT_OPTIMIZER_V2_2_PARALLEL_TILED_REPORT.md | 1 | 10756 |
| PACT_OPTIMIZER_V2_1_SHARED_FRONTIER_REPORT.md | 1 | 10655 |
| README.md | 1 | 10204 |
| PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION.md | 1 | 9124 |
| experiments | 10 | 5827 |
| .gitignore | 1 | 3893 |
| benchmarks | 4 | 2564 |
| current_solution.md | 1 | 2523 |
| LICENSE | 1 | 1074 |
| .gitattributes | 1 | 762 |
| pyproject.toml | 1 | 663 |
| Makefile | 1 | 134 |
| requirements.txt | 1 | 10 |

## Largest tracked files

| Path | Bytes | Text lines |
|---|---|---|
| results/phase2c_repair_multiseed/initial_worktree.patch | 53799318 | 822460 |
| results/pact_v2/comparison.csv | 10182820 | 50735 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_3_fillcell.odb | 8456994 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_route.odb | 8456994 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_3_fillcell.odb | 8448583 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_route.odb | 8448583 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_3_fillcell.odb | 8294847 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_route.odb | 8294847 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_3_fillcell.odb | 8291839 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_route.odb | 8291839 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_3_fillcell.odb | 8291740 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_route.odb | 8291740 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_3_fillcell.odb | 8289923 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_route.odb | 8289923 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_3_fillcell.odb | 8262908 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_route.odb | 8262908 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_3_fillcell.odb | 8256112 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_route.odb | 8256112 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_3_fillcell.odb | 8253879 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_route.odb | 8253879 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_3_fillcell.odb | 8252016 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_route.odb | 8252016 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_8b6295eabcab/5_3_fillcell.odb | 7714997 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_8b6295eabcab/5_route.odb | 7714997 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_3_fillcell.odb | 7710633 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_route.odb | 7710633 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_34c4efab4658/5_3_fillcell.odb | 7614586 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_34c4efab4658/5_route.odb | 7614586 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_f5334df8b242/5_3_fillcell.odb | 7611575 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_f5334df8b242/5_route.odb | 7611575 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_0fd3dde8ed21/5_3_fillcell.odb | 7600861 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_0fd3dde8ed21/5_route.odb | 7600861 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_6dc9a5e67277/5_3_fillcell.odb | 7600509 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_6dc9a5e67277/5_route.odb | 7600509 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_ca5d4a289098/5_2_route.odb | 6917635 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_2_route.odb | 6914681 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_942cc66b689d/5_2_route.odb | 6914001 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_2_route.odb | 6900602 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_2_route.odb | 6748883 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_2_route.odb | 6747066 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_2_route.odb | 6746685 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_2_route.odb | 6743677 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_2_route.odb | 6714386 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_2_route.odb | 6713436 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_2_route.odb | 6711023 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_2_route.odb | 6703854 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_8b6295eabcab/5_2_route.odb | 6336008 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_2_route.odb | 6331644 | 0 |
| results/phase2c_repair_multiseed/physical_results.json | 6276858 | 176343 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_34c4efab4658/5_2_route.odb | 6235597 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_f5334df8b242/5_2_route.odb | 6232586 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_0fd3dde8ed21/5_2_route.odb | 6221872 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_6dc9a5e67277/5_2_route.odb | 6221156 | 0 |
| results/pact_candidate_stateful/s15850/selected_geometry/f47e6837c4dacd553187a3ee88d5e8aff729a45b9375e10a8eeac2817177a93e.json | 5979222 | 315971 |
| results/pact_candidate_stateful/s15850/selected_geometry/5d90e5faf9dcfb7f820a641638cc06c83c19ac634534c5aa75c4cedda6f5a38e.json | 5979212 | 315971 |
| results/pact_candidate_stateful/s15850/baseline_geometry.json | 5979142 | 315971 |
| results/phase2c_repair_multiseed/raw/s15850/s13/A/extracted.spef | 5905098 | 223944 |
| results/phase2c_repair_multiseed/raw/s15850/s17/activity_extreme/extracted.spef | 5900853 | 223699 |
| results/phase2c_repair_multiseed/raw/s15850/s17/A/extracted.spef | 5890584 | 223535 |
| results/phase2c_repair_multiseed/raw/s15850/s13/activity_extreme/extracted.spef | 5880391 | 223192 |
| results/phase2c_repair_multiseed/raw/s15850/s13/balanced/extracted.spef | 5491888 | 211685 |
| results/phase2c_repair_multiseed/raw/s15850/s13/J50/extracted.spef | 5490740 | 211717 |
| results/phase2c_repair_multiseed/raw/s15850/s17/J50/extracted.spef | 5484655 | 211533 |
| results/phase2c_repair_multiseed/raw/s15850/s17/balanced/extracted.spef | 5482537 | 211459 |
| results/phase2c_repair_multiseed/raw/s15850/s13/P/extracted.spef | 5419337 | 209596 |
| results/phase2c_repair_multiseed/raw/s15850/s17/P/extracted.spef | 5416906 | 209468 |
| results/phase2c_repair_multiseed/raw/s15850/s17/T/extracted.spef | 5411948 | 209268 |
| results/phase2c_repair_multiseed/raw/s15850/s13/T/extracted.spef | 5392106 | 208653 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_0ec8661a1ff0/5_1_grt.odb | 5078898 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_207a0abc5f0b/5_1_grt.odb | 5072917 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_fe8da173bf88/5_1_grt.odb | 5002533 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_cfceed3bf166/5_1_grt.odb | 5001561 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ffae4066bf72/5_1_grt.odb | 4994662 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_ad0eb1d73411/5_1_grt.odb | 4993474 | 0 |
| results/phase2d_independent_gp/raw/s15850/s29/A/extracted.spef | 4985490 | 195805 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_16738bfbd10f/5_1_grt.odb | 4984155 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s17_9f827a3c0231/5_1_grt.odb | 4983399 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_1156aed4c738/5_1_grt.odb | 4978066 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s15850/phase2c_s13_239ff0f69b2e/5_1_grt.odb | 4977985 | 0 |
| results/phase2d_independent_gp/raw/s15850/s29/activity_extreme/extracted.spef | 4976518 | 195463 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_8b6295eabcab/5_1_grt.odb | 4739579 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_1_grt.odb | 4737185 | 0 |
| results/phase2d_independent_gp/raw/s15850/s29/J50/extracted.spef | 4721270 | 187884 |
| results/phase2d_independent_gp/raw/s15850/s29/balanced/extracted.spef | 4714790 | 187722 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_34c4efab4658/5_1_grt.odb | 4694201 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_f5334df8b242/5_1_grt.odb | 4693850 | 0 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_6dc9a5e67277/5_1_grt.odb | 4687865 | 0 |
| results/phase2d_independent_gp/raw/s15850/s29/T/extracted.spef | 4686848 | 186948 |
| results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_0fd3dde8ed21/5_1_grt.odb | 4685336 | 0 |
| results/phase2d_independent_gp/raw/s15850/s29/P/extracted.spef | 4677817 | 186632 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_9b9c8fda34e1/5_3_fillcell.odb | 4456326 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_9b9c8fda34e1/5_route.odb | 4456326 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_81e0299ed446/5_3_fillcell.odb | 4451714 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_81e0299ed446/5_route.odb | 4451714 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_4209638f5720/5_3_fillcell.odb | 4445945 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_4209638f5720/5_route.odb | 4445945 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_e0e52cb6e797/5_3_fillcell.odb | 4444883 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_e0e52cb6e797/5_route.odb | 4444883 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_787524e4aed6/5_3_fillcell.odb | 4444564 | 0 |
| results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s17_787524e4aed6/5_route.odb | 4444564 | 0 |

## Largest checkout files (including ignored dependencies)

| Path | Bytes |
|---|---|
| external/OpenROAD-flow-scripts/.git/objects/pack/pack-5235005c14bfe212134a871c8e6311f4e4ed7488.pack | 500470702 |
| external/OpenROAD/.git/objects/pack/pack-84718d8307ce38b2008a0a4218c8de91c1028375.pack | 325095201 |
| reports/physical_effect/s15850/P/activity.vcd | 283367204 |
| results/pact_v2/measurement/s15850/e14689c97ca5/activity.vcd | 283114340 |
| results/pact_candidate_stateful/measurement/s15850/5d90e5faf9dc/activity.vcd | 282936580 |
| results/pact_candidate_stateful/measurement/s15850/f47e6837c4da/activity.vcd | 282900054 |
| reports/physical_effect/s15850/PACT/activity.vcd | 281304985 |
| results/pact_v2/measurement/s15850/f3e118a35e7b/activity.vcd | 281129934 |
| results/pact_candidate_sensitive/measurement/s15850/630da6943398/activity.vcd | 281088651 |
| results/pact_candidate_sensitive/measurement/s15850/a3dd757a7e17/activity.vcd | 280915712 |
| results/pact_v2/measurement/s15850/1c4fe83a6b04/activity.vcd | 280530814 |
| reports/physical_effect/s15850/J50/activity.vcd | 256517374 |
| .optimizer-deps/llvmlite/binding/libllvmlite.so | 178881880 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_128x256_8/sky130_sram_1rw1r_128x256_8.lef | 102897488 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hs/lib/sky130_fd_sc_hs__tt_025C_1v80.lib | 72103677 |
| external/OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/gds/sg13g2_io.gds | 71399424 |
| external/OpenROAD/src/gpl/test/large02.defok | 71282730 |
| external/OpenROAD/src/gpl/test/large02.def | 64632121 |
| reports/physical_effect/s9234/T/activity.vcd | 64281053 |
| results/pact_v2/measurement/s9234/53bb5b018758/activity.vcd | 63892991 |
| reports/physical_effect/s9234/PACT/activity.vcd | 63604661 |
| results/pact_v2/measurement/s9234/797aff0b91f6/activity.vcd | 62768885 |
| results/pact_candidate_sensitive/measurement/s9234/4d6ff90b2adc/activity.vcd | 62605277 |
| results/pact_candidate_sensitive/measurement/s9234/1359e456272b/activity.vcd | 62598617 |
| results/pact_v2/measurement/s9234/f4bca5652bda/activity.vcd | 61902201 |
| reports/physical_effect/s9234/J50/activity.vcd | 59981111 |
| results/phase2c_repair_multiseed/initial_worktree.patch | 53799318 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_64x256_8/sky130_sram_1rw1r_64x256_8.lef | 52463418 |
| reports/physical_effect/s15850/J50/simulation.vvp | 51786630 |
| results/pact_candidate_sensitive/measurement/s15850/630da6943398/simulation.vvp | 51786270 |
| results/pact_v2/measurement/s15850/f3e118a35e7b/simulation.vvp | 51786219 |
| results/pact_v2/measurement/s15850/1c4fe83a6b04/simulation.vvp | 51786219 |
| reports/physical_effect/s15850/PACT/simulation.vvp | 51786183 |
| results/pact_candidate_sensitive/measurement/s15850/a3dd757a7e17/simulation.vvp | 51785819 |
| results/pact_candidate_stateful/measurement/s15850/f47e6837c4da/simulation.vvp | 51785816 |
| results/pact_candidate_stateful/measurement/s15850/5d90e5faf9dc/simulation.vvp | 51785816 |
| results/pact_v2/measurement/s15850/e14689c97ca5/simulation.vvp | 51785768 |
| reports/physical_effect/s15850/P/simulation.vvp | 51785723 |
| external/OpenROAD/src/gpl/test/large01.defok | 48933705 |
| external/OpenROAD/src/rcx/test/generate_pattern.defok | 48215198 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/chameleon/gds/DFFRAM_4K.gds.gz | 44626601 |
| external/OpenROAD/src/gpl/test/large01.def | 43964635 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_AO_RVT_FF_ccs_211120.lib.gz | 42599215 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_OA_RVT_FF_ccs_211120.lib.gz | 38631414 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/microwatt/gds/RAM512.gds.gz | 37347870 |
| external/OpenROAD/src/par/examples/embedding-aware-partitioning/sparcT1_chip2.hgr.ubfactor.2.numparts.2.embedding.dat | 37130453 |
| reports/physical_effect/s15850/P/transitions.npz | 36642191 |
| results/pact_candidate_stateful/measurement/s15850/5d90e5faf9dc/transitions.npz | 36617958 |
| results/pact_v2/measurement/s15850/e14689c97ca5/transitions.npz | 36617198 |
| results/pact_candidate_stateful/measurement/s15850/f47e6837c4da/transitions.npz | 36615825 |
| reports/physical_effect/s15850/PACT/transitions.npz | 36566449 |
| results/pact_v2/measurement/s15850/f3e118a35e7b/transitions.npz | 36538214 |
| results/pact_candidate_sensitive/measurement/s15850/630da6943398/transitions.npz | 36535749 |
| results/pact_candidate_sensitive/measurement/s15850/a3dd757a7e17/transitions.npz | 36516358 |
| results/pact_v2/measurement/s15850/1c4fe83a6b04/transitions.npz | 36485184 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hs/lib/sky130_fd_sc_hs__tt_100C_1v80.lib | 35764595 |
| reports/physical_effect/s15850/J50/transitions.npz | 34715628 |
| reports/working_solver/scaling_100000/checkpoint.json | 33067286 |
| external/OpenROAD/src/psm/doc/PDNSim-documentation.pdf | 32203838 |
| external/OpenROAD/src/rcx/test/generate_pattern.vok | 29203294 |
| external/OpenROAD/src/par/examples/min-cut-partitioning/sparcT1_chip2.hgr | 28550514 |
| external/OpenROAD/src/par/examples/embedding-aware-partitioning/sparcT1_chip2.hgr | 28550514 |
| reports/physical_effect/s5378/P/activity.vcd | 27041071 |
| results/pact_candidate_sensitive/measurement/s5378/b72833ffdd2b/activity.vcd | 26376034 |
| results/pact_candidate_sensitive/measurement/s5378/c11dfeee8d44/activity.vcd | 26213636 |
| reports/physical_effect/s5378/PACT/activity.vcd | 26159826 |
| results/pact_v2/measurement/s5378/b5c4710dcf54/activity.vcd | 26089958 |
| results/pact_candidate_stateful/measurement/s5378/42dfdefa6950/activity.vcd | 26055981 |
| results/pact_candidate_stateful/measurement/s5378/b2614a3a06b3/activity.vcd | 26021179 |
| reports/physical_effect/s5378/J50/activity.vcd | 25879946 |
| results/pact_v2/measurement/s5378/c4eabc41cb50/activity.vcd | 25750218 |
| results/pact_v2/measurement/s5378/3b627d8af4f2/activity.vcd | 25072243 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/microwatt/gds/Microwatt_FP_DFFRFile.gds.gz | 25048404 |
| results/pact_v2/measurement/s9234/53bb5b018758/simulation.vvp | 24274627 |
| reports/physical_effect/s9234/PACT/simulation.vvp | 24274591 |
| results/pact_candidate_sensitive/measurement/s9234/4d6ff90b2adc/simulation.vvp | 24274227 |
| results/pact_candidate_sensitive/measurement/s9234/1359e456272b/simulation.vvp | 24274227 |
| results/pact_v2/measurement/s9234/f4bca5652bda/simulation.vvp | 24274176 |
| results/pact_v2/measurement/s9234/797aff0b91f6/simulation.vvp | 24274176 |
| reports/physical_effect/s9234/J50/simulation.vvp | 24274137 |
| reports/physical_effect/s9234/T/simulation.vvp | 24274131 |
| external/OpenROAD/src/gpl/test/macro03.defok | 20692347 |
| external/OpenROAD/src/gpl/test/medium03.def | 20187481 |
| external/OpenROAD/src/psm/test/sky130hd_data/zerosoc_pads.def | 18946361 |
| reports/working_solver/scaling_50000/checkpoint.json | 18742271 |
| external/OpenROAD/src/par/examples/timing-aware-partitioning/ariane.v | 18277115 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_80x64_8/sky130_sram_1rw1r_80x64_8.lef | 17295196 |
| external/OpenROAD/src/gpl/test/macro03.def | 16620549 |
| results/pact_candidate_sensitive/measurement/s5378/c11dfeee8d44/simulation.vvp | 15804104 |
| results/pact_candidate_sensitive/measurement/s5378/b72833ffdd2b/simulation.vvp | 15804104 |
| results/pact_candidate_stateful/measurement/s5378/b2614a3a06b3/simulation.vvp | 15804101 |
| results/pact_candidate_stateful/measurement/s5378/42dfdefa6950/simulation.vvp | 15804101 |
| results/pact_v2/measurement/s5378/c4eabc41cb50/simulation.vvp | 15804053 |
| results/pact_v2/measurement/s5378/b5c4710dcf54/simulation.vvp | 15804053 |
| results/pact_v2/measurement/s5378/3b627d8af4f2/simulation.vvp | 15804053 |
| reports/physical_effect/s5378/PACT/simulation.vvp | 15804017 |
| reports/physical_effect/s5378/J50/simulation.vvp | 15804014 |
| reports/physical_effect/s5378/P/simulation.vvp | 15804008 |
| external/OpenROAD/src/gpl/doc/image/adaptec2.inf.gif | 15419357 |
| reports/working_solver/scaling_100000/supplied.architecture.json | 15355325 |

## Historical storage

| Category | Uncompressed unique blob bytes | Object disk bytes |
|---|---|---|
| results | 1357479290 | 255522999 |
| artifacts | 531833430 | 378767044 |
| reports | 99452136 | 54065983 |
| (root or unreachable) | 15103560 | 5001946 |
| scripts | 1869730 | 626683 |
| src | 679363 | 194567 |
| tests | 203227 | 69807 |
| docs | 104741 | 40795 |
| config | 36851 | 12636 |
| experiments | 5545 | 2006 |
| benchmarks | 5535 | 1349 |
| external | 210 | 162 |

Object disk bytes depend on packing/deltas and may count duplicate loose/packed storage differently from pack totals. No garbage collection or history rewrite was performed. Largest blobs are in `historical_blobs.tsv`.

## Causes and interpretation

The tracked checkout contains 27,885,967 text lines but only 44,950 source/test lines under src/scripts/tests. Most growth is generated data: results (1,722,288,194 bytes), artifacts (486,057,212) and reports (86,562,176). These contain repeated routed/placed OpenDB databases, extracted C/SPEF, generated netlists, route/simulator logs, large per-net CSV/JSON tables, frozen source/test copies and an entire initial_worktree.patch (52,976,858 bytes as a Git blob). Versioned physical final/fill databases repeat approximately 8 MB blobs; experiment results also copy the same source repeatedly. No tracked submodule gitlinks were found.

Ignored external dependency/source/build trees and local environments add approximately 3.3 GB. Historical unique blobs total 2,006,773,618 uncompressed bytes; results/artifacts/reports account for over 99% of those bytes. Actual .git logical storage is 1,399,485,073 bytes (packing/deltas differ from unique-blob size). The top objects are recorded in historical_blobs.tsv.

This explains the supplied roughly 22-million-line concern, but GitHub's remote code-frequency statistic was not independently fetched. Current-tree text LOC, implementation LOC, historical additions/deletions and Git object storage are distinct. Ordinary deletion commits do not remove old additions or blobs from history.

The baseline was captured after creating the cleanup branch and replacing the audit helper, before the deletion pass. Auxiliary validation-environment files appeared during the inventory. Original user edits and active untracked diagnostic/contribution work were preserved; the original README/planning notes have additional copies outside the nested checkout. Byte counts are logical file lengths, including externally allocated files exposed by a junction; they are not allocated disk usage or freed-space estimates.
