import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from phase0c_campaign_recover import eligible_cases  # noqa: E402
from phase0c_classify_recovery import detailed_classification  # noqa: E402


def test_recovery_eligibility_uses_frozen_matrix_order_and_status_only():
    campaign = {
        "designs": ["d0"], "physical_seeds": [11], "K_values": [1, 2],
        "route_families_each_K": ["B0", "P"], "native_B1_k1_method": "B1",
    }
    original = {"runs": {
        "d0/s11/k1/B0": {"status": "QUALIFIED"},
        "d0/s11/k1/P": {"status": "WORKSPACE_DISK_FLOOR_REACHED"},
        "d0/s11/k1/B1": {"status": "WORKSPACE_DISK_FLOOR_REACHED"},
        "d0/s11/k2/B0": {"status": "WORKSPACE_DISK_FLOOR_REACHED"},
        "d0/s11/k2/P": {"status": "ROUTE_FAILED"},
    }}
    assert eligible_cases(campaign, original, "WORKSPACE_DISK_FLOOR_REACHED") == [
        ("d0", 11, 1, "P"), ("d0", 11, 1, "B1"), ("d0", 11, 2, "B0")]


def test_detailed_classification_follows_frozen_gate_precedence():
    gates = {f"C{i}": {"status": "PASS"} for i in range(1, 10)}
    assert detailed_classification(gates).endswith("PHASE1_GO")
    gates["C9"]["status"] = "FAIL"
    gates["C3"]["status"] = "FAIL"
    assert detailed_classification(gates) == "MULTICHAIN_CONFLICT_NOT_ESTABLISHED_PHASE1_NO_GO"
