# Read-only command/API inventory. No design is read and no power/IR is solved.
puts "GATE10A_TOOL_VERSION [ord::openroad_version]"
foreach command {
  read_vcd read_saif report_power report_activity_annotation set_power_activity
  check_power_grid analyze_power_grid set_pdnsim_inst_power
  set_pdnsim_net_voltage set_pdnsim_source_settings write_pg_spice
  define_pdn_grid add_pdn_stripe add_pdn_connect pdngen global_connect
} {
  puts "GATE10A_COMMAND $command PRESENT [expr {[llength [info commands $command]] > 0}]"
  if {[catch {help $command} details]} {
    puts "GATE10A_HELP_ERROR $command $details"
  }
}
foreach command {
  sta::instance_power sta::design_power sta::power_units
  sta::power_ui_sta sta::power_sta_ui sta::activity sta::set_power_activity
  sta::pin_activity sta::net_pins sta::get_full_name sta::get_property
} {
  puts "GATE10A_API $command PRESENT [expr {[llength [info commands $command]] > 0}]"
}
puts "GATE10A_POWER_APIS [lsort [info commands sta::*power*]]"
puts "GATE10A_ACTIVITY_APIS [lsort [info commands sta::*activity*]]"
puts "GATE10A_SCENE_APIS [lsort [info commands sta::*scene*]]"
puts "GATE10A_NET_APIS [lsort [info commands sta::*net*]]"
foreach command {sta::instance_power sta::design_power sta::cmd_scene} {
  if {[catch {$command} details]} {puts "GATE10A_SIGNATURE $command $details"}
}
foreach command {
  sta::set_power_activity sta::report_power_insts_json
  sta::report_power_design_json sta::power_sta_ui
  sta::report_power_insts sta::report_power_design
} {
  if {[llength [info procs $command]]} {
    puts "GATE10A_PROC $command ARGS [info args $command]"
    puts [info body $command]
    puts "GATE10A_END_PROC $command"
  }
}
puts "GATE10A_API_COMPLETE"
