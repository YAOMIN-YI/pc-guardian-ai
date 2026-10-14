# PC Guardian AI

Portable Edge-AI Computer Diagnosis & Self-Repair System

可在一般 Windows 電腦執行的軟體 MVP。**不需要 UGen300**。目前採 CPU 確定性規則與可替換 mock 後端，尚無已訓練模型推論、UGen300/HailoRT 實測或離線硬體修復能力。

## 快速開始

若使用已附的 `PC-Guardian-AI-Windows-x64.zip`，完整解壓縮後雙擊 `Run-Demo.cmd` 即可，不需另裝 Python。請保留 `_internal` 資料夾。以下為原始碼開發方式。

需求：Windows 10/11、64 位元 Python 3.11 以上。此開發環境使用 Python 3.13。初次安裝需要網路；安裝完畢後，示範和本機診斷可離線執行。

1. 在此專案資料夾執行 `Setup.cmd`，建立專案自己的虛擬環境並安裝依賴。
2. 雙擊 `Run-Demo.cmd` 開啟**完全模擬**示範。掃描後可看三種故障；預設只預覽修復。
3. 雙擊 `Run-Live.cmd` 掃描本機。預設一般權限，外部網路探測關閉。

PowerShell 手動啟動方式（不需啟用 Activate.ps1）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]" -c constraints-windows.txt
.\.venv\Scripts\python.exe -m app --demo
```

命令列亦可執行：

```powershell
# 示範掃描並生成 JSON + Markdown
.\.venv\Scripts\python.exe -m app --demo --cli
# 示範修復預覽，不改動任何服務
.\.venv\Scripts\python.exe -m app --demo --cli --repair
# 示範執行：終端機必須逐次輸入 START SPOOLER，僅改動記憶體中的測試資料
.\.venv\Scripts\python.exe -m app --demo --cli --repair --execute
# 本機唯讀診斷
.\.venv\Scripts\python.exe -m app --cli
# 明確選擇外部連線測試
.\.venv\Scripts\python.exe -m app --cli --network-probe
```

`--network-probe` 會向系統 DNS 查詢 `example.com`，並嘗試 TCP 連線至 `1.1.1.1:443`。不會上傳診斷報告。網域封鎖或防火牆可能造成測試失敗，不能單憑端點失敗判定整台電腦斷網。

## 已完成範圍

| 項目 | MVP 行為 |
|---|---|
| 蒐集 | psutil 磁碟容量／網路介面，PowerShell 服務狀態，pywin32 Windows System Event Log |
| 列印故障 | 偵測 Spooler 停止；停用或未知設定不提供修復 |
| 磁碟故障 | 可用空間低於 10% **或** 5 GiB 發出提醒，不自動刪檔 |
| 網路故障 | 介面狀態、選用 DNS 與 TCP 探測，保留失敗／未知差異 |
| 唯一修復 | `start_print_spooler`，固定啟動 Print Spooler |
| 驗證 | 重新查詢是否 running，記錄修復前後狀態；不保證實際列印成功 |
| 報告 | JSON、可讀 Markdown、逐行 JSON audit logging |
| 介面 | PySide6 繁體中文 GUI 與 CLI，背景工作避免介面凍結 |

示範模式每次啟動載入三個合成故障。批准示範修復後，重新掃描會消除模擬列印故障；重新啟動程式可重設示範。即使在示範模式批准，也不會呼叫主機的修復或查詢服務函式。

## 修復的授權與限制

掃描可用一般權限執行。GUI 預設勾選 dry-run；取消勾選後，每次執行仍會出現預設「否」的確認視窗。CLI 不接受無互動批次批准。

真正啟動服務需要使用者自行以系統管理員身分開啟終端機／程式、重新掃描並明確批准。程式不會自動升權。**啟動服務可能讓佇列中的工作立即列印，服務之後會持續執行。**不會停止服務、更改啟動類型、清除佇列或自動回復停止狀態。

授權流程為：可信規則提供 action → 本次使用者批准 → 即時狀態／權限檢查 → 寫入稽核意圖 → 固定操作 → 再查詢驗證 → 保存结果。dry-run 不執行操作。稽核意圖無法寫入時阻止修復；修復後的儲存失敗會保留已觀察結果並顯示錯誤。

AI 後端只能回傳結構化診斷 ID 與白名單 action ID，無權提供服務名稱、PowerShell 腳本或執行參數。所有系統呼叫皆為固定命令／參數列表，`shell=False`，設有逾時。規則與執行器共同檢查證據。後端輸出失敗時保留規則診斷並標記 rejected。

這是本機使用者應用，不是用來隔離惡意 Python 外掛或對抗已取得管理員權限的攻擊者。audit.jsonl 是應用程式追加寫入的本機紀錄，沒有數位簽章、防刪除或防竄改保證。

## 資料位置與隱私

預設 `%LOCALAPPDATA%\PCGuardianAI`：`audit.jsonl` 與 `reports/<scan_id>.json/.md`。可用 `--data-dir "D:\GuardianReports"` 指定可寫入的位置（例如 USB）。不用將資料寫進程式安裝目錄。

報告含磁碟路徑、介面名稱與事件來源；System Event Log 僅讀有限數量記錄，預設略過訊息內文。不蒐集使用者檔案內容、密碼或瀏覽紀錄。分享報告前仍應檢查個人資料。範例報告僅使用合成資料。

## 架構

```text
app/
  ui/                 PySide6 GUI、逐次授權、背景工作
  collectors/         Windows / PowerShell / psutil / Event Log
  ai/                 analyzer、mock_backend、未實作 hailo_backend
  diagnosis/          可信規則診斷
  repair/             policy → executor → verifier
  reports/            原子寫入 JSON/Markdown、audit JSONL
  knowledge/rules/    閾值設定
  service.py          掃描、診斷、修復與報告協調
