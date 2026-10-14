"""Collect a portable snapshot with explicit gaps and opt-in network probes."""

from __future__ import annotations

from datetime import datetime, timezone
import platform
import socket
import subprocess
import sys
from typing import Any

try:
    import psutil
except ImportError:  # Permit a useful partial snapshot in an incomplete install.
    psutil = None

from .windows import collect_recent_events, get_spooler_status, is_admin, probe_system_dns


DNS_PROBE_HOST = "example.com"
TCP_PROBE_HOST = "1.1.1.1"
TCP_PROBE_PORT = 443
PROBE_TIMEOUT_SECONDS = 4

# Run system DNS resolution in an isolated child process so even a stuck
# resolver has a hard timeout; a timed-out worker thread would not be enough.
_DNS_PROBE_SCRIPT = (
    "import socket, sys\n"
    "try:\n"
    "    socket.getaddrinfo('example.com', 443, type=socket.SOCK_STREAM)\n"
    "except socket.gaierror:\n"
    "    sys.exit(2)\n"
    "sys.exit(0)\n"
)


def _collect_disks() -> tuple[list[dict[str, Any]], list[str]]:
    if psutil is None:
        return [], ["Disk collection unavailable: psutil is not installed"]
    disks: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception as exc:
        return [], [f"Cannot enumerate disks: {type(exc).__name__}: {exc}"]
    seen: set[str] = set()
    for partition in partitions:
        mount = partition.mountpoint
        if mount in seen:
            continue
        seen.add(mount)
        try:
            usage = psutil.disk_usage(mount)
            disks.append({"mountpoint": mount, "total_bytes": int(usage.total), "free_bytes": int(usage.free)})
        except Exception as exc:
            errors.append(f"Cannot read disk {mount}: {type(exc).__name__}: {exc}")
    if not partitions:
        errors.append("No mounted disks were returned by the operating system")
    return disks, errors


def _probe_dns() -> tuple[bool | None, str | None]:
    if platform.system() == "Windows":
        return probe_system_dns()
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", _DNS_PROBE_SCRIPT],
            shell=False,
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return False, f"DNS resolution of {DNS_PROBE_HOST} timed out after {PROBE_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return None, f"DNS probe could not start: {type(exc).__name__}: {exc}"
    if result.returncode == 0:
        return True, None
    if result.returncode == 2:
        return False, f"System DNS resolver could not resolve {DNS_PROBE_HOST}"
    return None, f"DNS probe failed unexpectedly (exit {result.returncode})"


def _probe_tcp() -> tuple[bool | None, str | None]:
    target = f"{TCP_PROBE_HOST}:{TCP_PROBE_PORT}"
    try:
        with socket.create_connection((TCP_PROBE_HOST, TCP_PROBE_PORT), timeout=PROBE_TIMEOUT_SECONDS):
            return True, None
    except OSError as exc:
        return False, f"TCP connection to {target} failed: {type(exc).__name__}: {exc}"


def _collect_network(probe_enabled: bool) -> dict[str, Any]:
    network: dict[str, Any] = {
        "probe_enabled": probe_enabled,
        "adapters": [],
        "dns_ok": None,
        "tcp_ok": None,
        "errors": [],
        "probe_targets": {
            "dns": f"{DNS_PROBE_HOST} through configured system DNS resolvers",
            "tcp": f"{TCP_PROBE_HOST}:{TCP_PROBE_PORT}",
        },
    }
    if psutil is None:
        network["errors"].append("Network adapter collection unavailable: psutil is not installed")
    else:
        try:
            network["adapters"] = [
                {"name": str(name), "is_up": bool(stats.isup)}
                for name, stats in psutil.net_if_stats().items()
            ]
        except Exception as exc:
            network["errors"].append(f"Cannot enumerate network adapters: {type(exc).__name__}: {exc}")
    if probe_enabled:
        network["dns_ok"], dns_error = _probe_dns()
        network["tcp_ok"], tcp_error = _probe_tcp()
        network["errors"].extend(error for error in (dns_error, tcp_error) if error)
    return network


def collect_snapshot(*, network_probe: bool = False) -> dict[str, Any]:
    """Return observations only; collection never starts or configures services.

    With network_probe=True, resolve example.com using the host's configured
    DNS resolver and open/close TCP 1.1.1.1:443. No application data is sent.
    Disabled probes remain None; partial collection failures are explicit.
    """
    errors: list[str] = []
    spooler = get_spooler_status()
    if spooler.get("error"):
        errors.append(f"Print Spooler: {spooler['error']}")
    disks, disk_errors = _collect_disks()
    errors.extend(disk_errors)
    network = _collect_network(bool(network_probe))
    errors.extend(network["errors"])
    events, event_errors = collect_recent_events()
    errors.extend(event_errors)
    return {
        "schema_version": 1,
        "source": "live",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "is_admin": is_admin(),
        "services": {"Spooler": spooler},
        "disks": disks,
        "network": network,
        "events": events,
        "errors": errors,
    }
