# Candidate-sensitive physical model

Candidate orders change selected scan edges, endpoint ownership and shared functional/scan loads. PACT reconstructs candidate shared MMST geometry, calibrated from baseline ground capacitance, with pin loads separate. Buffers remain anchored to baseline topology. `candidate_physical.py` and `stateful_geometry.py` provide geometry; `candidate_sensitive.py` and `candidate_stateful.py` combine it with workload trajectories.

Settled logic traverses three nontransparent levels; BUF/INV do not consume depth. Simultaneous fanins, packed waveforms and Q/QN complementarity are preserved. Unknown fanins and depth-excluded regions are omitted and reported as coverage limits.

Routing/extraction measure the implemented vector independently. Candidate ground-capacitance error and omitted regions can change the decisive spatial maximum. Counterfactual substitutions are order-dependent because the maximum is nonlinear; they neither uniquely allocate causality nor validate a replacement model.

The primary E metric excludes coupling. Fixed buffers, bounded cones and zero-delay transitions remain limitations. Gate 10A adds frozen measured activity, Liberty power and static PDNSim under separately registered supply/duty assumptions. See [objectives](objectives.md).
