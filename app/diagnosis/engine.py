"""Deterministic evidence rules. Unknown data never means healthy."""
import json
from importlib.resources import files


def _finding(code, title, severity, evidence, recommendation, action_id=None):
    return dict(id=code, title=title, severity=severity, evidence=evidence,
                recommendation=recommendation, action_id=action_id)


def diagnose(snapshot: dict) -> list[dict]:
    rules = json.loads(files("app.knowledge").joinpath("rules/mvp.json").read_text(encoding="utf-8"))
    findings = []
    spooler = snapshot.get("services", {}).get("Spooler", {})
    status, start_type = spooler.get("status"), spooler.get("start_type")
    if status == "stopped":
        eligible = start_type in ("automatic", "manual") and not spooler.get("error")
        findings.append(_finding("spooler_stopped", "Print Spooler 已停止", "warning",
            [f"Spooler status={status}; start_type={start_type}"],
            "若需要列印，可批准啟動服務。佇列中的工作可能立即列印。" if eligible else
            "服務停用或啟動設定不明，請先確認系統管理政策。此工具不會更改啟動類型。",
            "start_print_spooler" if eligible else None))
    elif status != "running" or spooler.get("error"):
        findings.append(_finding("spooler_unknown", "無法確認列印服務狀態", "info",
            [str(spooler.get("error") or status or "No service data")], "請確認權限後重新掃描。"))
    disks = snapshot.get("disks", [])
    for index, disk in enumerate(disks):
        total, free = disk.get("total_bytes"), disk.get("free_bytes")
        if not isinstance(total, (int, float)) or not isinstance(free, (int, float)) or total <= 0 or free < 0 or free > total:
            findings.append(_finding(f"disk_unknown_{index}", "磁碟容量資料無效", "info",
                [str(disk.get("mountpoint", "unknown"))], "重新掃描並檢查磁碟存取權限。"))
            continue
        pct = free / total * 100
        if pct < rules["disk_free_percent_warning"] or free < rules["disk_free_bytes_warning"]:
            findings.append(_finding(f"disk_low_{index}", "磁碟可用空間偏低", "warning",
                [f"{disk.get('mountpoint', '?')}: {free / 2**30:.2f} GiB free ({pct:.1f}%)"],
                "先備份，再由使用者於 Windows 儲存體設定檢查大型檔案。MVP 不會自動刪除檔案。"))
    if not disks:
        findings.append(_finding("disk_unknown", "未取得磁碟容量", "info", [], "請查看蒐集錯誤後重試。"))
    network = snapshot.get("network", {})
    adapters = network.get("adapters", [])
    if adapters and not any(a.get("is_up") for a in adapters):
        findings.append(_finding("network_link_down", "未偵測到已啟用的網路介面", "warning",
            ["All collected interfaces report is_up=false"], "檢查網路線、Wi-Fi 與飛航模式。"))
    if network.get("probe_enabled"):
        dns, tcp = network.get("dns_ok"), network.get("tcp_ok")
        if dns is False and tcp is True:
            findings.append(_finding("dns_failure", "DNS 名稱解析測試失敗", "warning",
                ["example.com DNS failed; 1.1.1.1:443 TCP succeeded"],
                "可能為 DNS 或網域政策問題。檢查 DNS 設定；此測試不能斷言所有網路皆故障。"))
        elif dns is False or tcp is False:
            findings.append(_finding("connectivity_failure", "網路連線測試未完全通過", "warning",
                [f"DNS example.com={dns}; TCP 1.1.1.1:443={tcp}"],
                "檢查路由器、代理伺服器或防火牆。測試端點遭封鎖也會造成失敗。"))
        if dns is None or tcp is None:
            findings.append(_finding("network_unknown", "網路測試資料不完整", "info",
                network.get("errors", []), "未知結果不代表連線正常。"))
    else:
        findings.append(_finding("network_not_tested", "尚未執行外部網路測試", "info", [],
            "選擇啟用網路探測後，才會查詢 example.com 與連線至 1.1.1.1:443。"))
    if snapshot.get("errors"):
        findings.append(_finding("collection_partial", "部分系統資料無法取得", "info",
            snapshot["errors"], "本次診斷僅涵蓋成功取得的資料。"))
    return findings

