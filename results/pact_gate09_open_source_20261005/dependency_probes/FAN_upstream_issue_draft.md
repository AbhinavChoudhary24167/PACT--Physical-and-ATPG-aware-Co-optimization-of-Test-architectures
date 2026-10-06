At commit `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, a valid netlist using the supplied Nangate MDT library can overflow the ATPG event queues and simulate compound-cell primitives with the wrong arity.

Minimal netlist:
```verilog
module compound_scan(CK, test_si, test_se, a, b, c, e, y, test_so);
input CK, test_si, test_se, a, b, c, e;
output y, test_so;
wire d;
AOI211_X1 U_COMPOUND (.A(a), .B(b), .C1(c), .C2(e), .ZN(d));
SDFF_X1 U_FF (.CK(CK), .D(d), .Q(y), .SE(test_se), .SI(test_si));
assign test_so = y;
endmodule
```

After `read_lib techlib/mod_nangate45.mdt`, `read_netlist compound_scan.v`, `build_circuit --frame 1`, `set_fault_type saf`, `add_fault --all`, and enabling static compression, dynamic compression, and X-fill, `run_atpg` crashes. An AddressSanitizer/UBSan build reports a heap-buffer-overflow in `Atpg::pushGateFanoutsToEventStack`, called from `identifyGateDominator`.

`Circuit::createCircuitComb` calculates `circuitLvl_` from the first primitive of the last library cell. AOI211 expands into four primitives at different levels, so PO/PPO may precede a driver and the event queues are too short. Independently, `Circuit::determineGateType` uses `cell->getNPort()` to select AND/NAND/OR/NOR/XOR/XNOR arity. A two-input primitive inside AOI211 is consequently labeled as a four-input gate.

Expected behavior: construct levels for every primitive, preserve AOI211's `!(a | b | (c & e))` function, and run ATPG without an out-of-bounds access.

Minimal local repair: calculate `circuitLvl_` as two plus the maximum level of all constructed PI/PPI/combinational gates (minimum two), and use `pmt->getNPort()` rather than the enclosing cell's port count for primitive arity. No changes to ATPG search, fault extraction, compression, simulation algorithms, or library models are needed.

Focused regression results: on unmodified source, level-order/bounds, primitive-arity, and exhaustive 32 input/FF-state truth-table checks each fail. With the repair all three pass, and ATPG on this fixture passes under ASan/UBSan. An independent single-primitive scan fixture also passes before and after the repair.

Diagnostic build command:
```sh
make -j1 install MODE=dbg CFLAGS='-Wall -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer'
```

I can provide the focused patch and regression files if useful.
