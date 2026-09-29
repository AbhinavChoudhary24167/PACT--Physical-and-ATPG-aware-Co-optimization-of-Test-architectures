read_liberty /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_db /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_candidate_sensitive/measurement/s9234/1359e456272b/routed.odb
write_verilog /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_candidate_sensitive/measurement/s9234/1359e456272b/routed_raw.v
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_candidate_sensitive/measurement/s9234/1359e456272b/extracted.spef
exit
