create_clock -name clk -period 10.0 [get_ports CK]
set_input_delay 0.0 -clock clk [all_inputs]
set_output_delay 0.0 -clock clk [all_outputs]
