read_liberty $::env(PACT_PHASE0B_LIBERTY)
read_db $::env(PACT_PHASE0B_BASE_ODB)
read_sdc $::env(PACT_PHASE0B_BASE_SDC)
set_dft_config -max_length 1000
puts "PHASE0B_DFT_PROBE_PRE_SCAN_REPLACE"
scan_replace
puts "PHASE0B_DFT_PROBE_POST_SCAN_REPLACE"
report_dft_plan -verbose
execute_dft_plan
write_db "$::env(PACT_PHASE0B_DFT_OUT)/native.odb"
write_verilog "$::env(PACT_PHASE0B_DFT_OUT)/native.v"
write_def "$::env(PACT_PHASE0B_DFT_OUT)/native.def"
