# Read-only capability probe: no design is loaded and no placement is run.
puts "PHASE2D_GLOBAL_PLACEMENT_HELP"
help global_placement
puts "PHASE2D_GLOBAL_PLACEMENT_BODY"
puts [info body global_placement]
puts "PHASE2D_RANDOM_SEED_COMMANDS"
puts [info commands *seed*]
puts [info commands gpl::*seed*]
puts [info commands gpl::*random*]
exit
