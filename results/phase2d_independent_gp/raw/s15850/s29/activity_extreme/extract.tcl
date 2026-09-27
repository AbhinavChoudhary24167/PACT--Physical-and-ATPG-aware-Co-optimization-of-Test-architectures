read_db /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2d_independent_gp/raw/orfs/results/nangate45/s15850/phase2c_s29_4a26c3278995/5_2_route.odb
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2d_independent_gp/raw/s15850/s29/activity_extreme/extracted.spef
exit
