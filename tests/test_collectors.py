"""Collector tests never call the network, Windows services, or Event Log."""

from datetime import datetime, timezone
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.collectors import system, windows


class WindowsCollectorTests(unittest.TestCase):
    def test_service_status_maps_state_and_startup_type(self):
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows, "_run_powershell", return_value='{"State":"Stopped","StartMode":"Auto"}'
        ) as run:
            self.assertEqual(
                windows.get_spooler_status(),
                {"status": "stopped", "start_type": "automatic", "error": None},
            )
            run.assert_called_once_with("service_status")

    def test_service_collection_failure_is_unknown(self):
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows, "_run_powershell", side_effect=RuntimeError("Access denied")
        ):
            result = windows.get_spooler_status()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["start_type"], "unknown")
        self.assertIn("Access denied", result["error"])

    def test_unrecognized_or_invalid_service_data_never_implies_running(self):
        for data in ('null', '[]', '{"State":"garbage","StartMode":"Auto"}', '{bad json'):
            with self.subTest(data=data), patch.object(windows.platform, "system", return_value="Windows"), patch.object(
                windows, "_run_powershell", return_value=data
            ):
                result = windows.get_spooler_status()
            self.assertEqual(result["status"], "unknown")
            self.assertTrue(result["error"])

    def test_non_windows_service_collection_is_explicitly_unavailable(self):
        with patch.object(windows.platform, "system", return_value="Linux"), patch.object(windows, "_run_powershell") as run:
            result = windows.get_spooler_status()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("requires Windows", result["error"])
        run.assert_not_called()

    def test_powershell_has_fixed_argument_vector_timeout_and_no_shell(self):
        response = SimpleNamespace(returncode=0, stdout='{"State":"Running","StartMode":"Auto"}', stderr="")
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows.subprocess, "run", return_value=response
        ) as run:
            windows._run_powershell("service_status")
        argv = run.call_args.args[0]
        self.assertIsInstance(argv, list)
        self.assertIn("-NoProfile", argv)
        self.assertIn("-NonInteractive", argv)
        self.assertIn("Get-CimInstance", argv[-1])
        self.assertNotIn("Start-Service", argv[-1])
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.kwargs["timeout"], windows.POWERSHELL_TIMEOUT_SECONDS)

    def test_arbitrary_powershell_operation_is_rejected_without_process(self):
        with patch.object(windows.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                windows._run_powershell("Start-Service AnythingElse; arbitrary text")
        run.assert_not_called()

    def test_start_preconditions_refuse_disabled_running_and_unknown_services(self):
        cases = (
            {"status": "stopped", "start_type": "disabled", "error": None},
            {"status": "running", "start_type": "automatic", "error": None},
            {"status": "unknown", "start_type": "unknown", "error": "Access denied"},
        )
        for state in cases:
            with self.subTest(state=state), patch.object(windows.platform, "system", return_value="Windows"), patch.object(
                windows, "is_admin", return_value=True
            ), patch.object(windows, "get_spooler_status", return_value=state), patch.object(windows, "_run_powershell") as run:
                with self.assertRaises(RuntimeError):
                    windows.start_spooler()
            run.assert_not_called()

    def test_start_refuses_non_elevated_session(self):
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows, "is_admin", return_value=False
        ), patch.object(windows, "_run_powershell") as run:
            with self.assertRaisesRegex(RuntimeError, "elevated"):
                windows.start_spooler()
        run.assert_not_called()

    def test_start_only_calls_fixed_operation_after_recheck(self):
        before = {"status": "stopped", "start_type": "manual", "error": None}
        after = {"status": "running", "start_type": "manual", "error": None}
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows, "is_admin", return_value=True
        ), patch.object(windows, "get_spooler_status", side_effect=[before, after]), patch.object(windows, "_run_powershell") as run:
            result = windows.start_spooler()
        self.assertEqual(result, after)
        run.assert_called_once_with("start_spooler")

    def test_windows_dns_invalid_result_or_timeout_is_unknown(self):
        with patch.object(windows, "_run_powershell", return_value='{"resolved":"true"}'):
            self.assertIsNone(windows.probe_system_dns()[0])
        with patch.object(windows, "_run_powershell", side_effect=RuntimeError("Timeout")):
            self.assertIsNone(windows.probe_system_dns()[0])
        with patch.object(windows, "_run_powershell", return_value='{"resolved":false}'):
            self.assertFalse(windows.probe_system_dns()[0])

    def test_events_are_bounded_and_exclude_sensitive_messages(self):
        event = SimpleNamespace(
            EventType=1,
            EventID=0xC0001234,
            TimeGenerated=datetime(2026, 1, 1, tzinfo=timezone.utc),
            SourceName="Test source",
            StringInserts=["sensitive user path"],
        )
        event_log = MagicMock()
        event_log.EVENTLOG_BACKWARDS_READ = 8
        event_log.EVENTLOG_SEQUENTIAL_READ = 1
        event_log.ReadEventLog.return_value = [event] * 100
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows.importlib, "import_module", return_value=event_log
        ):
            events, errors = windows.collect_recent_events()
        self.assertEqual(len(events), windows.MAX_EVENTS)
        self.assertEqual(events[0]["id"], 0x1234)
        self.assertEqual(events[0]["message"], windows.EVENT_MESSAGE_OMITTED)
        self.assertNotIn("sensitive", repr(events))
        self.assertEqual(errors, [])
        event_log.CloseEventLog.assert_called_once()
        event_log.ReadEventLog.assert_called_once()

    def test_events_stop_scanning_after_record_limit(self):
        event = SimpleNamespace(EventType=4)
        event_log = MagicMock()
        event_log.EVENTLOG_BACKWARDS_READ = 8
        event_log.EVENTLOG_SEQUENTIAL_READ = 1
        event_log.ReadEventLog.return_value = [event] * (windows.MAX_EVENT_RECORDS + 1)
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows.importlib, "import_module", return_value=event_log
        ):
            events, errors = windows.collect_recent_events()
        self.assertEqual(events, [])
        self.assertEqual(errors, [])
        event_log.ReadEventLog.assert_called_once()
        event_log.CloseEventLog.assert_called_once()

    def test_event_access_failure_is_reported(self):
        event_log = MagicMock()
        event_log.OpenEventLog.side_effect = PermissionError("Access denied")
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows.importlib, "import_module", return_value=event_log
        ):
            events, errors = windows.collect_recent_events()
        self.assertEqual(events, [])
        self.assertIn("Access denied", errors[0])
        event_log.CloseEventLog.assert_not_called()


