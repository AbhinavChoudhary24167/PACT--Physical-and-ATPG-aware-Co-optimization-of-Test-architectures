# Read-only frozen PG-connection inventory. No power or IR calculation.
read_liberty $::env(GATE10A_LIBERTY)
read_db $::env(GATE10A_ODB)
set block [ord::get_db_block]
set missing 0
foreach inst [$block getInsts] {
  set master [$inst getMaster]
  set model [get_lib_cells -quiet "*/[$master getName]"]
  if {![llength $model]} {continue}
  foreach pin {VDD VSS} {
    set term [$inst findITerm $pin]
    if {$term eq "NULL" || [$term getNet] eq "NULL"} {
      incr missing
      puts "GATE10A_MISSING_SUPPLY [$inst getName] [$master getName] $pin"
    }
  }
}
puts "GATE10A_MISSING_SUPPLY_TERMINALS $missing"
