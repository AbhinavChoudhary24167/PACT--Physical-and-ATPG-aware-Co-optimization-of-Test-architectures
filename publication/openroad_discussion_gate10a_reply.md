# Draft OpenROAD discussion response — not posted

b14_opt CS_C1 versus B3T: H8 -5.68763%, dynamic power -0.232057%, worst static VDD drop -0.401606% (-0.003 mV), p99 drop -0.00137429%; b15_opt CS_C1 versus B2: H8 -1.68276%, dynamic power -0.822562%, worst static VDD drop -0.703606% (-0.008 mV), p99 drop -0.980392%. Complete admissible evidence meets neither the material PI benefit nor spatial correspondence criterion. These are observed responses of an activity-derived static model; transient droop and thermal hotspot improvement were not evaluated.

Established: frozen Gate 09 activity and routed-wire differences. Observed: qualified Gate 10A architecture responses in the supplied tables, when available. Approximate: fixed-duty activity-derived OpenSTA power and static VDD PDNSim under ideal stripe-end supplies. Not evaluated: transient scan droop, thermal hotspots, ground bounce, package effects and signoff reliability.

Classification: `PACT_GATE10A_NO_MATERIAL_PHYSICAL_IMPACT`. Development recommendation: **FREEZE**. The full data and provenance are in `reports/gate10a/report.md` and its linked CSV/JSON records.
