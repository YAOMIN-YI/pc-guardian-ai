from app.diagnosis import diagnose


def test_three_faults(snapshot):
    findings = diagnose(snapshot)
    assert {f["id"] for f in findings} == {"spooler_stopped", "disk_low_0", "dns_failure"}
    assert [f["action_id"] for f in findings if f["action_id"]] == ["start_print_spooler"]


def test_disabled_spooler_never_offers_start(snapshot):
    snapshot["services"]["Spooler"]["start_type"] = "disabled"
    assert not any(f["action_id"] for f in diagnose(snapshot))


def test_unknown_data_never_claims_healthy(snapshot):
    snapshot.update(services={}, disks=[], network={"probe_enabled": True}, errors=["Access denied"])
    assert {f["id"] for f in diagnose(snapshot)} == {"spooler_unknown", "disk_unknown", "network_unknown", "collection_partial"}


def test_network_probe_disabled_and_endpoint_failure(snapshot):
    snapshot["network"]["probe_enabled"] = False
    assert "network_not_tested" in {f["id"] for f in diagnose(snapshot)}
    snapshot["network"].update(probe_enabled=True, dns_ok=True, tcp_ok=False)
    findings = diagnose(snapshot)
    assert "connectivity_failure" in {f["id"] for f in findings}
    assert "dns_failure" not in {f["id"] for f in findings}


def test_threshold_boundary_and_invalid_capacity(snapshot):
    snapshot["disks"] = [{"mountpoint": "X:", "total_bytes": 100 * 2**30, "free_bytes": 10 * 2**30}]
    assert not any(f["id"].startswith("disk_low") for f in diagnose(snapshot))
    snapshot["disks"][0]["total_bytes"] = 0
    assert "disk_unknown_0" in {f["id"] for f in diagnose(snapshot)}

