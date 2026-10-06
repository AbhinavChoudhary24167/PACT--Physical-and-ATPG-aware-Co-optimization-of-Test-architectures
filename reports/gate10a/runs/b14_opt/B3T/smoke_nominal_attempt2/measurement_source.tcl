# Gate10A measurement of a frozen routed database; no optimizer/backend writes.
set_thread_count 1
read_liberty $::env(GATE10A_LIBERTY)
read_db $::env(GATE10A_ODB)
source $::env(GATE10A_SET_RC)
read_sdc $::env(GATE10A_SDC)
# Without -add, create_clock replaces clocks at this source. Same frozen name
# retains the original I/O constraint references; exact waveform is explicit.
create_clock -name clk -period 10.0 -waveform {0 5} [get_ports CK]
if {[llength [get_clocks *]] != 1} {error "Unexpected frozen clock population"}
set_propagated_clock [get_clocks clk]
read_spef $::env(GATE10A_SPEF)
set_power_activity -global -density 0 -duty 0.5
set_power_activity -input -density 0 -duty 0.5
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set outdir $::env(GATE10A_OUTPUT)
set pin_out [open $outdir/annotated_pins.tsv w]
puts $pin_out "net\tpin\tdensity_per_ns\tduty\torigin"
set gate10a_annotated_nets {}
proc gate10a_annotate {name density duty origin} {
  global pin_out gate10a_annotated_nets
  set nets [get_nets -quiet $name]
  if {[llength $nets] != 1 || [get_full_name [lindex $nets 0]] ne $name} {
    error "Measured/clock net mapping is not exact: $name"
  }
  set pins [sta::net_pins [lindex $nets 0]]
  if {![llength $pins]} {error "Annotated net has no pins: $name"}
  foreach pin $pins {
    # This is the same low-level setter used by the public -pins command.
    sta::set_power_pin_activity $pin [expr {$density / [sta::time_ui_sta 1.0]}] $duty
    puts $pin_out "$name\t[sta::get_full_name $pin]\t[format %.17g $density]\t[format %.17g $duty]\t$origin"
  }
  dict set gate10a_annotated_nets $name $origin
}
source $::env(GATE10A_ACTIVITY_TCL)
close $pin_out
if {[llength [get_ports -quiet test_se]] != 1} {error "Frozen scan enable test_se missing"}
gate10a_annotate test_se 0 1 scan_enable_asserted
set_case_analysis 1 [get_ports test_se]
set_power_activity -input_ports test_se -density 0 -duty 1
set expected_ff_count [llength $gate10a_expected_ffs]
foreach name $gate10a_expected_ffs {
  set inst [$block findInst $name]
  if {$inst eq "NULL" || ![string match *DFF* [[$inst getMaster] getName]]} {
    error "Frozen FF population/identity mismatch: $name"
  }
}
puts "GATE10A_FF_POPULATION $expected_ff_count"
set unmapped [open $outdir/unannotated_nets.tsv w]
puts $unmapped "net\ttype\titerms\tbterms\tfallback_density_per_ns"
foreach net [$block getNets] {
  set type [$net getSigType]
  if {$type in {POWER GROUND}} {continue}
  if {![dict exists $gate10a_annotated_nets [$net getName]]} {
    puts $unmapped "[$net getName]\t$type\t[llength [$net getITerms]]\t[llength [$net getBTerms]]\t0"
  }
}
close $unmapped
report_activity_annotation -report_unannotated > $outdir/activity_annotation.txt

