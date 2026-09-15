# Command-availability probe only. It does not claim test-mode power.
foreach command {
  read_vcd read_saif report_power report_activity_annotation
  set_power_activity set_pdnsim_inst_power analyze_power_grid
} {
  puts "PHASE0C_COMMAND $command"
  if {[catch {help $command} details]} {
    puts "PHASE0C_UNAVAILABLE $command $details"
  } else {
    puts "PHASE0C_AVAILABLE $command"
  }
}
