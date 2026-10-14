import time


def verify_spooler(read_status, *, timeout=5.0, interval=0.25) -> tuple[bool, dict]:
    """Observe fresh state, never equate a successful command with recovery."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            state = read_status()
        except Exception as exc:
            state = {"status": "unknown", "error": f"{type(exc).__name__}: {exc}"}
        if state.get("status") == "running" and not state.get("error"):
            return True, state
        if time.monotonic() >= deadline:
            return False, state
        time.sleep(interval)

