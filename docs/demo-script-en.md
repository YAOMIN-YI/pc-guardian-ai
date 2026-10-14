# PC Guardian AI — 3-minute demo script

This recording demonstrates the working CPU software prototype with deterministic rules and a mock backend. The repair shown below is a simulation. There is no trained model inference or UGen300 execution in this version.

**Operator notes / 操作準備**

- 先按 README 安裝依賴，再以 `python -m app --demo` 開啟 GUI。此模式不修改主機服務。
- 保留 Demo / Simulated 標示。使用固定範例資料，不需讓自己的電腦故障。
- 初始畫面保留 dry-run。錄影前演練一次掃描、預覽、批准模擬修復與匯出報告。
- 腳本安排 180 秒，口白約 320 個英文單字，留下操作與畫面停留時間。以實際錄製為準，目標 2:50–3:00。
- 若 GUI 按鈕名稱與此稿略有差異，依功能操作。需要可重現的 CLI 備案時，使用文末指令。

## 0:00–0:25 — Introduction

**Screen:** title slide, then the app in demo mode.

**English narration:**

> This is PC Guardian AI, a portable Windows diagnosis and safe repair prototype. It helps a user understand a fault, review the evidence, and approve a supported change. Today I am showing the software MVP on a CPU. I do not yet have a UGen300, and this demonstration uses fixture data and simulated repair.

**繁中操作：** 顯示專案名稱後切換 GUI，讓觀眾看清楚示範模式。不要拿一般隨身碟冒充 AI 加速器。

## 0:25–0:55 — Diagnose three fault categories

**Screen:** run the demo scan and select findings.

**English narration:**

> The scan identifies three supported categories: a stopped Print Spooler, low disk space, and a DNS or connection problem. Each result includes evidence and a recommended next step. Unknown information stays unknown. A failed network probe does not automatically prove that the entire Internet connection is down.

**繁中操作：** 點掃描，依序呈現 Spooler、低磁碟空間、DNS／連線異常。每個項目停留數秒，不宣稱已找到所有 Windows 故障。

## 0:55–1:25 — Preview the safe repair

**Screen:** select the Spooler finding, keep dry-run enabled, preview the repair.

**English narration:**

> Only one action can change Windows in this MVP: starting the Print Spooler. First I preview that action in dry-run mode. The program does not delete files, reset the network, or accept generated shell commands. The repair policy accepts a fixed action identifier and checks the current service state before execution.

**繁中操作：** 維持 dry-run 勾選，執行預覽並呈現沒有修改的結果。說明啟動服務可能使排隊中的列印作業恢復。

## 1:25–1:55 — Approve and verify a simulation

**Screen:** explicitly approve the demo repair, show the resulting verification.

**English narration:**

> I now choose to run the simulated repair and explicitly approve it. The demo changes its simulated service state and checks it again. The report distinguishes the requested action from the verified result. A live repair would require the user’s approval and sufficient Windows permissions. The application does not silently elevate privileges.

**繁中操作：** 僅在 Demo 模式取消 dry-run，閱讀批准視窗並明確確認。呈現 simulated 與 verification 結果。若失敗就如實解釋，不能用剪接或口白稱成功。

## 1:55–2:20 — Show the report

**Screen:** export report, open the readable report and briefly show JSON / audit.

**English narration:**

> The local report records findings, evidence, the action outcome, and verification. JSON supports further tools, while the readable report helps the user or technician understand what happened. The audit log makes the sequence reviewable. It is a local log, not a tamper-proof security record.

**繁中操作：** 匯出本次示範報告，放大人類可讀部分，再短暫顯示 JSON。不要誤開其他主機上的真實私人紀錄。

## 2:20–2:50 — Explain the hardware plan

**Screen:** planned integration slide.

**English narration:**

> Our planned device combines USB storage with an ASUS UGen300 accelerator. The Windows host still collects evidence, enforces permissions, and performs repairs. A future HailoRT adapter will run a supported model and return structured diagnoses. We will verify driver and model compatibility, then measure diagnosis quality, latency, and resource use against the CPU baseline.

**繁中操作：** 對著架構／規劃頁說明。產品圖是規劃參考，不能以照片暗示已持有硬體。此版本目前使用規則與 mock，尚未進行模型或硬體推論。

## 2:50–3:00 — Close

**Screen:** final slide with real team, repository and video information filled in.

**English narration:**

> PC Guardian AI focuses on a small, testable repair workflow with explicit user control. The next milestone is validated UGen300 integration. Thank you.

**繁中操作：** 停留結尾頁。提案影片使用英文，YouTube 設為「知道連結者可觀看」。正式繳件前需填真實隊名及 GitHub 連結。

## CLI fallback / 命令列備案

先在專案資料夾、已安裝依賴的 Python 環境執行：

```powershell
python -m app --demo --cli
python -m app --demo --cli --repair
python -m app --demo --cli --repair --execute
```

第三個指令會要求明確輸入 `START SPOOLER` 才執行**模擬**修復。保留提示與結果畫面，不使用自動輸入繞過演示中的批准步驟。若要展示真實 Windows 服務變更，另用可拋棄測試環境並事先準備，不能把本次模擬影片改稱實機硬體成果。

## What remains before submission

The script is ready to rehearse. It is not a recorded video, a YouTube upload, or a submitted entry. Fill the team/author, GitHub URL and unlisted video URL in the deck. The currently verified Stage I cutoff is **2026-10-14 17:00 Asia/Taipei**. See `competition-rules.md` for sources and the final checklist.
