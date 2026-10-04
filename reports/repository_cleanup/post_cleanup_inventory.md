# Post Cleanup inventory

Logical file bytes; links are excluded. Text LOC counts LF-separated records (including a final unterminated line), excluding binary files. It includes generated text and is distinct from source/test LOC. The Git index supplies tracked paths.

| Measurement | Value |
|---|---|
| tracked_files | 1045 |
| tracked_bytes | 75341088 |
| tracked_text_lines | 2639272 |
| source_test_lines | 30424 |
| checkout_bytes | 3388457868 |
| git_bytes | 1398870744 |
| total_bytes | 4787328612 |

## Directory storage

| Directory | Files | Bytes |
|---|---|---|
| external | 11328 | 2898956093 |
| results | 1152 | 247431433 |
| .optimizer-deps | 1642 | 211299881 |
| reports | 85 | 15080902 |
| artifacts | 88 | 6398432 |
| scripts | 296 | 3007883 |
| src | 211 | 2551488 |
| tests | 201 | 2068458 |
| scratch | 55 | 1087932 |
| .optimizer-cache | 30 | 457845 |
| .pytest_cache | 5 | 43844 |
| docs | 11 | 25093 |
| config | 14 | 25056 |
| experiments | 10 | 5827 |
| .venv | 2 | 5569 |
| README.md | 1 | 4697 |
| benchmarks | 4 | 2564 |
| .gitignore | 1 | 1833 |
| LICENSE | 1 | 1074 |
| .gitattributes | 1 | 713 |
| pyproject.toml | 1 | 707 |
| CITATION.cff | 1 | 400 |
| Makefile | 1 | 134 |
| requirements.txt | 1 | 10 |

## Largest tracked files

