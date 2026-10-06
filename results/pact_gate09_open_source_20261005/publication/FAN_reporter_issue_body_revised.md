`ReportFaultCmd::exec` in `pkg/fan/src/atpg_cmd.cpp` can omit identities for compound-cell internal fault sites, and its primitive-input loop can resolve an internal input fault to a following output pin.

This is a reporting defect, separate from the compound circuit-construction defects in #5. For the comparisons below, the circuit construction and extracted fault classes are held identical between the old and new reporters.

### Minimal reproduction

Use the supplied `techlib/mod_nangate45.mdt` and save:

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

Apply the level/primitive-arity construction repairs described in #5 first, so ATPG on this fixture completes. Keep the same construction when comparing reporters.

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
report_fault
exit
```

Using the [upstream source](https://github.com/NTU-LaDS-II/FAN_ATPG/tree/26b2b36c0e9db11a4b6d9e759df6e44357121f39) with only those construction repairs applied, this reproduction prints 44 fault records, including eight unresolved compound internal identities. The count belongs to that specific construction; it is not claimed to remain identical after the separate shared-net connectivity correction.

A MUX2 + SDFF fixture also exposes duplicate public output names when an internal input does not connect to a public cell pin.

Expected: each fault site has a stable identity, using the public instance/pin identity when available and an internal primitive identity otherwise. Printing or filtering faults must preserve fault state and equivalence weight.

### Minimal repair

In `ReportFaultCmd::exec`:

1. In the primitive-input loop, immediately skip ports whose type is not `Port::INPUT`, then increment the input counter and match it to `pid`. Currently, a subsequent output port can retain the same counter value and be considered after the matching input.
2. Remember the selected primitive pin in both the input and output branches.
3. If no public cell port was resolved, print a stable `instance/primitive/pin` fallback. Retain the existing public-pin output format whenever a public pin exists.

For example:

```cpp
if (pmt->getPort(i)->type_ != Port::INPUT)
    continue;
++inCount;
if (inCount != pid)
    continue;
primitivePin = pmt->getPort(i);
```

And after the existing public-pin printing branch:

```cpp
else if (primitivePin) {
    std::cout << c->name_ << "/" << pmt->name_ << "/"
              << primitivePin->name_ << " ";
}
```

This change only names existing fault sites. It does not modify the fault extractor, ATPG generation, compression, circuit connectivity, fault state, or equivalence multiplicity.

### Focused checks

On identical corrected circuit construction, compare old and new reporters using the same fixed pattern file:

- Every record retains its fault state and equivalence weight; weighted totals and detected counts agree.
- Internal compound sites resolve to stable identities.
- Public identities remain unique and retain their existing names.
- Selected-state filtering returns the correct states and weighted totals.

The compound fixture checks fail for unresolved/duplicate identities before the reporting repair and pass afterward. The same comparisons pass on a fixed larger compound-cell pattern set, and a single-primitive s27 reporting control passes. AOI211 level/arity/truth checks and MUX shared-net fanin/truth checks also pass with the separately corrected construction.