# Preserve exact original PG geometry and derive the preregistered ideal sources.
set geo [open $outdir/pdn_geometry.tsv w]
puts $geo "net\ttype\tlayer\txmin_dbu\tymin_dbu\txmax_dbu\tymax_dbu\tvia"
set top_level -1
set top_shapes {}
foreach net [$block getNets] {
  if {[$net getSigType] ni {POWER GROUND}} {continue}
  foreach wire [$net getSWires] {
    foreach shape [$wire getWires] {
      set via ""
      set layer "VIA"
      if {[$shape isVia]} {
        set v [$shape getTechVia]
        if {$v eq "NULL"} {set v [$shape getBlockVia]}
        if {$v eq "NULL"} {error "Missing PG via identity"}
        set via [$v getName]
      } else {
        set tech_layer [$shape getTechLayer]
        set layer [$tech_layer getName]
        if {[$net getName] eq "VDD"} {
          set level [$tech_layer getRoutingLevel]
          if {$level > $top_level} {set top_level $level; set top_shapes {}}
          if {$level == $top_level} {
            lappend top_shapes [list [$shape xMin] [$shape yMin] [$shape xMax] [$shape yMax]]
          }
        }
      }
      puts $geo "[$net getName]\t[$net getSigType]\t$layer\t[$shape xMin]\t[$shape yMin]\t[$shape xMax]\t[$shape yMax]\t$via"
    }
  }
}
close $geo
if {![llength $top_shapes]} {error "No frozen VDD top stripe"}
set src [open $outdir/sources.csv w]
foreach box [lsort -integer -index 1 $top_shapes] {
  lassign $box x0 y0 x1 y1
  if {$x1 - $x0 <= $y1 - $y0} {error "Preregistered horizontal supply-stripe geometry mismatch"}
  set size [expr {double($y1 - $y0) / $dbu}]
  set y [expr {double($y1 + $y0) / (2 * $dbu)}]
  foreach x [list [expr {double($x0) / $dbu + $size/2}] [expr {double($x1) / $dbu - $size/2}]] {
    puts $src "[format %.17g $x],[format %.17g $y],[format %.17g $size],1.1"
  }
}
close $src
set_pdnsim_net_voltage -net VDD -voltage 1.1
set_pdnsim_net_voltage -net VSS -voltage 0.0
set_pdnsim_source_settings -external_resistance 0.0
check_power_grid -net VDD -error_file $outdir/connectivity_errors.txt

set powers [open $outdir/instance_power.csv w]
puts $powers "instance,x_um,y_um,master,physical_only,powered,liberty_modelled,internal_w,switching_w,leakage_w,total_w"
set sum_internal 0.0
set sum_switching 0.0
set sum_leakage 0.0
set powered_modelled_count 0
foreach inst [$block getInsts] {
  set name [$inst getName]
  set master [$inst getMaster]
  set master_name [$master getName]
  set physical_only [$master isFiller]
  if {[$master getType] in {CORE_WELLTAP CORE_SPACER}} {set physical_only 1}
  set powered 0
  foreach term [$inst getITerms] {
    if {[$term getSigType] eq "POWER" && [$term getNet] ne "NULL" && [[$term getNet] getName] eq "VDD"} {set powered 1}
  }
  set cells [get_cells -quiet $name]
  set liberty [get_lib_cells -quiet "*/$master_name"]
  set modelled [expr {[llength $cells] == 1 && [llength $liberty] == 1}]
  set internal 0.0
  set switching 0.0
  set leakage 0.0
  if {$modelled} {
    set values [sta::instance_power [lindex $cells 0] [sta::cmd_scene]]
    if {[llength $values] ni {3 4}} {error "Unexpected instance-power API tuple: $values"}
    lassign $values internal switching leakage
    if {$internal < 0 || $switching < 0 || $leakage < 0} {error "Negative instance power: $name"}
    set sum_internal [expr {$sum_internal + $internal}]
    set sum_switching [expr {$sum_switching + $switching}]
    set sum_leakage [expr {$sum_leakage + $leakage}]
    if {!$physical_only && !$powered} {error "Liberty powered cell missing VDD: $name"}
    if {!$physical_only && $powered} {incr powered_modelled_count}
  } elseif {!$physical_only} {
    error "Active cell lacks a unique Liberty model: $name $master_name"
  }
  lassign [$inst getLocation] x y
  set total [expr {$internal + $switching + $leakage}]
  puts $powers "$name,[format %.17g [expr {double($x)/$dbu}]],[format %.17g [expr {double($y)/$dbu}]],$master_name,$physical_only,$powered,$modelled,[format %.17g $internal],[format %.17g $switching],[format %.17g $leakage],[format %.17g $total]"
}
close $powers
puts "GATE10A_POWER_SI [format %.17g $sum_internal] [format %.17g $sum_switching] [format %.17g $sum_leakage]"
puts "GATE10A_POWERED_MODELED $powered_modelled_count"
report_power -digits 12 > $outdir/power_report.txt
report_power -digits 12 -format json > $outdir/power_report.json
analyze_power_grid -net VDD -vsrc $outdir/sources.csv -voltage_file $outdir/instance_voltage.csv -enable_em -em_outfile $outdir/segment_current.csv -error_file $outdir/solve_errors.txt
puts "GATE10A_MEASURE_COMPLETE"
