"""Small, fixed Windows operations; no AI text becomes executable input.

The repair executor is responsible for approval, dry-run, and audit logging.
``start_spooler`` provides a second precondition check immediately before the
single permitted service operation. Importing or collecting never repairs.
"""

from __future__ import annotations

import ctypes
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any


POWERSHELL_TIMEOUT_SECONDS = 12
DNS_TIMEOUT_SECONDS = 4
MAX_EVENTS = 20
MAX_EVENT_RECORDS = 256
EVENT_MESSAGE_OMITTED = "[Message omitted by default for privacy]"

_PS_PREFIX = (
    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
    "$ErrorActionPreference = 'Stop'; "
)
_PS_COMMANDS = {
    "service_status": _PS_PREFIX
    + "$svc = Get-CimInstance -ClassName Win32_Service -Filter \"Name='Spooler'\"; "
    + "if ($null -eq $svc) { throw 'Spooler service was not found.' }; "
    + "$svc | Select-Object State, StartMode | ConvertTo-Json -Compress",
    "start_spooler": _PS_PREFIX
    + "$svc = Get-CimInstance -ClassName Win32_Service -Filter \"Name='Spooler'\"; "
    + "if ($null -eq $svc) { throw 'Spooler service was not found.' }; "
    + "if ($svc.State -ne 'Stopped') { throw 'Spooler is no longer stopped.' }; "
    + "if ($svc.StartMode -notin @('Auto', 'Manual')) "
    + "{ throw 'Spooler startup type does not permit this repair.' }; "
    + "Start-Service -Name 'Spooler' -ErrorAction Stop",
    "dns_probe": _PS_PREFIX
    + "try { $null = Resolve-DnsName -Name 'example.com' -DnsOnly -QuickTimeout "
    + "-ErrorAction Stop; @{ resolved = $true } | ConvertTo-Json -Compress } "
    + "catch { @{ resolved = $false } | ConvertTo-Json -Compress }",
}


def is_admin() -> bool:
    """Return False when elevation cannot be established; never elevate."""
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _run_powershell(operation: str) -> str:
    """Execute one internal allowlisted operation with a bounded wait."""
    if operation not in _PS_COMMANDS:
        raise ValueError("Unsupported PowerShell operation")
    if platform.system() != "Windows":
        raise RuntimeError("Windows PowerShell is unavailable on this platform")
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    timeout = DNS_TIMEOUT_SECONDS if operation == "dns_probe" else POWERSHELL_TIMEOUT_SECONDS
    try:
        result = subprocess.run(
            [
                str(executable),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _PS_COMMANDS[operation],
            ],
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Windows {operation} operation timed out after {timeout}s; "
            "the result is unknown and must be checked before retrying"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Cannot launch Windows PowerShell: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No error details").strip()[:600]
        raise RuntimeError(f"Windows {operation} operation failed ({result.returncode}): {detail}")
    return result.stdout.strip().lstrip("\ufeff")


def probe_system_dns() -> tuple[bool | None, str | None]:
    """Resolve only example.com with Windows' DNS resolver, with a hard timeout."""
    try:
        result = json.loads(_run_powershell("dns_probe"))
        if not isinstance(result, dict) or type(result.get("resolved")) is not bool:
            return None, "Windows DNS probe returned an invalid result"
        if result["resolved"]:
            return True, None
        return False, "System DNS resolver could not resolve example.com"
    except (RuntimeError, ValueError, TypeError) as exc:
        return None, f"DNS probe could not establish a result: {exc}"


def get_spooler_status() -> dict[str, Any]:
    """Read the Spooler's running state and configured startup type."""
    unknown = {"status": "unknown", "start_type": "unknown", "error": None}
    if platform.system() != "Windows":
        return {**unknown, "error": "Print Spooler collection requires Windows"}
    try:
        data = json.loads(_run_powershell("service_status"))
        if not isinstance(data, dict):
            raise ValueError("Service response must be a JSON object")
        statuses = {
            "running": "running",
            "stopped": "stopped",
            "start pending": "start_pending",
            "stop pending": "stop_pending",
            "continue pending": "continue_pending",
            "pause pending": "pause_pending",
            "paused": "paused",
        }
        starts = {"auto": "automatic", "automatic": "automatic", "manual": "manual", "disabled": "disabled"}
        status = statuses.get(str(data.get("State", "")).lower(), "unknown")
        start_type = starts.get(str(data.get("StartMode", "")).lower(), "unknown")
        error = None
        if status == "unknown" or start_type == "unknown":
            error = "Windows returned an unrecognized service state or startup type"
        return {"status": status, "start_type": start_type, "error": error}
    except (RuntimeError, ValueError, TypeError) as exc:
        return {**unknown, "error": str(exc)}


def start_spooler() -> dict[str, Any]:
    """Start only the stopped, enabled Spooler; requires prior executor approval.

    No configuration or startup type is changed. A timeout is not a rollback:
    the caller must record the uncertainty and verify the current service state.
    """
    if platform.system() != "Windows":
        raise RuntimeError("Starting Print Spooler requires Windows")
    if not is_admin():
        raise RuntimeError("Starting Print Spooler requires an elevated Windows session")
    before = get_spooler_status()
    if before.get("error"):
        raise RuntimeError(f"Cannot establish safe service state: {before['error']}")
    if before["status"] != "stopped":
        raise RuntimeError("Print Spooler must be stopped before this repair")
    if before["start_type"] not in {"automatic", "manual"}:
        raise RuntimeError("Disabled or unknown Spooler startup type is not repairable")
    _run_powershell("start_spooler")
    return get_spooler_status()


def collect_recent_events() -> tuple[list[dict[str, Any]], list[str]]:
    """Read at most 20 recent System warnings/errors, inspecting at most 256 records.

    Full messages/insertion strings often contain personal data and are never
    formatted or stored by this collector. Missing access is reported explicitly.
    """
    if platform.system() != "Windows":
        return [], ["Windows Event Log collection requires Windows"]
    try:
        win32evtlog = importlib.import_module("win32evtlog")
    except ImportError:
        return [], ["Windows Event Log collection unavailable: install pywin32 on Windows"]
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    handle = None
    try:
        handle = win32evtlog.OpenEventLog(None, "System")
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        inspected = 0
        while inspected < MAX_EVENT_RECORDS and len(events) < MAX_EVENTS:
            records = win32evtlog.ReadEventLog(handle, flags, 0)
            if not records:
                break
            for record in records:
                inspected += 1
                level = {1: "error", 2: "warning"}.get(record.EventType)
                if level:
                    generated = record.TimeGenerated
                    if isinstance(generated, datetime):
                        generated = generated.astimezone(timezone.utc).isoformat()
                    else:
                        generated = str(generated)
                    events.append(
                        {
                            "id": int(record.EventID) & 0xFFFF,
                            "source": str(record.SourceName)[:128],
                            "level": level,
                            "time": generated,
                            "message": EVENT_MESSAGE_OMITTED,
                        }
                    )
                if inspected >= MAX_EVENT_RECORDS or len(events) >= MAX_EVENTS:
                    break
    except Exception as exc:
        errors.append(f"Windows Event Log read failed: {type(exc).__name__}: {exc}")
    finally:
        if handle is not None:
            try:
                win32evtlog.CloseEventLog(handle)
            except Exception as exc:
                errors.append(f"Windows Event Log close failed: {type(exc).__name__}: {exc}")
    return events, errors