tests/fixtures/       合成故障資料
docs/                 英文提案與 demo、競賽規則查核
```

`GuardianService` 是 GUI/CLI 共用入口，`Analyzer` 接收可替換後端。報告保留原始掃描證據，修復後觀察另存於 repairs；想了解新狀態請重新掃描。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

若系統暫存資料夾權限異常，可指定新的專用路徑 `--basetemp .pytest-work/run-1`（pytest 可能重建該路徑，請勿指定含重要資料的資料夾）。GUI 測試使用 offscreen。所有修復測試使用替身或模擬狀態，不停止或啟動本機 Spooler。

涵蓋三類診斷、未知資料、危險後端輸出拒絕、授權缺失、dry-run、權限不足、停用服務、競態再檢查、audit 失敗、修復後驗證、示範隔離、報告與 GUI 取消授權。真實 Windows 10/11 的管理員修復驗收，應在專用測試 VM 進行；本次未為製造故障而變更此電腦。

## USB 與未來 UGen300

USB 儲存裝置可攜帶程式、規則與報告，但本版本不是可開機救援系統。Windows 必須能開機且允許程式執行。未來 UGen300 只負責推論，主機上的 Windows 程式持續負責蒐集、授權、執行與驗證。

`--backend hailo` 現在會明確拒絕啟動，沒有假成功或悄悄退回 mock。整合步驟：

1. 取得硬體後确认主機 OS、ASUS 驅動、HailoRT 與 Hailo-10H 相容模型版本。
2. 實作 `HailoBackend.infer(evidence)`；保持相同 schema 與白名單驗證，不把命令執行權交給模型。
3. 加入拔除裝置、逾時、壞輸出測試。記錄實際模型、裝置與驅動版本。
4. 以匿名 fixture 評估診斷品質、延遲與記憶體，再與 CPU 基準比較；所有效能數據需實測。

建立 Windows 發行版可執行 `Build-Windows.cmd`。完整資料夾才能拷貝到 USB，不能只取其中的 EXE。原始碼安裝依賴需要網路；發行版可不依賴主機預裝 Python，仍需在目標 Windows 電腦驗收。

建置腳本會在自己的程序中限制 DLL 搜尋路徑，避免把其他應用的同名 ICU 元件收進發行版。`constraints-windows.txt` 固定本次測試版本。PySide6 上限為 6.13 之前，因 [Qt 官方列明 6.12 是最後支援 Windows 10 的版本](https://doc.qt.io/qt-6.12/windows.html)。

## 競賽資料

查核日：2026-10-13（Asia/Taipei）。官方頁顯示 Stage I 截止 **2026-10-14 17:00（台灣時間）**，第一階段不強制指定硬體。詳見 `docs/competition-rules.md`（含來源與最後確認事項）。英文簡報與 3 分鐘 demo 腳本位於 docs / 交付資料夾。團隊、聯絡方式、GitHub 與影片 URL 仍須填入真實資料。

本次未代為報名、公開上傳 GitHub 或送件。競賽原創／公開發表條件可能影響 repository 可見性，請依官方規範設定評審存取方式。

