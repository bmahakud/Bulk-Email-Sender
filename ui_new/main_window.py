"""
Professional Bulk Mailer – Main Window
Implements a MailFlow-Pro-style interface with:
  • Live dynamic analytics Dashboard (Index 0)
  • Dynamic campaign task creation (using dynamic tabs & "+" tab)
  • Start / Pause / Stop per task & globally
  • Global Tag Reference popup
"""
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QStatusBar,
    QMessageBox, QDialog, QScrollArea, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction

from backend.database import Database
from ui_new.task_panel import TaskPanel
from ui_new.dashboard import DashboardWidget

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #12131a;
    color: #e8eaf0;
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: none;
    background: #1a1b27;
}
QTabBar::tab {
    background: #1a1b27;
    color: #7880a0;
    padding: 11px 24px;
    font-size: 12px;
    font-weight: 600;
    border: none;
    border-right: 1px solid #252637;
    min-width: 120px;
}
QTabBar::tab:selected {
    background: #252637;
    color: #ffffff;
    border-bottom: 3px solid #5865f2;
}
QTabBar::tab:hover:!selected {
    background: #1f2030;
    color: #c0c8e8;
}
QScrollBar:vertical {
    background: #1a1b27;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3d3f52;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar:horizontal {
    background: #1a1b27;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #3d3f52;
    border-radius: 4px;
    min-width: 30px;
}
QStatusBar {
    background: #0d0e17;
    color: #5865f2;
    padding: 5px 15px;
    font-size: 11px;
    border-top: 1px solid #252637;
}
"""

class TagReferenceDialog(QDialog):
    """Modal showing every supported tag."""

    TAGS = [
        ("#TFN1#",    "Phone Number 1 (set in Tags panel)"),
        ("#TFN2#",    "Phone Number 2 (set in Tags panel)"),
        ("#DATE#",    "System date — auto-picked (e.g. June 29, 2026)"),
        ("#TIME#",    "System time — auto-picked or manual"),
        ("#EMAIL#",   "Recipient email address"),
        ("#NAME#",    "Recipient name from CSV; else email prefix"),
        ("#INVOICE#", "Random invoice  e.g. INV-26GFY-6366"),
        ("#ORDERID#", "Random order ID e.g. 8266367-2026"),
        ("#TXNID#",   "Random 9-char transaction ID"),
        ("#TYPE#",    "Random payment type (Bank Transfer, PayPal, ACH, …)"),
        ("#AMOUNT#",  "Amount — custom or random in range"),
        ("#KEY#",     "Random UUID key e.g. 462aebf1-d3db-4609-…"),
        ("#GUID#",    "Random GUID e.g. 4dc5f965-7c10-48d8-…"),
        ("#SNUMBER#", "Random 6-digit serial number"),
        ("#ADDRESS#", "Cycles through uploaded address list"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag Reference")
        self.setMinimumSize(720, 540)
        self.setStyleSheet("""
            QDialog { background:#1a1b27; color:#e8eaf0; }
            QLabel  { color:#e8eaf0; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(10)

        title = QLabel("🏷  Complete Tag Reference")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet("color:#5865f2; margin-bottom:8px;")
        lay.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:#1a1b27; border:none; }")

        inner = QWidget()
        inner.setStyleSheet("background:#1a1b27;")
        grid = QVBoxLayout(inner)
        grid.setSpacing(1)
        grid.setContentsMargins(0,0,0,0)

        for i, (tag, desc) in enumerate(self.TAGS):
            row = QWidget()
            row.setStyleSheet(
                "background:#252637; border-radius:4px; margin:2px 0;"
                if i % 2 == 0 else
                "background:#1e1f2e; border-radius:4px; margin:2px 0;"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12,8,12,8)
            t = QLabel(tag)
            t.setFont(QFont("Courier New", 11, QFont.Bold))
            t.setStyleSheet("color:#00d4aa; min-width:120px; max-width:120px;")
            t.setFixedWidth(140)
            d = QLabel(desc)
            d.setStyleSheet("color:#c0c8e8;")
            d.setWordWrap(True)
            rl.addWidget(t)
            rl.addWidget(d, 1)
            grid.addWidget(row)

        grid.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton { background:#5865f2; color:white; border:none;
                          padding:10px 30px; border-radius:6px; font-weight:600; }
            QPushButton:hover { background:#4752c4; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


class MainWindow(QMainWindow):
    """Professional Bulk Mailer – Main Window"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.task_panels: list[TaskPanel] = []

        self.setWindowTitle("✉ ProMailer Pro | Bulk Email Sender – Campaign Command Center")
        self.setMinimumSize(1380, 880)
        self.setStyleSheet(DARK_STYLE)

        self._build_menu()
        self._build_ui()
        self._init_status_timer()

    # ── Menu ─────────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet("""
            QMenuBar { background:#0d0e17; color:#aab; padding:4px; }
            QMenuBar::item { padding:6px 14px; }
            QMenuBar::item:selected { background:#252637; color:white; }
            QMenu { background:#252637; color:#e8eaf0; border:1px solid #3d3f52; }
            QMenu::item:selected { background:#5865f2; }
        """)
        file_menu = mb.addMenu("File")
        
        act_add_task = QAction("➕ Create New Task", self)
        act_add_task.triggered.connect(self._add_task_dynamic)
        file_menu.addAction(act_add_task)
        
        act_clear_smtp = QAction("Clear SMTP + Data", self)
        act_clear_smtp.triggered.connect(self._clear_smtp_and_data)
        file_menu.addAction(act_clear_smtp)
        
        file_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        help_menu = mb.addMenu("Tags Reference")
        act_tags = QAction("Show All Tags  (★)", self)
        act_tags.triggered.connect(self._show_tags_dialog)
        help_menu.addAction(act_tags)

    # ── Central UI ───────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        root.addWidget(self._make_header())

        # ── Top toolbar ──
        root.addWidget(self._make_toolbar())

        # ── Tab widget ──
        self.task_tabs = QTabWidget()
        self.task_tabs.setTabPosition(QTabWidget.North)
        self.task_tabs.setDocumentMode(True)
        self.task_tabs.setTabsClosable(True)
        root.addWidget(self.task_tabs, 1)

        # ── Add Permanent Dashboard ──
        self.dashboard = DashboardWidget(self)
        self.task_tabs.addTab(self.dashboard, "📊 Dashboard")
        
        # Hide close button on permanent dashboard tab
        tb = self.task_tabs.tabBar()
        tb.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

        # ── Add "+ Add Task" trigger tab at end ──
        self.add_task_trigger = QWidget()
        self.task_tabs.addTab(self.add_task_trigger, "➕ Add Task")
        tb.setTabButton(1, QTabBar.ButtonPosition.RightSide, None)

        # Add initial default task (Task 1)
        self._add_task_dynamic()
        self.task_tabs.setCurrentIndex(1)

        # Connect tab events ONLY after initial setup is complete
        self.task_tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.task_tabs.currentChanged.connect(self._on_tab_changed)

        # ── Status bar ──
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("✓ ProMailer Pro | Bulk Email Sender – Ready")

    def _make_header(self):
        bar = QWidget()
        bar.setFixedHeight(58)
        bar.setStyleSheet("""
            QWidget { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0d0e17, stop:0.6 #12131a, stop:1 #1a1b27);
                border-bottom: 2px solid #5865f2; }
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 8, 20, 8)

        logo = QLabel("✉  ProMailer Pro")
        logo.setFont(QFont("Segoe UI", 17, QFont.Bold))
        logo.setStyleSheet("color:#5865f2; letter-spacing:1px;")

        ver  = QLabel("v3.0 Professional")
        ver.setStyleSheet("color:#3d3f52; font-size:11px; margin-left:10px;")

        sub  = QLabel("Bulk Email Sender")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color:#7289da; font-size:12px; margin-left:16px; letter-spacing:0.5px;")

        self.lbl_online = QLabel("● Active Operations")
        self.lbl_online.setStyleSheet("color:#43b581; font-size:12px; font-weight:600;")

        lay.addWidget(logo)
        lay.addWidget(ver)
        lay.addWidget(sub)
        lay.addStretch()
        lay.addWidget(self.lbl_online)
        return bar

    def _make_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background:#0d0e17; border-bottom:1px solid #252637;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 4, 16, 4)
        lay.setSpacing(8)

        def tb_btn(label, color, slot):
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.setStyleSheet(f"""
                QPushButton {{ background:{color}; color:white; border:none;
                              padding:0 16px; border-radius:5px; font-weight:600; font-size:12px; }}
                QPushButton:hover {{ opacity:0.85; }}
            """)
            b.clicked.connect(slot)
            return b

        lay.addWidget(tb_btn("▶ Start All",  "#43b581", self._start_all))
        lay.addWidget(tb_btn("⏸ Pause All",  "#f0a500", self._pause_all))
        lay.addWidget(tb_btn("⏹ Stop All",   "#ed4245", self._stop_all))
        lay.addSpacing(16)
        lay.addWidget(tb_btn("➕ New Task",   "#5865f2", self._add_task_dynamic))
        lay.addWidget(tb_btn("🏷 Tags",       "#7289da", self._show_tags_dialog))
        lay.addWidget(tb_btn("🗑 Clear Data",  "#3d3f52", self._clear_smtp_and_data))
        lay.addStretch()

        self.lbl_stats = QLabel("Sent: 0  |  Failed: 0  |  Queue: 0")
        self.lbl_stats.setStyleSheet("color:#7880a0; font-size:11px;")
        lay.addWidget(self.lbl_stats)
        return bar

    # ── Task management ──────────────────────────────────────────────────────
    def _add_task_dynamic(self):
        """Creates a task dynamically, placing it right before reference '+' tab."""
        # Find next clean task id string
        next_id = 1
        if self.task_panels:
            next_id = max(p.task_id for p in self.task_panels) + 1
            
        panel = TaskPanel(next_id, self.db)
        panel.stats_changed.connect(self._refresh_global_stats)
        panel.activity_logged.connect(self.dashboard.log_activity)
        
        self.task_panels.append(panel)
        
        # Insert before the last tab (which is "+ Add Task")
        insert_idx = self.task_tabs.count() - 1
        self.task_tabs.insertTab(insert_idx, panel, f"Task {next_id}")
        self.task_tabs.setCurrentIndex(insert_idx)
        
        self.dashboard.log_activity(next_id, "Campaign workspace created.")
        self._refresh_global_stats()

    def _on_tab_changed(self, index):
        """Monitor if the user clicked the last '+' tab."""
        if index == self.task_tabs.count() - 1:
            self._add_task_dynamic()

    def _on_tab_close_requested(self, index):
        """Handles close event on dynamic tabs."""
        # Do not close permanent tabs (Dashboard/Add Task)
        if index == 0 or index == self.task_tabs.count() - 1:
            return
            
        widget = self.task_tabs.widget(index)
        if isinstance(widget, TaskPanel):
            reply = QMessageBox.question(
                self, "Remove Task",
                f"Are you sure you want to delete Task {widget.task_id}?\n"
                "All un-saved inputs for this task will be discarded.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if widget.worker and widget.worker.isRunning():
                    widget.stop_task()
                self.task_panels.remove(widget)
                self.task_tabs.removeTab(index)
                widget.deleteLater()
                self._refresh_global_stats()

    # ── Global controls ──────────────────────────────────────────────────────
    def _start_all(self):
        self.dashboard.log_activity(0, "Command: Start all campaigns sent")
        for p in self.task_panels:
            if p.enabled:
                p.start_task()

    def _pause_all(self):
        self.dashboard.log_activity(0, "Command: Pause all campaigns sent")
        for p in self.task_panels:
            p.pause_task()

    def _stop_all(self):
        self.dashboard.log_activity(0, "Command: Stop all campaigns sent")
        for p in self.task_panels:
            p.stop_task()

    def _clear_smtp_and_data(self):
        reply = QMessageBox.question(
            self, "Confirm",
            "Clear ALL SMTP accounts and recipient data from DB?\n\n"
            "(HTML templates, subjects and tags will be preserved.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_smtp_accounts()
            self.db.clear_recipients()
            for p in self.task_panels:
                p.refresh_smtp_list()
                p.refresh_recipient_count()
            self.dashboard.log_activity(0, "Settings/SMTP/Recipient DB truncated.")
            QMessageBox.information(self, "Cleared", "SMTP accounts and recipients cleared.")

    # ── Tags dialog ──────────────────────────────────────────────────────────
    def _show_tags_dialog(self):
        dlg = TagReferenceDialog(self)
        dlg.exec()

    # ── Stats refresh ─────────────────────────────────────────────────────────
    def _refresh_global_stats(self):
        total_sent = sum(p.sent_count  for p in self.task_panels)
        total_fail = sum(p.fail_count  for p in self.task_panels)
        total_q    = sum(p.queue_count for p in self.task_panels)
        self.lbl_stats.setText(f"Sent: {total_sent}  |  Failed: {total_fail}  |  Queue: {total_q}")

    def _init_status_timer(self):
        timer = QTimer(self)
        timer.timeout.connect(self._refresh_global_stats)
        timer.start(2000)

# Import fix for TabBar styling custom close button hiding
from PySide6.QtWidgets import QTabBar
