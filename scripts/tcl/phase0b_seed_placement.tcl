set input_db $::env(PACT_PHASE0B_SOURCE_ODB)
set output_db $::env(PACT_PHASE0B_PLACED_ODB)
set output_dir $::env(PACT_PHASE0B_PLACEMENT_OUT)
set seed $::env(PACT_PHASE0B_PHYSICAL_SEED)
if {$seed ni {11 13 17 19 23}} {error "Unregistered physical seed: $seed"}
read_db $input_db
set block [ord::get_db_block]
set core [$block getCoreArea]
set dbu [$block getDbUnitsPerMicron]
expr {srand($seed)}
set jitter [expr {round(8.0 * $dbu)}]
set names {}
foreach inst [$block getInsts] {lappend names [$inst getName]}
set moved 0
set moved_ffs 0
foreach name [lsort -dictionary $names] {
  set inst [$block findInst $name]
  if {[$inst getPlacementStatus] ne "PLACED"} {continue}
  if {[expr {rand()}] >= 0.4} {continue}
  set xy [$inst getLocation]
  set master [$inst getMaster]
  set x [expr {[lindex $xy 0] + round((2.0 * rand() - 1.0) * $jitter)}]
  set y [expr {[lindex $xy 1] + round((2.0 * rand() - 1.0) * $jitter)}]
  set x [expr {max([$core xMin], min($x, [$core xMax] - [$master getWidth]))}]
  set y [expr {max([$core yMin], min($y, [$core yMax] - [$master getHeight]))}]
  $inst setLocation $x $y
  incr moved
  if {[$master getName] eq "SDFF_X1"} {incr moved_ffs}
}
puts "PHASE0B_SEED $seed MOVED $moved MOVED_SCAN_FFS $moved_ffs DBU_PER_UM $dbu"
if {$moved_ffs < 1} {error "No scan FF was perturbed"}
detailed_placement -max_displacement 50
check_placement -verbose
write_db $output_db
write_def "$output_dir/placed.def"
write_verilog "$output_dir/placed.v"
