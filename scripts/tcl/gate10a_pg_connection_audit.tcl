# Common in-memory PG terminal normalization audit only; no power/IR is run.
read_db $::env(GATE10A_ODB)
set block [ord::get_db_block]
set directory $::env(GATE10A_OUTPUT)
proc gate10a_pg_shapes {block path} {
  set out [open $path w]
  foreach net [$block getNets] {
    if {[$net getSigType] ni {POWER GROUND}} {continue}
    foreach wire [$net getSWires] {
      foreach shape [$wire getWires] {
        set id ""
        set layer "VIA"
        if {[$shape isVia]} {
          set via [$shape getTechVia]
          if {$via eq "NULL"} {set via [$shape getBlockVia]}
          set id [$via getName]
        } else {set layer [[$shape getTechLayer] getName]}
        puts $out "[$net getName]\t[$net getSigType]\t$layer\t[$shape xMin]\t[$shape yMin]\t[$shape xMax]\t[$shape yMax]\t$id"
      }
    }
  }
  close $out
}
proc gate10a_pg_terms {block path} {
  set out [open $path w]
  puts $out "instance\tmaster\tpin\tnet"
  foreach inst [$block getInsts] {
    foreach term [$inst getITerms] {
      if {[$term getSigType] ni {POWER GROUND}} {continue}
      set net [$term getNet]
      puts $out "[$inst getName]\t[[$inst getMaster] getName]\t[[$term getMTerm] getName]\t[expr {$net eq "NULL" ? "" : [$net getName]}]"
    }
  }
  close $out
}
write_def $directory/before.def
gate10a_pg_shapes $block $directory/before_pg_shapes.tsv
gate10a_pg_terms $block $directory/before_pg_terms.tsv
add_global_connection -net VDD -inst_pattern {.*} -pin_pattern {^VDD$} -power
add_global_connection -net VSS -inst_pattern {.*} -pin_pattern {^VSS$} -ground
global_connect
write_def $directory/after.def
gate10a_pg_shapes $block $directory/after_pg_shapes.tsv
gate10a_pg_terms $block $directory/after_pg_terms.tsv
puts "GATE10A_PG_AUDIT_COMPLETE"
