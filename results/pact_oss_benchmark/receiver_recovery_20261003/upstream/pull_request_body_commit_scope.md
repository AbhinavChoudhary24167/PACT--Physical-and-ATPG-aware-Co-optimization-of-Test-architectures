`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` call the non-static `sta::dbNetwork` methods `getLibertyScanIn()` and `getLibertyScanOut()` without an object receiver, causing compilation to fail.

Qualify both calls with the existing `db_network_` member. The diff contains only the two receiver qualifications and formatting of the affected return statements.
