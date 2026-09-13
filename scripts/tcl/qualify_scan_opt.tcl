source helpers.tcl
read_lef sky130hd/sky130hd.tlef
read_lef sky130hd/sky130_fd_sc_hd_merged.lef
read_liberty sky130hd/sky130_fd_sc_hd__tt_025C_1v80.lib
read_def one_cell_sky130.def
create_clock -name main_clock -period 2.0 [get_ports {clock}]
set_dft_config -max_length 10
puts "COMMANDS scan_replace=[info commands scan_replace] report_dft_plan=[info commands report_dft_plan] execute_dft_plan=[info commands execute_dft_plan] scan_opt=[info commands scan_opt]"
scan_replace
report_dft_plan -verbose
execute_dft_plan
write_verilog "$::env(PACT_DFT_OUT)/before_scan_opt.v"
scan_opt
write_verilog "$::env(PACT_DFT_OUT)/after_scan_opt.v"
