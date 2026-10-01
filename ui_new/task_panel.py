"""
TaskPanel – one complete campaign task panel.
Contains: Recipients | SMTP | Tags | Content | Delays tabs, plus live log.
All tabs use QScrollArea so nothing is ever hidden.
"""
import csv
import base64
import random
import os
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QLineEdit,
    QFileDialog, QGroupBox, QRadioButton, QCheckBox,
    QSpinBox, QDoubleSpinBox, QListWidget, QGridLayout,
    QListWidgetItem, QTabWidget, QFrame, QFormLayout,
    QScrollArea, QMessageBox, QDialog, QDialogButtonBox,
    QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from backend.database import Database
from backend.task_worker import TaskWorker

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# ── Shared style helpers ───────────────────────────────────────────────────────
def BTN(c, hover=None):
    h = hover or c
    return f"""
    QPushButton {{ background:{c}; color:#fff; border:none;
                  padding:7px 16px; border-radius:5px; font-weight:600; font-size:12px; }}
    QPushButton:hover {{ background:{h}; }}
    QPushButton:disabled {{ background:#2e2f3e; color:#555; }}
"""

SHARED_SS = """
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background:#252637; color:#e8eaf0; border:1px solid #3d3f52;
        border-radius:5px; padding:6px 10px; font-size:12px; }
    QLineEdit:focus, QTextEdit:focus { border:1px solid #5865f2; }
    QListWidget { background:#1a1b27; color:#c0c8e8; border:1px solid #3d3f52;
                  border-radius:5px; padding:4px; }
    QListWidget::item { padding:4px 6px; border-bottom:1px solid #252637; }
    QListWidget::item:selected { background:#5865f2; color:#fff; }
    QGroupBox { color:#a0a8c8; font-weight:700; border:1px solid #3d3f52;
                border-radius:6px; margin-top:14px; padding-top:18px; background:#1e1f2e; }
    QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; color:#c0c8e8; }
    QCheckBox, QRadioButton { color:#c0c8e8; spacing:6px; }
    QCheckBox:checked, QRadioButton:checked { color:#ffffff; font-weight:bold; }
    QRadioButton::indicator {
        width: 14px;
        height: 14px;
        border-radius: 9px;
        border: 2px solid #4a4d6d;
        background-color: #1a1b27;
    }
    QRadioButton::indicator:hover {
        border-color: #5865f2;
    }
    QRadioButton::indicator:checked {
        border: 2px solid #5865f2;
        background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.4, fx:0.5, fy:0.5,
                                        stop:0 #ffffff, stop:0.6 #ffffff,
                                        stop:0.7 #5865f2, stop:1.0 #5865f2);
    }
    QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border-radius: 3px;
        border: 2px solid #4a4d6d;
        background-color: #1a1b27;
    }
    QCheckBox::indicator:hover {
        border-color: #5865f2;
    }
    QCheckBox::indicator:checked {
        border: 2px solid #5865f2;
        background-color: #5865f2;
        image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'><path d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/></svg>");
    }
    QScrollArea { background:#1a1b27; border:none; }
    QScrollBar:vertical { background:#1a1b27; width:8px; border-radius:4px; }
    QScrollBar::handle:vertical { background:#3d3f52; border-radius:4px; min-height:30px; }
    QScrollBar:horizontal { background:#1a1b27; height:8px; border-radius:4px; }
    QScrollBar::handle:horizontal { background:#3d3f52; border-radius:4px; min-width:30px; }
    QTabWidget::pane { background:#1a1b27; border:none; }
    QTabBar::tab { background:#252637; color:#7880a0; padding:9px 20px;
                   font-size:12px; border:none; margin-right:2px; border-radius:4px 4px 0 0; }
    QTabBar::tab:selected { background:#1a1b27; color:#fff; border-bottom:2px solid #5865f2; }
    QTabBar::tab:hover:!selected { background:#2a2b3d; color:#c0c8e8; }
    QLabel { color:#c0c8e8; }
"""
PANEL_BG = "background:#1a1b27;"


def _scroll_wrap(inner_widget):
    """Wrap a widget in a styled QScrollArea."""
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(inner_widget)
    return sa


