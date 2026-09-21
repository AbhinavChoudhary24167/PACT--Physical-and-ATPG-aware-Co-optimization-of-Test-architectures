# Build a functional pre-scan counterpart of the FAN placed netlist. Only the
# test pins SI/SE are discarded. D, CK, Q and QN nets, FF names, and locations
# are retained so OpenROAD itself can perform scan_replace and stitching.
read_liberty $::env(PACT_PHASE0B_LIBERTY)
read_db $::env(PACT_PHASE0B_BASE_ODB)
set block [ord::get_db_block]
set db [ord::get_db]
set dff_master [$db findMaster DFF_X1]
if {$dff_master == "NULL"} {error "DFF_X1 master missing"}
set names {}
foreach inst [$block getInsts] {
  if {[[$inst getMaster] getName] eq "SDFF_X1"} {lappend names [$inst getName]}
}
if {[llength $names] < 2} {error "Pre-scan conversion found too few FFs"}
foreach name [lsort -dictionary $names] {
  set old [$block findInst $name]
  set xy [$old getLocation]
  set orient [$old getOrient]
  set status [$old getPlacementStatus]
  set connection {}
  foreach pin {D CK Q QN} {
    set term [$old findITerm $pin]
    if {$term == "NULL"} {error "SDFF $name lacks $pin"}
    set net [$term getNet]
    if {$net != "NULL"} {dict set connection $pin [$net getName]}
  }
  odb::dbInst_destroy $old
  set new [odb::dbInst_create $block $dff_master $name]
  if {$new == "NULL"} {error "DFF recreation failed for $name"}
  foreach pin [dict keys $connection] {
    set term [$new findITerm $pin]
    if {$term == "NULL"} {error "DFF $name lacks $pin"}
    $term connect [$block findNet [dict get $connection $pin]]
  }
  $new setLocation {*}$xy
  $new setOrient $orient
  $new setPlacementStatus $status
}
puts "PHASE0B_PRESCAN_CONVERTED [llength $names]"
write_verilog "$::env(PACT_PHASE0B_DFT_OUT)/prescan.v"
write_db "$::env(PACT_PHASE0B_DFT_OUT)/prescan.odb"
read_sdc $::env(PACT_PHASE0B_BASE_SDC)
set_dft_config -max_length 1000
scan_replace
puts "PHASE0B_SCAN_REPLACE_DONE"
report_dft_plan -verbose
execute_dft_plan
write_db "$::env(PACT_PHASE0B_DFT_OUT)/native.odb"
write_verilog "$::env(PACT_PHASE0B_DFT_OUT)/native.v"
write_def "$::env(PACT_PHASE0B_DFT_OUT)/native.def"
