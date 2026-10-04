# Junction handling

The pre-cleanup checkout byte measurement includes files visible through Windows junctions (unlike symbolic links). They are logical accessible bytes, not exclusively bytes allocated within this directory. External targets were not deleted. Minimal retained inputs were copied into real repository directories, then only each junction was removed. The external original remains outside the checkout. Therefore the checkout reduction is a logical repository-size reduction and must not be interpreted as freed disk space.

Removed junctions:

- `reports/physical_effect/s15850`
