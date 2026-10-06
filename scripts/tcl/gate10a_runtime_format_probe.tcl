# Read exact installed runtime report definitions; no design or solve.
read_liberty /root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
foreach name {sta::report_power_design_json sta::report_power_insts_json sta::format_power psm::check_power_grid psm::analyze_power_grid} {
  if {![catch {info body $name} body]} {
    puts "GATE10A_RUNTIME_PROC $name"
    puts $body
  }
}
foreach name {sta::set_power_pin_activity sta::set_power_input_port_activity sta::set_power_activity report_activity_annotation} {
  puts "GATE10A_RUNTIME_API $name [info commands $name]"
  if {![catch {info body $name} body]} {puts $body}
}
puts "GATE10A_RUNTIME_FORMAT_COMPLETE"
