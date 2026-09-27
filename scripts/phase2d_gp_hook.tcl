# Retain the newly initialized ancestry rather than resetting all cells to center.
# The external seed creates scratch coordinates from an UNPLACED floorplan.
rename global_placement phase2d_original_global_placement
proc global_placement {args} {
  set adapted {}
  foreach arg $args {
    if {$arg ne "-force_center_initial_place"} {lappend adapted $arg}
  }
  puts "PHASE2D_GP_FROM_FRESH_ANCESTRY: $adapted"
  phase2d_original_global_placement {*}$adapted
}
