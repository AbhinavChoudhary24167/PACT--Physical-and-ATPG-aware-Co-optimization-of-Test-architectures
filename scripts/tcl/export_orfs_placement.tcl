set block [expr {[info exists ::env(PACT_ORFS_BLOCK)] ? $::env(PACT_ORFS_BLOCK) : "s5378"}]
set db "$::env(PACT_ORFS_ROOT)/flow/results/nangate45/$block/base/3_place.odb"
if {![file exists $db]} {error "ORFS placement database missing: $db"}
read_db $db
write_def "$::env(PACT_ORFS_OUT)/placed.def"
write_verilog "$::env(PACT_ORFS_OUT)/placed.v"
