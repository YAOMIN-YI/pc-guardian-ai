# MVP 驗證紀錄

日期：2026-10-13（Asia/Taipei）。版本：0.1.0。

## 已執行

- 自動測試：**63 passed，7 subtests passed**。包含 8 項 PySide6 GUI 測試。
- 真實 Windows 唯讀掃描：取得 Spooler 狀態、磁碟容量、介面與 Windows Event Log；本次未回報蒐集錯誤。
- CLI UTF-8：繁中 Windows 下重導向後可讀取為 UTF-8 JSON。
- 模擬流程：三種故障 → dry-run → 未批准阻止 → 明確批准模擬啟動 → 重新驗證 → 保存報告 → 重掃消除列印故障。
- 安全邊界：拒絕未知 action／AI 任意命令、拒絕未知或停用的服務狀態、一般權限禁止真實修復、稽核意圖寫入失敗阻止變更。
- 逾時處理：即使啟動呼叫回報錯誤，也查詢真實服務狀態並保存操作錯誤，不假設逾時表示沒有變更。
- Demo 隔離：會話固定模式；即使 fixture source 被誤改成 live，也不呼叫主機服務操作。
- GUI：預設 dry-run、確認預設否、取消不送出批准、背景執行及關閉等待、錯誤恢复、修復後停用動作直到重掃。
- PyInstaller Windows x64 發行版：demo CLI 與本機唯讀 CLI 通過；包含 pywin32 Event Log 與規則／fixture 資源。
- 封裝後 Qt GUI：offscreen 啟動並完成背景示範掃描通過。原始碼 GUI 已另做畫面檢視；本項不等同每台目標電腦的互動驗收。
- 建置環境：Python 3.13.3、PySide6 6.12.0、psutil 7.2.2、pywin32 312、PyInstaller 6.22.3。固定依賴見 constraints-windows.txt。

## 測試範圍界線

沒有為製造故障而停止、停用或啟動此主機的 Print Spooler。批准後的修復與各種失敗分支使用替身及示範狀態驗證。這不能代替 Windows 10/11 各版本的管理員實機驗收。

沒有 UGen300／HailoRT 裝置、模型部署、加速量測或離線硬體修復測試。`--backend hailo` 明確回報尚未實作。

外部 DNS/TCP 探測目前以單元測試驗證；本次真實系統掃描保持探測關閉。未測試不同代理伺服器、企業政策與防火牆。

服務驗證只證明觀察當時 Spooler 為 running，不保證實際列印、驅動或實體印表機正常。

## 後續驗收

在可拋棄 Windows 10 與 Windows 11 VM，分別驗收一般權限、管理員批准、啟動失敗、停用服務、佇列既有工作、無網路／DNS 錯誤、USB 唯讀／拔除與報告磁碟已滿。每項記錄環境與實際結果。取得 UGen300 後另測主機／驱動／runtime／模型相容矩陣。
