# Stage-A runtime import blocker (R0)

The unchanged route adapter imports `pact.optimizer.io`, then `PlacedCosts`,
`phase2a_shift` (SciPy) and `optimizer.kernels` (Numba). System Python lacks
SciPy; the existing PACT virtual environment has the recorded NumPy 2.5.3 and
SciPy 1.18.1 but lacks the optional optimizer Numba dependency. These imports
occur before the route plan or any physical attempt is created. No optimizer
kernel is called by the route adapter.

Restore the existing PACT virtual environment and supply Numba 0.67.0 plus
llvmlite 0.49.0 in an owned D-backed import directory. Official Numba 0.67
supports NumPy 2.5: https://numba.readthedocs.io/en/latest/release/0.67.0-notes.html
No prior environment, algorithm, architecture, parameter, route command,
measurement source or common backend is changed. Wheels and versions are bound.