| Path | Bytes | Text lines |
|---|---|---|
| results/pact_candidate_stateful/s15850/baseline_geometry.json | 5979142 | 315971 |
| results/pact_candidate_sensitive/s15850/topology.json | 3750334 | 219656 |
| results/pact_candidate_stateful/s9234/baseline_geometry.json | 3118804 | 165881 |
| reports/repository_cleanup/file_classification.tsv | 2857809 | 15510 |
| results/pact_candidate_stateful/s5378/prior_corpus.json.gz | 2758109 | 0 |
| results/pact_candidate_stateful/s5378/baseline_geometry.json | 2334278 | 121738 |
| results/pact_candidate_stateful/s9234/prior_corpus.json.gz | 2009717 | 0 |
| results/pact_candidate_sensitive/s9234/topology.json | 1957424 | 115277 |
| results/pact_candidate_sensitive/s5378/topology.json | 1466854 | 84511 |
| results/pact_v2/s9234/evaluations.csv.gz | 1433102 | 0 |
| results/pact_v2/s5378/evaluations.csv.gz | 1385090 | 0 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/routes/s15850.json | 1370510 | 39742 |
| reports/repository_cleanup/pre_cleanup_tracked_inventory.tsv | 1315517 | 15510 |
| results/pact_candidate_sensitive/s5378/evaluations.csv.gz | 1295814 | 0 |
| results/pact_candidate_stateful/s15850/prior_corpus.json.gz | 1053449 | 0 |
| results/pact_candidate_sensitive/s15850/physical_model.json | 1030968 | 64224 |
| results/phase2c_repair/freeze.json | 982450 | 43765 |
| artifacts/raw/phase0b/placements/s15850/s11/placed.def | 962818 | 13873 |
| reports/working_solver/final/s15850_300/result.json | 902641 | 39571 |
| reports/physical_effect/s15850/J50/net_mapping.json | 840043 | 46788 |
| reports/physical_effect/s15850/PACT/net_mapping.json | 839876 | 46779 |
| reports/physical_effect/s15850/P/net_mapping.json | 839714 | 46770 |
| results/pact_v2/s15850/evaluations.csv.gz | 797372 | 0 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/routes/s5378.json | 697575 | 19486 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/routes/s9234.json | 575185 | 16478 |
| results/pact_candidate_sensitive/s9234/evaluations.csv.gz | 531466 | 0 |
| results/pact_candidate_sensitive/s9234/physical_model.json | 515285 | 30489 |
| results/pact_candidate_stateful/summary.json | 503244 | 11882 |
| reports/physical_effect/s15850/PACT/net_activity_capacitance.csv | 498998 | 5057 |
| reports/physical_effect/s15850/J50/net_activity_capacitance.csv | 498921 | 5058 |
| reports/physical_effect/s15850/P/net_activity_capacitance.csv | 498158 | 5056 |
| artifacts/raw/phase0b/placements/s9234/s11/placed.def | 491817 | 7104 |
| results/pact_candidate_sensitive/s5378/physical_model.json | 471549 | 26712 |
| results/phase2c_repair/s15850.placed_graph.json | 440338 | 26994 |
| reports/physical_effect/s9234/PACT/net_mapping.json | 431284 | 24169 |
| reports/physical_effect/s9234/J50/net_mapping.json | 431125 | 24160 |
| reports/physical_effect/s9234/T/net_mapping.json | 431125 | 24160 |
| artifacts/raw/phase0b/placements/s5378/s11/placed.def | 399542 | 5349 |
| artifacts/raw/phase0b/rewire/s5378/s11/P/rewired.def | 399542 | 5349 |
| reports/repository_cleanup/pre_cleanup_git_state.txt | 397757 | 5410 |
| artifacts/raw/phase0b/placements/s15850/s11/placed.v | 396389 | 20567 |
| artifacts/raw/tool_qualification/fan_atpg/benchmarks/s15850.v | 392146 | 19014 |
| results/pact_h8_rootcause/evidence_manifest.json | 368456 | 5681 |
| results/pact_stage_b/inputs/s15850.json.gz | 337519 | 0 |
| reports/physical_effect/s5378/P/net_mapping.json | 335544 | 18271 |
| reports/physical_effect/s5378/J50/net_mapping.json | 335543 | 18271 |
| reports/physical_effect/s5378/PACT/net_mapping.json | 335542 | 18271 |
| results/phase2c_repair/s9234.placed_graph.json | 265449 | 16055 |
| reports/physical_effect/s9234/PACT/net_activity_capacitance.csv | 256028 | 2635 |
| reports/physical_effect/s9234/J50/net_activity_capacitance.csv | 255371 | 2634 |
| reports/physical_effect/s9234/T/net_activity_capacitance.csv | 254705 | 2634 |
| results/pact_candidate_sensitive/s15850/evaluations.csv.gz | 228898 | 0 |
| results/phase2c_repair/s5378.placed_graph.json | 219174 | 13347 |
| artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s15850.stil | 217156 | 1526 |
| results/pact_h8_rootcause/evidence_index.json | 205050 | 3328 |
| artifacts/derived/s9234/s9234_nangate45_compatible.v | 204191 | 10204 |
| artifacts/raw/tool_qualification/fan_atpg/benchmarks/s9234.v | 204191 | 10204 |
| artifacts/raw/phase0b/placements/s9234/s11/placed.v | 202766 | 10739 |
| reports/physical_effect/s5378/PACT/net_activity_capacitance.csv | 201581 | 1977 |
| reports/physical_effect/s5378/J50/net_activity_capacitance.csv | 201474 | 1977 |
| reports/physical_effect/s5378/P/net_activity_capacitance.csv | 201358 | 1977 |
| reports/working_solver/final/s9234/result.json | 199918 | 8442 |
| reports/working_solver/final/s5378/result.json | 198728 | 8421 |
| results/pact_h8_rootcause/mechanism_summary.csv | 193757 | 305 |
| reports/working_solver/final/s15850/result.json | 192301 | 8258 |
| artifacts/raw/tool_qualification/fan_atpg/s15850.atpg.log | 184936 | 868 |
| artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s15850.pat | 181676 | 139 |
| reports/end_to_end/s15850/integration_v1/patterns_recovered.pat | 181672 | 138 |
| results/pact_candidate_sensitive/summary.json | 179937 | 4982 |
| results/pact_stage_b/inputs/s9234.json.gz | 174631 | 0 |
| artifacts/raw/phase0b/placements/s5378/s11/placed.v | 171467 | 7902 |
| artifacts/raw/phase0b/rewire/s5378/s11/P/rewired.v | 171467 | 7902 |
| artifacts/derived/s5378/s5378_nangate45_compatible.v | 166314 | 7256 |
| artifacts/raw/tool_qualification/fan_atpg/benchmarks/s5378.v | 166314 | 7256 |
| results/pact_oss_benchmark/stage_a/P0_FREEZE.json | 159036 | 2343 |
| results/pact_candidate_stateful/s15850/model_contract.json | 148958 | 3126 |
| results/pact_stage_b/inputs/s5378.json.gz | 127606 | 0 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/measurement_attempts/s15850/541edd9b8a402c089751f83af6753d6efd438d9bd803e1309e64bc5fa614d4db/topology_verification.json | 126335 | 4856 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/measurement_attempts/s15850/24124a8d821b7a19ffb08cc72b90c6bbf44713b1eb4bb5812809ec988bec6f2b/topology_verification.json | 126261 | 4856 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/measurement_attempts/s15850/f0ec44569fab2217d7aa9f8dd4bb03a265c3d352c935343052f3505432cea877/topology_verification.json | 126251 | 4856 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/measurement_attempts/s15850/1cff03ead6aa224ba65fdb67bb53fb1d50427cea9daad270237b4feca57b0ae7/topology_verification.json | 126242 | 4856 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/measurement_attempts/s15850/c081f811b1806ae67132a1b56f1eddc0e4defdbba44fd87c7cbb0ce1d15bb4b8/topology_verification.json | 126240 | 4856 |
| reports/repository_cleanup/retained_evidence_sha256.json | 121152 | 676 |
| artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s9234.stil | 114282 | 1581 |
| results/pact_v2/summary.json | 109871 | 3087 |
| reports/repository_cleanup/post_cleanup_tracked_inventory.tsv | 94770 | 1045 |
| artifacts/raw/tool_qualification/fan_atpg/s9234.atpg.log | 87674 | 1006 |
| results/pact_candidate_stateful/s9234/model_contract.json | 84655 | 1732 |
| artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s9234.pat | 84298 | 162 |
| reports/end_to_end/s9234/integration_v1/patterns_recovered.pat | 84294 | 161 |
| artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s5378.stil | 83294 | 1239 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/pairwise_comparison.csv | 75586 | 223 |
| artifacts/derived/s15850/ff_identity_map.json | 74125 | 3224 |
| results/stage_a/pairwise_comparison.csv | 67051 | 223 |
| artifacts/derived/phase0c/s15850/s11/k2/A.architecture.json | 66760 | 3760 |
| artifacts/derived/phase0c/s15850/s11/k2/B0.architecture.json | 66760 | 3760 |
| artifacts/derived/phase0c/s15850/s11/k2/J50.architecture.json | 66760 | 3760 |
| artifacts/derived/phase0c/s15850/s11/k2/P.architecture.json | 66760 | 3760 |
| artifacts/derived/phase0c/s15850/s11/k2/T.architecture.json | 66760 | 3760 |
| reports/working_solver/final/s15850/optimized.architecture.json | 66760 | 3760 |

