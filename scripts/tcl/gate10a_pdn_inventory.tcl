# Frozen DB structural inventory only: no modification, STA, power, or IR solve.
read_db $::env(GATE10A_ODB)
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
puts "GATE10A_PDN_BLOCK [$block getName] DBU $dbu INSTS [llength [$block getInsts]]"
set box [$block getDieArea]
puts "GATE10A_PDN_DIE [$box xMin] [$box yMin] [$box xMax] [$box yMax]"
foreach net [$block getNets] {
  set type [$net getSigType]
  if {$type ne "POWER" && $type ne "GROUND"} {continue}
  set wires [$net getSWires]
  set shapes 0
  set vias 0
  set layers {}
  foreach wire $wires {
    foreach shape [$wire getWires] {
      incr shapes
      if {[$shape isVia]} {
        incr vias
      } else {
        set layer [$shape getTechLayer]
        dict incr layers [$layer getName]
        if {[$layer getName] eq "metal7"} {
          puts "GATE10A_PDN_TOP_SHAPE [$net getName] [$shape xMin] [$shape yMin] [$shape xMax] [$shape yMax]"
        }
      }
    }
  }
  puts "GATE10A_PDN_NET [$net getName] $type SWIRES [llength $wires] SHAPES $shapes VIAS $vias ITERM [llength [$net getITerms]] BTERM [llength [$net getBTerms]] LAYERS $layers"
}
puts "GATE10A_PDN_INVENTORY_COMPLETE"
