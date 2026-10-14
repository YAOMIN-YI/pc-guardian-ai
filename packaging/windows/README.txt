PC Guardian AI v0.1.0 - Windows x64 portable software MVP

繁體中文快速開始

1. 完整解壓縮 PCGuardianAI 資料夾，保留 _internal；不能只移動 EXE。
2. 雙擊 Run-Demo.cmd。這會使用合成資料，不改動主機。
3. Run-Live.cmd 會唯讀掃描目前的 Windows，預设僅預演修復。
4. 只有取消預演並逐次批准，程式才會嘗試啟動 Print Spooler。
   本機修復需自行以系統管理員權限重開，程式不會自動升權。
   啟動列印服務可能讓佇列中的文件立即列印，服務將持續執行。

此資料夾已包含 Python/Qt 執行依賴，不需另外安裝 Python。
可複製整個資料夾到 USB；不是可開機救援工具。
一般啟動不需要 UGen300，也不會執行外部網路探測。
如需網路測試，在终端機執行：PCGuardianAI.exe --network-probe
它會查詢 example.com DNS，並連線至 1.1.1.1:443，不上傳報告。

預設報告：%LOCALAPPDATA%\PCGuardianAI\reports
預設稽核：%LOCALAPPDATA%\PCGuardianAI\audit.jsonl
可透過 --data-dir "D:\GuardianReports" 指定可寫入的目錄。

目前後端為 CPU 確定性規則 / mock，沒有已訓練模型推論，
沒有 UGen300/HailoRT 實測，沒有離線硬體修復能力。
僅支援停止中的 Print Spooler 啟動；磁碟、網路問題提供診斷建議。
服務 running 不代表實體印表機一定能列印。

測試涵蓋模擬批准修復與 Windows 唯讀掃描。
本次未在真實系統上停止或啟動列印服務；真實修復應另於測試 VM 驗收。
建置為 Windows x64，其他架構、Windows 版本仍需各別驗收。

完整原始碼、測試與說明另見 PC-Guardian-AI-Source.zip。