## Largest checkout files (including ignored dependencies)

| Path | Bytes |
|---|---|
| external/OpenROAD-flow-scripts/.git/objects/pack/pack-5235005c14bfe212134a871c8e6311f4e4ed7488.pack | 500470702 |
| external/OpenROAD/.git/objects/pack/pack-84718d8307ce38b2008a0a4218c8de91c1028375.pack | 325095201 |
| .optimizer-deps/llvmlite/binding/libllvmlite.so | 178881880 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_128x256_8/sky130_sram_1rw1r_128x256_8.lef | 102897488 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hs/lib/sky130_fd_sc_hs__tt_025C_1v80.lib | 72103677 |
| external/OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/gds/sg13g2_io.gds | 71399424 |
| external/OpenROAD/src/gpl/test/large02.defok | 71282730 |
| external/OpenROAD/src/gpl/test/large02.def | 64632121 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_64x256_8/sky130_sram_1rw1r_64x256_8.lef | 52463418 |
| external/OpenROAD/src/gpl/test/large01.defok | 48933705 |
| external/OpenROAD/src/rcx/test/generate_pattern.defok | 48215198 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/chameleon/gds/DFFRAM_4K.gds.gz | 44626601 |
| external/OpenROAD/src/gpl/test/large01.def | 43964635 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_AO_RVT_FF_ccs_211120.lib.gz | 42599215 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_OA_RVT_FF_ccs_211120.lib.gz | 38631414 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/microwatt/gds/RAM512.gds.gz | 37347870 |
| external/OpenROAD/src/par/examples/embedding-aware-partitioning/sparcT1_chip2.hgr.ubfactor.2.numparts.2.embedding.dat | 37130453 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hs/lib/sky130_fd_sc_hs__tt_100C_1v80.lib | 35764595 |
| external/OpenROAD/src/psm/doc/PDNSim-documentation.pdf | 32203838 |
| external/OpenROAD/src/rcx/test/generate_pattern.vok | 29203294 |
| external/OpenROAD/src/par/examples/min-cut-partitioning/sparcT1_chip2.hgr | 28550514 |
| external/OpenROAD/src/par/examples/embedding-aware-partitioning/sparcT1_chip2.hgr | 28550514 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/microwatt/gds/Microwatt_FP_DFFRFile.gds.gz | 25048404 |
| external/OpenROAD/src/gpl/test/macro03.defok | 20692347 |
| external/OpenROAD/src/gpl/test/medium03.def | 20187481 |
| external/OpenROAD/src/psm/test/sky130hd_data/zerosoc_pads.def | 18946361 |
| external/OpenROAD/src/par/examples/timing-aware-partitioning/ariane.v | 18277115 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_80x64_8/sky130_sram_1rw1r_80x64_8.lef | 17295196 |
| external/OpenROAD/src/gpl/test/macro03.def | 16620549 |
| external/OpenROAD/src/gpl/doc/image/adaptec2.inf.gif | 15419357 |
| external/OpenROAD/src/drt/test/aes_nangate45_preroute.def | 14361033 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/chameleon/gds/ibex_wrapper.gds.gz | 13193815 |
| external/OpenROAD-flow-scripts/flow/designs/src/bp_quad/bsg_chip_block.sv2v.v | 13117017 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib | 12800135 |
| external/OpenROAD/src/gpl/test/macro01.defok | 12013923 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_128x256_8/sky130_sram_1rw1r_128x256_8.gds | 11790182 |
| external/OpenROAD-flow-scripts/flow/designs/src/coyote/coyote.sv2v.v | 11551571 |
| external/OpenROAD/src/gpl/doc/image/replace_tcl_interp_example.gif | 10639520 |
| external/OpenROAD-flow-scripts/flow/designs/src/tinyRocket/freechips.rocketchip.system.TinyConfig.v | 10304063 |
| external/OpenROAD/src/gpl/doc/image/coyote_movie.gif | 10065130 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_44x64_8/sky130_sram_1rw1r_44x64_8.lef | 9706517 |
| external/OpenROAD/src/gpl/test/macro01.def | 9583774 |
| external/OpenROAD-flow-scripts/flow/designs/src/ariane/ariane.sv2v.v | 9514787 |
| external/OpenROAD-flow-scripts/flow/designs/src/ariane133/ariane.sv2v.v | 9514473 |
| external/OpenROAD-flow-scripts/flow/designs/src/ariane136/ariane.sv2v.v | 9514463 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/chameleon/gds/apb_sys_0.gds.gz | 7979526 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_SIMPLE_RVT_FF_ccs_250407.lib.gz | 7442959 |
| external/OpenROAD/src/gpl/test/macro02.defok | 7084937 |
| external/OpenROAD-flow-scripts/flow/designs/asap7/jpeg/jpeg_encoder15_7nm_synth.v | 6952136 |
| external/OpenROAD/src/drt/test/aes_nangate45.route_guide | 6930468 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_64x256_8/sky130_sram_1rw1r_64x256_8.gds | 6900388 |
| external/OpenROAD/src/dbSta/test/example1_fast.lib | 6749164 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/microwatt/gds/multiply_add_64x64.gds.gz | 6706794 |
| external/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib | 6692032 |
| external/OpenROAD/src/cts/test/ModNangate45/ModNangate45_typ.lib | 6691570 |
| external/OpenROAD/src/gpl/test/medium02.def | 6502773 |
| external/OpenROAD-flow-scripts/flow/designs/src/swerv/swerv_wrapper.sv2v.v | 6338695 |
| external/OpenROAD/src/pdn/test/pads_connect_from_non_pref_edge.defok | 6193712 |
| external/OpenROAD/src/psm/test/Nangate45_data/aes_multi_bterms.def | 6078038 |
| external/OpenROAD-flow-scripts/flow/designs/src/black_parrot/pickled.v | 6065823 |
| results/pact_candidate_stateful/s15850/baseline_geometry.json | 5979142 |
| external/OpenROAD/src/gpl/test/incremental02.defok | 5739503 |
| external/OpenROAD-flow-scripts/flow/designs/sky130hd/chameleon/gds/DMC_32x16HC.gds.gz | 5684822 |
| external/OpenROAD/src/gpl/test/macro02.def | 5669598 |
| results/pact_oss_benchmark/topology_recovery_20261004/verilog_input_alias/upstream_ci_20261004/initial_diagnosis.json | 5653191 |
| external/OpenROAD/src/gpl/doc/image/aes_cipher_top_ASAP_N7.gif | 5652149 |
| external/OpenROAD/src/gpl/test/incremental02.def | 5600897 |
| results/pact_oss_benchmark/topology_recovery_20261004/verilog_input_alias/upstream_ci_round2_20261004/OpenSTA_CI-Public_pr-merge.log | 5549747 |
| results/pact_oss_benchmark/topology_recovery_20261004/verilog_input_alias/upstream_ci_20261004/console.txt | 5549747 |
| external/OpenROAD/src/dpl/test/cell_on_block2.def | 5495164 |
| external/OpenROAD/src/dpl/test/cell_on_block2.defok | 5494666 |
| external/OpenROAD/src/psm/test/Nangate45_data/aes.def | 5214763 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS/asap7sc7p5t_SEQ_RVT_FF_ccs_220123.lib | 5188096 |
| external/OpenROAD/src/dpl/test/ibex-opt.def | 4768288 |
| external/OpenROAD/src/dpl/test/ibex-opt.defok | 4768151 |
| external/OpenROAD/src/dpl/test/ibex.defok | 4763349 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SLVT_FF_nldm_211120.lib.gz | 4358007 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SLVT_TT_nldm_211120.lib.gz | 4352757 |
| external/OpenROAD/src/pdn/test/asap7_macro_covered_partial.defok | 4347677 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_LVT_FF_nldm_211120.lib.gz | 4317540 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SLVT_SS_nldm_211120.lib.gz | 4308746 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130ram/sky130_sram_1rw1r_80x64_8/sky130_sram_1rw1r_80x64_8.gds | 4308002 |
| external/OpenROAD/src/pad/test/skywater130_coyote_tc/coyote_tc.v | 4299699 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_LVT_TT_nldm_211120.lib.gz | 4274330 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_RVT_FF_nldm_211120.lib.gz | 4256548 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_LVT_SS_nldm_211120.lib.gz | 4251641 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hd/gds/sky130_fd_sc_hd.gds | 4182250 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_RVT_TT_nldm_211120.lib.gz | 4181747 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_RVT_SS_nldm_211120.lib.gz | 4181198 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SRAM_FF_nldm_211120.lib.gz | 4179436 |
| external/OpenROAD/src/psm/test/asap7_data/aes_place.def | 4158758 |
| external/OpenROAD/src/dpl/test/ibex_core_replace.def | 4142908 |
| external/OpenROAD-flow-scripts/flow/platforms/sky130hs/gds/sky130_fd_sc_hs.gds | 4136798 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SRAM_TT_nldm_211120.lib.gz | 4106097 |
| external/OpenROAD-flow-scripts/flow/designs/src/mock-alu/src/main/resources/mult_koggestone.v | 4060676 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_AO_SRAM_SS_nldm_211120.lib.gz | 4060576 |
| external/OpenROAD-flow-scripts/flow/designs/src/mock-alu/src/main/resources/mac_brentkung.v | 3943289 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_OA_SLVT_FF_nldm_211120.lib.gz | 3936499 |
| external/OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM/asap7sc7p5t_OA_SLVT_TT_nldm_211120.lib.gz | 3924913 |
| external/OpenROAD-flow-scripts/flow/designs/src/mock-alu/src/main/resources/asap7/mult_hancarlson.v | 3910435 |
