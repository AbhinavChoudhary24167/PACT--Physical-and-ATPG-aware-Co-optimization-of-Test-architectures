# Floating reduction audit

Attempt 1 remains PACT_PHASE2CR_TOPOLOGY_FAIL; scientific results were not evaluated. It stopped correctly under the preregistered rule. Original files and source are preserved under attempt1/; witness.log is unchanged.

The exact assertion at attempt1/phase2cr_run.py:148 compared lhs `66.95` (built-in sum) with rhs `66.94999999999999` (predictor). Absolute difference: 1.4210854715202004e-14 um; relative difference: 2.1226071269905908e-16.

Both paths use the same net order: ['n2121gat', 'test_so', 'n2119gat'], and the same operands: [34.699999999999996, 15.750000000000002, 16.5]. Every operand was independently recomputed from its emitted point set. Operands and sequential accumulator are Python binary64 floats; the stored predictor is NumPy float64. CPython 3.12 built-in sum uses compensated float summation; the predictor uses ordered sequential += from 0.0. The sequential partial sums are [34.699999999999996, 50.449999999999996, 66.94999999999999], reproducing the predictor exactly.

Thus only the floating reduction algorithm/association differs, not traversal order, topology, point sets, or predictor definition. The authorized fix is ordered sequential witness addition. Independent numeric reductions use only rtol=1e-12, atol=1e-10; structural checks stay exact. No scientific/predictor source is changed. See float_reduction_audit.json for operands, types, hex values, source hashes and full points.

Authorized continuation: corrected_audit_witness_status = PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS. Initial witness remains FAIL / FLOAT_REDUCTION_ORDER.
