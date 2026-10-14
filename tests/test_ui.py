"""Offscreen safety and lifecycle checks; no host services are changed."""

from __future__ import annotations

import copy
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import MainWindow


class FakeService:
    def __init__(self) -> None:
        self.last_result = None
        self.calls = []
        self.delay = 0

    def scan(self) -> dict:
        time.sleep(self.delay)
        self.last_result = {
            "scan_id": "gui-test-scan",
            "snapshot": {},
            "backend": {"name": "mock"},
            "findings": [{
                "id": "spooler_stopped",
                "title": "列印服務停止",
                "severity": "warning",
                "evidence": ["Spooler: Stopped"],
                "recommendation": "先預演，再批准啟動服務。",
                "action_id": "start_print_spooler",
            }],
            "repairs": [],
            "report_paths": {},
        }
        return copy.deepcopy(self.last_result)

    def repair(self, action_id: str, *, dry_run: bool, approved: bool) -> dict:
        self.calls.append((action_id, dry_run, approved))
        repair = {
            "status": "dry_run" if dry_run else "success",
            "message": "預演完成。" if dry_run else "模擬修復已驗證。",
            "dry_run": dry_run,
            "simulated": True,
            "verified": not dry_run,
        }
        self.last_result["repairs"].append(repair)
        if not dry_run:
            self.last_result["findings"] = []
        return repair

    def export(self) -> dict:
        return {}


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def wait_until_idle(window: MainWindow, *, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while window.busy and time.monotonic() < deadline:
        QTest.qWait(10)
    assert not window.busy, "Background operation did not finish"
    QApplication.processEvents()


@pytest.fixture
def scanned_window(qt_app):
    service = FakeService()
    window = MainWindow(service, demo=True)
    window.show()
    window.scan()
    wait_until_idle(window)
    yield window, service
    wait_until_idle(window)
    window.close()
    QApplication.processEvents()


def test_dry_run_is_default_and_does_not_grant_approval(scanned_window, monkeypatch):
    window, service = scanned_window

    def unexpected_prompt(*args, **kwargs):
        pytest.fail("Dry-run should not ask for mutation approval")

    monkeypatch.setattr(QMessageBox, "question", unexpected_prompt)
    assert window.dry_run_checkbox.isChecked()
    assert window.repair_button.isEnabled()
    QTest.mouseClick(window.repair_button, Qt.MouseButton.LeftButton)
    wait_until_idle(window)
    assert service.calls == [("start_print_spooler", True, False)]
    assert window.verified_count.text() == "0"


def test_cancel_never_calls_repair_and_confirmation_defaults_to_no(scanned_window, monkeypatch):
    window, service = scanned_window
    prompts = []

    def reject(*args):
        prompts.append(args)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", reject)
    window.dry_run_checkbox.setChecked(False)
    QTest.mouseClick(window.repair_button, Qt.MouseButton.LeftButton)
    assert service.calls == []
    assert len(prompts) == 1
    assert prompts[0][-1] == QMessageBox.StandardButton.No
    assert "佇列中的文件可能立即列印" in prompts[0][2]
    assert "服務會保持執行" in prompts[0][2]
    assert "未送出" in window.status_label.text()


def test_each_execution_requires_explicit_confirmation(scanned_window, monkeypatch):
    window, service = scanned_window
    prompts = []

    def approve(*args):
        prompts.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", approve)
    window.dry_run_checkbox.setChecked(False)
    window.request_repair()
    wait_until_idle(window)
    assert len(prompts) == 1
    assert service.calls == [("start_print_spooler", False, True)]
    assert window.dry_run_checkbox.isChecked(), "Approval must not persist"
    assert not window.repair_button.isEnabled()
    assert window.verified_count.text() == "1"
    assert "模擬執行" in window.audit_view.toPlainText()


def test_unrecognized_action_is_not_exposed(scanned_window):
    window, service = scanned_window
    result = copy.deepcopy(service.last_result)
    result["findings"][0]["action_id"] = "arbitrary_shell_command"
    window._render_result(result)
    assert not window.repair_button.isEnabled()
    window.request_repair()
    assert service.calls == []


def test_scan_runs_in_background_and_close_waits_for_completion(qt_app):
    service = FakeService()
    service.delay = 0.15
    window = MainWindow(service, demo=True)
    window.show()
    started = time.monotonic()
    window.scan()
    assert time.monotonic() - started < 0.10
    assert window.busy
    assert not window.scan_button.isEnabled()
    assert not window.repair_button.isEnabled()
    window.close()
    assert window.isVisible(), "Closing must wait for an in-flight operation"
    wait_until_idle(window)
    assert not window.isVisible()
    assert window._thread is None


def test_service_error_restores_controls(qt_app):
    class BrokenService(FakeService):
        def scan(self):
            raise RuntimeError("collection unavailable")

    window = MainWindow(BrokenService(), demo=True)
    window.show()
    window.scan()
    wait_until_idle(window)
    assert "collection unavailable" in window.status_label.text()
    assert window.scan_button.isEnabled()
    assert not window.repair_button.isEnabled()
    window.close()


def test_failed_rescan_invalidates_old_repair_offer(scanned_window, monkeypatch):
    window, service = scanned_window

    def fail_scan():
        raise RuntimeError("rescan unavailable")

    monkeypatch.setattr(service, "scan", fail_scan)
    window.scan()
    wait_until_idle(window)
    assert not window.repair_button.isEnabled()
    window.request_repair()
    assert service.calls == []


def test_actual_demo_service_reports_and_verified_action(qt_app, tmp_path, monkeypatch):
    from app.collectors import windows
    from app.service import GuardianService

    def host_access_forbidden(*args, **kwargs):
        pytest.fail("Demo GUI must never inspect or mutate host services")

    monkeypatch.setattr(windows, "get_spooler_status", host_access_forbidden)
    monkeypatch.setattr(windows, "start_spooler", host_access_forbidden)
    monkeypatch.setattr(windows, "is_admin", host_access_forbidden)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    service = GuardianService(data_dir=tmp_path, demo=True, network_probe=False)
    window = MainWindow(service, demo=True, network_probe=False)
    window.show()
    try:
        window.scan()
        wait_until_idle(window)
        assert window.issue_count.text() == "3"
        assert "未連線探測" in window.backend_label.text()
        window.request_repair()
        wait_until_idle(window)
        assert service.last_result["repairs"][-1]["dry_run"] is True
        assert window.repair_button.isEnabled()
        window.dry_run_checkbox.setChecked(False)
        window.request_repair()
        wait_until_idle(window)
        repair = service.last_result["repairs"][-1]
        assert repair["verified"] is True
        assert repair["simulated"] is True
        assert repair["approved"] is True
        assert window.issue_count.text() == "2"
        assert window.verified_count.text() == "1"
        assert not window.repair_button.isEnabled()
        assert window.dry_run_checkbox.isChecked()
        assert len(service.last_result["findings"]) == 3, "Keep original evidence in report"
        from pathlib import Path
        assert all(Path(path).is_file() for path in service.last_result["report_paths"].values())
        window.scan()
        wait_until_idle(window)
        assert window.issue_count.text() == "2"
        assert not window.repair_button.isEnabled()
    finally:
        wait_until_idle(window)
        window.close()
