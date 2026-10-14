from copy import deepcopy
import json
from unittest.mock import Mock
import pytest
from app.repair.executor import RepairExecutor
from app.repair.verifier import verify_spooler
from app.reports import AuditLog


def execute(snapshot, tmp_path, *, source="live", status="stopped", start_type="manual",
            approved=False, dry_run=False, admin=True, action="start_print_spooler", eligible=True, audit=None):
    snapshot["source"] = source
    state = {"status": status, "start_type": start_type, "error": None}
    snapshot["services"]["Spooler"] = deepcopy(state)
    def start():
        state["status"] = "running"
    starter = Mock(side_effect=start)
    reader = Mock(side_effect=lambda: deepcopy(state))
    executor = RepairExecutor(audit or AuditLog(tmp_path / "audit.jsonl"), reader, starter, lambda: admin,
                              demo=source == "demo")
    result = executor.execute(action, snapshot=snapshot, scan_id="test", eligible=eligible,
                              approved=approved, dry_run=dry_run)
    return result, starter, reader


@pytest.mark.parametrize("changes", [
    {}, {"approved": "yes"}, {"approved": True, "admin": False},
    {"approved": True, "start_type": "disabled"}, {"approved": True, "start_type": "unknown"},
    {"approved": True, "status": "unknown"}, {"approved": True, "action": "run_powershell"},
    {"approved": True, "eligible": False},
])
def test_policy_prevents_unapproved_or_unsafe_mutations(snapshot, tmp_path, changes):
    result, starter, _ = execute(snapshot, tmp_path, **changes)
    assert result["status"] == "blocked"
    starter.assert_not_called()


def test_dry_run_never_mutates_even_when_approved(snapshot, tmp_path):
    result, starter, _ = execute(snapshot, tmp_path, approved=True, dry_run=True)
    assert result["status"] == "dry_run" and not result["verified"]
    starter.assert_not_called()


def test_approved_fixed_action_gets_fresh_verification_and_audit(snapshot, tmp_path):
    result, starter, reader = execute(snapshot, tmp_path, approved=True)
    assert result["verified"] and result["before"]["status"] == "stopped" and result["after"]["status"] == "running"
    starter.assert_called_once_with()
    assert reader.call_count >= 2
    rows = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["repair_requested", "repair_authorized", "repair_finished"]


def test_demo_never_touches_host_functions(snapshot, tmp_path):
    result, starter, reader = execute(snapshot, tmp_path, source="demo", approved=True, admin=False)
    assert result["simulated"] and result["verified"]
    starter.assert_not_called()
    reader.assert_not_called()


def test_state_race_already_running_does_not_start(snapshot, tmp_path):
    result, starter, _ = execute(snapshot, tmp_path, status="running", approved=True)
    assert result["status"] == "not_needed"
    starter.assert_not_called()


@pytest.mark.parametrize("fail_on", [1, 2])
def test_audit_failure_blocks_mutation(snapshot, tmp_path, fail_on):
    audit = Mock()
    audit.append.side_effect = [OSError("full disk")] if fail_on == 1 else [None, OSError("full disk"), None]
    result, starter, _ = execute(snapshot, tmp_path, approved=True, audit=audit)
    starter.assert_not_called()
    assert not result["verified"]


def test_final_audit_failure_does_not_hide_verified_outcome(snapshot, tmp_path):
    audit = Mock()
    audit.append.side_effect = [None, None, OSError("full disk")]
    result, starter, _ = execute(snapshot, tmp_path, approved=True, audit=audit)
    assert result["verified"] and result["audit_error"]
    starter.assert_called_once()


def test_verification_failure_is_not_success():
    success, after = verify_spooler(lambda: {"status": "stopped"}, timeout=0)
    assert not success and after["status"] == "stopped"
    success, after = verify_spooler(Mock(side_effect=RuntimeError("denied")), timeout=0)
    assert not success and "denied" in after["error"]


def test_timeout_after_mutation_still_verifies(snapshot, tmp_path):
    snapshot["source"] = "live"
    state = {"status": "stopped", "start_type": "manual", "error": None}
    def timed_out_start():
        state["status"] = "running"
        raise TimeoutError("SCM response lost")
    executor = RepairExecutor(AuditLog(tmp_path / "audit.jsonl"), lambda: deepcopy(state),
                              timed_out_start, lambda: True)
    result = executor.execute("start_print_spooler", snapshot=snapshot, scan_id="test",
                              eligible=True, approved=True, dry_run=False)
    assert result["status"] == "verified_with_warning"
    assert result["verified"] and result["after"]["status"] == "running"
    assert "SCM response lost" in result["execution_error"]


def test_snapshot_cannot_override_session_mode(snapshot, tmp_path):
    snapshot["source"] = "live"
    host = Mock(side_effect=AssertionError("Demo touched host"))
    executor = RepairExecutor(AuditLog(tmp_path / "audit.jsonl"), host, host, host, demo=True)
    result = executor.execute("start_print_spooler", snapshot=snapshot, scan_id="test",
                              eligible=True, approved=True, dry_run=False)
    assert not result["verified"]
    host.assert_not_called()

