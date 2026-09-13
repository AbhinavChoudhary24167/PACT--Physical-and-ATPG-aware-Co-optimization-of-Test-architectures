read_db $::env(PACT_BASE_ODB)
source $::env(PACT_REWIRE_TCL)
set block [ord::get_db_block]
set index 0
set previous_net $scan_root_net
foreach name $scan_order {
  set inst [$block findInst $name]
  if {$inst == "NULL"} {error "Scan FF missing: $name"}
  set si [$inst findITerm SI]
  if {$si == "NULL"} {error "SI pin missing: $name"}
  set net [$block findNet $previous_net]
  if {$net == "NULL"} {error "Scan net missing: $previous_net"}
  $si disconnect
  $si connect $net
  if {[[[$inst findITerm SI] getNet] getName] ne $previous_net} {
    error "Failed SI rewire for $name"
  }
  set previous_net [dict get $q_by_ff $name]
  incr index
}
if {$index != [llength $scan_order]} {error "Scan count changed"}
set output_inst [$block findInst $scan_out_buffer]
if {$output_inst == "NULL"} {error "Scan output buffer missing"}
set output_term [$output_inst findITerm $scan_out_buffer_pin]
set last_net [$block findNet $previous_net]
if {$last_net == "NULL"} {error "Scan final Q net missing"}
$output_term disconnect
$output_term connect $last_net
if {[[$output_term getNet] getName] ne $previous_net} {error "Failed scan-out rewire"}
write_db $::env(PACT_VARIANT_ODB)
write_def "$::env(PACT_REWIRE_OUT)/rewired.def"
write_verilog "$::env(PACT_REWIRE_OUT)/rewired.v"
puts "REWIRED_COUNT $index"
