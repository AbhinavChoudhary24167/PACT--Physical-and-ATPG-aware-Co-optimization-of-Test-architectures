# Preserved upstream work

These exports protect local tool repairs during the 2026-10-08 storage campaign.
Each tool directory records its upstream URL, exact source HEAD, refs, dirty state
and patch basis in `provenance.json`. Local absolute paths are provenance, not
installation requirements. The original source trees remain intact.

FAN repair patches are binary-capable diffs from upstream
`26b2b36c0e9db11a4b6d9e759df6e44357121f39` to the named repaired HEAD.
Inspect the patch and choose its stated basis before applying it with `git apply
--check`; the similarly named repairs can overlap and should not be stacked
without review. The base FAN tree has generated PAT/STIL/RPT modifications, not
an additional source repair; their diff is retained locally under
`cleanup/local/` with a SHA256 recorded in its provenance.

`build-image/` contains the small exported changes detected while the inactive
build image was mounted read-only. Its source checkout/submodule arrangement
has not been fully reconciled. The complete lossless image archive therefore
remains the recovery authority; these small patches alone are not asserted to
replace it. See [archive index](../../archives/MANIFEST.csv) and
[upstream documentation](../../docs/upstream.md).

Exports do not imply that a repair has been accepted or merged upstream.
