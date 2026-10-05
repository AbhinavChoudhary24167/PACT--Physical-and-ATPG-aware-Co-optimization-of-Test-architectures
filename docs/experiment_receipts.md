# Atomic experiment receipts

`scripts/pact_experiment_receipts.py` provides lifecycle evidence independently of optimizer policy. `atomic_write` synchronizes a temporary JSON file before replacing the destination. Immutable publication uses exclusive creation, so an existing event cannot be overwritten.

`LaneReceipts` records REGISTERED, STARTED, CHECKPOINTED, COMPLETED, FAILED and INTERRUPTED transitions. Completion requires an explicit complete search receipt. Terminal records cannot transition again; later worker failures leave completed lanes intact. Failure/interruption handling retains the last checkpoint and leaves unstarted lanes registered.

Resource observations record process identity, timestamps, memory and operating-system uptime or boot identity. Disk targets are caller-supplied and default to the current workspace volume, without a machine-specific drive layout.

```python
from pact_experiment_receipts import LaneReceipts

lanes = LaneReceipts(output_dir, registration, disk_paths={"scratch": scratch_root})
lanes.transition(epsilon, "REGISTERED")
lanes.transition(epsilon, "STARTED")
lanes.transition(epsilon, "CHECKPOINTED", last_checkpoint=checkpoint)
lanes.transition(epsilon, "COMPLETED", completion_receipt=complete_result, exit_code=0)
```

The supervising caller supplies its complete result and measured exit/timeout evidence. A disappeared process alone never establishes completion or OOM.

The continuation qualifier now uses one configurable `ACTIVITY_OUT` for both the activity workflow and final aggregation. A caller can select a separate campaign namespace without changing search or activity definitions. The default retains the established continuation layout.