class PasteDialog(QDialog):
    """Reusable paste-text dialog."""
    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(660, 420)
        self.setStyleSheet("""
            QDialog { background:#1a1b27; color:#e8eaf0; }
            QLabel  { color:#a0a8c8; font-size:12px; }
            QTextEdit { background:#252637; color:#e8eaf0; border:1px solid #3d3f52;
                        border-radius:5px; padding:8px; font-family:'Courier New'; font-size:12px; }
            QPushButton { background:#5865f2; color:white; border:none;
                          padding:8px 24px; border-radius:5px; font-weight:600; }
            QPushButton:hover { background:#4752c4; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        lbl = QLabel(hint)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText("Paste here…")
        lay.addWidget(self.edit, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def get_text(self) -> str:
        return self.edit.toPlainText()


class TaskPanel(QWidget):
    """Full campaign task panel (one per task tab)."""

    stats_changed = Signal()
    activity_logged = Signal(int, str)

    def __init__(self, task_id: int, db: Database, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.db = db
        self.worker: TaskWorker = None
        self.enabled = True
        self.sent_count = 0
        self.fail_count = 0
        self.queue_count = 0
        self._prev_rec_count = -1
        self._rec_change_timer = QTimer(self)
        self._rec_change_timer.setSingleShot(True)
        self._rec_change_timer.timeout.connect(self._on_rec_timer_timeout)

        self.setStyleSheet(PANEL_BG + SHARED_SS)
        self._build_ui()
        self._load_settings()   # restore persisted parameters

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_top_bar())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background: #1e202f;
                width: 5px;
            }
            QSplitter::handle:hover {
                background: #5865f2;
            }
        """)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet(SHARED_SS)
        self.sub_tabs.setMinimumWidth(560)
        self.sub_tabs.addTab(self._tab_recipients(), "📨 Recipients")
        self.sub_tabs.addTab(self._tab_smtp(),       "📧 SMTP")
        self.sub_tabs.addTab(self._tab_tags(),       "🏷 Tags")
        self.sub_tabs.addTab(self._tab_content(),    "📝 Content")
        self.sub_tabs.addTab(self._tab_delays(),     "⚙ Delays & Limits")
        self.splitter.addWidget(self.sub_tabs)
        self.splitter.addWidget(self._make_log_pane())

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)  # Tab content pane gets 100% of window resize growth
        self.splitter.setStretchFactor(1, 0)  # Log pane stays docked at compact size
        self.splitter.setSizes([880, 380])
        root.addWidget(self.splitter, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_splitter_initialized', False):
            self._splitter_initialized = True
            total_w = self.splitter.width()
            if total_w > 500:
                log_w = max(360, min(420, int(total_w * 0.30)))
                left_w = total_w - log_w
                self.splitter.setSizes([left_w, log_w])

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _make_top_bar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#0d0e17; border-bottom:1px solid #252637;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 4, 14, 4)
        lay.setSpacing(10)

        self.chk_enable = QCheckBox(f"✓ Task {self.task_id}")
        self.chk_enable.setChecked(True)
        self.chk_enable.setStyleSheet(
            "color:#e8eaf0; font-weight:700; font-size:13px; spacing:6px;")
        self.chk_enable.toggled.connect(lambda v: setattr(self, 'enabled', v))

        self.lbl_status = QLabel("● Idle")
        self.lbl_status.setStyleSheet("color:#7880a0; font-size:12px; font-weight:700; padding:0 12px;")

        self.lbl_queue  = QLabel("Queue: 0")
        self.lbl_sent   = QLabel("Sent: 0")
        self.lbl_failed = QLabel("Failed: 0")
        for lbl in (self.lbl_queue, self.lbl_sent, self.lbl_failed):
            lbl.setStyleSheet("color:#7880a0; font-size:12px; padding:0 8px;")

        self.btn_start = QPushButton("▶ Send Task")
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_stop  = QPushButton("⏹ Stop")
        self.btn_test  = QPushButton("🔍 Test SMTP")

        self.btn_start.setStyleSheet(BTN("#43b581", "#369e6b"))
        self.btn_pause.setStyleSheet(BTN("#f0a500", "#c88a00"))
        self.btn_stop.setStyleSheet(BTN("#ed4245", "#c93638"))
        self.btn_test.setStyleSheet(BTN("#5865f2", "#4752c4"))

        self.btn_start.clicked.connect(self.start_task)
        self.btn_pause.clicked.connect(self.pause_task)
        self.btn_stop.clicked.connect(self.stop_task)
        self.btn_test.clicked.connect(self.test_smtp)

        lay.addWidget(self.chk_enable)
        lay.addWidget(self.lbl_status)
        lay.addWidget(self.lbl_queue)
        lay.addWidget(self.lbl_sent)
        lay.addWidget(self.lbl_failed)
        lay.addStretch()
        lay.addWidget(self.btn_test)
        lay.addWidget(self.btn_start)
        lay.addWidget(self.btn_pause)
        lay.addWidget(self.btn_stop)
        return bar

    # ── Recipients tab ────────────────────────────────────────────────────────
    def _tab_recipients(self):
        outer = QWidget(); outer.setStyleSheet(PANEL_BG)
        root_lay = QVBoxLayout(outer)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Button bar (always visible, NOT inside scroll)
        btn_bar = QWidget()
        btn_bar.setStyleSheet("background:#1a1b27; border-bottom:1px solid #252637;")
        btn_lay = QHBoxLayout(btn_bar)
        btn_lay.setContentsMargins(12, 8, 12, 8)
        btn_lay.setSpacing(8)

        b_csv   = QPushButton("📂 Load CSV/Excel"); b_csv.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_paste = QPushButton("📋 Paste Emails");   b_paste.setStyleSheet(BTN("#4752c4", "#3a47a0"))
        b_clear = QPushButton("🗑 Clear");           b_clear.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_valid = QPushButton("✔ Validate");         b_valid.setStyleSheet(BTN("#43b581", "#369e6b"))

        b_csv.clicked.connect(self._load_recipients_csv)
        b_paste.clicked.connect(self._open_paste_email_dialog)   # ← FIXED
        b_clear.clicked.connect(self._clear_recipients)
        b_valid.clicked.connect(self._validate_recipients)

        self.lbl_rec_count = QLabel("0 recipients loaded")
        self.lbl_rec_count.setStyleSheet("color:#43b581; font-size:12px; font-weight:600;")

        btn_lay.addWidget(b_csv)
        btn_lay.addWidget(b_paste)
        btn_lay.addWidget(b_clear)
        btn_lay.addWidget(b_valid)
        btn_lay.addStretch()
        btn_lay.addWidget(self.lbl_rec_count)
        root_lay.addWidget(btn_bar)

        # Scrollable content
        inner = QWidget(); inner.setStyleSheet(PANEL_BG)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 10, 14, 14)
        lay.setSpacing(10)

        # Recipient Activity Log (above recipients)
        g_rec_log = QGroupBox("📋 Recipient Activity Log")
        rll = QVBoxLayout()
        rll.setContentsMargins(10, 8, 10, 8)
        rll.setSpacing(4)

        self.txt_rec_log = QTextEdit()
        self.txt_rec_log.setReadOnly(True)
        self.txt_rec_log.setFont(QFont("Courier New", 10))
        self.txt_rec_log.setFixedHeight(80)
        self.txt_rec_log.setStyleSheet("""
            QTextEdit {
                background: #0d0e17; color: #00d4aa;
                border: 1px solid #252637; border-radius: 5px; padding: 6px;
            }
        """)
        self.txt_rec_log.setPlaceholderText("Recipient activity, additions, validations, and send logs appear here...")
        rll.addWidget(self.txt_rec_log)

        # Clear recipient log button
        rec_log_foot = QHBoxLayout()
        rec_log_foot.addStretch()
        b_clr_rec_log = QPushButton("🗑 Clear Log")
        b_clr_rec_log.setStyleSheet("""
            QPushButton {
                background: #3d3f52; color: #ffffff; border: none;
                padding: 4px 12px; border-radius: 4px;
                font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background: #52546e; }
        """)
        b_clr_rec_log.setFixedHeight(28)
        b_clr_rec_log.clicked.connect(self.txt_rec_log.clear)
        rec_log_foot.addWidget(b_clr_rec_log)
        rll.addLayout(rec_log_foot)

        g_rec_log.setLayout(rll)
        lay.addWidget(g_rec_log)

        lbl_hint = QLabel("Paste emails below (one per line).  Format:  email  or  email,Name")
        lbl_hint.setStyleSheet("color:#7880a0; font-size:11px;")
        lay.addWidget(lbl_hint)

        self.txt_recipients = QTextEdit()
        self.txt_recipients.setPlaceholderText(
            "user@example.com\nuser2@example.com,John Doe\n...")
        self.txt_recipients.setFont(QFont("Courier New", 11))
        self.txt_recipients.setMinimumHeight(260)
        self.txt_recipients.textChanged.connect(self._on_recipients_changed)
        lay.addWidget(self.txt_recipients)

        # Validation label
        self.lbl_valid = QLabel("Not validated")
        self.lbl_valid.setStyleSheet("color:#f0a500; font-size:11px;")
        lay.addWidget(self.lbl_valid)

        # Fallback
        g_fb = QGroupBox("Fallback Email (if recipient invalid)")
        fl = QHBoxLayout()
        self.txt_fallback = QLineEdit()
        self.txt_fallback.setPlaceholderText("fallback@example.com")
        fl.addWidget(self.txt_fallback)
        g_fb.setLayout(fl)
        lay.addWidget(g_fb)
        lay.addStretch()

        root_lay.addWidget(_scroll_wrap(inner), 1)
        return outer

    # ── SMTP tab ──────────────────────────────────────────────────────────────
    def _tab_smtp(self):
        outer = QWidget(); outer.setStyleSheet(PANEL_BG)
        root_lay = QVBoxLayout(outer)
        root_lay.setContentsMargins(0, 0, 0, 0)

        inner = QWidget(); inner.setStyleSheet(PANEL_BG)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Interactive OAuth Login
        g_oauth = QGroupBox("Microsoft 365 OAuth Login")
        gl_oauth = QHBoxLayout()
        b_oauth = QPushButton("🔑 Link Microsoft Account"); b_oauth.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_oauth.clicked.connect(self._interactive_microsoft_login)
        gl_oauth.addWidget(b_oauth)
        gl_oauth.addStretch()
        g_oauth.setLayout(gl_oauth); lay.addWidget(g_oauth)

        # Single SMTP
        g1 = QGroupBox("Single SMTP  —  Paste one account line to test")
        gl1 = QVBoxLayout()
        gl1.addWidget(QLabel("Format:  email | password | token | client_id"))
        self.txt_single_smtp = QTextEdit()
        self.txt_single_smtp.setPlaceholderText(
            "lxao5455@outlook.com|jnhg8221|M.C503_BAY...|9e5f94bc-e8a4-4e73-b8be-63364c29d753")
        self.txt_single_smtp.setFixedHeight(80)
        gl1.addWidget(self.txt_single_smtp)
        b1 = QPushButton("➕ Add This SMTP"); b1.setStyleSheet(BTN("#43b581", "#369e6b"))
        b1.clicked.connect(self._add_single_smtp)
        gl1.addWidget(b1)
        g1.setLayout(gl1); lay.addWidget(g1)

        # Bulk load
        g2 = QGroupBox("Bulk SMTP Load")
        gl2 = QHBoxLayout()
        b_csv = QPushButton("📂 CSV / Excel"); b_csv.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_csv.clicked.connect(self._load_smtp_csv)
        b_pst = QPushButton("📋 Paste Bulk");  b_pst.setStyleSheet(BTN("#4752c4", "#3a47a0"))
        b_pst.clicked.connect(self._paste_bulk_smtp)
        b_clr = QPushButton("🗑 Clear All SMTP"); b_clr.setStyleSheet(BTN("#ed4245", "#c93638"))
        b_clr.clicked.connect(self._clear_smtp)
        gl2.addWidget(b_csv); gl2.addWidget(b_pst); gl2.addWidget(b_clr); gl2.addStretch()
        g2.setLayout(gl2); lay.addWidget(g2)

        self.lbl_smtp_count = QLabel("0 SMTP accounts loaded")
        self.lbl_smtp_count.setStyleSheet("color:#43b581; font-size:12px; font-weight:700;")
        lay.addWidget(self.lbl_smtp_count)

        self.smtp_list = QListWidget()
        self.smtp_list.setMinimumHeight(200)
        lay.addWidget(self.smtp_list)
        lay.addStretch()

        root_lay.addWidget(_scroll_wrap(inner), 1)
        self.refresh_smtp_list()
        return outer

    # ── Tags tab ──────────────────────────────────────────────────────────────
    def _tab_tags(self):
        outer = QWidget(); outer.setStyleSheet(PANEL_BG)
        root_lay = QVBoxLayout(outer)
        root_lay.setContentsMargins(0, 0, 0, 0)

        inner = QWidget(); inner.setStyleSheet(PANEL_BG)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Phone numbers
        g_tfn = QGroupBox("Phone Numbers")
        fl = QFormLayout(); fl.setSpacing(10)
        self.inp_tfn1 = QLineEdit(); self.inp_tfn1.setPlaceholderText("e.g. 1-800-555-0101")
        self.inp_tfn2 = QLineEdit(); self.inp_tfn2.setPlaceholderText("e.g. 1-888-555-0202")
        fl.addRow("#TFN1#:", self.inp_tfn1)
        fl.addRow("#TFN2#:", self.inp_tfn2)
        g_tfn.setLayout(fl); lay.addWidget(g_tfn)

        # Date/Time
        g_dt = QGroupBox("Date & Time")
        dtl = QFormLayout(); dtl.setSpacing(10)
        self.chk_date_auto = QCheckBox("Auto-pick system date"); self.chk_date_auto.setChecked(True)
        self.inp_date = QLineEdit(); self.inp_date.setPlaceholderText("Manual: June 29, 2026")
        self.chk_time_auto = QCheckBox("Auto-pick system time"); self.chk_time_auto.setChecked(True)
        self.inp_time = QLineEdit(); self.inp_time.setPlaceholderText("Manual: 10:30 AM")
        dtl.addRow("#DATE# Auto:", self.chk_date_auto)
        dtl.addRow("#DATE# Manual:", self.inp_date)
        dtl.addRow("#TIME# Auto:", self.chk_time_auto)
        dtl.addRow("#TIME# Manual:", self.inp_time)
        g_dt.setLayout(dtl); lay.addWidget(g_dt)

        # Amount
        g_amt = QGroupBox("#AMOUNT# Settings")
        aml = QFormLayout(); aml.setSpacing(10)
        amr_row = QHBoxLayout()
        self.rb_amt_custom = QRadioButton("Custom (fixed)"); self.rb_amt_custom.setChecked(True)
        self.rb_amt_random = QRadioButton("Random in range")
        amr_row.addWidget(self.rb_amt_custom); amr_row.addWidget(self.rb_amt_random); amr_row.addStretch()
        self.inp_amt_custom = QLineEdit()
        self.inp_amt_custom.setPlaceholderText("e.g. 200.00")
        self.spn_amt_min = QDoubleSpinBox(); self.spn_amt_min.setRange(0, 99999); self.spn_amt_min.setValue(100)
        self.spn_amt_max = QDoubleSpinBox(); self.spn_amt_max.setRange(0, 99999); self.spn_amt_max.setValue(300)
        aml.addRow("Mode:", amr_row)
        aml.addRow("Custom Value ($):", self.inp_amt_custom)
        aml.addRow("Random Min ($):", self.spn_amt_min)
        aml.addRow("Random Max ($):", self.spn_amt_max)
        g_amt.setLayout(aml); lay.addWidget(g_amt)

        # Address pool
        g_addr = QGroupBox("#ADDRESS# Pool  (one address per line: Street, City, State ZIP)")
        adl = QVBoxLayout()
        self.txt_addresses = QTextEdit()
        self.txt_addresses.setPlaceholderText(
            "123 Main St, New York, NY 10001\n456 Oak Ave, Los Angeles, CA 90001")
        self.txt_addresses.setFixedHeight(90)
        adl.addWidget(self.txt_addresses)
        g_addr.setLayout(adl); lay.addWidget(g_addr)

        lay.addStretch()
        root_lay.addWidget(_scroll_wrap(inner), 1)
        return outer

    # ── Content tab ───────────────────────────────────────────────────────────
    def _tab_content(self):
        outer = QWidget(); outer.setStyleSheet(PANEL_BG)
        root_lay = QVBoxLayout(outer)
        root_lay.setContentsMargins(0, 0, 0, 0)

        inner = QWidget(); inner.setStyleSheet(PANEL_BG)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Body mode
        g_mode = QGroupBox("Email Body Mode")
        grid_mode = QGridLayout(g_mode)
        grid_mode.setSpacing(10)
        
        self.rb_body_img = QRadioButton("Body+Img")
        self.rb_body_pdf = QRadioButton("Body+PDF")
        self.rb_body_img_pdf = QRadioButton("Body HTML+PDF")
        
        self.rb_inline_attach = QRadioButton("Inline+Attach")
        self.rb_inline_pdf = QRadioButton("Inline+PDF")
        self.rb_text_only = QRadioButton("Text Only")
        self.rb_html_only = QRadioButton("HTML Only")

        self.rb_html_only.setChecked(True)
        
        # Row 0
        grid_mode.addWidget(self.rb_body_img, 0, 0)
        grid_mode.addWidget(self.rb_body_pdf, 0, 1)
        grid_mode.addWidget(self.rb_body_img_pdf, 0, 2)
        
        # Row 1
        grid_mode.addWidget(self.rb_inline_attach, 1, 0)
        grid_mode.addWidget(self.rb_inline_pdf, 1, 1)
        grid_mode.addWidget(self.rb_text_only, 1, 2)
        grid_mode.addWidget(self.rb_html_only, 1, 3)
        
        lay.addWidget(g_mode)

        # Connect signals
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf,
                   self.rb_text_only, self.rb_html_only):
            rb.toggled.connect(self._update_content_visibility)

        # Subject lines
        g_sub = QGroupBox("Subject Lines  (rotation — one per line)")
        sl = QVBoxLayout()

        # Subject & Body Rotation Mode
        rot_box = QWidget()
        rot_box.setStyleSheet("background:#0d0e17; border:1px solid #252637; border-radius:6px;")
        rot_row = QHBoxLayout(rot_box)
        rot_row.setContentsMargins(10, 6, 10, 6)
        rot_row.setSpacing(16)
        rot_lbl = QLabel("Rotation Mode:")
        rot_lbl.setStyleSheet("color:#00d4aa; font-size:11px; font-weight:700;")
        self.rb_rot_per_smtp = QRadioButton("Per SMTP (1 SMTP uses 1 Subject + Body, rotates on switch)")
        self.rb_rot_random   = QRadioButton("Randomized (Paired Subject + Body changes every email)")
        self.rb_rot_per_smtp.setStyleSheet("color:#e8eaf0; font-size:11px; font-weight:600;")
        self.rb_rot_random.setStyleSheet("color:#e8eaf0; font-size:11px; font-weight:600;")
        self.rb_rot_per_smtp.setToolTip("1 SMTP account will send all its emails using 1 Subject + Body. Switches to next pair when SMTP rotates.")
        self.rb_rot_random.setToolTip("Each individual email gets a fresh random Subject and strictly matching Body.")
        self.rb_rot_per_smtp.setChecked(True)
        rot_row.addWidget(rot_lbl)
        rot_row.addWidget(self.rb_rot_per_smtp)
        rot_row.addWidget(self.rb_rot_random)
        rot_row.addStretch()
        sl.addWidget(rot_box)

        # Quick single-subject paste box
        quick_row = QHBoxLayout()
        quick_lbl = QLabel("Quick Add:")
        quick_lbl.setStyleSheet("color:#7880a0; font-size:11px; font-weight:600;")
        self.inp_quick_subject = QLineEdit()
        self.inp_quick_subject.setPlaceholderText("Paste a single subject line here and click + Add")
        b_add_subj = QPushButton("+ Add"); b_add_subj.setStyleSheet(BTN("#43b581", "#369e6b"))
        b_add_subj.setFixedWidth(80)
        b_add_subj.clicked.connect(self._add_quick_subject)
        self.inp_quick_subject.returnPressed.connect(self._add_quick_subject)
        quick_row.addWidget(quick_lbl)
        quick_row.addWidget(self.inp_quick_subject, 1)
        quick_row.addWidget(b_add_subj)
        sl.addLayout(quick_row)

        # Bulk subject actions bar
        bulk_row = QHBoxLayout()
        b_sub_csv   = QPushButton("📂 Load CSV/Excel"); b_sub_csv.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_sub_paste = QPushButton("📋 Paste Subjects"); b_sub_paste.setStyleSheet(BTN("#4752c4", "#3a47a0"))
        b_sub_clear = QPushButton("🗑 Clear");          b_sub_clear.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_sub_csv.clicked.connect(self._load_subjects_csv)
        b_sub_paste.clicked.connect(self._paste_bulk_subjects)
        b_sub_clear.clicked.connect(self._clear_subjects)

        self.lbl_subj_count = QLabel("0 subjects loaded")
        self.lbl_subj_count.setStyleSheet("color:#43b581; font-size:11px; font-weight:600;")

        bulk_row.addWidget(b_sub_csv)
        bulk_row.addWidget(b_sub_paste)
        bulk_row.addWidget(b_sub_clear)
        bulk_row.addStretch()
        bulk_row.addWidget(self.lbl_subj_count)
        sl.addLayout(bulk_row)

        sl.addWidget(QLabel("Bulk subjects (one per line — all will rotate):"  ))
        self.txt_subjects = QTextEdit()
        self.txt_subjects.setPlaceholderText(
            "Your invoice #INVOICE# is ready — ProMailer Pro | Bulk Email Sender\n"
            "Payment of $#AMOUNT# received on #DATE# — Order #ORDERID#\n"
            "Important notice for #NAME# — Action required by #DATE#\n"
            "Transaction #TXNID# confirmed — Contact us at #TFN1#")
        self.txt_subjects.setFixedHeight(90)
        self.txt_subjects.textChanged.connect(self._on_subjects_changed)
        sl.addWidget(self.txt_subjects)
        g_sub.setLayout(sl); lay.addWidget(g_sub)

        # Body Content Type selection (HTML Template vs Plain Text vs Paste Code/HTML)
        self.g_body_type = QGroupBox("Body Content Format")
        bt_lay = QHBoxLayout(self.g_body_type)
        self.rb_content_text = QRadioButton("Plain Text / Multiple Bodies (default)")
        self.rb_content_html = QRadioButton("HTML Template (.html file)")
        self.rb_content_code = QRadioButton("Paste Code / HTML")
        self.rb_content_text.setChecked(True)
        bt_lay.addWidget(self.rb_content_text)
        bt_lay.addWidget(self.rb_content_html)
        bt_lay.addWidget(self.rb_content_code)
        bt_lay.addStretch()
        lay.addWidget(self.g_body_type)
        self.rb_content_html.toggled.connect(self._update_content_visibility)
        self.rb_content_text.toggled.connect(self._update_content_visibility)
        self.rb_content_code.toggled.connect(self._update_content_visibility)

        # Body plain text
        self.g_txt = QGroupBox("Body Text  (plain text / fallback if no HTML)")
        tl = QVBoxLayout()

        # Bulk body actions bar
        bulk_body_row = QHBoxLayout()
        b_body_csv   = QPushButton("📂 Load CSV/Excel"); b_body_csv.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_body_paste = QPushButton("📋 Paste Multiple Bodies"); b_body_paste.setStyleSheet(BTN("#4752c4", "#3a47a0"))
        b_body_clear = QPushButton("🗑 Clear");                 b_body_clear.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_body_csv.clicked.connect(self._load_bodies_csv)
        b_body_paste.clicked.connect(self._paste_bulk_bodies)
        b_body_clear.clicked.connect(self._clear_bodies)

        self.lbl_body_count = QLabel("1 body template loaded")
        self.lbl_body_count.setStyleSheet("color:#43b581; font-size:11px; font-weight:600;")

        bulk_body_row.addWidget(b_body_csv)
        bulk_body_row.addWidget(b_body_paste)
        bulk_body_row.addWidget(b_body_clear)
        bulk_body_row.addStretch()
        bulk_body_row.addWidget(self.lbl_body_count)
        tl.addLayout(bulk_body_row)

        body_hint = QLabel(
            "ℹ️  Multiple body templates are supported! Separate each body template with === on a new line.\n"
            "Each body matches the corresponding Subject line (Subject 1 → Body 1, Subject 2 → Body 2)."
        )
        body_hint.setStyleSheet(
            "color:#7880a0; font-size:11px; background:#0d0e17; "
            "border-radius:4px; padding:8px 10px; margin-bottom:4px;"
        )
        body_hint.setWordWrap(True)
        tl.addWidget(body_hint)

        self.txt_body_plain = QTextEdit()
        self.txt_body_plain.setPlaceholderText(
            "Hello #NAME#,\n\n"
            "We are writing to inform you that your payment of $#AMOUNT# has been successfully\n"
            "received on #DATE# at #TIME#.\n\n"
            "Transaction Details:\n"
            "  Invoice Number  : #INVOICE#\n"
            "  Order ID        : #ORDERID#\n"
            "  Transaction ID  : #TXNID#\n"
            "  Payment Method  : #TYPE#\n"
            "  Amount          : $#AMOUNT#\n"
            "  Billing Address : #ADDRESS#\n\n"
            "If you have any questions, please contact our support team:\n"
            "  📞 #TFN1#  |  #TFN2#\n\n"
            "===\n\n"
            "Second body template text here (optional)..."
        )
        self.txt_body_plain.setFixedHeight(200)
        self.txt_body_plain.textChanged.connect(self._on_bodies_changed)
        tl.addWidget(self.txt_body_plain)
        self.g_txt.setLayout(tl); lay.addWidget(self.g_txt)

        # HTML templates (Email Body - file upload)
        self.g_html = QGroupBox("Email Body — HTML Templates  (multiple files = rotation  +  base64 inline images)")
        hl = QVBoxLayout()
        hl.addWidget(QLabel("💡 Upload HTML file(s) for the Email Body — images inside <img src='…'> auto-embedded as base64."))
        br = QHBoxLayout()
        b_add_h = QPushButton("+ Add Body HTML File"); b_add_h.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_add_h.clicked.connect(self._add_html)
        b_clr_h = QPushButton("Clear");           b_clr_h.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_h.clicked.connect(lambda: self.html_list.clear())
        br.addWidget(b_add_h); br.addWidget(b_clr_h); br.addStretch()
        hl.addLayout(br)
        self.html_list = QListWidget(); self.html_list.setFixedHeight(90)
        self.html_list.itemDoubleClicked.connect(lambda item: self.html_list.takeItem(self.html_list.row(item)))
        hl.addWidget(self.html_list)
        self.chk_inline_b64 = QCheckBox("Convert images to base64 inline  (recommended — avoids spam filters)")
        self.chk_inline_b64.setChecked(True)
        hl.addWidget(self.chk_inline_b64)
        self.g_html.setLayout(hl); lay.addWidget(self.g_html)

        # Paste Code / HTML widget
        self.g_code = QGroupBox("Email Body — Paste Code / HTML  (direct HTML code / base64 inline images)")
        cl = QVBoxLayout()
        code_hint = QLabel("💡 Paste your HTML code or template text below — tags like #NAME#, #AMOUNT#, #INVOICE#, #TFN1# auto-replaced.")
        code_hint.setStyleSheet("color:#7880a0; font-size:11px;")
        cl.addWidget(code_hint)

        c_bar = QHBoxLayout()
        b_clr_code = QPushButton("Clear"); b_clr_code.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_code.clicked.connect(lambda: self.txt_body_code.clear())
        c_bar.addWidget(b_clr_code); c_bar.addStretch()
        cl.addLayout(c_bar)

        self.txt_body_code = QTextEdit()
        self.txt_body_code.setFont(QFont("Courier New", 11))
        self.txt_body_code.setPlaceholderText(
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head><meta charset=\"utf-8\"></head>\n"
            "<body style=\"font-family: Arial, sans-serif; padding: 20px;\">\n"
            "  <h2>Hello #NAME#,</h2>\n"
            "  <p>Your payment of $#AMOUNT# has been received on #DATE#.</p>\n"
            "  <p>Invoice: #INVOICE# | Order: #ORDERID# | Transaction: #TXNID#</p>\n"
            "  <p>Support: #TFN1#</p>\n"
            "</body>\n"
            "</html>"
        )
        self.txt_body_code.setFixedHeight(200)
        cl.addWidget(self.txt_body_code)

        self.chk_code_inline_b64 = QCheckBox("Convert local image paths in HTML to base64 inline")
        self.chk_code_inline_b64.setChecked(True)
        cl.addWidget(self.chk_code_inline_b64)

        self.g_code.setLayout(cl); lay.addWidget(self.g_code)

        # Sender names
        g_snd = QGroupBox("Sender Names  (rotation — one per line)")
        snl = QVBoxLayout()
        self.chk_default_sender = QCheckBox("Use SMTP account email as sender name (default)")
        self.chk_default_sender.setChecked(True)
        snl.addWidget(self.chk_default_sender)
        self.txt_senders = QTextEdit()
        self.txt_senders.setPlaceholderText("Sophia Adams\nAva Harris\nJohn Smith")
        self.txt_senders.setFixedHeight(70)
        snl.addWidget(self.txt_senders)
        g_snd.setLayout(snl); lay.addWidget(g_snd)

        # Attachments
        self.g_att = QGroupBox("Attachments  (personalised filename = email-prefix + 4 random digits)")
        al = QVBoxLayout()

        # Image Container
        self.wdg_img_att = QWidget()
        self.wdg_img_att.setStyleSheet("background:transparent;")
        img_lay = QVBoxLayout(self.wdg_img_att)
        img_lay.setContentsMargins(0, 0, 0, 0)

        img_lbl = QLabel("Image Attachment  (Upload HTML Template to convert to Image, OR upload image file):")
        img_lbl.setStyleSheet("color:#7880a0; font-size:11px; font-weight:600;")
        img_lay.addWidget(img_lbl)

        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Image Format:")
        fmt_lbl.setStyleSheet("color:#7880a0; font-size:11px; font-weight:600;")
        self.cmb_img_format = QComboBox()
        self.cmb_img_format.addItems(["PNG", "JPG", "JPEG", "GIF"])
        self.cmb_img_format.setCurrentText("PNG")
        self.cmb_img_format.setFixedWidth(120)
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self.cmb_img_format)
        fmt_row.addStretch()
        img_lay.addLayout(fmt_row)

        ir = QHBoxLayout()
        b_add_i_html = QPushButton("+ Add HTML for Image (.html)"); b_add_i_html.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_add_i_html.clicked.connect(self._add_img_html)
        b_add_i = QPushButton("+ Add Image File (PNG/JPG/JPEG/GIF)"); b_add_i.setStyleSheet(BTN("#43b581", "#369e6b"))
        b_add_i.clicked.connect(self._add_img_att)
        b_clr_i = QPushButton("Clear"); b_clr_i.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_i.clicked.connect(lambda: self.img_att_list.clear())
        ir.addWidget(b_add_i_html); ir.addWidget(b_add_i); ir.addWidget(b_clr_i); ir.addStretch()
        img_lay.addLayout(ir)
        self.img_att_list = QListWidget(); self.img_att_list.setFixedHeight(70)
        self.img_att_list.itemDoubleClicked.connect(lambda item: self.img_att_list.takeItem(self.img_att_list.row(item)))
        img_lay.addWidget(self.img_att_list)
        al.addWidget(self.wdg_img_att)

        # PDF Container
        self.wdg_pdf_att = QWidget()
        self.wdg_pdf_att.setStyleSheet("background:transparent;")
        pdf_lay = QVBoxLayout(self.wdg_pdf_att)
        pdf_lay.setContentsMargins(0, 0, 0, 0)
        
        pdf_lbl = QLabel("PDF Attachment  (Upload HTML Template to convert to PDF — A4/A1 formats & exact 1-to-1 page count strictly preserved, OR upload .pdf):")
        pdf_lbl.setStyleSheet("color:#7880a0; font-size:11px; font-weight:600;")
        pdf_lay.addWidget(pdf_lbl)

        pr = QHBoxLayout()
        b_add_p_html = QPushButton("+ Add HTML for PDF (.html)"); b_add_p_html.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_add_p_html.clicked.connect(self._add_pdf_html)
        b_add_p = QPushButton("+ Add PDF File (.pdf)"); b_add_p.setStyleSheet(BTN("#f0a500", "#c88a00"))
        b_add_p.clicked.connect(self._add_pdf_att)
        b_clr_p = QPushButton("Clear"); b_clr_p.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_p.clicked.connect(lambda: self.pdf_att_list.clear())
        pr.addWidget(b_add_p_html); pr.addWidget(b_add_p); pr.addWidget(b_clr_p); pr.addStretch()
        pdf_lay.addLayout(pr)
        self.pdf_att_list = QListWidget(); self.pdf_att_list.setFixedHeight(70)
        self.pdf_att_list.itemDoubleClicked.connect(lambda item: self.pdf_att_list.takeItem(self.pdf_att_list.row(item)))
        pdf_lay.addWidget(self.pdf_att_list)
        al.addWidget(self.wdg_pdf_att)

        self.lbl_note = QLabel(
            "📌 Name example:  groupleeman4829.png  /  groupleeman4829.pdf\n"
            "   (email prefix + 4 random digits — @domain.com is NOT included)")
        self.lbl_note.setStyleSheet("color:#7880a0; font-size:11px; margin-top:4px;")
        al.addWidget(self.lbl_note)
        self.g_att.setLayout(al); lay.addWidget(self.g_att)
        lay.addStretch()

        root_lay.addWidget(_scroll_wrap(inner), 1)

        # Initial invocation
        self._update_content_visibility()

        return outer

    # ── Delays & Limits tab ───────────────────────────────────────────────────
    def _tab_delays(self):
        outer = QWidget(); outer.setStyleSheet(PANEL_BG)
        root_lay = QVBoxLayout(outer)
        root_lay.setContentsMargins(0, 0, 0, 0)

        inner = QWidget(); inner.setStyleSheet(PANEL_BG)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        g1 = QGroupBox("Delay Between Emails")
        dl = QFormLayout(); dl.setSpacing(12)
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setRange(0, 120); self.spn_delay.setValue(1.0)
        self.spn_delay.setSuffix(" seconds")
        dl.addRow("Delay per email:", self.spn_delay)
        g1.setLayout(dl); lay.addWidget(g1)

        g2 = QGroupBox("Per-SMTP Switch Mode")
        sl = QVBoxLayout()
        self.rb_auto  = QRadioButton("Auto — switch SMTP automatically on error (HTTP 400 / 401 / 403 / 429)")
        self.rb_limit = QRadioButton("Limit — switch SMTP after every N emails")
        self.rb_auto.setChecked(True)
        sl.addWidget(self.rb_auto)
        lr = QHBoxLayout()
        lr.addWidget(self.rb_limit)
        self.spn_limit = QSpinBox(); self.spn_limit.setRange(1, 9999); self.spn_limit.setValue(5)
        self.spn_limit.setFixedWidth(100)
        lr.addWidget(self.spn_limit)
        lr.addWidget(QLabel("emails per SMTP")); lr.addStretch()
        sl.addLayout(lr)
        g2.setLayout(sl); lay.addWidget(g2)

        g3 = QGroupBox("Advanced Options")
        avl = QFormLayout(); avl.setSpacing(12)
        self.spn_bounce = QSpinBox(); self.spn_bounce.setRange(0, 100)
        self.spn_bounce.setValue(25); self.spn_bounce.setSuffix("%")
        self.chk_auto_remove = QCheckBox(
            "Auto-remove sent recipients from pool  (keeps your list clean for next batch)")
        self.chk_auto_remove.setChecked(True)
        avl.addRow("Bounce threshold:", self.spn_bounce)
        avl.addWidget(self.chk_auto_remove)
        g3.setLayout(avl); lay.addWidget(g3)

        # Tag format reminder
        g4 = QGroupBox("Available Tags  (quick reference)")
        tl = QVBoxLayout()
        tags_txt = QLabel(
            "#NAME#  #EMAIL#  #USER#  #TFN#  #TFN1#  #TFN2#  #DATE#  #TIME#\n"
            "#AMOUNT#  #INVOICE#  #ORDERID#  #ORDER#  #TXNID#  #TYPE#\n"
            "#LETTERS#  #LICENSE#  #REGARDS#  #ADDRESS#\n"
            "#KEY#  #GUID#  #NUMBER#  #RANDOM#  #SERIAL#  #SNUMBER#"
        )
        tags_txt.setFont(QFont("Courier New", 11))
        tags_txt.setStyleSheet("color:#00d4aa; background:#0d0e17; padding:12px; border-radius:5px;")
        tl.addWidget(tags_txt)
        g4.setLayout(tl); lay.addWidget(g4)

        lay.addStretch()
        root_lay.addWidget(_scroll_wrap(inner), 1)
        return outer

    # ── Log pane ──────────────────────────────────────────────────────────────
    def _make_log_pane(self):
        w = QWidget()
        w.setStyleSheet(PANEL_BG)
        w.setMinimumWidth(300)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Courier New", 10))
        self.log_box.setStyleSheet("""
            QTextEdit {
                background:#0d0e17; color:#00d4aa;
                border:1px solid #252637; border-radius:5px; padding:6px;
            }
        """)

        hdr_row = QHBoxLayout()
        hdr = QLabel(f"▼ Task {self.task_id} Log")
        hdr.setFixedHeight(30)
        hdr.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        hdr.setStyleSheet(
            "color:#7880a0; font-size:12px; font-weight:700; "
            "padding:4px 8px; background:#0d0e17; border-radius:3px;")
        hdr_row.addWidget(hdr)
        lay.addLayout(hdr_row)
        lay.addWidget(self.log_box, 1)

        foot_row = QHBoxLayout()
        foot_row.setSpacing(6)
        self.lbl_current_smtp = QLabel("SMTP: –")
        self.lbl_current_smtp.setFixedHeight(30)
        self.lbl_current_smtp.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.lbl_current_smtp.setStyleSheet("color:#5865f2; font-size:11px;")

        b_dl_foot = QPushButton("📥 Download Log")
        b_dl_foot.setStyleSheet("""
            QPushButton {
                background: #5865f2; color: #ffffff; border: none;
                padding: 4px 10px; border-radius: 5px;
                font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background: #4752c4; }
        """)
        b_dl_foot.setFixedHeight(30)
        b_dl_foot.clicked.connect(self._download_log)

        b_clr = QPushButton("🗑 Clear Log")
        b_clr.setStyleSheet("""
            QPushButton {
                background: #3d3f52; color: #ffffff; border: none;
                padding: 4px 10px; border-radius: 5px;
                font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background: #52546e; }
        """)
        b_clr.setFixedHeight(30)
        b_clr.clicked.connect(self.log_box.clear)

        foot_row.addWidget(self.lbl_current_smtp, 1)
        foot_row.addWidget(b_dl_foot)
        foot_row.addWidget(b_clr)
        lay.addLayout(foot_row)
        return w

    def _download_log(self):
        """Export all logs from this task's log box to a file (TXT, LOG, or CSV)."""
        log_text = self.log_box.toPlainText()
        if not log_text.strip():
            QMessageBox.information(
                self, "Download Log",
                f"Task {self.task_id} log is currently empty.\nRun a campaign or send test emails to generate logs."
            )
            return

        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"task_{self.task_id}_log_{now_str}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Task {self.task_id} Log",
            default_filename,
            "Text Files (*.txt);;Log Files (*.log);;CSV Spreadsheet (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            if file_path.lower().endswith(".csv"):
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Task", "Log Entry"])
                    for line in log_text.splitlines():
                        if not line.strip():
                            continue
                        ts = ""
                        entry = line
                        if line.startswith("[") and "]" in line:
                            idx = line.index("]")
                            ts = line[1:idx].strip()
                            entry = line[idx + 1:].strip()
                        writer.writerow([ts, f"Task {self.task_id}", entry])
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_text)

            self._log(f"💾 Log downloaded to: {Path(file_path).name}")
            QMessageBox.information(
                self,
                "Log Downloaded",
                f"Task {self.task_id} log has been successfully saved to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save log file:\n{str(e)}"
            )

    # ── Recipients helpers ────────────────────────────────────────────────────
    def _on_recipients_changed(self):
        import re
        raw_text = self.txt_recipients.toPlainText()
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        # Check actual valid email addresses (user@domain.ext)
        valid = [l for l in lines if re.search(r'[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}', l)]
        count = len(valid)
        self.lbl_rec_count.setText(f"{count} recipients loaded")
        pfx = f"task_{self.task_id}_"
        self.db.set_setting(pfx + "recipients", raw_text)

        # Restart debounce timer on every keystroke so it only logs when user finishes typing
        if hasattr(self, '_rec_change_timer'):
            self._rec_change_timer.start(800)

    def _on_rec_timer_timeout(self):
        import re
        raw_text = self.txt_recipients.toPlainText()
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        valid_matches = []
        for l in lines:
            m = re.search(r'[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}', l)
            if m:
                valid_matches.append(m.group(0))

        count = len(valid_matches)
        if count == 0:
            return

        # Deduplicate: don't re-log if the valid recipients list hasn't changed
        summary = f"{count}:" + ",".join(valid_matches[:5])
        if summary == getattr(self, '_last_logged_rec_summary', None):
            return
        self._last_logged_rec_summary = summary

        if count <= 2:
            sample_emails = ", ".join(valid_matches[:2])
            self._log(f"👥 {count} recipient(s) loaded: {sample_emails}")
        else:
            self._log(f"👥 {count} recipient(s) loaded in editor")

    def _clear_recipients(self):
        if hasattr(self, '_rec_change_timer'):
            self._rec_change_timer.stop()
        self._last_logged_rec_summary = None
        self.txt_recipients.clear()
        self.lbl_rec_count.setText("0 recipients loaded")
        self.db.clear_recipients()
        pfx = f"task_{self.task_id}_"
        self.db.set_setting(pfx + "recipients", "")
        self._prev_rec_count = 0
        self._log("🗑 Recipients cleared from list and database pool")

    def _validate_recipients(self):
        lines = [l.strip() for l in self.txt_recipients.toPlainText().split('\n') if l.strip()]
        valid = [l for l in lines if '@' in l]
        invalid = len(lines) - len(valid)
        status_txt = f"✅ {len(valid)} valid  |  ❌ {invalid} invalid"
        self.lbl_valid.setText(status_txt)
        self.lbl_valid.setStyleSheet(
            "color:#43b581; font-size:11px; font-weight:600;" if not invalid
            else "color:#f0a500; font-size:11px; font-weight:600;")
        self._log(f"✔ Recipient validation: {len(valid)} valid  |  {invalid} invalid")

    def _load_recipients_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Recipients CSV/Excel", "", "CSV/Excel (*.csv *.xlsx *.xls)")
        if not path:
            return
        rows = self._read_csv_or_excel(path)
        lines = []
        for row in rows:
            if len(row) >= 2:
                lines.append(f"{row[0]},{row[1]}")
            elif len(row) == 1:
                lines.append(row[0])
        current = self.txt_recipients.toPlainText().strip()
        combined = (current + "\n" + "\n".join(lines)).strip() if current else "\n".join(lines)
        self.txt_recipients.setPlainText(combined)
        self._log(f"📂 Loaded {len(lines)} recipients from file: {Path(path).name}")

    def _open_paste_email_dialog(self):
        """Open a proper paste dialog for emails — FIXED version."""
        dlg = PasteDialog(
            "Paste Email Data",
            "Paste email addresses below — one per line.\n"
            "Format:  email@example.com   or   email@example.com,FirstName\n"
            "You can paste up to 5000 rows at once.",
            self
        )
        if dlg.exec() == QDialog.Accepted:
            pasted = dlg.get_text().strip()
            if not pasted:
                return
            current = self.txt_recipients.toPlainText().strip()
            combined = (current + "\n" + pasted).strip() if current else pasted
            self.txt_recipients.setPlainText(combined)
            count = len(
                [l for l in pasted.split('\n') if '@' in l.strip()])
            self._log(f"📋 Pasted {count} email rows")

    def _read_csv_or_excel(self, path):
        rows = []
        p = Path(path)
        try:
            if p.suffix.lower() in ('.xlsx', '.xls'):
                if HAS_OPENPYXL:
                    wb = openpyxl.load_workbook(path, read_only=True)
                    ws = wb.active
                    for row in ws.iter_rows(values_only=True):
                        clean = [str(c).strip() for c in row if c is not None]
                        if clean:
                            rows.append(clean)
                else:
                    self._log("⚠ openpyxl not installed — pip install openpyxl")
            else:
                with open(path, newline='', encoding='utf-8-sig') as f:
                    for row in csv.reader(f):
                        clean = [c.strip() for c in row if c.strip()]
                        if clean:
                            rows.append(clean)
        except Exception as e:
            self._log(f"❌ Error reading file: {e}")
        return rows

    def refresh_recipient_count(self):
        self._on_recipients_changed()

    # ── SMTP helpers ──────────────────────────────────────────────────────────
    def _add_single_smtp(self):
        raw = self.txt_single_smtp.toPlainText().strip()
        added = 0
        for line in raw.split('\n'):
            parts = line.strip().split('|')
            if len(parts) >= 4:
                self.db.add_smtp_account(parts[0], parts[1], parts[2], parts[3])
                added += 1
        self.refresh_smtp_list()
        self.txt_single_smtp.clear()
        if added:
            self._log(f"✅ Added {added} SMTP account(s)")

    def _load_smtp_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load SMTP CSV/Excel", "", "CSV/Excel (*.csv *.xlsx *.xls)")
        if not path:
            return
        rows = self._read_csv_or_excel(path)
        added = 0
        for row in rows:
            if len(row) == 1 and '|' in row[0]:
                row = [r.strip() for r in row[0].split('|')]
            if len(row) >= 4:
                self.db.add_smtp_account(row[0], row[1], row[2], row[3])
                added += 1
        self.refresh_smtp_list()
        self._log(f"✅ Added {added} SMTP accounts from file")

    def _paste_bulk_smtp(self):
        dlg = PasteDialog(
            "Paste SMTP Accounts",
            "Format (one per line):  email | password | token | client_id\n"
            "Example:  user@outlook.com|pass123|M.C503_BAY...|9e5f94bc-…",
            self
        )
        if dlg.exec() == QDialog.Accepted:
            raw = dlg.get_text()
            added = 0
            for line in raw.split('\n'):
                parts = line.strip().split('|')
                if len(parts) >= 4:
                    self.db.add_smtp_account(parts[0], parts[1], parts[2], parts[3])
                    added += 1
            self.refresh_smtp_list()
            self._log(f"✅ Added {added} SMTP accounts from paste")

    def _clear_smtp(self):
        if QMessageBox.question(
                self, "Confirm", "Clear ALL SMTP accounts from database?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.clear_smtp_accounts()
            self.refresh_smtp_list()
            self._log("🗑 All SMTP accounts cleared")

    def refresh_smtp_list(self):
        self.smtp_list.clear()
        accounts = self.db.get_smtp_accounts()
        for acc in accounts:
            icon = "🟢" if acc['status'] == 'ready' else "🔴"
            self.smtp_list.addItem(
                f"{icon}  {acc['email']}    sent:{acc['emails_sent']}    [{acc['status']}]")
        self.lbl_smtp_count.setText(f"{len(accounts)} SMTP accounts loaded")

    def test_smtp(self):
        accounts = self.db.get_smtp_accounts(status='ready')
        self._log(f"🔍 SMTP test: {len(accounts)} ready accounts found")
        if not accounts:
            QMessageBox.warning(self, "No SMTP", "No ready SMTP accounts in database.")

    def _interactive_microsoft_login(self):
        try:
            self._log("🔑 Initiating interactive Microsoft login...")
            from graph.auth import GraphAuth
            auth = GraphAuth()
            self._log(f"Configured Client ID: {auth.client_id}")
            self._log(f"Configured Tenant ID: {auth.tenant_id}")
            self._log(f"Configured Authority: {auth.authority}")
            result = auth.acquire_token_interactive()
            if result and "access_token" in result:
                user_info = auth.get_user_info(result["access_token"])
                email = "your-email@outlook.com"
                if user_info:
                    email = user_info.get("userPrincipalName") or user_info.get("mail") or email
                
                client_id = os.getenv("CLIENT_ID", "your_client_id_here")
                refresh_token = result.get("refresh_token", result["access_token"])
                
                # Save to database
                self.db.add_smtp_account(email, "dummy_password", refresh_token, client_id)
                self.refresh_smtp_list()
                self._log(f"✅ Microsoft account linked: {email}")
                
                QMessageBox.information(
                    self, "Success", f"Successfully linked Microsoft account:\n{email}"
                )
            else:
                self._log("❌ Microsoft Login failed: No token was returned")
                QMessageBox.warning(self, "Error", "Failed to acquire login token.")
        except Exception as e:
            self._log(f"❌ Microsoft Login error: {e}")
            QMessageBox.critical(self, "Error", f"Microsoft Login failed:\n{str(e)}")

    # ── Content helpers ───────────────────────────────────────────────────────
    def _add_html(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select HTML Templates", "", "HTML (*.html *.htm)")
        if not files:
            return
        max_bytes = 100 * 1024
        rejected = []
        for f in files:
            try:
                size = Path(f).stat().st_size
            except Exception:
                size = 0
            if size > max_bytes:
                rejected.append(f"{Path(f).name} ({size // 1024} KB)")
            else:
                self.html_list.addItem(f)
        if rejected:
            QMessageBox.warning(
                self, "Template too large",
                "These HTML templates are over 100KB and were NOT added:\n\n"
                + "\n".join(rejected)
                + "\n\nPlease keep HTML body templates below 100KB."
            )

    def _add_img_html(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select HTML Template for Image Attachment", "", "HTML Templates (*.html *.htm)"
        )
        if not files:
            return

        max_bytes = 100 * 1024
        rejected = []
        accepted = []

        for f in files:
            try:
                size = Path(f).stat().st_size
            except Exception:
                size = 0

            if size > max_bytes:
                rejected.append(f"{Path(f).name} ({size // 1024} KB)")
                continue

            accepted.append(f)

        if accepted:
            self.img_att_list.clear()
            for f in accepted:
                self.img_att_list.addItem(f)

        if rejected:
            QMessageBox.warning(
                self,
                "Template too large",
                "These HTML templates are over 100KB and were NOT added:\n\n"
                + "\n".join(rejected)
                + "\n\nPlease ensure HTML templates are below 100KB."
            )

    def _add_img_att(self):
        fmt_filter_map = {
            "PNG":  "PNG Images (*.png)",
            "JPG":  "JPG Images (*.jpg *.jpeg)",
            "JPEG": "JPEG Images (*.jpeg *.jpg)",
            "GIF":  "GIF Images (*.gif)",
        }
        selected_fmt = self.cmb_img_format.currentText()
        filter_str = fmt_filter_map.get(selected_fmt, "Images (*.png *.jpg *.jpeg *.gif)")
        files, _ = QFileDialog.getOpenFileNames(
            self, f"Select {selected_fmt} Images", "", filter_str)
        if not files:
            return
        max_bytes = 100 * 1024
        rejected = []
        accepted = []
        for f in files:
            try:
                size = Path(f).stat().st_size
            except Exception:
                size = 0
            if size > max_bytes:
                rejected.append(f"{Path(f).name} ({size // 1024} KB)")
            else:
                accepted.append(f)
        if accepted:
            self.img_att_list.clear()
            for f in accepted:
                self.img_att_list.addItem(f)
        if rejected:
            QMessageBox.warning(
                self, "Image(s) too large",
                "These images are over 100KB and were NOT added:\n\n" + "\n".join(rejected) +
                "\n\nPlease compress or resize them before uploading."
            )

    def _add_pdf_html(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select HTML Template for PDF Attachment", "", "HTML Templates (*.html *.htm)"
        )
        if not files:
            return

        max_bytes = 100 * 1024
        rejected = []
        accepted = []

        for f in files:
            try:
                size = Path(f).stat().st_size
            except Exception:
                size = 0

            if size > max_bytes:
                rejected.append(f"{Path(f).name} ({size // 1024} KB)")
                continue

            accepted.append(f)

        if accepted:
            self.pdf_att_list.clear()
            for f in accepted:
                self.pdf_att_list.addItem(f)

        if rejected:
            QMessageBox.warning(
                self,
                "Template too large",
                "These HTML templates are over 100KB and were NOT added:\n\n"
                + "\n".join(rejected)
                + "\n\nPlease ensure HTML templates are below 100KB."
            )

    def _add_pdf_att(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if not files:
            return

        max_bytes = 100 * 1024
        rejected = []
        accepted = []

        for f in files:
            if Path(f).suffix.lower() == ".pdf":
                try:
                    size = Path(f).stat().st_size
                except Exception:
                    size = 0

                if size > max_bytes:
                    rejected.append(
                        f"{Path(f).name} ({size // 1024} KB)"
                    )
                    continue

            accepted.append(f)

        if accepted:
            self.pdf_att_list.clear()
            for f in accepted:
                self.pdf_att_list.addItem(f)

        if rejected:
            QMessageBox.warning(
                self,
                "PDF(s) too large",
                "These PDFs are over 100KB and were NOT added:\n\n"
                + "\n".join(rejected)
                + "\n\nPlease compress or reduce them before uploading."
            )












    # ── Campaign config builder ───────────────────────────────────────────────
    def _build_campaign_tags(self):
        return {
            "tfn1":          self.inp_tfn1.text(),
            "tfn2":          self.inp_tfn2.text(),
            "date_auto":     self.chk_date_auto.isChecked(),
            "date_manual":   self.inp_date.text(),
            "time_auto":     self.chk_time_auto.isChecked(),
            "time_manual":   self.inp_time.text(),
            "amount_mode":   "custom" if self.rb_amt_custom.isChecked() else "random",
            "amount_custom": self.inp_amt_custom.text(),
            "amount_min":    self.spn_amt_min.value(),
            "amount_max":    self.spn_amt_max.value(),
        }

    def _recipients_to_db(self):
        import re
        # Clear out any old/stale recipients so ONLY the currently listed recipients are sent
        self.db.clear_recipients()
        self.db.reset_smtp_statuses()
        added = 0
        for line in self.txt_recipients.toPlainText().split('\n'):
            line = line.strip()
            if not line or '@' not in line:
                continue

            # Robust extraction: find the actual email address in the line
            email_match = re.search(r'[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}', line)
            if email_match:
                email = email_match.group(0).strip()
                # Remaining text on the line is the name, stripping any delimiters (comma, dot, pipe, semicolon)
                name = line.replace(email, "").strip(" ,|;.\t").strip()
            else:
                parts = line.split(',')
                email = parts[0].strip()
                name  = parts[1].strip() if len(parts) > 1 else ""

            self.db.add_or_reset_recipient(email, name)
            added += 1
        return added

    @staticmethod
    def _format_text_for_email(text: str) -> str:
        """
        Converts plain text or code to email-compliant HTML that preserves exact
        formatting, paragraph breaks, and line breaks across all email clients
        (Gmail, Outlook, Yahoo, Apple Mail, Web & Mobile).
        """
        if not text:
            return ""

        tb_s = text.strip()
        is_raw_html = (
            tb_s.startswith((
                "<html", "<!doctype", "<!DOCTYPE", "<table", "<div", "<p", "<?xml",
                "<body", "<!--", "<style", "<center", "<span", "<section", "<header",
                "<main", "<article", "<form", "<ul", "<ol", "<h1", "<h2", "<h3"
            ))
            or ("<html" in tb_s.lower() and "</html>" in tb_s.lower())
            or ("<body" in tb_s.lower() and "</body>" in tb_s.lower())
            or ("</div>" in tb_s.lower())
            or ("</table>" in tb_s.lower())
        )

        if is_raw_html:
            return text

        # Normalize line endings
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return ""

        # Split by double newlines into paragraphs
        raw_paragraphs = normalized.split("\n\n")
        html_paragraphs = []

        for para in raw_paragraphs:
            para_stripped = para.strip("\n")
            if not para_stripped:
                # Extra blank line preserved as vertical spacing
                html_paragraphs.append('<div style="height: 14px; line-height: 14px;">&nbsp;</div>')
                continue
            lines = para_stripped.split("\n")
            formatted_lines = []
            for line in lines:
                leading_spaces = len(line) - len(line.lstrip(" "))
                prefix = "&nbsp;" * leading_spaces if leading_spaces > 0 else ""
                formatted_lines.append(prefix + line.lstrip(" "))
            para_content = "<br>\n".join(formatted_lines)
            html_paragraphs.append(
                f'<p style="margin: 0 0 14px 0; font-family: Arial, Helvetica, sans-serif; '
                f'font-size: 14px; color: #222222; line-height: 1.6;">\n{para_content}\n</p>'
            )

        if not html_paragraphs:
            return ""

        joined_paragraphs = "\n".join(html_paragraphs)
        return (
            f'<div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; '
            f'color: #222222; line-height: 1.6; margin: 0; padding: 0;">\n'
            f'{joined_paragraphs}\n'
            f'</div>'
        )

    def _get_html_templates(self):
        templates = []
        if self.rb_content_code.isChecked():
            code = self.txt_body_code.toPlainText().strip()
            if code:
                code = self._format_text_for_email(code)
                if getattr(self, 'chk_code_inline_b64', None) and self.chk_code_inline_b64.isChecked():
                    try:
                        from backend.template_manager import TemplateManager
                        code = TemplateManager().process_html_inline_images(code, "")
                    except Exception:
                        pass
                templates.append(code)
            return templates

        for i in range(self.html_list.count()):
            fpath = self.html_list.item(i).text()
            try:
                html = Path(fpath).read_text(encoding='utf-8')
                if self.chk_inline_b64.isChecked():
                    from backend.template_manager import TemplateManager
                    html = TemplateManager().process_html_inline_images(html, fpath)
                templates.append(html)
            except Exception as e:
                self._log(f"⚠ Cannot read {fpath}: {e}")
        if not templates:
            plain = self.txt_body_plain.toPlainText().strip()
            if plain:
                templates = [self._format_text_for_email(plain)]
        return templates

    # ── Subject & Body helpers ────────────────────────────────────────────────
    def _on_subjects_changed(self):
        lines = [l.strip() for l in self.txt_subjects.toPlainText().split('\n') if l.strip()]
        if hasattr(self, 'lbl_subj_count'):
            self.lbl_subj_count.setText(f"{len(lines)} subject(s) loaded")

    def _on_bodies_changed(self):
        import re
        raw = self.txt_body_plain.toPlainText()
        bodies = [b.strip() for b in re.split(r'\s*={3,}\s*', raw) if b.strip()]
        count = len(bodies)
        if hasattr(self, 'lbl_body_count'):
            self.lbl_body_count.setText(f"{count} body template(s) loaded")

    def _add_quick_subject(self):
        line = self.inp_quick_subject.text().strip()
        if not line:
            return
        current = self.txt_subjects.toPlainText().strip()
        if current:
            self.txt_subjects.setPlainText(current + "\n" + line)
        else:
            self.txt_subjects.setPlainText(line)
        self.inp_quick_subject.clear()
        self._log(f"📝 Quick-added subject: {line[:50]}")

    def _load_subjects_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Subjects (TXT / CSV / Excel)", "",
            "All Supported (*.txt *.csv *.xlsx *.xls);;Text Files (*.txt);;CSV/Excel (*.csv *.xlsx *.xls);;All Files (*.*)"
        )
        if not path:
            return

        p = Path(path)
        if p.suffix.lower() == ".txt":
            try:
                lines = [l.strip() for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            except Exception as e:
                self._log(f"❌ Error reading text file: {e}")
                return
            if not lines:
                QMessageBox.information(self, "Empty File", "No subject lines found in the selected text file.")
                return

            current = self.txt_subjects.toPlainText().strip()
            combined = (current + "\n" + "\n".join(lines)).strip() if current else "\n".join(lines)
            self.txt_subjects.setPlainText(combined)
            self._log(f"📂 Loaded {len(lines)} subject line(s) from text file: {p.name}")
            return

        rows = self._read_csv_or_excel(path)
        subj_lines = []
        body_lines = []
        for idx, row in enumerate(rows):
            if not row:
                continue
            subj = str(row[0]).strip()
            # If the first row looks like a header, skip it
            if idx == 0 and subj.lower() in ("subject", "subjects", "subject line", "subject lines", "subject_line") and len(rows) > 1:
                continue
            if subj:
                subj_lines.append(subj)
                if len(row) >= 2:
                    body_lines.append(str(row[1]).strip())

        if not subj_lines:
            QMessageBox.information(self, "No Subjects", "No valid subject lines found in the selected file.")
            return

        current = self.txt_subjects.toPlainText().strip()
        combined = (current + "\n" + "\n".join(subj_lines)).strip() if current else "\n".join(subj_lines)
        self.txt_subjects.setPlainText(combined)
        self._log(f"📂 Loaded {len(subj_lines)} subject lines from file: {Path(path).name}")

        if body_lines:
            curr_b = self.txt_body_plain.toPlainText().strip()
            comb_b = (curr_b + "\n===\n" + "\n===\n".join(body_lines)).strip() if curr_b else "\n===\n".join(body_lines)
            self.txt_body_plain.setPlainText(comb_b)
            self._log(f"📄 Also loaded {len(body_lines)} matching body templates from file")

    def _paste_bulk_subjects(self):
        dlg = PasteDialog(
            "Paste Bulk Subject Lines",
            "Paste subject lines below (one per line — all will rotate):\n"
            "Tags like #NAME#, #INVOICE#, #AMOUNT#, #DATE# are supported.",
            self
        )
        if dlg.exec() == QDialog.Accepted:
            pasted = dlg.get_text().strip()
            if not pasted:
                return
            lines = [l.strip() for l in pasted.split('\n') if l.strip()]
            if not lines:
                return
            current = self.txt_subjects.toPlainText().strip()
            combined = (current + "\n" + "\n".join(lines)).strip() if current else "\n".join(lines)
            self.txt_subjects.setPlainText(combined)
            self._log(f"📋 Pasted {len(lines)} subject lines")

    def _clear_subjects(self):
        self.txt_subjects.clear()
        self._log("🗑 Subject lines cleared")

    def _load_bodies_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Body Templates (TXT / CSV / Excel)", "",
            "All Supported (*.txt *.csv *.xlsx *.xls);;Text Files (*.txt);;CSV/Excel (*.csv *.xlsx *.xls);;All Files (*.*)"
        )
        if not path:
            return

        p = Path(path)
        if p.suffix.lower() == ".txt":
            try:
                raw_text = p.read_text(encoding="utf-8", errors="replace").strip()
            except Exception as e:
                self._log(f"❌ Error reading text file: {e}")
                return
            if not raw_text:
                QMessageBox.information(self, "Empty File", "The selected text file is empty.")
                return

            import re
            body_parts = [b.strip() for b in re.split(r'\s*={3,}\s*', raw_text) if b.strip()]
            self.txt_body_plain.setPlainText(raw_text)
            self._on_bodies_changed()
            self._log(f"📄 Loaded {len(body_parts)} body template(s) from text file: {p.name}")
            return

        rows = self._read_csv_or_excel(path)
        body_lines = []
        subj_lines = []
        for idx, row in enumerate(rows):
            if not row:
                continue
            if len(row) >= 2:
                s = str(row[0]).strip()
                b = str(row[1]).strip()
                if idx == 0 and (s.lower() in ("subject", "subjects") or b.lower() in ("body", "text", "template", "message")) and len(rows) > 1:
                    continue
                if b:
                    body_lines.append(b)
                if s:
                    subj_lines.append(s)
            else:
                b = str(row[0]).strip()
                if idx == 0 and b.lower() in ("body", "text", "template", "message") and len(rows) > 1:
                    continue
                if b:
                    body_lines.append(b)

        if not body_lines:
            QMessageBox.information(self, "No Body Content", "No valid body content found in the selected file.")
            return

        curr_b = self.txt_body_plain.toPlainText().strip()
        comb_b = (curr_b + "\n===\n" + "\n===\n".join(body_lines)).strip() if curr_b else "\n===\n".join(body_lines)
        self.txt_body_plain.setPlainText(comb_b)
        self._log(f"📄 Loaded {len(body_lines)} body template(s) from file: {Path(path).name}")

        if subj_lines:
            curr_s = self.txt_subjects.toPlainText().strip()
            comb_s = (curr_s + "\n" + "\n".join(subj_lines)).strip() if curr_s else "\n".join(subj_lines)
            self.txt_subjects.setPlainText(comb_s)
            self._log(f"📂 Also loaded {len(subj_lines)} matching subject lines from file")

    def _paste_bulk_bodies(self):
        dlg = PasteDialog(
            "Paste Multiple Body Templates",
            "Paste multiple body templates below.\n"
            "Separate each template with === on a new line.\n\n"
            "Example:\n"
            "Hello #NAME#, your invoice #INVOICE# is ready...\n"
            "===\n"
            "Hi #NAME#, order #ORDERID# has been confirmed...\n"
            "===\n"
            "Dear #NAME#, notice regarding transaction #TXNID#...",
            self
        )
        if dlg.exec() == QDialog.Accepted:
            pasted = dlg.get_text().strip()
            import re
            new_bodies = [b.strip() for b in re.split(r'\s*={3,}\s*', pasted) if b.strip()]
            if not new_bodies:
                return
            curr_b = self.txt_body_plain.toPlainText().strip()
            comb_b = (curr_b + "\n===\n" + "\n===\n".join(new_bodies)).strip() if curr_b else "\n===\n".join(new_bodies)
            self.txt_body_plain.setPlainText(comb_b)
            self._log(f"📋 Pasted {len(new_bodies)} body template(s)")

    def _clear_bodies(self):
        self.txt_body_plain.clear()
        self._log("🗑 Body templates cleared")

    # ── Persistent Settings (survive SMTP/Data clear + app restart) ──────────
    def _save_settings(self):
        """Persist all task parameters to DB so they survive clear/restart."""
        import json
        pfx = f"task_{self.task_id}_"
        s = self.db.set_setting

        # Tags
        s(pfx + "tfn1", self.inp_tfn1.text())
        s(pfx + "tfn2", self.inp_tfn2.text())
        s(pfx + "date_auto", "1" if self.chk_date_auto.isChecked() else "0")
        s(pfx + "date_manual", self.inp_date.text())
        s(pfx + "time_auto", "1" if self.chk_time_auto.isChecked() else "0")
        s(pfx + "time_manual", self.inp_time.text())
        s(pfx + "amt_mode", "custom" if self.rb_amt_custom.isChecked() else "random")
        s(pfx + "amt_custom", self.inp_amt_custom.text())
        s(pfx + "amt_min", str(self.spn_amt_min.value()))
        s(pfx + "amt_max", str(self.spn_amt_max.value()))
        s(pfx + "addresses", self.txt_addresses.toPlainText())
        # Note: Recipients are not saved across sessions so each launch starts empty

        # Content
        s(pfx + "subjects", self.txt_subjects.toPlainText())
        s(pfx + "senders", self.txt_senders.toPlainText())
        s(pfx + "default_sender", "1" if self.chk_default_sender.isChecked() else "0")
        s(pfx + "body_plain", self.txt_body_plain.toPlainText())
        s(pfx + "body_code", self.txt_body_code.toPlainText())
        s(pfx + "inline_b64", "1" if self.chk_inline_b64.isChecked() else "0")
        s(pfx + "img_format", self.cmb_img_format.currentText())

        # Body mode
        if self.rb_text_only.isChecked():
            bm = "text"
        elif self.rb_inline_attach.isChecked():
            bm = "inline_img"
        elif self.rb_inline_pdf.isChecked():
            bm = "inline_pdf"
        elif self.rb_body_pdf.isChecked():
            bm = "body_pdf"
        elif self.rb_body_img_pdf.isChecked():
            bm = "body_img_pdf"
        elif self.rb_body_img.isChecked():
            bm = "body_img"
        else:
            bm = "html"
        s(pfx + "body_mode", bm)
        if self.rb_text_only.isChecked():
            bct = "text"
        elif self.rb_content_code.isChecked():
            bct = "code"
        elif self.rb_content_text.isChecked():
            bct = "text"
        else:
            bct = "html"
        s(pfx + "body_content_type", bct)

        # HTML file paths
        html_paths = [self.html_list.item(i).text() for i in range(self.html_list.count())]
        s(pfx + "html_paths", json.dumps(html_paths))
        img_paths = [self.img_att_list.item(i).text() for i in range(self.img_att_list.count())]
        s(pfx + "img_paths", json.dumps(img_paths))
        pdf_paths = [self.pdf_att_list.item(i).text() for i in range(self.pdf_att_list.count())]
        s(pfx + "pdf_paths", json.dumps(pdf_paths))

        # Delays
        s(pfx + "delay", str(self.spn_delay.value()))
        s(pfx + "smtp_mode", "auto" if self.rb_auto.isChecked() else "limit")
        s(pfx + "limit_per_smtp", str(self.spn_limit.value()))
        s(pfx + "auto_remove", "1" if self.chk_auto_remove.isChecked() else "0")
        s(pfx + "bounce_pct", str(self.spn_bounce.value()))
        s(pfx + "rot_mode", "per_smtp" if getattr(self, 'rb_rot_per_smtp', None) and self.rb_rot_per_smtp.isChecked() else "random")

    def _load_settings(self):
        """Restore persisted task parameters from DB."""
        import json
        pfx = f"task_{self.task_id}_"
        g = self.db.get_setting

        # Tags
        v = g(pfx + "tfn1");       self.inp_tfn1.setText(v) if v else None
        v = g(pfx + "tfn2");       self.inp_tfn2.setText(v) if v else None
        v = g(pfx + "date_auto");  self.chk_date_auto.setChecked(v != "0") if v else None
        v = g(pfx + "date_manual"); self.inp_date.setText(v) if v else None
        v = g(pfx + "time_auto");  self.chk_time_auto.setChecked(v != "0") if v else None
        v = g(pfx + "time_manual"); self.inp_time.setText(v) if v else None
        v = g(pfx + "amt_mode")
        if v == "random":
            self.rb_amt_random.setChecked(True)
        elif v == "custom":
            self.rb_amt_custom.setChecked(True)
        v = g(pfx + "amt_custom"); self.inp_amt_custom.setText(v) if v else None
        v = g(pfx + "amt_min")
        if v: self.spn_amt_min.setValue(float(v))
        v = g(pfx + "amt_max")
        if v: self.spn_amt_max.setValue(float(v))
        v = g(pfx + "addresses"); self.txt_addresses.setPlainText(v) if v else None

        # Recipients - always start completely empty on launch
        self.txt_recipients.blockSignals(True)
        self.txt_recipients.clear()
        self.txt_recipients.blockSignals(False)
        self._on_recipients_changed()

        # Content
        v = g(pfx + "subjects");   self.txt_subjects.setPlainText(v) if v else None
        v = g(pfx + "senders");    self.txt_senders.setPlainText(v) if v else None
        v = g(pfx + "default_sender"); self.chk_default_sender.setChecked(v != "0") if v else None
        v = g(pfx + "body_plain"); self.txt_body_plain.setPlainText(v) if v else None
        v = g(pfx + "body_code");  self.txt_body_code.setPlainText(v) if v else None
        v = g(pfx + "inline_b64"); self.chk_inline_b64.setChecked(v != "0") if v else None
        v = g(pfx + "img_format")
        if v: self.cmb_img_format.setCurrentText(v)

        # Rotation mode
        v = g(pfx + "rot_mode", "per_smtp")
        if v == "random" and hasattr(self, 'rb_rot_random'):
            self.rb_rot_random.setChecked(True)
        elif hasattr(self, 'rb_rot_per_smtp'):
            self.rb_rot_per_smtp.setChecked(True)

        # Body mode
        v = g(pfx + "body_mode")
        # Block signals temporarily to prevent trigger loops during config load
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf,
                   self.rb_text_only, self.rb_html_only):
            rb.blockSignals(True)
            
        if v == "text":
            self.rb_text_only.setChecked(True)
        elif v in ("inline_img", "inline_attach", "html_image"):
            self.rb_inline_attach.setChecked(True)
        elif v == "inline_pdf":
            self.rb_inline_pdf.setChecked(True)
        elif v == "text_inline":
            self.rb_body_img.setChecked(True)
            self.rb_content_text.setChecked(True)
        elif v == "body_pdf":
            self.rb_body_pdf.setChecked(True)
        elif v == "body_img_pdf":
            self.rb_body_img_pdf.setChecked(True)
        elif v == "body_img":
            self.rb_body_img.setChecked(True)
        elif v == "html":
            self.rb_html_only.setChecked(True)
        else:
            self.rb_html_only.setChecked(True)
            
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf,
                   self.rb_text_only, self.rb_html_only):
            rb.blockSignals(False)
            
        bct = g(pfx + "body_content_type", "text")
        self.rb_content_html.blockSignals(True)
        self.rb_content_text.blockSignals(True)
        self.rb_content_code.blockSignals(True)
        if bct == "html":
            self.rb_content_html.setChecked(True)
        elif bct == "code":
            self.rb_content_code.setChecked(True)
        else:
            self.rb_content_text.setChecked(True)
        self.rb_content_html.blockSignals(False)
        self.rb_content_text.blockSignals(False)
        self.rb_content_code.blockSignals(False)

        self._update_content_visibility()

        # HTML file paths
        v = g(pfx + "html_paths")
        if v:
            try:
                for p in json.loads(v):
                    if Path(p).exists():
                        self.html_list.addItem(p)
            except Exception:
                pass
        v = g(pfx + "img_paths")
        if v:
            try:
                for p in json.loads(v):
                    if Path(p).exists():
                        self.img_att_list.addItem(p)
            except Exception:
                pass
        v = g(pfx + "pdf_paths")
        if v:
            try:
                for p in json.loads(v):
                    if Path(p).exists():
                        self.pdf_att_list.addItem(p)
            except Exception:
                pass

        # Delays
        v = g(pfx + "delay")
        if v: self.spn_delay.setValue(float(v))
        v = g(pfx + "smtp_mode")
        if v == "limit": self.rb_limit.setChecked(True)
        elif v == "auto": self.rb_auto.setChecked(True)
        v = g(pfx + "limit_per_smtp")
        if v: self.spn_limit.setValue(int(v))
        v = g(pfx + "auto_remove"); self.chk_auto_remove.setChecked(v != "0") if v else None
        v = g(pfx + "bounce_pct")
        if v: self.spn_bounce.setValue(int(v))
        self._on_subjects_changed()
        self._on_bodies_changed()

    # ── Task execution ────────────────────────────────────────────────────────
    def start_task(self):
        if not self.enabled:
            return
        if self.worker and self.worker.isRunning():
            self._log("⚠ Task is already running"); return

        # Persist all settings before sending
        self._save_settings()

        added = self._recipients_to_db()
        self._log(f"📋 {added} new recipients added to pool")

        subjects = [s.strip() for s in self.txt_subjects.toPlainText().split('\n') if s.strip()]
        if not subjects:
            subjects = ["Hello #NAME#"]

        senders = [s.strip() for s in self.txt_senders.toPlainText().split('\n') if s.strip()]
        if self.chk_default_sender.isChecked():
            senders = []

        addresses = [a.strip() for a in self.txt_addresses.toPlainText().split('\n') if a.strip()]

        body_mode = "html"
        if self.rb_text_only.isChecked():
            body_mode = "text"
        elif self.rb_inline_attach.isChecked():
            body_mode = "inline_img"
        elif self.rb_inline_pdf.isChecked():
            body_mode = "inline_pdf"
        elif self.rb_body_pdf.isChecked():
            body_mode = "body_pdf"
        elif self.rb_body_img_pdf.isChecked():
            body_mode = "body_img_pdf"
        elif self.rb_body_img.isChecked():
            body_mode = "body_img"

        # Determine body content format (html vs text vs code)
        if self.rb_text_only.isChecked() or self.rb_content_text.isChecked():
            body_content_type = "text"
        elif self.rb_content_code.isChecked():
            body_content_type = "code"
        else:
            body_content_type = "html"

        # Isolate mode data: only include attachments/templates relevant to the selected body_mode
        img_paths = []
        if body_mode in ("body_img", "text_inline"):
            raw_img_items = [self.img_att_list.item(i).text() for i in range(self.img_att_list.count())]
            direct_imgs = [p for p in raw_img_items if Path(p).suffix.lower() not in ('.html', '.htm')]
            html_imgs = [p for p in raw_img_items if Path(p).suffix.lower() in ('.html', '.htm')]
            if direct_imgs:
                img_paths = direct_imgs
            elif html_imgs:
                img_paths = html_imgs
            else:
                img_paths = []

        pdf_paths = []
        if body_mode in ("body_pdf", "body_img_pdf", "inline_pdf"):
            raw_pdf_items = [self.pdf_att_list.item(i).text() for i in range(self.pdf_att_list.count())]
            direct_pdfs = [p for p in raw_pdf_items if Path(p).suffix.lower() not in ('.html', '.htm')]
            html_pdfs = [p for p in raw_pdf_items if Path(p).suffix.lower() in ('.html', '.htm')]
            if direct_pdfs:
                pdf_paths = direct_pdfs
            elif html_pdfs:
                pdf_paths = html_pdfs
            else:
                pdf_paths = []

        templates = []
        body_plain = ""

        import re
        raw_b_text = self.txt_body_plain.toPlainText()
        raw_b_list = [b.strip() for b in re.split(r'\s*={3,}\s*', raw_b_text) if b.strip()]
        body_plain_list = [self._format_text_for_email(b) for b in raw_b_list] if raw_b_list else []

        if body_content_type == "text" or body_mode in ("text", "text_inline"):
            formatted_text = body_plain_list[0] if body_plain_list else self._format_text_for_email(raw_b_text)
            body_plain = formatted_text
            templates = body_plain_list if body_plain_list else ([formatted_text] if formatted_text else [])
        elif body_content_type == "code":
            formatted_code = self._format_text_for_email(self.txt_body_code.toPlainText())
            body_plain = formatted_code
            templates = self._get_html_templates()
            if not templates and formatted_code:
                templates = [formatted_code]
        else:
            # HTML Template mode
            templates = self._get_html_templates()
            formatted_text = self._format_text_for_email(raw_b_text)
            body_plain = formatted_text
            if not templates and formatted_text:
                templates = [formatted_text]

        rotation_mode = "per_smtp" if getattr(self, 'rb_rot_per_smtp', None) and self.rb_rot_per_smtp.isChecked() else "random"

        config = {
            "templates":          templates,
            "subjects":           subjects,
            "sender_names":       senders,
            "campaign_tags":      self._build_campaign_tags(),
            "addresses":          addresses,
            "image_paths":        img_paths,
            "pdf_paths":          pdf_paths,
            "delay":              self.spn_delay.value(),
            "smtp_mode":          "auto" if self.rb_auto.isChecked() else "limit",
            "limit_per_smtp":     self.spn_limit.value(),
            "auto_remove":        self.chk_auto_remove.isChecked(),
            "body_mode":          body_mode,
            "body_content_type":  body_content_type,
            "body_plain":         body_plain,
            "body_plain_list":    body_plain_list,
            "rotation_mode":      rotation_mode,
            "img_format":         self.cmb_img_format.currentText(),
        }

        self.worker = TaskWorker(self.task_id, config, self.db)
        self.worker.log_message.connect(self._log)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.status_changed.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        self._set_status("running")

    def pause_task(self):
        if self.worker and self.worker.isRunning():
            if self.worker._paused:
                self.worker.resume()
                self.btn_pause.setText("⏸ Pause")
            else:
                self.worker.pause()
                self.btn_pause.setText("▶ Resume")

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    # ── Worker signals ────────────────────────────────────────────────────────
    def _on_progress(self, d: dict):
        self.sent_count  = d['sent']
        self.fail_count  = d['failed']
        self.queue_count = d['remaining']
        self.lbl_sent.setText(f"Sent: {d['sent']}")
        self.lbl_failed.setText(f"Failed: {d['failed']}")
        self.lbl_queue.setText(f"Queue: {d['remaining']}")
        self.lbl_current_smtp.setText(f"SMTP: {d['current_smtp']}")
        self.stats_changed.emit()

    def _on_status(self, status: str):
        self._set_status(status)

    def _on_finished(self):
        self._set_status("done")
        self.btn_pause.setText("⏸ Pause")
        self.refresh_smtp_list()

    def _set_status(self, status: str):
        colors = {"running": "#43b581", "paused": "#f0a500",
                  "stopped": "#ed4245", "done": "#5865f2", "idle": "#7880a0"}
        labels = {"running": "● Running", "paused": "⏸ Paused",
                  "stopped": "⏹ Stopped", "done": "✔ Done",   "idle": "● Idle"}
        c = colors.get(status, "#7880a0")
        t = labels.get(status, status)
        self.lbl_status.setText(t)
        self.lbl_status.setStyleSheet(f"color:{c}; font-size:12px; font-weight:700; padding:0 12px;")

    def _is_recipient_log(self, msg: str) -> bool:
        """Return True only if msg is strictly relevant to recipients."""
        lower = msg.lower()
        # Strictly exclude internal base64 debug, smtp auth/linking, general task startup, and subjects
        if any(ex in lower for ex in (
            "base64",
            "auth error",
            "microsoft account",
            "starting |",
            "exhausted",
            "downloaded to",
            "smtp",
            "switch",
            "subject",
        )):
            return False

        # Include specific recipient events
        if any(kw in lower for kw in (
            "recipient(s) loaded",
            "recipients loaded",
            "recipients added to pool",
            "recipients from file",
            "email rows",
            "recipient validation",
            "recipients cleared",
            "unsubscribed",
            "fallback",
        )):
            return True

        # Include per-recipient delivery statuses (OK ->, FAIL ->, 📧 ->)
        if " -> " in msg or " → " in msg:
            if any(marker in msg for marker in ("OK", "FAIL", "📧", "Skipping")):
                return True

        return False

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log_box.append(entry)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.activity_logged.emit(self.task_id, msg)

        # Mirror recipient-related entries strictly to the Recipient Log box above recipients
        if hasattr(self, 'txt_rec_log') and self._is_recipient_log(msg):
            self.txt_rec_log.append(entry)
            sb2 = self.txt_rec_log.verticalScrollBar()
            sb2.setValue(sb2.maximum())
            
    def _update_content_visibility(self):
        show_html = False
        show_txt = False
        show_code = False
        show_img_att = False
        show_pdf_att = False
        show_body_type = False

        if self.rb_text_only.isChecked():
            show_body_type = False
            show_txt = True
        else:
            show_body_type = True
            if self.rb_content_html.isChecked():
                show_html = True
            elif self.rb_content_code.isChecked():
                show_code = True
            elif self.rb_content_text.isChecked():
                show_txt = True
            else:
                show_html = True

            if self.rb_body_img.isChecked():
                show_img_att = True
            elif self.rb_body_pdf.isChecked() or self.rb_body_img_pdf.isChecked() or self.rb_inline_pdf.isChecked():
                show_pdf_att = True

        self.g_body_type.setVisible(show_body_type)
        self.g_html.setVisible(show_html)
        self.g_txt.setVisible(show_txt)
        self.g_code.setVisible(show_code)
        self.wdg_img_att.setVisible(show_img_att)
        self.wdg_pdf_att.setVisible(show_pdf_att)
        self.g_att.setVisible(show_img_att or show_pdf_att)

    def reset_task_data(self):
        """Completely reset all UI fields, counters, and inputs to a fresh initial state."""
        # Stop worker if active
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self.worker = None

        # Reset counters & status
        self.sent_count = 0
        self.fail_count = 0
        self.queue_count = 0
        self.enabled = True
        if hasattr(self, 'chk_enable'):
            self.chk_enable.setChecked(True)
        if hasattr(self, 'lbl_status'):
            self.lbl_status.setText("● Idle")
            self.lbl_status.setStyleSheet("color:#7880a0; font-size:12px; font-weight:700; padding:0 12px;")
        if hasattr(self, 'lbl_queue'):
            self.lbl_queue.setText("Queue: 0")
        if hasattr(self, 'lbl_sent'):
            self.lbl_sent.setText("Sent: 0")
        if hasattr(self, 'lbl_failed'):
            self.lbl_failed.setText("Failed: 0")
        if hasattr(self, 'lbl_current_smtp'):
            self.lbl_current_smtp.setText("SMTP: –")
        if hasattr(self, 'btn_pause'):
            self.btn_pause.setText("⏸ Pause")
        if hasattr(self, 'btn_start'):
            self.btn_start.setEnabled(True)

        # Recipients Tab
        if hasattr(self, 'txt_recipients'):
            self.txt_recipients.blockSignals(True)
            self.txt_recipients.clear()
            self.txt_recipients.blockSignals(False)
        if hasattr(self, 'txt_rec_log'):
            self.txt_rec_log.clear()
        self._prev_rec_count = 0
        self._last_logged_rec_summary = None
        if hasattr(self, 'txt_fallback'):
            self.txt_fallback.clear()
        if hasattr(self, 'lbl_rec_count'):
            self.lbl_rec_count.setText("0 recipients loaded")
        if hasattr(self, 'lbl_valid'):
            self.lbl_valid.setText("Not validated")
            self.lbl_valid.setStyleSheet("color:#f0a500; font-size:11px;")

        # SMTP Tab
        if hasattr(self, 'smtp_list'):
            self.smtp_list.clear()
        if hasattr(self, 'txt_single_smtp'):
            self.txt_single_smtp.clear()
        if hasattr(self, 'lbl_smtp_count'):
            self.lbl_smtp_count.setText("0 SMTP accounts loaded")

        # Tags Tab
        if hasattr(self, 'inp_tfn1'):
            self.inp_tfn1.clear()
        if hasattr(self, 'inp_tfn2'):
            self.inp_tfn2.clear()
        if hasattr(self, 'chk_date_auto'):
            self.chk_date_auto.setChecked(True)
        if hasattr(self, 'inp_date'):
            self.inp_date.clear()
        if hasattr(self, 'chk_time_auto'):
            self.chk_time_auto.setChecked(True)
        if hasattr(self, 'inp_time'):
            self.inp_time.clear()
        if hasattr(self, 'rb_amt_custom'):
            self.rb_amt_custom.setChecked(True)
        if hasattr(self, 'inp_amt_custom'):
            self.inp_amt_custom.clear()
        if hasattr(self, 'spn_amt_min'):
            self.spn_amt_min.setValue(100.0)
        if hasattr(self, 'spn_amt_max'):
            self.spn_amt_max.setValue(300.0)
        if hasattr(self, 'txt_addresses'):
            self.txt_addresses.clear()

        # Content Tab
        for rb in (getattr(self, 'rb_body_img', None), getattr(self, 'rb_body_pdf', None),
                   getattr(self, 'rb_body_img_pdf', None), getattr(self, 'rb_inline_attach', None),
                   getattr(self, 'rb_inline_pdf', None), getattr(self, 'rb_text_only', None),
                   getattr(self, 'rb_html_only', None)):
            if rb:
                rb.blockSignals(True)
        if hasattr(self, 'rb_html_only'):
            self.rb_html_only.setChecked(True)
        for rb in (getattr(self, 'rb_body_img', None), getattr(self, 'rb_body_pdf', None),
                   getattr(self, 'rb_body_img_pdf', None), getattr(self, 'rb_inline_attach', None),
                   getattr(self, 'rb_inline_pdf', None), getattr(self, 'rb_text_only', None),
                   getattr(self, 'rb_html_only', None)):
            if rb:
                rb.blockSignals(False)

        for rb in (getattr(self, 'rb_content_html', None), getattr(self, 'rb_content_text', None),
                   getattr(self, 'rb_content_code', None)):
            if rb:
                rb.blockSignals(True)
        if hasattr(self, 'rb_content_text'):
            self.rb_content_text.setChecked(True)
        for rb in (getattr(self, 'rb_content_html', None), getattr(self, 'rb_content_text', None),
                   getattr(self, 'rb_content_code', None)):
            if rb:
                rb.blockSignals(False)

        if hasattr(self, 'inp_quick_subject'):
            self.inp_quick_subject.clear()
        if hasattr(self, 'txt_subjects'):
            self.txt_subjects.clear()
        if hasattr(self, 'lbl_subj_count'):
            self.lbl_subj_count.setText("0 subjects loaded")
        if hasattr(self, 'chk_default_sender'):
            self.chk_default_sender.setChecked(True)
        if hasattr(self, 'txt_senders'):
            self.txt_senders.clear()
        if hasattr(self, 'txt_body_plain'):
            self.txt_body_plain.clear()
        if hasattr(self, 'lbl_body_count'):
            self.lbl_body_count.setText("0 body template(s) loaded")
        if hasattr(self, 'rb_rot_per_smtp'):
            self.rb_rot_per_smtp.setChecked(True)
        if hasattr(self, 'html_list'):
            self.html_list.clear()
        if hasattr(self, 'chk_inline_b64'):
            self.chk_inline_b64.setChecked(True)
        if hasattr(self, 'txt_body_code'):
            self.txt_body_code.clear()
        if hasattr(self, 'chk_code_inline_b64'):
            self.chk_code_inline_b64.setChecked(True)
        if hasattr(self, 'img_att_list'):
            self.img_att_list.clear()
        if hasattr(self, 'cmb_img_format'):
            self.cmb_img_format.setCurrentText("PNG")
        if hasattr(self, 'pdf_att_list'):
            self.pdf_att_list.clear()

        # Update visibility
        self._update_content_visibility()

        # Delays & Limits Tab
        if hasattr(self, 'spn_delay'):
            self.spn_delay.setValue(1.0)
        if hasattr(self, 'rb_auto'):
            self.rb_auto.setChecked(True)
        if hasattr(self, 'spn_limit'):
            self.spn_limit.setValue(5)
        if hasattr(self, 'spn_bounce'):
            self.spn_bounce.setValue(25)
        if hasattr(self, 'chk_auto_remove'):
            self.chk_auto_remove.setChecked(True)

        # Log Pane
        if hasattr(self, 'log_box'):
            self.log_box.clear()
            self._log("✨ Workspace reset. Ready for new campaign.")

        self.stats_changed.emit()
        try:
            self._save_settings()
        except Exception:
            pass
