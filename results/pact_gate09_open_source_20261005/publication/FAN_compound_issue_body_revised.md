Using the [upstream source](https://github.com/NTU-LaDS-II/FAN_ATPG/tree/26b2b36c0e9db11a4b6d9e759df6e44357121f39), compound cells in the supplied `techlib/mod_nangate45.mdt` expose three circuit-construction defects: incomplete level bounds, primitive arity selected from the enclosing cell, and receiver pins being added as drivers on shared internal nets.

Related context: #3 reports a build-circuit segmentation fault. I have not tested that issue's netlist, so this report does not diagnose its crash. The fixtures below isolate specific construction invariants.

### AOI211 + scan FF reproduction

Save as `compound_scan.v`:

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

With an ASan/UBSan build:

```sh
make -j1 install MODE=dbg CFLAGS='-Wall -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer'
```

Run these commands in FAN:

```text
read_lib techlib/mod_nangate45.mdt
read_netlist compound_scan.v
build_circuit --frame 1
set_fault_type saf
add_fault -a
set_static_compression on
set_dynamic_compression on
set_X-Fill on
run_atpg
report_statistics
```

Actual: ASan reports a heap-buffer-overflow in `Atpg::pushGateFanoutsToEventStack`, reached through `identifyGateDominator`. Separate construction checks show a PO/PPO level preceding a driving primitive, and incorrect compound-primitive arity.

Expected: every driver precedes its receiver in level order; all levels fit the event queues; functional simulation preserves `D = !(a | b | (c & e))` and current-state Q; ATPG completes without an out-of-bounds access.

The defects in `pkg/core/src/circuit.cpp` are:

1. `Circuit::createCircuitComb` sets `circuitLvl_` using only the first primitive of the last top-level cell. A library cell may contain multiple primitives at different levels. A minimal repair is:
   ```cpp
   circuitLvl_ = 2;
   for (int i = 0; i < numPI_ + numPPI_ + numComb_; ++i)
       if (circuitGates_[i].numLevel_ + 2 > circuitLvl_)
           circuitLvl_ = circuitGates_[i].numLevel_ + 2;
   ```
2. `Circuit::determineGateType` selects AND/NAND/OR/NOR/XOR/XNOR arity using `cell->getNPort()`. It should use `pmt->getNPort()` in those branches. For example, a two-input primitive within AOI211 is otherwise classified from the parent cell's larger port count.

Focused before/after checks: driver/receiver level order and bounds, primitive arity, and exhaustive 32 combinations of the four functional inputs plus FF state fail before these repairs and pass after them. The repaired AOI fixture also completes ATPG under ASan/UBSan. A separate single-primitive scan fixture passes before and after.

### Independent shared-net receiver reproduction

Save as `compound_mux.v`:

```verilog
module compound_mux(CK, test_si, test_se, a, b, s, y, test_so);
input CK, test_si, test_se, a, b, s;
output y, test_so;
wire d;
MUX2_X1 U_COMPOUND (.A(a), .B(b), .S(s), .Z(d));
SDFF_X1 U_FF (.CK(CK), .D(d), .Q(y), .SE(test_se), .SI(test_si));
assign test_so = y;
endmodule
```

In the supplied MDT model, S is shared by an AND input and an inverter input. `createCircuitPmt` enumerates the other pins on a primitive input net. When such a pin is neither an internal primitive output nor a public input, execution falls through with the initialized `faninID = 0`, appends that ID, and increments `numFI_`. Another receiving input is thereby treated as a driver.

The narrow repair is `else { continue; }` after the two legitimate driving-pin cases, before appending the fanin and reciprocal fanout. No library-model or simulation-algorithm changes are needed.

For an isolated comparison, hold the level and primitive-arity repairs above fixed on both sides, then add only this shared-net repair. Check:

- For each combinational primitive, `numFI_` equals the number of input ports in `cell->libc_->getCell(gate.primitiveId_)`.
- For all 16 combinations of a, b, s and FF state, functional `Simulator::goodSim()` gives PO = current Q and PPO = `s ? b : a`; check both `goodSimLow_` and `goodSimHigh_`.

Both checks fail before the shared-net repair (extra fanin and incorrect MUX/Q semantics) and pass after it.

These repairs change the constructed circuit to match the supplied library. They do not change ATPG search, compression, X-fill, or library models. Correcting connectivity can change the extracted fault universe, so comparison against a broken construction should not assume an unchanged fault count.
