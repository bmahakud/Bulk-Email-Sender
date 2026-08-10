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
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
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

        self.setStyleSheet(PANEL_BG + SHARED_SS)
        self._build_ui()
        self._load_settings()   # restore persisted parameters

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_top_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background:#252637; width:4px; }")

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet(SHARED_SS)
        self.sub_tabs.addTab(self._tab_recipients(), "📨 Recipients")
        self.sub_tabs.addTab(self._tab_smtp(),       "📧 SMTP")
        self.sub_tabs.addTab(self._tab_tags(),       "🏷 Tags")
        self.sub_tabs.addTab(self._tab_content(),    "📝 Content")
        self.sub_tabs.addTab(self._tab_delays(),     "⚙ Delays & Limits")
        splitter.addWidget(self.sub_tabs)
        splitter.addWidget(self._make_log_pane())
        splitter.setSizes([860, 480])
        root.addWidget(splitter, 1)

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
        self.inp_amt_custom = QLineEdit("200.00"); self.inp_amt_custom.setPlaceholderText("e.g. 200.00")
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
        self.rb_body_img_pdf = QRadioButton("Body+Img+PDF")
        
        self.rb_inline_attach = QRadioButton("Inline+Attach")
        self.rb_inline_pdf = QRadioButton("Inline+PDF")
        self.rb_text_inline = QRadioButton("Text+Inline")
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
        grid_mode.addWidget(self.rb_text_inline, 1, 2)
        grid_mode.addWidget(self.rb_text_only, 1, 3)
        grid_mode.addWidget(self.rb_html_only, 1, 4)
        
        lay.addWidget(g_mode)

        # Connect signals
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf, self.rb_text_inline,
                   self.rb_text_only, self.rb_html_only):
            rb.toggled.connect(self._update_content_visibility)

        # Subject lines
        g_sub = QGroupBox("Subject Lines  (rotation — one per line)")
        sl = QVBoxLayout()

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

        sl.addWidget(QLabel("Bulk subjects (one per line — all will rotate):"  ))
        self.txt_subjects = QTextEdit()
        self.txt_subjects.setPlaceholderText(
            "Your invoice #INVOICE# is ready — ProMailer Pro | Bulk Email Sender\n"
            "Payment of $#AMOUNT# received on #DATE# — Order #ORDERID#\n"
            "Important notice for #NAME# — Action required by #DATE#\n"
            "Transaction #TXNID# confirmed — Contact us at #TFN1#")
        self.txt_subjects.setFixedHeight(90)
        sl.addWidget(self.txt_subjects)
        g_sub.setLayout(sl); lay.addWidget(g_sub)

        # Sender names
        g_snd = QGroupBox("Sender Names  (rotation — one per line)")
        snl = QVBoxLayout()
        self.chk_default_sender = QCheckBox("Use SMTP account email as sender name (default)")
        self.chk_default_sender.setChecked(True)
        snl.addWidget(self.chk_default_sender)
        self.txt_senders = QTextEdit()
        self.txt_senders.setPlaceholderText("Sophia Adams\nAva Harris\nJohn Smith")
        self.txt_senders.setFixedHeight(80)
        snl.addWidget(self.txt_senders)
        g_snd.setLayout(snl); lay.addWidget(g_snd)

        # Body plain text
        self.g_txt = QGroupBox("Body Text  (plain text / fallback if no HTML)")
        tl = QVBoxLayout()

        body_hint = QLabel(
            "\u2139\ufe0f  What to write in the body:\n"
            "  \u2022 Start with a personalised greeting using #NAME#\n"
            "  \u2022 Mention the transaction / invoice details using tags\n"
            "  \u2022 Add a call-to-action or contact number via #TFN1#\n"
            "  \u2022 Close with your brand name or company footer"
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
            "  \U0001f4de  #TFN1#  |  #TFN2#\n\n"
            "Thank you for choosing our services.\n\n"
            "Warm regards,\n"
            "Customer Support Team\n"
            "Powered by ProMailer Pro | Bulk Email Sender"
        )
        self.txt_body_plain.setFixedHeight(200)
        tl.addWidget(self.txt_body_plain)
        self.g_txt.setLayout(tl); lay.addWidget(self.g_txt)

        # HTML templates
        self.g_html = QGroupBox("HTML Templates  (multiple files = rotation  +  base64 inline images)")
        hl = QVBoxLayout()
        hl.addWidget(QLabel("💡 Upload HTML files — images inside <img src='…'> auto-embedded as base64."))
        br = QHBoxLayout()
        b_add_h = QPushButton("+ Add HTML File"); b_add_h.setStyleSheet(BTN("#5865f2", "#4752c4"))
        b_add_h.clicked.connect(self._add_html)
        b_clr_h = QPushButton("Clear");           b_clr_h.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_h.clicked.connect(lambda: self.html_list.clear())
        br.addWidget(b_add_h); br.addWidget(b_clr_h); br.addStretch()
        hl.addLayout(br)
        self.html_list = QListWidget(); self.html_list.setFixedHeight(90)
        hl.addWidget(self.html_list)
        self.chk_inline_b64 = QCheckBox("Convert images to base64 inline  (recommended — avoids spam filters)")
        self.chk_inline_b64.setChecked(True)
        hl.addWidget(self.chk_inline_b64)
        self.g_html.setLayout(hl); lay.addWidget(self.g_html)

        # Attachments
        self.g_att = QGroupBox("Attachments  (personalised filename = email-prefix + 4 random digits)")
        al = QVBoxLayout()

        # Image Container
        self.wdg_img_att = QWidget()
        self.wdg_img_att.setStyleSheet("background:transparent;")
        img_lay = QVBoxLayout(self.wdg_img_att)
        img_lay.setContentsMargins(0, 0, 0, 0)
        ir = QHBoxLayout()
        b_add_i = QPushButton("+ Image Attachments  (GIF/PNG/JPG/WEBP → base64)")
        b_add_i.setStyleSheet(BTN("#43b581", "#369e6b"))
        b_add_i.clicked.connect(self._add_img_att)
        b_clr_i = QPushButton("Clear"); b_clr_i.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_i.clicked.connect(lambda: self.img_att_list.clear())
        ir.addWidget(b_add_i); ir.addWidget(b_clr_i); ir.addStretch()
        img_lay.addLayout(ir)
        self.img_att_list = QListWidget(); self.img_att_list.setFixedHeight(70)
        img_lay.addWidget(self.img_att_list)
        al.addWidget(self.wdg_img_att)

        # PDF Container
        self.wdg_pdf_att = QWidget()
        self.wdg_pdf_att.setStyleSheet("background:transparent;")
        pdf_lay = QVBoxLayout(self.wdg_pdf_att)
        pdf_lay.setContentsMargins(0, 0, 0, 0)
        pr = QHBoxLayout()
        b_add_p = QPushButton("+ PDF Attachments → base64"); b_add_p.setStyleSheet(BTN("#f0a500", "#c88a00"))
        b_add_p.clicked.connect(self._add_pdf_att)
        b_clr_p = QPushButton("Clear"); b_clr_p.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr_p.clicked.connect(lambda: self.pdf_att_list.clear())
        pr.addWidget(b_add_p); pr.addWidget(b_clr_p); pr.addStretch()
        pdf_lay.addLayout(pr)
        self.pdf_att_list = QListWidget(); self.pdf_att_list.setFixedHeight(70)
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
            "#NAME#  #EMAIL#  #TFN#  #TFN1#  #TFN2#  #DATE#  #TIME#\n"
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

        hdr = QLabel(f"▼ Task {self.task_id} Log")
        hdr.setStyleSheet(
            "color:#7880a0; font-size:11px; font-weight:700; "
            "padding:4px; background:#0d0e17; border-radius:3px;")
        lay.addWidget(hdr)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Courier New", 10))
        self.log_box.setStyleSheet("""
            QTextEdit {
                background:#0d0e17; color:#00d4aa;
                border:1px solid #252637; border-radius:5px; padding:6px;
            }
        """)
        lay.addWidget(self.log_box, 1)

        foot_row = QHBoxLayout()
        self.lbl_current_smtp = QLabel("SMTP: –")
        self.lbl_current_smtp.setStyleSheet("color:#5865f2; font-size:11px;")
        b_clr = QPushButton("Clear Log"); b_clr.setStyleSheet(BTN("#3d3f52", "#52546e"))
        b_clr.setFixedHeight(28)
        b_clr.clicked.connect(self.log_box.clear)
        foot_row.addWidget(self.lbl_current_smtp, 1)
        foot_row.addWidget(b_clr)
        lay.addLayout(foot_row)
        return w

    # ── Recipients helpers ────────────────────────────────────────────────────
    def _on_recipients_changed(self):
        lines = [l.strip() for l in self.txt_recipients.toPlainText().split('\n') if l.strip()]
        valid = [l for l in lines if '@' in l]
        self.lbl_rec_count.setText(f"{len(valid)} recipients loaded")

    def _clear_recipients(self):
        self.txt_recipients.clear()

    def _validate_recipients(self):
        lines = [l.strip() for l in self.txt_recipients.toPlainText().split('\n') if l.strip()]
        valid = [l for l in lines if '@' in l]
        invalid = len(lines) - len(valid)
        self.lbl_valid.setText(f"✅ {len(valid)} valid  |  ❌ {invalid} invalid")
        self.lbl_valid.setStyleSheet(
            "color:#43b581; font-size:11px; font-weight:600;" if not invalid
            else "color:#f0a500; font-size:11px; font-weight:600;")

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
        self._log(f"📂 Loaded {len(lines)} recipients from file")

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
        for f in files:
            self.html_list.addItem(f)

    def _add_img_att(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images/HTML", "", "Images/HTML (*.gif *.png *.jpg *.jpeg *.webp *.html *.htm)")
        for f in files:
            self.img_att_list.addItem(f)

    def _add_pdf_att(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs/HTML", "", "PDF/HTML (*.pdf *.html *.htm)")
        for f in files:
            self.pdf_att_list.addItem(f)

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
        added = 0
        for line in self.txt_recipients.toPlainText().split('\n'):
            line = line.strip()
            if not line or '@' not in line:
                continue
            parts = line.split(',')
            email = parts[0].strip()
            name  = parts[1].strip() if len(parts) > 1 else ""
            self.db.add_or_reset_recipient(email, name)
            added += 1
        return added

    def _get_html_templates(self):
        templates = []
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
                templates = [f"<p>{plain.replace(chr(10), '<br>')}</p>"]
        return templates

    # ── Quick-Add single subject helper ────────────────────────────────────────
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

        # Content
        s(pfx + "subjects", self.txt_subjects.toPlainText())
        s(pfx + "senders", self.txt_senders.toPlainText())
        s(pfx + "default_sender", "1" if self.chk_default_sender.isChecked() else "0")
        s(pfx + "body_plain", self.txt_body_plain.toPlainText())
        s(pfx + "inline_b64", "1" if self.chk_inline_b64.isChecked() else "0")

        # Body mode
        if self.rb_text_only.isChecked():
            bm = "text"
        elif self.rb_inline_attach.isChecked() or self.rb_inline_pdf.isChecked():
            bm = "html_image"
        elif self.rb_text_inline.isChecked():
            bm = "body_img"
        elif self.rb_body_pdf.isChecked() or self.rb_body_img_pdf.isChecked():
            bm = "body_pdf"
        elif self.rb_body_img.isChecked():
            bm = "body_img"
        else:
            bm = "html"
        s(pfx + "body_mode", bm)

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

        # Content
        v = g(pfx + "subjects");   self.txt_subjects.setPlainText(v) if v else None
        v = g(pfx + "senders");    self.txt_senders.setPlainText(v) if v else None
        v = g(pfx + "default_sender"); self.chk_default_sender.setChecked(v != "0") if v else None
        v = g(pfx + "body_plain"); self.txt_body_plain.setPlainText(v) if v else None
        v = g(pfx + "inline_b64"); self.chk_inline_b64.setChecked(v != "0") if v else None

        # Body mode
        v = g(pfx + "body_mode")
        # Block signals temporarily to prevent trigger loops during config load
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf, self.rb_text_inline,
                   self.rb_text_only, self.rb_html_only):
            rb.blockSignals(True)
            
        if v == "text":
            self.rb_text_only.setChecked(True)
        elif v == "html_image":
            self.rb_inline_attach.setChecked(True)
        elif v == "body_pdf":
            self.rb_body_pdf.setChecked(True)
        elif v == "body_img":
            self.rb_text_inline.setChecked(True)
        elif v == "html":
            self.rb_html_only.setChecked(True)
        else:
            self.rb_html_only.setChecked(True)
            
        for rb in (self.rb_body_img, self.rb_body_pdf, self.rb_body_img_pdf,
                   self.rb_inline_attach, self.rb_inline_pdf, self.rb_text_inline,
                   self.rb_text_only, self.rb_html_only):
            rb.blockSignals(False)
            
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
        elif self.rb_inline_attach.isChecked() or self.rb_inline_pdf.isChecked():
            body_mode = "html_image"
        elif self.rb_text_inline.isChecked():
            body_mode = "body_img"
        elif self.rb_body_pdf.isChecked() or self.rb_body_img_pdf.isChecked():
            body_mode = "body_pdf"
        elif self.rb_body_img.isChecked():
            body_mode = "body_img"

        config = {
            "templates":      self._get_html_templates(),
            "subjects":       subjects,
            "sender_names":   senders,
            "campaign_tags":  self._build_campaign_tags(),
            "addresses":      addresses,
            "image_paths":    [self.img_att_list.item(i).text() for i in range(self.img_att_list.count())],
            "pdf_paths":      [self.pdf_att_list.item(i).text() for i in range(self.pdf_att_list.count())],
            "delay":          self.spn_delay.value(),
            "smtp_mode":      "auto" if self.rb_auto.isChecked() else "limit",
            "limit_per_smtp": self.spn_limit.value(),
            "auto_remove":    self.chk_auto_remove.isChecked(),
            "body_mode":      body_mode,
            "body_plain":     self.txt_body_plain.toPlainText(),
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

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{ts}] {msg}")
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.activity_logged.emit(self.task_id, msg)
            
    def _update_content_visibility(self):
        show_html = False
        show_txt = False
        show_img_att = False
        show_pdf_att = False
        
        if self.rb_body_img.isChecked():
            show_html = True
            show_img_att = True
        elif self.rb_body_pdf.isChecked():
            show_html = True
            show_pdf_att = True
        elif self.rb_body_img_pdf.isChecked():
            show_html = True
            show_img_att = True
            show_pdf_att = True
        elif self.rb_inline_attach.isChecked():
            show_html = True
            show_img_att = True
        elif self.rb_inline_pdf.isChecked():
            show_html = True
            show_pdf_att = True
        elif self.rb_text_inline.isChecked():
            show_txt = True
            show_html = True
        elif self.rb_html_only.isChecked():
            show_html = True
        elif self.rb_text_only.isChecked():
            show_txt = True
            
        self.g_html.setVisible(show_html)
        self.g_txt.setVisible(show_txt)
        self.wdg_img_att.setVisible(show_img_att)
        self.wdg_pdf_att.setVisible(show_pdf_att)
        self.g_att.setVisible(show_img_att or show_pdf_att)
