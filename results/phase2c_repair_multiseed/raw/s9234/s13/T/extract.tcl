read_db /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2c_repair_multiseed/raw/orfs/results/nangate45/s9234f/phase2c_s13_5d5b64bd2274/5_2_route.odb
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2c_repair_multiseed/raw/s9234/s13/T/extracted.spef
exit
