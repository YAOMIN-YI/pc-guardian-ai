from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from .policy import check_policy
from .verifier import verify_spooler


class RepairExecutor:
    def __init__(self, audit, read_status, start_service, is_admin, *, demo=False):
        self.audit = audit
        self.read_status = read_status
        self.start_service = start_service
        self.is_admin = is_admin
        self.demo = demo

    def execute(self, action_id: str, *, snapshot: dict, scan_id: str,
                eligible: bool, dry_run: bool = True, approved: bool = False) -> dict:
        # Execution mode belongs to the session, never to editable input data.
        demo = self.demo
        record = dict(id=uuid4().hex, at=datetime.now(timezone.utc).isoformat(),
            scan_id=scan_id, action_id=action_id, approved=approved is True,
            dry_run=bool(dry_run), simulated=demo, verified=False,
            status="blocked", message="", before=None, after=None)
        try:
            self.audit.append("repair_requested", **record)
        except OSError as exc:
            record["message"] = f"Audit unavailable; no action executed: {exc}"
            return record
        try:
            if snapshot.get("source") != ("demo" if demo else "live"):
                raise ValueError("Snapshot source does not match the execution session")
            state = deepcopy(snapshot.get("services", {}).get("Spooler", {})) if demo else self.read_status()
            record["before"] = state
            reason = check_policy(action_id, approved=approved, dry_run=dry_run,
                source=snapshot.get("source"), platform=snapshot.get("platform"),
                is_admin=False if demo else self.is_admin(), service=state)
            if not eligible:
                reason = "No eligible action in the current trusted diagnosis. Run a fresh scan."
            if reason:
                record["message"] = reason
            elif dry_run:
                record.update(status="dry_run", message="Preview only: would request Start-Service Spooler. No change made.")
            elif state.get("status") == "running":
                record.update(status="not_needed", message="Service is already running; no change made.",
                              verified=True, after=deepcopy(state))
            else:
                # Durable intent must be written BEFORE any system mutation.
                self.audit.append("repair_authorized", **record)
                if demo:
                    snapshot["services"]["Spooler"]["status"] = "running"
                    read_after = lambda: deepcopy(snapshot["services"]["Spooler"])
                else:
                    read_after = self.read_status
                    try:
                        self.start_service()
                    except Exception as exc:
                        # A timed-out command may already have changed SCM state.
                        # Preserve that uncertainty and still read fresh evidence.
                        record["execution_error"] = f"{type(exc).__name__}: {exc}"
                verified, after = verify_spooler(read_after)
                record.update(status="verified" if verified else "verification_failed",
                    verified=verified, after=after,
                    message=("Simulated service is running. Host unchanged." if demo else
                             "Print Spooler is running. This does not prove printing works.") if verified else
                            "Start requested, but fresh observation did not confirm running. Inspect manually.")
                if record.get("execution_error"):
                    record["status"] = "verified_with_warning" if verified else "verification_failed"
                    record["message"] = (
                        "Service is now running, but the start operation reported an error. "
                        if verified else "Start operation reported an error and running state was not verified. "
                    ) + record["execution_error"] + ". Inspect the report before retrying."
        except Exception as exc:
            record.update(status="failed", message=f"{type(exc).__name__}: {exc}. Check current service state before retrying.")
        try:
            self.audit.append("repair_finished", **record)
        except OSError as exc:
            # Do not hide the action's actual outcome if a later audit write fails.
            record["audit_error"] = str(exc)
            record["message"] += " Final audit write failed; retain this report."
        return record

