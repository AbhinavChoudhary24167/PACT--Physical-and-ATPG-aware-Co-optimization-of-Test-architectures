read_db /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2d_independent_gp/raw/orfs/results/nangate45/s5378/phase2c_s29_5f2b28506038/5_2_route.odb
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/rcx_patterns.rules -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef /mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/phase2d_independent_gp/raw/s5378/s29/1f1a3a458946/extracted.spef
exit
