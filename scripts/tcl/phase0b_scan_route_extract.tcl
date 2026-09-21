# Structured OpenDB extraction. dbWire::getLength sums routed non-via shapes;
# it is only scan-net-only when the Q->SI net has no other sinks or BTerms.
read_db $::env(PACT_PHASE0B_ROUTED_ODB)
source $::env(PACT_PHASE0B_ORDER_TCL)
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set out [open $::env(PACT_PHASE0B_SCAN_ROUTE_TSV) w]
puts $out "source_ff\tdest_ff\tq_net\tsi_net\tconnected\trouted_nonvia_dbu\titerm_count\tbterm_count\tdbu_per_um"
foreach source [lrange $scan_order 0 end-1] dest [lrange $scan_order 1 end] {
  set a [$block findInst $source]
  set b [$block findInst $dest]
  if {$a == "NULL" || $b == "NULL"} {error "Routed scan FF missing"}
  set q_term [$a findITerm Q]
  set si_term [$b findITerm SI]
  if {$q_term == "NULL" || $si_term == "NULL"} {error "Routed Q/SI term missing"}
  set q_net [$q_term getNet]
  set si_net [$si_term getNet]
  if {$q_net == "NULL" || $si_net == "NULL"} {error "Routed scan term disconnected"}
  set same [expr {[$q_net getName] eq [$si_net getName]}]
  set wire [$si_net getWire]
  set length [expr {$wire == "NULL" ? -1 : [$wire getLength]}]
  puts $out "$source\t$dest\t[$q_net getName]\t[$si_net getName]\t$same\t$length\t[llength [$si_net getITerms]]\t[llength [$si_net getBTerms]]\t$dbu"
}
close $out
# SUPERSEDED FAILED PROBE: OpenROAD Tcl returns an opaque SWIG uint64 from
# dbWire.getLength in this build. Preserved with its failed run evidence;
# scripts/phase0b_scan_route_extract.py is the qualified implementation.
