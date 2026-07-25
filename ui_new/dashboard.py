"""
Dashboard – Central command center for analytics and recent activity.
Provides premium modern cards, tables, and a unified real-time log.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from datetime import datetime

CARD_SS = """
QFrame {
    background-color: #1e1f2e;
    border: 1px solid #252637;
    border-radius: 8px;
}
QLabel {
    color: #e8eaf0;
    border: none;
    background: transparent;
}
"""

class StatCard(QFrame):
    """Sleek analytics stat card."""
    def __init__(self, title: str, val: str, color: str, icon_str: str = ""):
        super().__init__()
        self.setStyleSheet(CARD_SS)
        self.setMinimumHeight(100)
        self.setMinimumWidth(180)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        
        row = QHBoxLayout()
        row.setSpacing(8)
        self.lbl_icon = QLabel(icon_str)
        self.lbl_icon.setFont(QFont("Segoe UI", 16))
        self.lbl_icon.setStyleSheet(f"color: {color};")
        row.addWidget(self.lbl_icon)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_title.setStyleSheet("color: #7880a0;")
        row.addWidget(self.lbl_title)
        row.addStretch()
        lay.addLayout(row)
        
        self.lbl_val = QLabel(val)
        self.lbl_val.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.lbl_val.setStyleSheet(f"color: {color}; font-weight: 800; margin-top:2px;")
        lay.addWidget(self.lbl_val)

    def set_value(self, text: str):
        self.lbl_val.setText(text)

class DashboardWidget(QWidget):
    """Main overview dashboard."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        self.setStyleSheet("""
            QWidget { background-color: #12131a; color: #e8eaf0; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #1a1b27; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #3d3f52; border-radius: 4px; }
            QTableWidget {
                background-color: #1a1b27;
                color: #e8eaf0;
                gridline-color: #252637;
                border: 1px solid #252637;
                border-radius: 6px;
            }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #252637; }
            QHeaderView::section {
                background-color: #252637;
                color: #7880a0;
                padding: 6px;
                font-weight: bold;
                border: none;
            }
        """)
        
        self._build_ui()
        
        # Start a refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)
        
        # --- TITLE BLOCK ---
        title_row = QHBoxLayout()
        lbl_title = QLabel("📊 System Dashboard")
        lbl_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        lbl_title.setStyleSheet("color: #5865f2;")
        title_row.addWidget(lbl_title)
        
        self.lbl_time = QLabel("")
        self.lbl_time.setFont(QFont("Segoe UI", 11))
        self.lbl_time.setStyleSheet("color: #7880a0;")
        title_row.addStretch()
        title_row.addWidget(self.lbl_time)
        root.addLayout(title_row)
        
        # --- CARDS GRID ---
        self.cards_lay = QHBoxLayout()
        self.cards_lay.setSpacing(16)
        
        self.card_sent = StatCard("SENT EMAILS", "0", "#43b581", "✉")
        self.card_fail = StatCard("FAILED EMAILS", "0", "#ed4245", "⚠")
        self.card_queue = StatCard("IN QUEUE", "0", "#f0a500", "⏳")
        self.card_rate = StatCard("SUCCESS RATE", "100.0%", "#00d4aa", "★")
        self.card_active = StatCard("ACTIVE TASKS", "0", "#5865f2", "⚙")
        
        self.cards_lay.addWidget(self.card_sent)
        self.cards_lay.addWidget(self.card_fail)
        self.cards_lay.addWidget(self.card_queue)
        self.cards_lay.addWidget(self.card_rate)
        self.cards_lay.addWidget(self.card_active)
        root.addLayout(self.cards_lay)
        
        # --- SCROLLABLE BODY ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)
        
        # Left Panel (Task List table)
        tb_grp = QFrame()
        tb_grp.setStyleSheet("background-color: #1a1b27; border: 1px solid #252637; border-radius: 8px;")
        tcl = QVBoxLayout(tb_grp)
        tcl.setContentsMargins(16, 16, 16, 16)
        
        tbar = QHBoxLayout()
        lbl_tb = QLabel("📋 Active Campaigns Overview")
        lbl_tb.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl_tb.setStyleSheet("color:#e8eaf0;")
        tbar.addWidget(lbl_tb)
        tbar.addStretch()
        tcl.addLayout(tbar)
        
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Task ID", "Status", "Queue Remainder", "Sent / Failed", "Progress"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(240)
        tcl.addWidget(self.table)
        body_lay.addWidget(tb_grp)
        
        # Right Panel (Recent unified Activity Log)
        log_grp = QFrame()
        log_grp.setStyleSheet("background-color: #1a1b27; border: 1px solid #252637; border-radius: 8px;")
        lg_lay = QVBoxLayout(log_grp)
        lg_lay.setContentsMargins(16, 16, 16, 16)
        
        lbl_lg = QLabel("🔔 Recent Activity Stream")
        lbl_lg.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl_lg.setStyleSheet("color:#e8eaf0; margin-bottom:4px;")
        lg_lay.addWidget(lbl_lg)
        
        self.recent_activity = QTableWidget(0, 3)
        self.recent_activity.setHorizontalHeaderLabels(["Time", "Campaign Task", "Event Detail"])
        self.recent_activity.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.recent_activity.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.recent_activity.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.recent_activity.verticalHeader().hide()
        self.recent_activity.setMinimumHeight(260)
        lg_lay.addWidget(self.recent_activity)
        body_lay.addWidget(log_grp)
        
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        
        self.activities_log = []

    def log_activity(self, task_id: int, detail: str):
        """Append to system-wide activity database feed."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.activities_log.insert(0, (now_str, f"Task {task_id}", detail))
        # Keep log size friendly
        if len(self.activities_log) > 100:
            self.activities_log.pop()
        self.update_activity_table()

    def update_activity_table(self):
        self.recent_activity.setRowCount(0)
        for ts, task, desc in self.activities_log:
            row = self.recent_activity.rowCount()
            self.recent_activity.insertRow(row)
            
            i_ts = QTableWidgetItem(ts)
            i_tsk = QTableWidgetItem(task)
            i_dsc = QTableWidgetItem(desc)
            
            # Colors
            if "success" in desc.lower() or "sent" in desc.lower():
                i_dsc.setForeground(QColor("#43b581"))
            elif "fail" in desc.lower() or "error" in desc.lower():
                i_dsc.setForeground(QColor("#ed4245"))
            elif "start" in desc.lower():
                i_dsc.setForeground(QColor("#5865f2"))
            elif "pause" in desc.lower():
                i_dsc.setForeground(QColor("#f0a500"))
                
            self.recent_activity.setItem(row, 0, i_ts)
            self.recent_activity.setItem(row, 1, i_tsk)
            self.recent_activity.setItem(row, 2, i_dsc)

    def update_dashboard(self):
        """Calculates global counters and updates tables."""
        tasks = self.main_window.task_panels
        
        self.lbl_time.setText(f"System Time: {datetime.now().strftime('%H:%M:%S')}  |  Date: {datetime.now().strftime('%B %d, %Y')}")
        
        total_sent = 0
        total_failed = 0
        total_queue = 0
        active_count = 0
        
        self.table.setRowCount(0)
        
        for p in tasks:
            total_sent += p.sent_count
            total_failed += p.fail_count
            total_queue += p.queue_count
            
            is_active = p.worker and p.worker.isRunning()
            if is_active:
                active_count += 1
                
            status_text = "Idle"
            if p.worker:
                if p.worker._paused:
                    status_text = "Paused"
                elif p.worker.isRunning():
                    status_text = "Running"
                else:
                    status_text = "Done"
            
            # Progress calculation
            denom = p.sent_count + p.fail_count + p.queue_count
            percent = 0
            if denom > 0:
                percent = int(((p.sent_count + p.fail_count) / denom) * 100)
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(f"Task {p.task_id} Overview"))
            self.table.setItem(row, 1, QTableWidgetItem(status_text))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.queue_count)))
            self.table.setItem(row, 3, QTableWidgetItem(f"{p.sent_count} Sent / {p.fail_count} Failed"))
            
            # Progress bar inside cell
            prog_bar = QProgressBar()
            prog_bar.setRange(0, 100)
            prog_bar.setValue(percent)
            prog_bar.setTextVisible(True)
            prog_bar.setAlignment(Qt.AlignCenter)
            prog_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #252637;
                    border: 1px solid #3d3f52;
                    border-radius: 4px;
                    text-align: center;
                    color: white;
                    font-size: 11px;
                }
                QProgressBar::chunk {
                    background-color: #5865f2;
                    border-radius: 3px;
                }
            """)
            self.table.setCellWidget(row, 4, prog_bar)
            
        rate_val = 100.0
        tot = total_sent + total_failed
        if tot > 0:
            rate_val = round((total_sent / tot) * 100, 2)
            
        self.card_sent.set_value(f"{total_sent}")
        self.card_fail.set_value(f"{total_failed}")
        self.card_queue.set_value(f"{total_queue}")
        self.card_rate.set_value(f"{rate_val}%")
        self.card_active.set_value(f"{active_count}")
