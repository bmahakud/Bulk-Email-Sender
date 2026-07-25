"""
Modern Sender Tab – fully wired to EmailSenderWorker backend.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QSpinBox, QTextEdit, QGroupBox,
                               QFormLayout, QProgressBar, QFrame, QRadioButton,
                               QButtonGroup, QCheckBox, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from backend.database import Database
from backend.email_sender import EmailSenderWorker


class SenderTab(QWidget):
    """Email Sending Control Panel"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.worker = None
        self.is_paused = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # ── Title ──────────────────────────────────────────────────────────────
        title = QLabel("Email Sending Control")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        subtitle = QLabel("Configure and control your email campaigns")
        subtitle.setStyleSheet("color: #7f8c8d; font-size:13px; margin-bottom:15px;")
        layout.addWidget(subtitle)

        # ── Settings ───────────────────────────────────────────────────────────
        cfg_grp = QGroupBox("Campaign Settings")
        cfg_grp.setStyleSheet(self.get_groupbox_style())
        cfg_lay = QFormLayout(); cfg_lay.setSpacing(15)

        # Delay
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 60); self.delay_spin.setValue(2)
        self.delay_spin.setSuffix(" seconds"); self.delay_spin.setFixedWidth(150)
        self.delay_spin.setStyleSheet(self.get_spin_style())
        cfg_lay.addRow("<b>Delay:</b>", self.delay_spin)

        # Per-SMTP mode
        mode_lay = QVBoxLayout()
        self.smtp_mode = QButtonGroup()
        self.radio_auto = QRadioButton("Auto Mode – switches on error 400/401/403")
        self.radio_auto.setChecked(True); self.smtp_mode.addButton(self.radio_auto); mode_lay.addWidget(self.radio_auto)
        self.radio_limit = QRadioButton("Limit Mode – each SMTP sends N emails then rotates")
        self.smtp_mode.addButton(self.radio_limit); mode_lay.addWidget(self.radio_limit)

        lim_row = QHBoxLayout()
        lim_row.addWidget(QLabel("   Emails per SMTP:"))
        self.smtp_limit_spin = QSpinBox()
        self.smtp_limit_spin.setRange(1, 500); self.smtp_limit_spin.setValue(5)
        self.smtp_limit_spin.setFixedWidth(100); self.smtp_limit_spin.setEnabled(False)
        self.smtp_limit_spin.setStyleSheet(self.get_spin_style())
        self.radio_limit.toggled.connect(self.smtp_limit_spin.setEnabled)
        lim_row.addWidget(self.smtp_limit_spin); lim_row.addStretch()
        mode_lay.addLayout(lim_row)
        cfg_lay.addRow("<b>Per SMTP:</b>", mode_lay)

        # Auto-remove
        self.auto_remove_check = QCheckBox("Auto-remove sent recipients from database")
        self.auto_remove_check.setChecked(True)
        cfg_lay.addRow("<b>Auto Remove:</b>", self.auto_remove_check)

        cfg_grp.setLayout(cfg_lay)
        layout.addWidget(cfg_grp)

        # ── Control buttons ────────────────────────────────────────────────────
        ctrl = QHBoxLayout(); ctrl.setSpacing(15)
        self.btn_start = QPushButton("🚀 START SENDING")
        self.btn_start.setStyleSheet(self.get_btn_style("#27ae60")); self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.start_sending); ctrl.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸️ PAUSE")
        self.btn_pause.setStyleSheet(self.get_btn_style("#f39c12")); self.btn_pause.setMinimumHeight(50)
        self.btn_pause.setEnabled(False); self.btn_pause.clicked.connect(self.pause_resume)
        ctrl.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹️ STOP")
        self.btn_stop.setStyleSheet(self.get_btn_style("#e74c3c")); self.btn_stop.setMinimumHeight(50)
        self.btn_stop.setEnabled(False); self.btn_stop.clicked.connect(self.stop_sending)
        ctrl.addWidget(self.btn_stop)
        layout.addLayout(ctrl)

        # ── Progress ───────────────────────────────────────────────────────────
        prog_grp = QGroupBox("📊 Campaign Progress")
        prog_grp.setStyleSheet(self.get_groupbox_style("#9b59b6"))
        prog_lay = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border:2px solid #bdc3c7; border-radius:5px; text-align:center;
                           height:30px; font-size:14px; font-weight:bold; }
            QProgressBar::chunk { background-color:#9b59b6; }
        """)
        self.progress_bar.setValue(0); prog_lay.addWidget(self.progress_bar)

        stat_row = QHBoxLayout()
        self.card_sent      = self._mini_card("✅ Sent",        "0",    "#27ae60")
        self.card_failed    = self._mini_card("❌ Failed",      "0",    "#e74c3c")
        self.card_remaining = self._mini_card("⏳ Remaining",   "0",    "#3498db")
        self.card_smtp      = self._mini_card("📧 Current SMTP","—",    "#9b59b6")
        for c in (self.card_sent, self.card_failed, self.card_remaining, self.card_smtp):
            stat_row.addWidget(c)
        prog_lay.addLayout(stat_row)
        prog_grp.setLayout(prog_lay)
        layout.addWidget(prog_grp)

        # ── Live log ───────────────────────────────────────────────────────────
        log_grp = QGroupBox("📋 Live Activity Log"); log_grp.setStyleSheet(self.get_groupbox_style("#34495e"))
        log_lay = QVBoxLayout()
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit { background:#2c3e50; color:#ecf0f1; border:none; border-radius:5px;
                        padding:10px; font-family:'Courier New',monospace; font-size:12px; }
        """)
        self.log_text.setMaximumHeight(220)
        self._log("System ready. Configure settings then click START SENDING.")
        log_lay.addWidget(self.log_text)
        log_grp.setLayout(log_lay)
        layout.addWidget(log_grp)

    # ── Campaign actions ───────────────────────────────────────────────────────
    def start_sending(self):
        # Pull config from templates tab and settings
        main_win = self.window()
        tpl_tab = None
        for child in main_win.findChildren(QWidget):
            if child.__class__.__name__ == 'TemplatesTab':
                tpl_tab = child
                break

        if tpl_tab is None:
            QMessageBox.warning(self, "Error", "Cannot find Templates tab."); return

        camp_data = tpl_tab.get_campaign_data()

        if not camp_data.get('subjects'):
            QMessageBox.warning(self, "Missing Data", "Add at least one subject line in the Templates tab."); return

        client_id = self.db.get_setting('client_id', '')

        config = {
            'delay':          self.delay_spin.value(),
            'mode':           'limit' if self.radio_limit.isChecked() else 'auto',
            'limit_per_smtp': self.smtp_limit_spin.value(),
            'auto_remove':    self.auto_remove_check.isChecked(),
            'client_id':      client_id,
            **camp_data,
        }

        self.worker = EmailSenderWorker(config, self.db)
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.log_message.connect(self._log)
        self.worker.finished.connect(self.on_finished)

        # Update totals
        total = len(self.db.get_recipients(status='pending'))
        self._update_card(self.card_remaining, str(total))
        self.progress_bar.setMaximum(max(total, 1))

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.worker.start()

    def pause_resume(self):
        if not self.worker: return
        if not self.is_paused:
            self.worker.pause()
            self.btn_pause.setText("▶️ RESUME")
            self.is_paused = True
        else:
            self.worker.resume()
            self.btn_pause.setText("⏸️ PAUSE")
            self.is_paused = False

    def stop_sending(self):
        if self.worker:
            self.worker.stop()
        self._reset_controls()

    def on_finished(self):
        self._reset_controls()
        self._log("✅ Campaign finished.")

    def _reset_controls(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False); self.btn_pause.setText("⏸️ PAUSE")
        self.btn_stop.setEnabled(False)
        self.is_paused = False

    # ── Signal callbacks ───────────────────────────────────────────────────────
    def on_progress(self, data: dict):
        sent      = data.get('sent', 0)
        failed    = data.get('failed', 0)
        remaining = data.get('remaining', 0)
        smtp      = data.get('current_smtp', '—')
        total     = sent + failed + remaining
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(sent + failed)
        self._update_card(self.card_sent,      str(sent))
        self._update_card(self.card_failed,    str(failed))
        self._update_card(self.card_remaining, str(remaining))
        self._update_card(self.card_smtp,      smtp)

    # ── UI helpers ─────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")

    def _mini_card(self, title, value, color):
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background:{color};border-radius:8px;padding:12px;}}")
        lay = QVBoxLayout(f); lay.setSpacing(4)
        tl = QLabel(title); tl.setStyleSheet("color:white;font-size:11px;font-weight:bold;")
        tl.setAlignment(Qt.AlignCenter)
        vl = QLabel(value); vl.setFont(QFont("Arial", 18, QFont.Bold))
        vl.setStyleSheet("color:white;"); vl.setAlignment(Qt.AlignCenter)
        vl.setObjectName(f"val_{title.replace(' ','_').lower()}")
        lay.addWidget(tl); lay.addWidget(vl)
        return f

    def _update_card(self, frame, value):
        vl = frame.findChild(QLabel)
        # Second child is value label
        children = [c for c in frame.children() if isinstance(c, QLabel)]
        if len(children) >= 2:
            children[1].setText(value)

    def get_groupbox_style(self, border="#9b59b6"):
        return f"""
            QGroupBox {{ font-size:14px; font-weight:bold; border:2px solid {border};
                         border-radius:8px; margin-top:10px; padding-top:15px; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:15px; padding:0 8px; }}
        """

    def get_btn_style(self, color):
        darken = {"#27ae60":"#229954","#f39c12":"#d68910","#e74c3c":"#c0392b"}
        h = darken.get(color, color)
        return f"""
            QPushButton {{ background:{color}; color:white; border:none;
                           padding:15px 30px; font-size:16px; font-weight:bold; border-radius:8px; }}
            QPushButton:hover {{ background:{h}; }}
            QPushButton:disabled {{ background:#bdc3c7; color:#7f8c8d; }}
        """

    def get_spin_style(self):
        return """
            QSpinBox { padding:8px; border:1px solid #d0d0d0; border-radius:4px;
                       font-size:14px; background:white; color:#2c3e50; }
            QSpinBox:focus { border:2px solid #5dade2; }
        """
