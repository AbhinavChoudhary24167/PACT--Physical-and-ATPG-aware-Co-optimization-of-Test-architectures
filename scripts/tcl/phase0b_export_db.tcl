read_db $::env(PACT_PHASE0B_EXPORT_ODB)
write_def "$::env(PACT_PHASE0B_EXPORT_OUT)/placed.def"
write_verilog "$::env(PACT_PHASE0B_EXPORT_OUT)/placed.v"
