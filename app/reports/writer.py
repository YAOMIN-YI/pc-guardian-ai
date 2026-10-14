import json
import os
import tempfile
from pathlib import Path


def _atomic_write(path: Path, content: str):
    fd, temp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_reports(result: dict, directory: Path) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # scan_id is generated inside GuardianService, never supplied by the backend.
    report_id = result["scan_id"]
    paths = {"json": str((directory / f"{report_id}.json").resolve()),
             "markdown": str((directory / f"{report_id}.md").resolve())}
    payload = {**result, "report_paths": paths}
    snapshot = result["snapshot"]
    lines = ["# PC Guardian AI 診斷報告", "", f"Scan: {report_id}",
        f"Time: {snapshot['collected_at']}", f"Mode: {snapshot['source']}",
        "Backend: CPU deterministic rules / mock AI. UGen300 hardware not validated.",
        "", "掃描結果為當時觀察。未知或未測試的項目不代表正常。", "", "## 診斷", ""]
    for finding in result["findings"]:
        lines.extend([f"### {finding['title']} ({finding['severity']})", "",
            *[f"- {e}" for e in finding['evidence']], "", finding["recommendation"],
            f"Action: {finding['action_id'] or 'none'}", ""])
    if not result["findings"]:
        lines.extend(["本次規則未偵測到異常；不代表完整健康保證。", ""])
    lines.extend(["## 修復歷程", ""])
    for repair in result["repairs"]:
        lines.extend([f"- {repair['at']}: {repair['action_id']} / {repair['status']}",
            f"  {repair['message']}",
            f"  approved={repair['approved']}; dry_run={repair['dry_run']}; simulated={repair['simulated']}; verified={repair['verified']}"])
    if not result["repairs"]:
        lines.append("未執行修復。")
    lines.extend(["", "## 限制與隱私", "", "此版本不包含已訓練 AI 推論、UGen300 執行或離線硬體修復。",
        "啟動 Print Spooler 只驗證服務已執行，不保證印表機或實際列印正常。",
        "資料留存在本機。報告可能包含磁碟路徑、介面名稱與事件來源，分享前請檢查。",
        "Audit JSONL 為本機紀錄，非防竄改或數位簽章證據。", ""])
    _atomic_write(Path(paths["json"]), json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    _atomic_write(Path(paths["markdown"]), "\n".join(lines))
    return paths

