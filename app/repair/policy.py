ACTION_ID = "start_print_spooler"
ACTION_DESCRIPTION = "啟動 Windows Print Spooler；佇列中的工作可能立即列印，服務將持續執行。"


def check_policy(action_id: str, *, approved: bool, dry_run: bool,
                 source: str, platform: str, is_admin: bool, service: dict) -> str | None:
    if action_id != ACTION_ID:
        return "Action is not allowlisted."
    if source not in ("demo", "live"):
        return "Unknown snapshot source."
    if platform != "Windows":
        return "Live service repair requires Windows."
    if service.get("error") or service.get("status") not in ("stopped", "running"):
        return "Current service state could not be verified."
    if service.get("status") == "stopped" and service.get("start_type") not in ("manual", "automatic"):
        return "Service is disabled or its startup type is unknown; policy blocks changes."
    if not dry_run and approved is not True:
        return "Explicit approval is required for each execution."
    if not dry_run and source == "live" and not is_admin:
        return "Administrator permission required. Relaunch manually as administrator and approve again."
    return None

