# B3 receiver-only compile repair

Exact B2 is unchanged and already built/qualified. The defect is in B3 PR #10666,
base `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. The original failure is preserved.

`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` invoke nonstatic
`sta::dbNetwork` members as unqualified functions. The declarations are already
included in dbNetwork.hh:436–437; adding another package/header cannot supply an
object receiver. Existing methods use `db_network_->` at lines48,58,69,74,79.

The OneBitScanCell constructor stores its supplied STA network. ScanCellFactory
obtains `sta->getDbNetwork()`, derives the TestCell from the same live network,
rejects invalid TestCells and passes that network to the cell. OpenRoad creates
STA before DFT; scan architecture/optimization runs synchronously with that STA.
The network lives until STA teardown. No ownership, lifetime or API change occurs.

The patch adds only `db_network_->` to the two existing calls. It changes no
clustering, scan ordering, cost, parameters, NN/2-Opt/3-Opt, endpoint semantics,
DFT/database behavior or formatting outside those immediate calls. B3R is the
separately labeled derivative; it is never reported as byte-exact B3.
