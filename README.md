# PACT- Physical-and ATPG-aware Co-optimization of Test architectures
Can an intervention-aware learning model jointly reason over physical-design state and ATPG-derived activity to predict the marginal impact of legal scan-architecture transformations, enabling closed-loop optimization of test power integrity, routability, timing, and test cost while preserving test quality by construction?

Modern scan insertion/scan architecture decisions are largely disconnected from downstream physical-design conditions and realistic ATPG-induced switching activity.

That leads directly to measurable problems:

    1. Test-mode IR-drop/power risk
    2. Routing congestion from scan chains
    3. Timing degradation
    4. Excessive scan wirelength
    5. Test time
    6. Poor physical locality
    7. Iterations between DFT and PD teams
