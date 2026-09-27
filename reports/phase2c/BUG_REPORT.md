# Phase-2C mandatory stop: inherited SI/SO graph mismatch

**Status: STOPPED_LEGACY_DEFINITION_BUG. No valid Phase-2C generalization classification.**

The experiment stopped under the user's explicit instruction: “If a bug is found,
stop and document it before changing the experiment.” The same rule was frozen
in section K of EXPERIMENT_CONTRACT.md. This is a demonstrated discrepancy between
the inherited contract and implementation, not a measured failure of M3 or M5
to generalize and not a tool/infrastructure outage.

## Concrete reproducer and cause

In the frozen s5378 seed-11 P architecture, `output38` (BUF_X1) originally has
its A input on `n1588gat`, driven by `U_n1588gat`. The selected chain-0 tail is
`U_n2121gat`. The frozen routed physical inventory assigns `output38` to
`U_n2121gat`, as required by the actual rewiring code.

However, Phase-2B's placed graph retains the `output38/A` sink and `test_so`
transparent child beneath `n1588gat`. The exporter removes the output BTerm,
but not the original scan-output buffer input/branch. `construct_weights`
then adds tail-to-SO geometry with `master=None`, so it does not move that
buffer input capacitance or branch to the selected tail.

- `scripts/phase2b_extract.py:placed_graph`: skips test_si/test_so BTerms, but
  only filters FF SI ITerms from sinks; transparent output-buffer branches remain.
- `src/pact/analysis/phase2b_loads.py:construct_weights`: traverses those original
  roots/branches, then adds direct selected-tail output geometry without a pin load.
- `scripts/phase0c_rewire_odb.py:rewire`: explicitly disconnects output-buffer A
  and reconnects it to the selected chain-0 tail.

This contradicts the contract's removal of original SI/SO connections before
constructing the selected architecture graph. It affects both the ownership
of M3 input-pin load and the M5 tree geometry. It does **not** establish the
magnitude or sign of any correlation change after correction. No corrected
metric, coefficient, graph rule, waveform or historical result was substituted.

The read-only audit reproduces the owner mismatch in all 21 frozen architectures:

| Design | Original source FF | Output buffer | Pin load fF | Frozen architectures with mismatched owner |
|---|---|---|---:|---:|
| s5378 | U_n1588gat | output38 | 0.974659 | 9/9 |
| s9234 | U_g59 | output67 | 0.974659 | 6/6 |
| s15850 | U_g73 | output196 | 0.974659 | 6/6 |

Run the audit with the existing OpenROAD Python environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python openroad -python -no_init -exit scripts/phase2c_bug_audit.py
```

`legacy_bug_audit.json` records all concrete instance/net/owner identities, graph,
ODB and physical-inventory hashes. It reads prior evidence only. Reproduction
does not invoke routing, extraction, ATPG or an optimizer.

## Why the previous checks did not catch it

Phase-2B's reported correlations, architecture orders and pairwise comparisons
reproduce exactly; the frozen hashes pass. Event and packed evaluators also
agree for the supplied weights. Both numerical checks can succeed while sharing
the same upstream graph error. The missing test is selected-SO-buffer ownership
against the actual pre-route rewiring semantics, not another correlation threshold.

## Disposition

The source and Phase-2B artifacts remain unchanged. Completed Phase-2C physical
evidence is retained as provisional; ongoing process trees were terminated at
the stop. No failed seed is replaced. New scientific execution is guarded
against accidental resume while this audit exists.

A separately authorized correction must first resolve whether the stated metric
is intended to follow actual selected-architecture SO buffer connectivity or to
be a deliberately different approximation. It must preserve the original result,
document the correction, and create a new freeze before new correlation analysis.
Do not relabel this stop as GENERALIZATION_FAIL or INFRASTRUCTURE_BLOCKED.
