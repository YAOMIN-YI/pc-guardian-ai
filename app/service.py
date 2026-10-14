from copy import deepcopy
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import uuid4
import json
import os

from app.ai.analyzer import Analyzer
from app.ai.mock_backend import MockBackend
from app.repair.executor import RepairExecutor
from app.reports import AuditLog, write_reports


def default_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "PCGuardianAI"


class GuardianService:
    """One GUI/CLI session. Demo data and live collectors never mix."""
    def __init__(self, data_dir: Path | None = None, demo: bool = False,
                 network_probe: bool = False, backend_name: str = "mock"):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.demo = demo
        self.network_probe = network_probe
        self.last_result = None
        if backend_name == "mock":
            backend = MockBackend()
        elif backend_name == "hailo":
            from app.ai.hailo_backend import HailoBackend
            backend = HailoBackend()
        else:
            raise ValueError(f"Unknown backend: {backend_name}")
        self.analyzer = Analyzer(backend)
        self.audit = AuditLog(self.data_dir / "audit.jsonl")
        self._demo_snapshot = json.loads(files("app.knowledge").joinpath("demo.json").read_text(encoding="utf-8"))
        self._demo_snapshot["source"] = "demo"

    def scan(self) -> dict:
        if self.demo:
            snapshot = deepcopy(self._demo_snapshot)
            snapshot["source"] = "demo"
            snapshot["collected_at"] = datetime.now(timezone.utc).isoformat()
        else:
            from app.collectors import collect_snapshot
            snapshot = collect_snapshot(network_probe=self.network_probe)
        findings, backend = self.analyzer.analyze(snapshot)
        self.last_result = dict(schema_version=1, scan_id=uuid4().hex, snapshot=snapshot,
            findings=findings, backend=backend, repairs=[], report_paths={})
        self.audit.append("scan_completed", scan_id=self.last_result["scan_id"],
                          source=snapshot["source"], finding_ids=[f["id"] for f in findings])
        self.export()
        return deepcopy(self.last_result)

    def repair(self, action_id: str, *, dry_run: bool = True, approved: bool = False) -> dict:
        if self.last_result is None:
            raise ValueError("Scan before requesting repair.")
        from app.collectors.windows import get_spooler_status, start_spooler, is_admin
        result = self.last_result
        eligible = any(f["action_id"] == action_id for f in result["findings"])
        # Demo executor never invokes any of these host functions.
        executor = RepairExecutor(self.audit, get_spooler_status, start_spooler, is_admin, demo=self.demo)
        snapshot = deepcopy(self._demo_snapshot) if self.demo else result["snapshot"]
        if self.demo:
            snapshot["source"] = "demo"
        record = executor.execute(action_id, snapshot=snapshot, scan_id=result["scan_id"],
                                  eligible=eligible, dry_run=dry_run, approved=approved)
        result["repairs"].append(record)
        if self.demo:
            self._demo_snapshot = snapshot
        # Keep original evidence intact; fresh observation is stored with repair.
        try:
            self.export()
        except OSError as exc:
            record["report_error"] = str(exc)
            record["message"] += " Report export failed; audit may contain the result."
        return deepcopy(record)

    def export(self) -> dict:
        if self.last_result is None:
            raise ValueError("No scan available to export.")
        paths = write_reports(self.last_result, self.data_dir / "reports")
        self.last_result["report_paths"] = paths
        return paths

