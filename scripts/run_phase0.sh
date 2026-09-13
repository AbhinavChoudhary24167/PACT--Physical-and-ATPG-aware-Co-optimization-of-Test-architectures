#!/usr/bin/env bash
# Reproduce the qualified s5378 subset. The full Phase-0 success gate needs a
# second design or multiple physical seeds and a routed activity-aware order.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${PACT_VENV:?Set PACT_VENV to a Python environment with pyproject dependencies}"
: "${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT to the pinned ORFS checkout}"
: "${PACT_FAN_ATPG_ROOT:?Set PACT_FAN_ATPG_ROOT to the pinned FAN_ATPG checkout}"

test "$(git -C "$PACT_ORFS_ROOT" rev-parse HEAD)" = 5e8b1450d19263f797a27c4f371b9dd19f32a3aa
test "$(git -C "$PACT_FAN_ATPG_ROOT" rev-parse HEAD)" = 26b2b36c0e9db11a4b6d9e759df6e44357121f39
cd "$ROOT"
bash scripts/run_tests.sh
timeout 30s "$PACT_VENV/bin/python" scripts/translate_s5378.py
bash scripts/run_orfs_smoke.sh
bash scripts/export_orfs_placement.sh
timeout 30s "$PACT_VENV/bin/python" scripts/establish_s5378_identity.py
bash scripts/run_orfs_route_smoke.sh
PACT_ORFS_VARIANT=base bash scripts/collect_orfs_route_metrics.sh
bash scripts/run_metric_smoke.sh
bash scripts/rewire_orfs_nearest.sh
timeout 30s "$PACT_VENV/bin/python" scripts/verify_rewire_s5378.py
bash scripts/run_orfs_nearest_route.sh
PACT_ORFS_VARIANT=nearest_neighbor bash scripts/collect_orfs_route_metrics.sh
bash scripts/run_metric_campaign.sh
bash scripts/run_cli_checks.sh
printf '%s\n' 'Observed subset reproduced. Full Phase-0 gate remains open: G5/G7 and physical activity-order routing.' >&2
exit 2