class SnapshotTests(unittest.TestCase):
    def test_network_probes_are_disabled_by_default(self):
        fake_psutil = MagicMock()
        fake_psutil.net_if_stats.return_value = {"Ethernet": SimpleNamespace(isup=True)}
        with patch.object(system, "psutil", fake_psutil), patch.object(system, "_probe_dns") as dns, patch.object(
            system, "_probe_tcp"
        ) as tcp:
            network = system._collect_network(False)
        self.assertFalse(network["probe_enabled"])
        self.assertIsNone(network["dns_ok"])
        self.assertIsNone(network["tcp_ok"])
        self.assertEqual(network["adapters"], [{"name": "Ethernet", "is_up": True}])
        dns.assert_not_called()
        tcp.assert_not_called()

    def test_network_probe_failures_and_endpoint_metadata_are_preserved(self):
        with patch.object(system, "psutil", None), patch.object(system, "_probe_dns", return_value=(False, "DNS failed")), patch.object(
            system, "_probe_tcp", return_value=(True, None)
        ):
            network = system._collect_network(True)
        self.assertFalse(network["dns_ok"])
        self.assertTrue(network["tcp_ok"])
        self.assertIn("DNS failed", network["errors"])
        self.assertIn("example.com", network["probe_targets"]["dns"])
        self.assertEqual(network["probe_targets"]["tcp"], "1.1.1.1:443")

    def test_partial_disk_failure_retains_accessible_disk(self):
        fake_psutil = MagicMock()
        fake_psutil.disk_partitions.return_value = [
            SimpleNamespace(mountpoint="C:\\"),
            SimpleNamespace(mountpoint="D:\\"),
            SimpleNamespace(mountpoint="C:\\"),
        ]
        fake_psutil.disk_usage.side_effect = [SimpleNamespace(total=100, free=12), PermissionError("Not ready")]
        with patch.object(system, "psutil", fake_psutil):
            disks, errors = system._collect_disks()
        self.assertEqual(disks, [{"mountpoint": "C:\\", "total_bytes": 100, "free_bytes": 12}])
        self.assertEqual(len(errors), 1)
        self.assertIn("Not ready", errors[0])
        self.assertEqual(fake_psutil.disk_usage.call_count, 2)

    def test_snapshot_reports_missing_observations_without_claiming_success(self):
        unknown = {"status": "unknown", "start_type": "unknown", "error": "Unavailable"}
        with patch.object(system, "psutil", None), patch.object(system, "get_spooler_status", return_value=unknown), patch.object(
            system, "collect_recent_events", return_value=([], ["Event Log unavailable"])
        ), patch.object(system, "is_admin", return_value=False):
            snapshot = system.collect_snapshot()
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["source"], "live")
        self.assertEqual(snapshot["services"]["Spooler"]["status"], "unknown")
        self.assertIsNone(snapshot["network"]["dns_ok"])
        self.assertEqual(snapshot["disks"], [])
        self.assertEqual(len(snapshot["errors"]), 4)
        self.assertIsNotNone(datetime.fromisoformat(snapshot["collected_at"]).tzinfo)

    def test_non_windows_dns_subprocess_timeout_and_launch_failure_differ(self):
        with patch.object(system.platform, "system", return_value="Linux"), patch.object(
            system.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixed probe", 4)
        ):
            self.assertFalse(system._probe_dns()[0])
        with patch.object(system.platform, "system", return_value="Linux"), patch.object(
            system.subprocess, "run", side_effect=OSError("Cannot launch interpreter")
        ):
            self.assertIsNone(system._probe_dns()[0])

    def test_windows_dns_uses_fixed_powershell_probe(self):
        with patch.object(system.platform, "system", return_value="Windows"), patch.object(
            system, "probe_system_dns", return_value=(True, None)
        ) as probe, patch.object(system.subprocess, "run") as run:
            self.assertEqual(system._probe_dns(), (True, None))
        probe.assert_called_once_with()
        run.assert_not_called()

    def test_tcp_probe_uses_only_disclosed_target_and_timeout(self):
        with patch.object(system.socket, "create_connection") as connect:
            self.assertEqual(system._probe_tcp(), (True, None))
        connect.assert_called_once_with(("1.1.1.1", 443), timeout=4)
        connect.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
