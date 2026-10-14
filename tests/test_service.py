import json
from unittest.mock import Mock
import pytest
from app.service import GuardianService
from app.__main__ import main


def test_demo_end_to_end_no_host_calls_and_persistent_reports(tmp_path, monkeypatch):
    import app.collectors.windows as windows
    for name in ("get_spooler_status", "start_spooler", "is_admin"):
        monkeypatch.setattr(windows, name, Mock(side_effect=AssertionError("Demo touched host")))
    service = GuardianService(tmp_path, demo=True)
    # Even an edited/mislabeled fixture must stay in the session's demo mode.
    service._demo_snapshot["source"] = "live"
    scanned = service.scan()
    assert scanned["snapshot"]["source"] == "demo"
    assert len(scanned["findings"]) == 3
    preview = service.repair("start_print_spooler")
    assert preview["status"] == "dry_run"
    blocked = service.repair("start_print_spooler", dry_run=False)
    assert blocked["status"] == "blocked"
    repaired = service.repair("start_print_spooler", dry_run=False, approved=True)
    assert repaired["verified"] and repaired["simulated"]
    saved = json.loads(open(service.last_result["report_paths"]["json"], encoding="utf-8").read())
    assert saved["snapshot"]["services"]["Spooler"]["status"] == "stopped"  # original evidence
    assert len(saved["repairs"]) == 3 and saved["repairs"][-1]["after"]["status"] == "running"
    assert "spooler_stopped" not in {f["id"] for f in service.scan()["findings"]}


def test_repair_requires_scan(tmp_path):
    with pytest.raises(ValueError, match="Scan"):
        GuardianService(tmp_path, demo=True).repair("start_print_spooler")


def test_cli_demo_and_hailo_disclosure(tmp_path, capsys):
    assert main(["--demo", "--cli", "--repair", "--data-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["repairs"][0]["dry_run"]
    assert main(["--demo", "--cli", "--backend", "hailo", "--data-dir", str(tmp_path)]) == 1
    assert "not implemented" in capsys.readouterr().err


def test_noninteractive_execute_rejected(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["--demo", "--cli", "--repair", "--execute", "--data-dir", str(tmp_path)]) == 1
    assert "interactive" in capsys.readouterr().err

