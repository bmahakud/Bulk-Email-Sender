"""
Modern Templates Tab – HTML, Attachments, Subject Lines, Sender Names (DB-integrated)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QGroupBox,
                               QListWidget, QScrollArea, QFrame, QCheckBox,
                               QLineEdit, QTabWidget, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from backend.database import Database


class TemplatesTab(QWidget):
    """Template Management"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.init_ui()
        self.load_from_db()

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f5f6fa; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 50)

        title = QLabel("Email Templates & Content")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        subtitle = QLabel("Configure body, attachments, subject lines, sender names, and custom tags")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border:1px solid #e0e0e0; border-radius:5px; background:white; }
            QTabBar::tab { padding:12px 24px; font-size:12px; font-weight:600;
                           background:#f5f6fa; color:#5a6c7d; border:none; margin-right:2px; }
            QTabBar::tab:selected { background:white; color:#2c3e50; border-bottom:3px solid #5dade2; }
            QTabBar::tab:hover { background:#e8e8e8; color:#2c3e50; }
        """)

        tabs.addTab(self.create_body_tab(),        "📝 Body Content")
        tabs.addTab(self.create_attachments_tab(), "📎 Attachments")
        tabs.addTab(self.create_subject_tab(),     "✉️ Subject Lines")
        tabs.addTab(self.create_sender_tab(),      "👤 Sender Names")
        tabs.addTab(self.create_custom_tags_tab(), "🏷️ Custom Tags")

        layout.addWidget(tabs)

        # Action buttons
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(12)
        btn_save  = QPushButton("💾 Save All")
        btn_save.setStyleSheet(self.get_button_style("#5dade2"))
        btn_save.clicked.connect(self.save_to_db)
        btn_clear = QPushButton("🧹 Clear All")
        btn_clear.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_clear.clicked.connect(self.clear_all)
        btn_layout.addWidget(btn_save); btn_layout.addWidget(btn_clear); btn_layout.addStretch()
        layout.addLayout(btn_layout)

        scroll.setWidget(content)
        main = QVBoxLayout(self); main.setContentsMargins(0,0,0,0); main.addWidget(scroll)

    # ── Sub-tabs ───────────────────────────────────────────────────────────────
    def create_body_tab(self):
        w = QWidget(); w.setStyleSheet("background-color:white;")
        lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)

        g = QGroupBox("Plain Text Body"); g.setStyleSheet(self.get_groupbox_style())
        gl = QVBoxLayout()
        self.body_text_edit = QTextEdit()
        self.body_text_edit.setPlaceholderText("Plain text email body…")
        self.body_text_edit.setMaximumHeight(120)
        self.body_text_edit.setStyleSheet(self.get_input_style())
        gl.addWidget(self.body_text_edit); g.setLayout(gl); lay.addWidget(g)

        h = QGroupBox("HTML Body (with Inline Images)"); h.setStyleSheet(self.get_groupbox_style())
        hl = QVBoxLayout()
        info = QLabel("💡 Upload HTML files. Local images auto-converted to base64 inline.")
        info.setStyleSheet("color:#7f8c8d; font-size:11px;"); hl.addWidget(info)

        brow = QHBoxLayout()
        ba = QPushButton("+ Add HTML File"); ba.setStyleSheet(self.get_button_style("#a29bfe"))
        ba.clicked.connect(self.add_html_file)
        bc = QPushButton("Clear HTML"); bc.setStyleSheet(self.get_button_style("#95a5a6"))
        bc.clicked.connect(lambda: self.html_list.clear())
        brow.addWidget(ba); brow.addWidget(bc); brow.addStretch(); hl.addLayout(brow)

        self.html_list = QListWidget(); self.html_list.setMaximumHeight(100)
        self.html_list.setStyleSheet(self.get_list_style()); hl.addWidget(self.html_list)
        self.inline_images_check = QCheckBox("Convert images to base64 inline images (recommended)")
        self.inline_images_check.setChecked(True); hl.addWidget(self.inline_images_check)
        h.setLayout(hl); lay.addWidget(h); lay.addStretch()
        return w

    def create_attachments_tab(self):
        w = QWidget(); w.setStyleSheet("background-color:white;")
        lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)

        ig = QGroupBox("Image Attachments (GIF / PNG / JPEG / WEBP)")
        ig.setStyleSheet(self.get_groupbox_style())
        il = QVBoxLayout()
        info_i = QLabel("💡 Images converted to base64 with personalised names.")
        info_i.setStyleSheet("color:#7f8c8d; font-size:11px;"); il.addWidget(info_i)
        ibr = QHBoxLayout()
        ai = QPushButton("+ Add Images"); ai.setStyleSheet(self.get_button_style("#55efc4"))
        ai.clicked.connect(self.add_image_attachments)
        ci = QPushButton("Clear"); ci.setStyleSheet(self.get_button_style("#95a5a6"))
        ci.clicked.connect(lambda: self.image_list.clear())
        ibr.addWidget(ai); ibr.addWidget(ci); ibr.addStretch(); il.addLayout(ibr)
        self.image_list = QListWidget(); self.image_list.setMaximumHeight(90)
        self.image_list.setStyleSheet(self.get_list_style()); il.addWidget(self.image_list)
        ig.setLayout(il); lay.addWidget(ig)

        pg = QGroupBox("PDF Attachments"); pg.setStyleSheet(self.get_groupbox_style())
        pl = QVBoxLayout()
        info_p = QLabel("💡 PDFs converted to base64 with personalised names.")
        info_p.setStyleSheet("color:#7f8c8d; font-size:11px;"); pl.addWidget(info_p)
        pbr = QHBoxLayout()
        ap = QPushButton("+ Add PDFs"); ap.setStyleSheet(self.get_button_style("#fdcb6e"))
        ap.clicked.connect(self.add_pdf_attachments)
        cp = QPushButton("Clear"); cp.setStyleSheet(self.get_button_style("#95a5a6"))
        cp.clicked.connect(lambda: self.pdf_list.clear())
        pbr.addWidget(ap); pbr.addWidget(cp); pbr.addStretch(); pl.addLayout(pbr)
        self.pdf_list = QListWidget(); self.pdf_list.setMaximumHeight(90)
        self.pdf_list.setStyleSheet(self.get_list_style()); pl.addWidget(self.pdf_list)
        pg.setLayout(pl); lay.addWidget(pg); lay.addStretch()
        return w

    def create_subject_tab(self):
        w = QWidget(); w.setStyleSheet("background-color:white;")
        lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)
        sg = QGroupBox("Subject Lines (Rotation)"); sg.setStyleSheet(self.get_groupbox_style())
        sl = QVBoxLayout()
        info = QLabel("💡 Multiple subjects rotate per email (saved across sessions).")
        info.setStyleSheet("color:#7f8c8d; font-size:11px; margin-bottom:10px;"); sl.addWidget(info)

        row = QHBoxLayout()
        self.single_subject_input = QLineEdit()
        self.single_subject_input.setPlaceholderText("Enter a subject line")
        self.single_subject_input.setStyleSheet(self.get_input_style())
        btn_add = QPushButton("Add"); btn_add.setStyleSheet(self.get_button_style("#5dade2"))
        btn_add.setMaximumWidth(80); btn_add.clicked.connect(self.add_single_subject)
        row.addWidget(self.single_subject_input); row.addWidget(btn_add); sl.addLayout(row)

        sl.addWidget(self._bold_label("Bulk paste (one per line):"))
        self.subject_bulk_text = QTextEdit()
        self.subject_bulk_text.setPlaceholderText("Line 1 subject\nLine 2 subject…")
        self.subject_bulk_text.setMaximumHeight(100)
        self.subject_bulk_text.setStyleSheet(self.get_input_style()); sl.addWidget(self.subject_bulk_text)
        btn_bulk = QPushButton("Add All"); btn_bulk.setStyleSheet(self.get_button_style("#a29bfe"))
        btn_bulk.clicked.connect(self.add_bulk_subjects); sl.addWidget(btn_bulk)

        sl.addWidget(self._bold_label("Current Subject Lines:"))
        self.subject_list = QListWidget(); self.subject_list.setMaximumHeight(150)
        self.subject_list.setStyleSheet(self.get_list_style()); sl.addWidget(self.subject_list)
        btn_clr = QPushButton("Clear All Subjects"); btn_clr.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_clr.clicked.connect(self._clear_subjects); sl.addWidget(btn_clr)

        sg.setLayout(sl); lay.addWidget(sg); lay.addStretch()
        return w

    def create_sender_tab(self):
        w = QWidget(); w.setStyleSheet("background-color:white;")
        lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)
        grp = QGroupBox("Sender Names (Rotation)"); grp.setStyleSheet(self.get_groupbox_style())
        gl = QVBoxLayout()
        gl.addWidget(self._info("💡 Custom sender names rotate per email (saved across sessions)."))
        self.use_default_sender = QCheckBox("Use Default SMTP address as sender name")
        self.use_default_sender.setChecked(True); gl.addWidget(self.use_default_sender)
        gl.addWidget(self._bold_label("Custom Sender Names (one per line):"))
        self.sender_bulk_text = QTextEdit()
        self.sender_bulk_text.setPlaceholderText("Ava Harris\nSophia Adams\n…")
        self.sender_bulk_text.setMaximumHeight(100)
        self.sender_bulk_text.setStyleSheet(self.get_input_style()); gl.addWidget(self.sender_bulk_text)
        btn_add = QPushButton("Add Names"); btn_add.setStyleSheet(self.get_button_style("#a29bfe"))
        btn_add.clicked.connect(self.add_bulk_senders); gl.addWidget(btn_add)
        gl.addWidget(self._bold_label("Current Sender Names:"))
        self.sender_list = QListWidget(); self.sender_list.setMaximumHeight(150)
        self.sender_list.setStyleSheet(self.get_list_style()); gl.addWidget(self.sender_list)
        btn_clr = QPushButton("Clear All Sender Names"); btn_clr.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_clr.clicked.connect(self._clear_senders); gl.addWidget(btn_clr)
        grp.setLayout(gl); lay.addWidget(grp); lay.addStretch()
        return w

    def create_custom_tags_tab(self):
        w = QWidget(); w.setStyleSheet("background-color:white;")
        lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)
        grp = QGroupBox("Custom Tags"); grp.setStyleSheet(self.get_groupbox_style())
        gl = QVBoxLayout()
        gl.addWidget(self._info("💡 Use {{tagname}} in HTML / subjects. Values are persisted."))

        from PySide6.QtWidgets import QFormLayout
        form = QFormLayout(); form.setSpacing(12)
        self.tag_tfn     = self._inp("TFN value");     form.addRow("TFN:", self.tag_tfn)
        self.tag_date    = self._inp("2024-01-15");    form.addRow("Date:", self.tag_date)
        self.tag_time    = self._inp("10:30 AM");      form.addRow("Time:", self.tag_time)
        self.tag_order   = self._inp("#ORDER#");       form.addRow("Order:", self.tag_order)
        self.tag_custom1 = self._inp("Custom value 1"); form.addRow("Custom 1:", self.tag_custom1)
        self.tag_custom2 = self._inp("Custom value 2"); form.addRow("Custom 2:", self.tag_custom2)
        gl.addLayout(form)

        ex = QFrame(); ex.setStyleSheet("QFrame{background:#f8f9fa;border-radius:6px;padding:12px;margin-top:15px;}")
        el = QVBoxLayout(ex)
        el.addWidget(self._bold_label("Usage example:"))
        eg = QLabel("Hello {{name}}, your TFN is {{tfn}}<br>Date: {{date}} · Order: {{order}}")
        eg.setStyleSheet("color:#5a6c7d; font-size:11px;"); eg.setWordWrap(True); el.addWidget(eg)
        gl.addWidget(ex); grp.setLayout(gl); lay.addWidget(grp); lay.addStretch()
        return w

    # ── Small helpers ──────────────────────────────────────────────────────────
    def _bold_label(self, text):
        l = QLabel(text); l.setStyleSheet("font-weight:600; margin-top:10px;"); return l
    def _info(self, text):
        l = QLabel(text); l.setStyleSheet("color:#7f8c8d; font-size:11px; margin-bottom:10px;"); return l
    def _inp(self, placeholder):
        w = QLineEdit(); w.setPlaceholderText(placeholder); w.setStyleSheet(self.get_input_style()); return w

    # ── File helpers ───────────────────────────────────────────────────────────
    def add_html_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select HTML Files", "", "HTML Files (*.html *.htm)")
        for f in files:
            self.html_list.addItem(f)

    def add_image_attachments(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "",
                                                "Images (*.gif *.png *.jpg *.jpeg *.webp)")
        for f in files:
            self.image_list.addItem(f)

    def add_pdf_attachments(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
        for f in files:
            self.pdf_list.addItem(f)

    def add_single_subject(self):
        subj = self.single_subject_input.text().strip()
        if subj:
            self.subject_list.addItem(subj)
            self.db.add_subject(subj)
            self.single_subject_input.clear()

    def add_bulk_subjects(self):
        text = self.subject_bulk_text.toPlainText().strip()
        for ln in text.split('\n'):
            ln = ln.strip()
            if ln:
                self.subject_list.addItem(ln)
                self.db.add_subject(ln)
        self.subject_bulk_text.clear()

    def add_bulk_senders(self):
        text = self.sender_bulk_text.toPlainText().strip()
        for ln in text.split('\n'):
            ln = ln.strip()
            if ln:
                self.sender_list.addItem(ln)
                self.db.add_sender_name(ln)
        self.sender_bulk_text.clear()
        self.use_default_sender.setChecked(False)

    def _clear_subjects(self):
        self.subject_list.clear()
        self.db.clear_subjects()

    def _clear_senders(self):
        self.sender_list.clear()
        self.db.clear_sender_names()

    # ── Persist / load ─────────────────────────────────────────────────────────
    def save_to_db(self):
        """Persist all custom tags and HTML templates to DB."""
        self.db.set_setting('tag_tfn',     self.tag_tfn.text())
        self.db.set_setting('tag_date',    self.tag_date.text())
        self.db.set_setting('tag_time',    self.tag_time.text())
        self.db.set_setting('tag_order',   self.tag_order.text())
        self.db.set_setting('tag_custom1', self.tag_custom1.text())
        self.db.set_setting('tag_custom2', self.tag_custom2.text())

        # Save HTML templates
        self.db.clear_templates()
        for i in range(self.html_list.count()):
            fpath = self.html_list.item(i).text()
            try:
                content = Path(fpath).read_text(encoding='utf-8')
                self.db.add_template(fpath, content)
            except Exception:
                pass

        QMessageBox.information(self, "Saved", "Templates and settings saved successfully!")

    def load_from_db(self):
        """Restore from DB on startup."""
        self.tag_tfn.setText(self.db.get_setting('tag_tfn'))
        self.tag_date.setText(self.db.get_setting('tag_date'))
        self.tag_time.setText(self.db.get_setting('tag_time'))
        self.tag_order.setText(self.db.get_setting('tag_order'))
        self.tag_custom1.setText(self.db.get_setting('tag_custom1'))
        self.tag_custom2.setText(self.db.get_setting('tag_custom2'))

        # Templates
        for tpl in self.db.get_templates():
            self.html_list.addItem(tpl['filename'])

        # Subjects
        for subj in self.db.get_subjects():
            self.subject_list.addItem(subj)

        # Sender names
        for name in self.db.get_sender_names():
            self.sender_list.addItem(name)

    def clear_all(self):
        if QMessageBox.question(self, "Confirm", "Clear all template content from DB?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.body_text_edit.clear(); self.html_list.clear()
            self.image_list.clear(); self.pdf_list.clear()
            self._clear_subjects(); self._clear_senders()
            self.tag_tfn.clear(); self.tag_date.clear(); self.tag_time.clear()
            self.tag_order.clear(); self.tag_custom1.clear(); self.tag_custom2.clear()
            self.db.clear_templates()
            for key in ('tag_tfn','tag_date','tag_time','tag_order','tag_custom1','tag_custom2'):
                self.db.set_setting(key, '')

    # ── Data extraction for sender ─────────────────────────────────────────────
    def get_campaign_data(self) -> dict:
        """Return all template/config data for EmailSenderWorker."""
        # Build HTML template list (inline-convert images)
        templates = []
        for i in range(self.html_list.count()):
            fpath = self.html_list.item(i).text()
            try:
                html = Path(fpath).read_text(encoding='utf-8')
                if self.inline_images_check.isChecked():
                    from backend.template_manager import TemplateManager
                    tm = TemplateManager()
                    html = tm.process_html_inline_images(html, fpath)
                templates.append(html)
            except Exception:
                pass
        # Fall back to plain text
        plain = self.body_text_edit.toPlainText().strip()
        if not templates and plain:
            templates = [f"<p>{plain}</p>"]

        subjects = [self.subject_list.item(i).text() for i in range(self.subject_list.count())]
        sender_names = [self.sender_list.item(i).text() for i in range(self.sender_list.count())]

        custom_tags = {
            'tfn':     self.tag_tfn.text(),
            'date':    self.tag_date.text(),
            'time':    self.tag_time.text(),
            'order':   self.tag_order.text(),
            'custom1': self.tag_custom1.text(),
            'custom2': self.tag_custom2.text(),
        }

        image_paths = [self.image_list.item(i).text() for i in range(self.image_list.count())]
        pdf_paths   = [self.pdf_list.item(i).text()   for i in range(self.pdf_list.count())]

        return {
            'templates':    templates,
            'subjects':     subjects,
            'sender_names': sender_names,
            'custom_tags':  custom_tags,
            'image_paths':  image_paths,
            'pdf_paths':    pdf_paths,
        }

    # ── Styles ─────────────────────────────────────────────────────────────────
    def get_button_style(self, color):
        return f"""
            QPushButton {{ background-color:{color}; color:white; border:none;
                           padding:10px 20px; font-size:13px; font-weight:500; border-radius:5px; }}
            QPushButton:hover {{ opacity:0.85; }}
        """
    def get_groupbox_style(self):
        return """
            QGroupBox { font-size:13px; font-weight:600; border:1px solid #e0e0e0;
                        border-radius:6px; margin-top:15px; padding-top:20px; background:white; }
            QGroupBox::title { subcontrol-origin:margin; left:15px; padding:0 8px; color:#2c3e50; }
        """
    def get_input_style(self):
        return """
            QTextEdit, QLineEdit { border:1px solid #d0d0d0; border-radius:5px;
                                   padding:8px; background:white; font-size:12px; }
            QTextEdit:focus, QLineEdit:focus { border:1px solid #5dade2; }
        """
    def get_list_style(self):
        return """
            QListWidget { border:1px solid #e0e0e0; border-radius:5px; background:white; padding:5px; }
            QListWidget::item { padding:5px; border-bottom:1px solid #f0f0f0; }
        """
