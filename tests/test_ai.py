import pytest
from app.ai.analyzer import Analyzer, validate_output
from app.diagnosis import diagnose


@pytest.mark.parametrize("output", [
    {"summary": "Run this", "diagnoses": [], "command": "Remove-Item C:\\"},
    {"summary": "bad", "diagnoses": [{"finding_id": "spooler_stopped", "action_id": "delete_files"}]},
    {"summary": "bad", "diagnoses": [{"finding_id": "invented", "action_id": "start_print_spooler"}]},
    {"summary": "bad", "diagnoses": [{"finding_id": "disk_low_0", "action_id": "start_print_spooler"}]},
    {"summary": "bad", "diagnoses": [{"finding_id": "spooler_stopped", "action_id": "start_print_spooler", "args": ["other_service"]}]},
    {"summary": "bad", "diagnoses": [{"finding_id": ["malformed"], "action_id": None}]},
])
def test_backend_rejects_arbitrary_commands_and_unsupported_actions(snapshot, output):
    with pytest.raises(ValueError):
        validate_output(output, diagnose(snapshot))


def test_backend_failure_leaves_trusted_rules_with_disclosure(snapshot):
    class Broken:
        name = "test-malformed"
        def infer(self, evidence):
            evidence["findings"][0]["action_id"] = "delete_files"
            raise RuntimeError("unavailable")
    findings, metadata = Analyzer(Broken()).analyze(snapshot)
    assert metadata["status"] == "rejected"
    assert findings[0]["action_id"] == "start_print_spooler"


def test_hailo_fails_explicitly():
    from app.ai.hailo_backend import HailoBackend
    with pytest.raises(NotImplementedError, match="not implemented"):
        HailoBackend()

