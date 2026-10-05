#!/bin/bash
# Sequential scientific jobs, each with its own immutable worker receipts.
set -u
campaign_root=/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT
campaign_python=/root/pact-deps/pact-venv/bin/python
campaign_args=(--design b14_opt --source-admission "$campaign_root/results/pact_gate09_open_source_20261005/source_admission/b14_opt__mapped_library_models.json" --attempt python_transport --dependency-repair "$campaign_root/results/pact_gate09_open_source_20261005/dependency_repairs/FAN_ATPG/compound_reporter_qualification.json")
measurement_args=(--source-admission "$campaign_root/results/pact_gate09_open_source_20261005/source_admission/b14_opt__mapped_library_models.json" --attempt python_transport --dependency-repair "$campaign_root/results/pact_gate09_open_source_20261005/dependency_repairs/FAN_ATPG/compound_reporter_qualification.json")
for campaign_method in B4 B5; do
  "$campaign_python" "$campaign_root/scripts/pact_gate09_campaign.py" route --method "$campaign_method" "${campaign_args[@]}"
done
for campaign_method in B0 B1 B2 B4 B5; do
  "$campaign_python" "$campaign_root/scripts/pact_gate09_competitor_measure.py" prepare --method "$campaign_method" "${measurement_args[@]}"
  "$campaign_python" "$campaign_root/scripts/pact_gate09_competitor_measure.py" run --method "$campaign_method" "${measurement_args[@]}"
done
printf 'GATE09_BASELINE_DRIVER_TERMINAL\n'
