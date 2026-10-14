# PC Guardian AI — English video script

**Total duration:** 03:00 (180 seconds). **Narration:** 342 English words across eight continuous segments. This script matches the actual demo workflow and can be read by an AI voice. Fit each voice clip inside its assigned segment, leaving any spare time for the viewer to inspect the screen.

**中文使用說明：** 本版搭配三分鐘英文合成配音影片；下列中文為操作提示，不需配音。PC Guardian AI 應用程式目前只有 CPU 規則／mock，沒有已訓練模型推論或 UGen300 實測。全程使用 fixture，啟動 Print Spooler 只在示範資料內模擬，不修改主機。

**成片製作說明：** 1920 × 1080，03:00，英文合成配音與英文字幕。線上語音服務無法使用，實際採用 Windows 本機 Microsoft Zira Desktop 合成聲音，非神經語音或聲音複製。操作片段來自實際 PySide6 應用程式的隔離示範流程；透過程式點擊真實按鈕，擷取視窗內容後剪輯停留時間、局部放大，未錄製使用者整個桌面。字幕依合成語音的字詞時間對齊。應用程式介面保留中文，章節、重點提示、旁白及字幕均為英文。

| 時間 | 影片內容 |
|---|---|
| 00:00–00:20 | 片頭、產品定位、CPU／mock 示範狀態 |
| 00:20–00:48 | 掃描並展示三類問題與證據 |
| 00:48–01:12 | dry-run 修復預覽 |
| 01:12–01:43 | 先取消，再明確批准模擬修復 |
| 01:43–02:05 | 修復後重新驗證服務狀態 |
| 02:05–02:30 | 展示診斷與修復報告 |
| 02:30–02:46 | 重掃後保留兩個未解決問題 |
| 02:46–03:00 | 未來 USB 儲存裝置＋UGen300 整合規劃 |

## 00:00–00:20 — PC Guardian AI

**Narration**

This is PC Guardian AI, a portable Windows diagnosis and safe repair prototype. Today's demonstration uses test fixtures, CPU rules, and a mock backend. The app runs no trained model, and every repair is simulated without changing this computer.

**Screen action**

Show the opening title for ten seconds, then the app's initial screen with Demo / Simulated clearly visible. Keep dry-run enabled.

**中文操作提示**

前十秒為片頭，接著展示應用程式，讓 Demo／Simulated 與 dry-run 標示清楚入鏡。這裡的「沒有模型推論」指 PC Guardian AI 本身，與影片使用合成旁白是不同功能。

## 00:20–00:48 — Three supported faults

**Narration**

The scan displays three issues: a stopped Print Spooler, low disk space, and a DNS problem. The evidence and suggested next steps appear alongside the findings. Missing information stays unknown. A failed network check is evidence about that test, rather than proof that the computer has completely lost Internet access.

**Screen action**

Run the demo scan. Hold on the three static finding cards and their displayed evidence. Do not suggest that the cards are selectable.

**中文操作提示**

執行掃描後展示三張固定結果卡和證據。結果卡不是可點選項目，不安排點選卡片的動作。

## 00:48–01:12 — Preview before repair

**Narration**

The only permitted repair in this prototype is starting the Print Spooler. Disk cleanup and network configuration remain manual. I begin with dry-run enabled. This previews the allowlisted action without changing service state. Future model output must never become a command for Windows to execute.

**Screen action**

Keep dry-run checked and run the Spooler repair preview. Show its result and the unchanged simulated service state.

**中文操作提示**

保留 dry-run 勾選，執行列印服務修復預覽，讓觀眾看見僅預覽而未改變服務狀態。

## 01:12–01:43 — Cancel, then approve

**Narration**

Now I turn off dry-run and request the simulated repair. The confirmation explains the action and reminds us that starting the service could resume queued print jobs. First, I choose No. Nothing runs. I request it again and choose Yes. This approval allows the demo to update its simulated service state, while leaving the host untouched.

**Screen action**

Uncheck dry-run, request repair, display confirmation and choose No. Request again, display confirmation and choose Yes. Keep the demo label visible.

**中文操作提示**

關閉 dry-run，第一次確認選 No；再按一次修復，第二次確認選 Yes。保留取消與批准的完整操作順序。

## 01:43–02:05 — Verify the outcome

**Narration**

Approval is followed by verification. The app checks the service again and reports that the simulated Spooler is running. A request to repair something is not itself evidence of recovery. The result must reflect the follow-up check, including any permission failure, execution error, or uncertainty.

**Screen action**

Hold on the actual simulated repair result and verification. Show the successful service recheck without implying a real host change.

**中文操作提示**

停留在模擬修復成功與重新檢查的結果。全程不改動真實 Windows 服務。

## 02:05–02:30 — A readable record

**Narration**

The readable report brings the findings, repair result, and verification together. It gives the user or a support technician a record of what happened. The application also writes structured JSON and a local audit log. Those files support later review, but we do not claim that the log is tamper-proof.

**Screen action**

Open or display the report within the GUI. Scroll the human-readable report to show the findings, repair and verification sections. The video need not show a JSON file.

**中文操作提示**

展示 GUI 內的人類可讀報告，可稍微捲動到修復與驗證紀錄。口白提到程式另存 JSON 與 audit log，但不宣稱畫面正在展示這些檔案。

## 02:30–02:46 — Two issues remain

**Narration**

A new scan shows two remaining issues: low disk space and the DNS problem. The Spooler finding is gone. Resolving one issue does not mark every other finding as healthy.

**Screen action**

Run the demo scan again. Hold on the two remaining cards: low disk space and DNS. Do not reset the demo before this rescan.

**中文操作提示**

再次掃描，停留在磁碟與 DNS 的兩張剩餘結果卡。重掃前不要重設示範資料。

## 02:46–03:00 — Planned hardware integration

**Narration**

Next, USB storage will carry the software, with UGen300 planned for supported model inference. Windows retains control of permissions and repairs. Hardware integration and performance remain unvalidated.

**Screen action**

Show a simple closing slate: PC Guardian AI; Next milestone: validated UGen300 integration; CPU software prototype. Keep the hardware work clearly labeled as planned.

**中文操作提示**

切至簡潔結尾字幕：專案名稱、下一里程碑為經驗證的 UGen300 整合、目前為 CPU 軟體原型。不要加入未完成的硬體成果或身分欄位。

## Final recording checks

- Show all three initial findings.
- Keep dry-run enabled for the preview.
- Show the first confirmation cancelled, then the second confirmation approved.
- Show simulated service recovery and its verification.
- Present the readable report in the GUI.
- Rescan and show only the two unresolved findings.
- End with planned UGen300 integration, without performance claims or identity placeholders.
- Keep the finished video at or below three minutes. This script is not evidence that the hardware integration has been tested.

