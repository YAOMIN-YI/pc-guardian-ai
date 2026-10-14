"""Consent-first Windows diagnosis interface.

The GUI never constructs commands. GuardianService owns policy, execution,
verification and durable auditing; the UI supplies approval for one action only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QThread, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


SPOOLER_ACTION = "start_print_spooler"


class TaskWorker(QThread):
    """Run one bounded service operation outside the GUI thread."""

    result = Signal(object)
    failed = Signal(str)
    def __init__(self, operation: Callable[[], Any], parent: QWidget) -> None:
        super().__init__(parent)
        self.operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.result.emit(self.operation())
        except Exception as exc:  # Display failures without dropping the UI.
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def label(text: str, style: str = "", *, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if style:
        widget.setObjectName(style)
    return widget


def panel() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return frame, layout


class MainWindow(QMainWindow):
    """Desktop UI with a replaceable service, useful for offscreen tests."""

    def __init__(
        self, service: Any, *, demo: bool = False, network_probe: bool = False
    ) -> None:
        super().__init__()
        self.service = service
        self.demo = demo
        self.network_probe = network_probe
        self._thread: QThread | None = None
        self._worker: TaskWorker | None = None
        self._busy = False
        self._close_when_finished = False
        self._operation_kind = ""
        self._result: dict[str, Any] | None = None
        self._eligible_action: str | None = None
        self._resolved_actions: set[str] = set()
        self._report_paths: dict[str, str] = {}
        self.setWindowTitle("PC Guardian AI | 電腦診斷與安全修復")
        self.resize(1280, 900)
        self.setMinimumSize(1020, 740)
        self.setFont(QFont("Microsoft JhengHei UI", 10))
        self._build_ui()
        self.setStyleSheet(STYLES)
        self._update_controls()

    @property
    def busy(self) -> bool:
        return self._busy

    def _build_ui(self) -> None:
        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(212)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(26, 30, 22, 28)
        side.setSpacing(12)
        side.addWidget(label("PG /", "brandMark"))
        side.addWidget(label("PC Guardian\nAI", "brand"))
        side.addWidget(label("Portable Edge-AI\nDiagnosis & Self-Repair", "sidebarMuted"))
        side.addSpacing(30)
        side.addWidget(label("01   電腦健康檢查", "navActive"))
        side.addWidget(label("02   批准安全修復", "navItem"))
        side.addWidget(label("03   驗證與報告", "navItem"))
        side.addStretch()
        side.addWidget(label("SOFTWARE MVP", "sidebarEyebrow"))
        side.addWidget(label("Windows 10 / 11\nUSB 隨身工具開發版", "sidebarMuted"))
        side.addSpacing(10)
        side.addWidget(label("UGen300 / HailoRT\n尚未接入或驗證", "hardwareNote"))
        row.addWidget(sidebar)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 25, 30, 24)
        body.setSpacing(15)
        row.addWidget(content, 1)

        top = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        title_column.addWidget(label("PC GUARDIAN AI / SYSTEM CARE", "eyebrow"))
        title_column.addWidget(label("看見問題，安心修復。", "pageTitle"))
        title_column.addWidget(label("蒐集狀態 → 解釋原因 → 逐次授權 → 修復後驗證", "muted"))
        top.addLayout(title_column, 1)
        self.scan_button = QPushButton("開始健康檢查")
        self.scan_button.setObjectName("primary")
        self.scan_button.setMinimumHeight(46)
        self.scan_button.clicked.connect(self.scan)
        top.addWidget(self.scan_button)
        body.addLayout(top)

        self.scope_banner = label(
            "示範模式  ·  使用測試資料；修復僅更新記憶體中的模擬狀態，不操作本機。"
            if self.demo
            else "本機模式  ·  掃描目前的 Windows；修復必須逐次批准，預設僅預演。",
            "demoBanner" if self.demo else "scopeBanner",
            wrap=True,
        )
        body.addWidget(self.scope_banner)
        self.backend_label = label(
            "推論：Mock 規則示範（非語言模型）  ·  CPU 執行  ·  UGen300 硬體未驗證\n"
            + self._network_scope_text(),
            "mutedSmall",
            wrap=True,
        )
        body.addWidget(self.backend_label)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.issue_count = self._metric(cards, "待處理項目", "—", "規則涵蓋三類常見故障")
        self.action_count = self._metric(cards, "白名單安全修復", "—", "僅支援啟動列印服務")
        self.verified_count = self._metric(cards, "驗證通過", "—", "每次執行後重新檢查")
        body.addLayout(cards)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        findings_panel, findings_layout = panel()
        findings_header = QHBoxLayout()
        findings_header.addWidget(label("診斷結果", "sectionTitle"))
        findings_header.addStretch()
        self.scan_id_label = label("尚未掃描", "mutedSmall")
        findings_header.addWidget(self.scan_id_label)
        findings_layout.addLayout(findings_header)
        findings_scroll = QScrollArea()
        findings_scroll.setWidgetResizable(True)
        findings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        findings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.findings_container = QWidget()
        self.findings_layout = QVBoxLayout(self.findings_container)
        self.findings_layout.setContentsMargins(0, 0, 8, 0)
        self.findings_layout.setSpacing(12)
        self.findings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.findings_layout.addWidget(label("執行健康檢查，查看列印、磁碟與網路狀態。", "muted", wrap=True))
        findings_scroll.setWidget(self.findings_container)
        findings_layout.addWidget(findings_scroll, 1)
        columns.addWidget(findings_panel, 3)

        right = QVBoxLayout()
        right.setSpacing(15)
        repair_panel, repair_layout = panel()
        repair_panel.setMinimumWidth(305)
        repair_panel.setMaximumWidth(360)
        repair_layout.addWidget(label("安全修復", "sectionTitle"))
        repair_layout.addWidget(label("啟動 Print Spooler", "actionTitle"))
        repair_layout.addWidget(label(
            "只啟動停止中的 Windows 列印服務。佇列中的文件可能開始列印，服務會保持執行。",
            "muted", wrap=True,
        ))
        self.dry_run_checkbox = QCheckBox("預演模式（不變更系統）")
        self.dry_run_checkbox.setChecked(True)
        self.dry_run_checkbox.toggled.connect(self._update_controls)
        repair_layout.addWidget(self.dry_run_checkbox)
        self.repair_button = QPushButton("預演啟動列印服務")
        self.repair_button.setObjectName("repairButton")
        self.repair_button.setMinimumHeight(43)
        self.repair_button.clicked.connect(self.request_repair)
        repair_layout.addWidget(self.repair_button)
        self.repair_hint = label("偵測到列印服務停止後，才會提供此動作。", "mutedSmall", wrap=True)
        repair_layout.addWidget(self.repair_hint)
        right.addWidget(repair_panel)

        audit_panel, audit_layout = panel()
        audit_panel.setMaximumWidth(360)
        audit_layout.addWidget(label("執行紀錄", "sectionTitle"))
        self.audit_view = QTextBrowser()
        self.audit_view.setOpenExternalLinks(False)
        self.audit_view.setMinimumHeight(90)
        self.audit_view.setPlainText("尚未執行修復。\n預演、執行與驗證結果會保留於報告。")
        audit_layout.addWidget(self.audit_view, 1)
        right.addWidget(audit_panel, 1)
        columns.addLayout(right, 2)
        body.addLayout(columns, 1)

        self.status_label = label("準備就緒。健康檢查不會自動修復問題。", "status", wrap=True)
        body.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        body.addWidget(self.progress)

        footer = QHBoxLayout()
        footer.addWidget(label("本機保留 JSON + Markdown 報告", "mutedSmall"), 1)
        self.view_report_button = QPushButton("檢視報告")
        self.view_report_button.clicked.connect(self.show_report)
        footer.addWidget(self.view_report_button)
        self.export_button = QPushButton("重新產生報告")
        self.export_button.clicked.connect(self.export_report)
        footer.addWidget(self.export_button)
        self.folder_button = QPushButton("開啟報告資料夾")
        self.folder_button.clicked.connect(self.open_report_folder)
        footer.addWidget(self.folder_button)
        body.addLayout(footer)

    @staticmethod
    def _metric(layout: QHBoxLayout, heading: str, value: str, detail: str) -> QLabel:
        frame, column = panel()
        column.setContentsMargins(19, 14, 19, 14)
        column.setSpacing(4)
        column.addWidget(label(heading, "metricHeading"))
        number = label(value, "metricNumber")
        column.addWidget(number)
        column.addWidget(label(detail, "mutedSmall", wrap=True))
        layout.addWidget(frame, 1)
        return number

    @Slot()
    def scan(self) -> None:
        if self._busy:
            return
        # A failed rescan must not leave an old repair offer active.
        self._eligible_action = None
        self._start_task("scan", self.service.scan, "正在蒐集狀態並診斷，請稍候…")

    def _network_scope_text(self) -> str:
        if self.demo:
            return "網路資料：測試情境（DNS / TCP 結果為模擬資料，未連線探測）"
        if self.network_probe:
            return "網路探測：已啟用（會進行 DNS / TCP 連線測試）"
        return "網路探測：未啟用（僅蒐集本機網路狀態，可於啟動時選擇探測）"

    @Slot()
    def request_repair(self) -> None:
        if self._busy or self._eligible_action != SPOOLER_ACTION:
            return
        dry_run = self.dry_run_checkbox.isChecked()
        approved = False
        if not dry_run:
            context = "示範模式：此動作只會變更模擬狀態。\n\n" if self.demo else "本機模式：此動作將變更目前電腦的服務狀態。\n\n"
            answer = QMessageBox.question(
                self,
                "批准本次啟動列印服務",
                context
                + "動作：啟動 Print Spooler 服務。\n"
                + "風險：佇列中的文件可能立即列印，服務會保持執行。\n"
                + "本工具不會自動提權；若權限不足，動作將失敗並留下紀錄。\n\n"
                + "是否明確批准這一次動作？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.status_label.setText("已取消，未送出修復動作。")
                return
            approved = True
        self._start_task(
            "repair",
            lambda: self.service.repair(SPOOLER_ACTION, dry_run=dry_run, approved=approved),
            "正在預演安全修復…" if dry_run else "正在執行並驗證本次已批准的動作…",
        )

    @Slot()
    def export_report(self) -> None:
        if self._busy or not self._result:
            return
        self._start_task("export", self.service.export, "正在產生本機報告…")

    def _start_task(self, kind: str, operation: Callable[[], Any], message: str) -> None:
        if self._busy:
            return
        self._busy = True
        self._operation_kind = kind
        self.status_label.setText(message)
        self.progress.show()
        self._update_controls()
        worker = TaskWorker(operation, self)
        worker.result.connect(self._on_result)
        worker.failed.connect(self._on_error)
        worker.finished.connect(self._on_finished)
        worker.finished.connect(worker.deleteLater)
        self._thread = worker
        self._worker = worker
        worker.start()

    @Slot(object)
    def _on_result(self, result: Any) -> None:
        if self._operation_kind == "scan":
            self._render_result(result)
            self.status_label.setText("健康檢查完成。請檢閱診斷，再選擇是否預演或批准修復。")
        elif self._operation_kind == "repair":
            latest = getattr(self.service, "last_result", None)
            if latest:
                self._render_result(latest)
            self.status_label.setText(str(result.get("message", "修復流程已完成，請檢閱驗證結果。")))
            # Approval never persists from one action to the next.
            self.dry_run_checkbox.setChecked(True)
        else:
            self._report_paths = dict(result)
            self.status_label.setText("JSON 與 Markdown 報告已產生，可檢視或開啟資料夾。")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.status_label.setText("操作未完成：" + message)
        self.dry_run_checkbox.setChecked(True)

    @Slot()
    def _on_finished(self) -> None:
        if self._thread is not None:
            # The finished signal precedes thread-local cleanup. Join before
            # releasing Python references or allowing this window to close.
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._busy = False
        self.progress.hide()
        self._update_controls()
        if self._close_when_finished:
            self.close()

    def _render_result(self, result: dict[str, Any]) -> None:
        self._result = result
        self._report_paths = dict(result.get("report_paths", {}))
        findings = result.get("findings", [])
        repairs = result.get("repairs", [])
        self._resolved_actions = {
            str(item["action_id"]) for item in repairs
            if item.get("action_id") and item.get("verified") is True and not item.get("dry_run")
        }
        unresolved = [item for item in findings if not item.get("action_id")
                      or item["action_id"] not in self._resolved_actions]
        self._eligible_action = next(
            (SPOOLER_ACTION for item in unresolved if item.get("action_id") == SPOOLER_ACTION),
            None,
        )
        self.issue_count.setText(str(len(unresolved)))
        self.action_count.setText("1" if self._eligible_action else "0")
        self.verified_count.setText(str(sum(
            1 for item in repairs if item.get("verified") is True and not item.get("dry_run")
        )))
        scan_id = str(result.get("scan_id", ""))
        self.scan_id_label.setText("檢查 " + scan_id[:12])
        self.scan_id_label.setToolTip(scan_id)
        backend = result.get("backend", {})
        backend_name = str(backend.get("name", backend.get("backend", "mock")))
        self.backend_label.setText(
            f"推論後端：{backend_name}  ·  本版為 CPU / Mock 規則示範，非語言模型  ·  UGen300 未驗證\n"
            + self._network_scope_text()
        )
        while self.findings_layout.count():
            item = self.findings_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not findings:
            self.findings_layout.addWidget(label(
                "目前沒有偵測到規則涵蓋的問題。這不代表所有硬體與軟體都已通過檢查。",
                "muted", wrap=True,
            ))
        for finding in findings:
            self.findings_layout.addWidget(self._finding_card(finding))
        self.audit_view.setPlainText("\n\n".join(self._repair_text(item) for item in repairs)
                                     or "尚未執行修復。\n預演、執行與驗證結果會保留於報告。")
        self._update_controls()

    def _finding_card(self, finding: dict[str, Any]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("findingCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(7)
        title_row = QHBoxLayout()
        severity = str(finding.get("severity", "info")).lower()
        severity_text = {"critical": "高優先", "error": "異常", "high": "高優先", "warning": "需注意", "medium": "需注意", "low": "提示", "info": "提示"}.get(severity, severity)
        badge = label(severity_text, "severity")
        badge.setProperty("severity", severity)
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        title_row.addWidget(badge)
        title_row.addWidget(label(str(finding.get("title", "未命名診斷")), "findingTitle", wrap=True), 1)
        layout.addLayout(title_row)
        evidence = finding.get("evidence", [])
        evidence_text = "\n".join("• " + str(item) for item in evidence)
        if evidence_text:
            layout.addWidget(label(evidence_text, "evidence", wrap=True))
        layout.addWidget(label(str(finding.get("recommendation", "請檢閱報告。")), "recommendation", wrap=True))
        if finding.get("action_id") == SPOOLER_ACTION:
            action_note = (
                "本次修復已驗證。此卡保留原始診斷證據；重新檢查可更新狀態。"
                if SPOOLER_ACTION in self._resolved_actions
                else "可使用右側安全修復面板預演與逐次授權。"
            )
            layout.addWidget(label(action_note, "actionAvailable", wrap=True))
        return frame

    @staticmethod
    def _repair_text(item: dict[str, Any]) -> str:
        mode = "預演" if item.get("dry_run") else ("模擬執行" if item.get("simulated") else "本機執行")
        verified = "通過" if item.get("verified") is True else "未通過 / 不適用"
        return f"{mode} · {item.get('status', 'unknown')}\n{item.get('message', '')}\n驗證：{verified}"

    @Slot()
    def _update_controls(self) -> None:
        self.scan_button.setEnabled(not self._busy)
        self.scan_button.setText("重新檢查" if self._result else "開始健康檢查")
        self.dry_run_checkbox.setEnabled(not self._busy)
        eligible = self._eligible_action == SPOOLER_ACTION
        self.repair_button.setEnabled(eligible and not self._busy)
        if self.dry_run_checkbox.isChecked():
            self.repair_button.setText("預演啟動列印服務")
        else:
            self.repair_button.setText("批准並模擬執行…" if self.demo else "批准並執行修復…")
        if eligible:
            self.repair_hint.setText("已發現可修復項目。取消預演後，仍需逐次明確批准。")
        elif SPOOLER_ACTION in self._resolved_actions:
            self.repair_hint.setText("本次服務啟動已驗證。重新檢查後才會重新評估可用動作。")
        else:
            self.repair_hint.setText("偵測到列印服務停止後，才會提供此動作。")
        has_result = bool(self._result) and not self._busy
        self.view_report_button.setEnabled(has_result)
        self.export_button.setEnabled(has_result)
        self.folder_button.setEnabled(has_result and bool(self._report_paths))

    @Slot()
    def show_report(self) -> None:
        if not self._result or self._busy:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("PC Guardian AI — 診斷與修復報告")
        dialog.resize(900, 710)
        layout = QVBoxLayout(dialog)
        path_label = label(self._report_paths.get("markdown", "尚未儲存 Markdown 報告"), "mutedSmall", wrap=True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setOpenLinks(False)
        path = self._report_paths.get("markdown")
        try:
            content = Path(path).read_text(encoding="utf-8") if path else ""
            if content:
                view.setMarkdown(content[:250_000])
            else:
                view.setPlainText(json.dumps(self._result, ensure_ascii=False, indent=2))
        except (OSError, UnicodeError) as exc:
            view.setPlainText(f"無法開啟報告：{exc}\n\n" + json.dumps(self._result, ensure_ascii=False, indent=2))
        layout.addWidget(view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    @Slot()
    def open_report_folder(self) -> None:
        if self._busy:
            return
        report = self._report_paths.get("markdown") or self._report_paths.get("json")
        if report and Path(report).parent.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(report).resolve().parent)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            # Do not terminate a worker while a service mutation/audit is in flight.
            self._close_when_finished = True
            self.status_label.setText("正在完成目前作業與紀錄，完成後會自動關閉。")
            event.ignore()
            return
        event.accept()


STYLES = """
QMainWindow, QDialog { background: #f2f5f7; color: #172f3b; }
QWidget { color: #172f3b; font-size: 13px; }
QLabel { background: transparent; }
QFrame#sidebar { background: #122e3a; border: none; }
QLabel#brandMark { color: #69dbc4; font-size: 37px; font-weight: 700; }
QLabel#brand { color: white; font-size: 27px; font-weight: 700; line-height: 1.1; }
QLabel#sidebarMuted { color: #b6cbd3; font-size: 11px; }
QLabel#sidebarEyebrow { color: #76ceb9; font-size: 11px; font-weight: 700; }
QLabel#hardwareNote { color: #d2e0e5; background: #1e3e4b; padding: 11px; border-radius: 7px; font-size: 11px; }
QLabel#navActive { color: #77e3cc; background: #224551; border-radius: 7px; padding: 12px 8px; font-weight: 600; }
QLabel#navItem { color: #b8cbd1; padding: 12px 8px; }
QLabel#eyebrow { font-size: 10px; color: #537483; font-weight: 700; }
QLabel#pageTitle { font-size: 27px; font-weight: 700; color: #15303e; }
QLabel#muted { color: #526c78; font-size: 12px; }
QLabel#mutedSmall { color: #59727e; font-size: 11px; }
QLabel#demoBanner { padding: 11px 14px; background: #e2f3ed; border: 1px solid #bdded2; border-radius: 8px; color: #225c4e; font-weight: 600; }
QLabel#scopeBanner { padding: 11px 14px; background: #e9effa; border: 1px solid #c7d5ed; border-radius: 8px; color: #315a8b; font-weight: 600; }
QFrame#panel { background: white; border: 1px solid #dce5e9; border-radius: 10px; }
QLabel#metricHeading { color: #536c79; font-size: 12px; }
QLabel#metricNumber { font-size: 31px; font-weight: 700; color: #173c4b; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
QLabel#actionTitle { font-size: 15px; font-weight: 600; }
QScrollArea, QScrollArea > QWidget > QWidget { background: white; border: none; }
QFrame#findingCard { background: #f8fafb; border: 1px solid #e0e8ec; border-radius: 8px; }
QLabel#findingTitle { font-weight: 600; font-size: 14px; }
QLabel#severity { background: #fff0d6; color: #89560c; padding: 4px 7px; border-radius: 4px; font-size: 10px; font-weight: 600; }
QLabel#severity[severity="critical"], QLabel#severity[severity="error"], QLabel#severity[severity="high"] { background: #fce3e1; color: #983a35; }
QLabel#severity[severity="info"], QLabel#severity[severity="low"] { background: #e6eef6; color: #3b607b; }
QLabel#evidence { font-size: 11px; color: #526c79; }
QLabel#recommendation { font-size: 12px; color: #294957; }
QLabel#actionAvailable { font-size: 11px; color: #247464; }
QLabel#status { color: #375967; font-size: 12px; }
QPushButton { background: white; border: 1px solid #cad9df; border-radius: 7px; padding: 9px 13px; font-weight: 600; }
QPushButton:hover { background: #edf4f5; border-color: #90adb8; }
QPushButton:pressed { background: #e0ebee; }
QPushButton:focus { border: 2px solid #327a94; }
QPushButton:disabled { color: #98a9b1; background: #f0f3f5; border-color: #e0e7eb; }
QPushButton#primary { color: white; background: #16745f; border: 1px solid #16745f; padding: 11px 20px; }
QPushButton#primary:hover { background: #11644f; }
QPushButton#primary:disabled { background: #96bdb4; border-color: #96bdb4; }
QPushButton#repairButton { color: #1e6958; background: #e6f5ef; border: 1px solid #b9dacf; }
QPushButton#repairButton:hover { background: #d4eee3; }
QPushButton#repairButton:disabled { color: #8eaaa2; background: #f0f5f3; border-color: #dde7e3; }
QCheckBox { font-size: 12px; spacing: 8px; padding: 6px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QTextBrowser { border: none; background: white; color: #486572; font-size: 11px; }
QProgressBar { border: none; background: #dae9e5; border-radius: 2px; }
QProgressBar::chunk { background: #239278; border-radius: 2px; }
QScrollBar:vertical { background: #f1f5f7; width: 8px; border: none; }
QScrollBar::handle:vertical { background: #c9d9df; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
